"""Generic wiring between arbitrary game-state features and arbitrary
connectome neuron populations, in both directions.

flappy/play.py hardcodes one path: y_velocity -> haltere_current_for_velocity
-> haltere afferents in, DLM spikes out. That path is real and measured (see
flappy/circuit.py) but it is one point in a much larger space -- any scalar
the game exposes could drive any current-injectable population, any
population could be read as the flap signal, and some populations (a looming
VPN, an always-on bias) don't need to depend on game state to be worth
driving at all. This module is that space, factored out so a new wiring is a
few lines of configuration instead of a new script that reimplements
neuron-selection, current-injection and spike-decoding from scratch.

Nothing here is more biological than flappy/circuit.py's own haltere current:
every Wiring is host-side current injected before the connectome kernel runs,
same "engineered joystick, not a measured reflex" honesty stance as the rest
of this project. Wiring y_velocity into an antennal (JO) afferent instead of
a haltere afferent does not make it a model of antennal mechanosensation --
it changes which real synaptic pathway the artificial current rides in on,
which is exactly the kind of comparison this module exists to make cheap.

Neuron populations are always resolved live from the graph's own annotations
(see resolve_neurons below), never a hardcoded body-ID list, matching
flappy/circuit.py and flappy/dlm_pair_sweep.py's convention -- a different
`--dataset` or a re-run reconstruction changes which cells match, not the
code.
"""
import numpy as np
from connectome_sim.physiology.common import annotations
from connectome_sim.vision.retina import BilinearLuminance
from flappy.circuit import DLM_TYPES, haltere_current_for_velocity
from flappy.inverse_data import reset as reset_brain

NEURON_PRESETS = {
    'haltere': lambda a: (a.subclass == 'haltere').to_numpy(),
    'antenna': lambda a: a.type.astype(str).str.startswith('JO-').to_numpy(),
    'dlm': lambda a: a.type.isin(DLM_TYPES).to_numpy(),
}


def resolve_neurons(brain, spec):
    """Resolve a neuron-population spec against this brain's own graph.

    `spec` is one of:
      - a preset name in NEURON_PRESETS ('haltere', 'antenna', 'dlm')
      - a single connectome `type` string, matched exactly
        (e.g. 'LoVP92', 'DNg13' -- any type the reconstruction names)
      - a list/tuple/set of type strings, matched as a set (like DLM_TYPES)
      - {'type_prefix': 'JO-'} / {'subclass': 'wm'} / {'superclass': 'cb_intrinsic'}
      - a ready-made np.ndarray of indices, passed through unchanged

    Raises rather than returning an empty population -- a typo'd type name
    silently resolving to "inject into nothing" is a worse failure than a
    crash, same stance as circuit.py's wing_motor_readouts/haltere_afferents.
    """
    if isinstance(spec, np.ndarray):
        return spec.astype(np.int32)
    a = annotations(brain.ids)
    if isinstance(spec, str) and spec in NEURON_PRESETS:
        mask = NEURON_PRESETS[spec](a)
    elif isinstance(spec, str):
        mask = (a.type.astype(str) == spec).to_numpy()
    elif isinstance(spec, dict):
        if 'type_prefix' in spec:
            mask = a.type.astype(str).str.startswith(spec['type_prefix']).to_numpy()
        elif 'type' in spec:
            types = spec['type'] if isinstance(spec['type'], (list, tuple, set)) else [spec['type']]
            mask = a.type.isin(list(types)).to_numpy()
        elif 'subclass' in spec:
            mask = (a.subclass == spec['subclass']).to_numpy()
        elif 'superclass' in spec:
            mask = (a.superclass == spec['superclass']).to_numpy()
        else:
            raise ValueError(f"Unrecognised neuron spec {spec!r}; expected one of "
                              f"'type_prefix'/'type'/'subclass'/'superclass'")
    elif isinstance(spec, (list, tuple, set)):
        mask = a.type.isin(list(spec)).to_numpy()
    else:
        raise ValueError(f'Unrecognised neuron spec {spec!r}')
    idx = np.flatnonzero(mask).astype(np.int32)
    if not len(idx):
        raise ValueError(f'No neurons matched spec {spec!r} in this graph')
    return idx


def game_state(game, obs):
    """Every literal number this tick's game state can be reduced to -- no
    filtering, no biological framing, available as a dict so any of it can
    be wired straight into a current via Wiring(feature=<key>). Distances
    and angles are `float('inf')`/`0.` when nothing is in view (no_pipes
    mode, or nothing within MIN_DEPTH) -- a Wiring's mapping function is
    responsible for handling that, the same way haltere_current_for_velocity
    is responsible for rectifying a negative y_velocity."""
    obstacles = game.obstacles()
    lower = obstacles['lower'] or {'distance': float('inf'), 'angle': 0.}
    upper = obstacles['upper'] or {'distance': float('inf'), 'angle': 0.}
    return {
        'y_velocity': obs['y_velocity'], 'y': obs['y'], 'rotation': obs['rotation'],
        'score': float(obs['score']), 'tick': float(obs['tick']),
        'lower_pipe_distance': lower['distance'], 'lower_pipe_angle': lower['angle'],
        'upper_pipe_distance': upper['distance'], 'upper_pipe_angle': upper['angle'],
        'frame_luminance': _frame_luminance_mean(game),
    }


def _frame_luminance_mean(game):
    """Mean grayscale brightness of the rendered 3D-projected frame -- a
    derived SUMMARY of the same pixels the retina samples for real vision,
    not photoreceptor transduction. Wiring this into a non-visual population
    is an engineered "something is close" proxy, not a model of any visual
    pathway; real vision (see ConnectomeAgent.use_vision) always drives the
    retina directly from the same frame regardless of whether this is used."""
    return float(game.pixels().mean() / 255.)


class Wiring:
    """One game-state feature driving one neuron population's injected
    current, every tick.

    `feature` is a key into game_state()'s dict (a string), or a
    callable(game, obs, state) -> float for anything not already in there
    (state is that tick's game_state() dict, handed in so a custom feature
    can reuse it instead of recomputing). `mapping` turns that raw value
    into an mV-equivalent current; the default passes it through unchanged
    -- callers should normally supply one, the way
    flappy.circuit.haltere_current_for_velocity does for y_velocity->haltere.
    """
    def __init__(self, target, feature, mapping=lambda v: v, label=None):
        self.target = target
        self.feature = feature
        self.mapping = mapping
        self.label = label or (feature if isinstance(feature, str) else str(target))

    def _resolve(self, brain):
        return _ResolvedWiring(resolve_neurons(brain, self.target), self.feature,
                                self.mapping, self.label)


class AlwaysOn:
    """A neuron population held at a fixed current every tick, independent
    of game state -- e.g. a tonic bias onto a named VPN type like LoVP92.
    Mechanically a Wiring whose feature ignores game state; kept as its own
    class because "always on" is a different intent from "driven by this
    feature" and should read that way at the call site, not be inferred from
    a `lambda *_: constant` buried in a Wiring."""
    def __init__(self, target, current, label=None):
        self.target = target
        self.current = float(current)
        self.label = label or f'{target}=const({current})'

    def _resolve(self, brain):
        return _ResolvedWiring(resolve_neurons(brain, self.target),
                                lambda game, obs, state: self.current,
                                lambda v: v, self.label)


class _ResolvedWiring:
    def __init__(self, indices, feature, mapping, label):
        self.indices = indices
        self.feature = feature
        self.mapping = mapping
        self.label = label

    def current(self, game, obs, state):
        if isinstance(self.feature, str):
            if self.feature not in state:
                raise ValueError(f'Unknown feature {self.feature!r}; game_state() has {sorted(state)}')
            value = state[self.feature]
        else:
            value = self.feature(game, obs, state)
        return float(self.mapping(value))


class OutputChannel:
    """One neuron population read out toward the flap decision, generalising
    flappy/circuit.py's wing_motor_readouts (DLM only) to any preset or
    named type -- e.g. OutputChannel('dlm') or OutputChannel('DNg13').

    Same two decoders flappy/controls.py's FlapControls already offers,
    generalised past its hardcoded 'DLMn' readout-type filter: `threshold=
    None` fires whenever the population spikes at all this tick; a numeric
    threshold integrates spikes and carries the remainder across ticks."""
    def __init__(self, target, threshold=None, label=None):
        self.target = target
        self.threshold = threshold
        self.label = label or str(target)

    def _resolve(self, brain):
        return _ResolvedOutput(resolve_neurons(brain, self.target), self.threshold, self.label)


class _ResolvedOutput:
    def __init__(self, indices, threshold, label):
        self.indices = indices
        self.threshold = threshold
        self.label = label
        self.accumulator = 0.

    def decode(self, counts, seconds):
        spikes = int(counts[self.indices].sum())
        rate_hz = spikes / seconds if seconds > 0 else 0.
        if self.threshold is None:
            fire = spikes > 0
        else:
            self.accumulator += spikes
            fire = self.accumulator >= self.threshold
            if fire: self.accumulator -= self.threshold
        return {'label': self.label, 'spikes': spikes, 'rate_hz': round(rate_hz, 3),
                'fire': bool(fire), 'accumulator': round(self.accumulator, 3)}


class ConnectomeAgent:
    """Wires an arbitrary set of game-state features into an arbitrary set
    of connectome neuron populations (`wirings`: Wiring / AlwaysOn) and reads
    an arbitrary set of populations back out toward the game's one action
    (`outputs`: OutputChannel), replacing flappy/play.py's hardcoded
    y_velocity->haltere->DLM path with a configurable one. See
    `default_agent()` below for that original path re-expressed here, kept
    for regression parity, not because it is privileged over any other
    wiring.

    Every tick, real photoreceptor vision runs first -- game.pixels() ->
    retina.sample() -> the brain's own luminance channel -- unless
    `use_vision=False`. This is the actual visual pathway and is never
    bypassed or replaced by a Wiring; a Wiring only ever adds artificial
    CURRENT alongside it, into whatever population it targets (visual or
    not). If two wirings target overlapping neurons, their currents are
    summed onto the shared indices for that tick rather than one silently
    overwriting the other.
    """
    def __init__(self, brain, wirings=(), outputs=(), use_vision=True, retina=None,
                 combine='any'):
        if combine not in ('any', 'all'):
            raise ValueError("combine must be 'any' or 'all'")
        self.brain = brain
        self.wirings = [w._resolve(brain) for w in wirings]
        self.outputs = [o._resolve(brain) for o in outputs] or [OutputChannel('dlm')._resolve(brain)]
        self.use_vision = use_vision
        self.retina = retina or BilinearLuminance()
        self.combine = combine

    def reset(self):
        """Return the brain to its just-loaded cold-start state -- required
        between independent episodes/trials, see flappy/inverse_data.py's
        `reset` and connectome-lab/REPRODUCIBILITY.md: brain and physics
        state carry across calls, a stale brain is not a fresh condition."""
        reset_brain(self.brain)

    def stimulation(self, game, obs, state):
        """Merge every wiring's current tick's current into one (indices,
        currents) pair for brain.step's `stimulation` argument -- that
        argument accepts exactly one such pair, so overlapping targets are
        summed here rather than left to silently clobber each other."""
        if not self.wirings:
            return None
        by_index = {}
        for w in self.wirings:
            current = w.current(game, obs, state)
            if current == 0.:
                continue
            for i in w.indices:
                by_index[int(i)] = by_index.get(int(i), 0.) + current
        if not by_index:
            return None
        idx = np.asarray(list(by_index.keys()), dtype=np.int32)
        cur = np.asarray(list(by_index.values()), dtype=np.float32)
        return (idx, cur)

    def step(self, game, duration_ms):
        obs = game.observation()
        state = game_state(game, obs)
        frame = game.pixels()
        light = (self.retina.sample(frame, self.brain.uv) if self.use_vision
                 else np.zeros(len(self.brain.retina), dtype=np.float32))
        stim = self.stimulation(game, obs, state)
        counts, _ = self.brain.step(light, duration_ms, stimulation=stim)
        channels = [o.decode(counts, duration_ms / 1000.) for o in self.outputs]
        flap = any(c['fire'] for c in channels) if self.combine == 'any' else all(c['fire'] for c in channels)
        return {'flap': bool(flap), 'total_spikes': int(counts.sum()),
                'game_state': state, 'channels': channels}


def default_agent(brain, haltere_gain=1.):
    """flappy/play.py's known-working y_velocity->haltere->DLM wiring,
    expressed in this framework -- same population, same mapping, same
    output type, kept for regression parity against play.py's own numbers."""
    return ConnectomeAgent(
        brain,
        wirings=[Wiring('haltere', 'y_velocity',
                         lambda v: haltere_current_for_velocity(v, m=haltere_gain) if haltere_gain else 0.,
                         label='haltere<-y_velocity')],
        outputs=[OutputChannel('dlm', label='DLM')])
