"""Live two-valence reinforcement adapter for Flappy Bird, extending
doom/training.py's DamageTraining pattern with an appetitive channel.

Two discrete game events, two host-side current pulses. No value function,
no eligibility over game variables, no learned reward predictor -- the only
learning is the existing dopamine-gated KC->MBON11 rule in
connectome_sim/physiology, which this module does not touch:

  crash (ground or pipe)  -> PPL101 aversive current, +4 mV-equivalent
  pipe cleared (score++)  -> sugar-cell appetitive current, +30

The aversive value and its 200 ms window are the sensitivity-test numbers
doom_learning_v4 introduced and doom/training.py already uses; not
re-derived here, not measured. The appetitive current reuses the 30 that
connectome_sim's native.py and gpu.py already drive `sugar` with for their
own `sugar=True` flag, and is held for the same 200 ms as the aversive
pulse so the two channels are symmetric in time. That symmetry is a
declared modeling choice, not a measured property of either pathway.

MemoryBrain.step() deliberately drops NativeBrain's `sugar=` kwarg, so the
appetitive channel is delivered as an ordinary `stimulation` pulse over
`brain.sugar` (23 gustatory cells in MaleCNS v1.0). That is host-side drive
injection before the kernel runs -- the same engineered-joystick mechanism
as the haltere and PPL101 channels, not a claim that clearing a pipe tastes
like sugar to a fly.

Deliberate divergences from doom/training.py:
- Doom distinguishes non-fatal damage (schedules a pulse) from terminal
  damage (does not). Flappy Bird has no non-fatal failure -- every crash
  ends the episode -- so the crash itself has to be the trigger.
- new_round() does *not* cancel a pulse in progress: it is allowed to
  continue into the next episode's early ticks, consistent with this repo's
  "neural/weight state persists across game resets" convention. Resetting
  the game does not reset the brain.
- The two windows run independently and may overlap (a crash immediately
  after clearing a pipe), in which case both currents are present in the
  same segment. Neither cancels the other.

Only images, the crash signal and the score enter the learning rule. Flap
decoding reads DLM (flappy.circuit.wing_motor_readouts); KC->MBON11
plasticity has no engineered path to those cells (checked directly: DLM's
strongest direct presynaptic partners are unnamed VNC interneurons and a
couple of descending neurons, none of them MBON-related). Weights genuinely
change here -- see telemetry()'s memory() report -- but there is no basis to
claim flap timing or survival improves as a result, and adding an appetitive
channel does not create such a basis. Same "mechanism enabled, not
validated" stance as doom/training.py and the v6 README.
"""
import math
import numpy as np

# Both declared choices; see module docstring for provenance.
AVERSIVE_CURRENT = 4.
APPETITIVE_CURRENT = 30.
PULSE_STEPS = 2000  # 200 ms at the 0.1 ms neural dt


class FlapTraining:
    def __init__(self, brain, enabled=True, reward=True):
        self.brain = brain
        self.enabled = bool(enabled)
        self.reward = bool(reward)
        self.brain.weights_frozen = not self.enabled
        # Separate windows: `until` stays the aversive one, keeping the name
        # doom/training.py and this repo's tests already use.
        self.until = 0
        self.sugar_until = 0
        self.events = 0
        self.rewards = 0
        self.delivered_steps = 0
        self.reward_steps = 0
        self.last_steps = 0

    def new_round(self):
        # Unlike doom/training.py's DamageTraining.new_round(), this cancels
        # nothing -- see module docstring. The game resets; the brain does not.
        self.last_steps = 0

    def _sugar_cells(self):
        cells = getattr(self.brain, 'sugar', None)
        if cells is None or not len(cells):
            raise ValueError('No sugar-sensing cells in this graph; construct with reward=False')
        return cells

    def step(self, frame, duration_ms, haltere_stimulation=None):
        if not math.isfinite(duration_ms) or duration_ms <= 0: raise ValueError('Positive duration required')
        b = self.brain
        steps = round(duration_ms / b.dt)
        if steps < 1: raise ValueError('Duration too short')
        start = b.cursor
        end = start + steps
        # Cut the tick at every pulse boundary that falls strictly inside it,
        # generalizing doom/training.py's single-boundary split: within each
        # segment the set of active currents is constant, which is what
        # rgb_step needs. The haltere current (unrelated to either
        # reinforcement channel) is present in every segment.
        edges = sorted({end} | {u for u in (self.until, self.sugar_until) if start < u < end})
        counts = np.zeros(b.n, dtype=np.int32)
        wall = 0.
        cursor = start
        aversive = appetitive = 0
        for edge in edges:
            n = edge - cursor
            pulses = [] if haltere_stimulation is None else [haltere_stimulation]
            if cursor < self.until:
                pulses.append((b.circuit['dan'], AVERSIVE_CURRENT)); aversive += n
            if cursor < self.sugar_until:
                pulses.append((self._sugar_cells(), APPETITIVE_CURRENT)); appetitive += n
            c, t = b.rgb_step(frame, n * b.dt, learning=self.enabled, stimulation=pulses or None)
            counts += c
            wall += t
            cursor = edge
        b.counts[:] = counts
        self.last_steps = aversive
        self.delivered_steps += aversive
        self.reward_steps += appetitive
        return counts, wall

    def observe(self, aversive, appetitive=False):
        """`aversive` is a crash or pipe strike; `appetitive` is a pipe
        cleared without touching it (flappy.game.Game reports both). Both are
        one-tick edge events, not levels -- the caller does not have to
        debounce. They are independent: a tick can carry neither, either, or
        both. `appetitive` defaults False so callers that only track crashes
        keep working unchanged."""
        if aversive:
            self.events += 1
            self.until = self.brain.cursor + PULSE_STEPS
        if appetitive and self.reward:
            self.rewards += 1
            self.sugar_until = self.brain.cursor + PULSE_STEPS
        return bool(aversive)

    def telemetry(self):
        b = self.brain
        m = b.memory()
        ratios = b.weight[b.circuit['edges']] / b.baseline_plastic
        if not np.isfinite(ratios).all(): raise RuntimeError('Nonfinite memory efficacy')
        return {**m, 'enabled': self.enabled, 'validated': False, 'reward': self.reward,
                'events': self.events, 'delivered_ms': round(self.delivered_steps * b.dt, 3),
                'rewards': self.rewards, 'reward_ms': round(self.reward_steps * b.dt, 3),
                'stimulus_active': self.last_steps > 0,
                'maximum_efficacy': float(ratios.max()), 'minimum_efficacy': float(ratios.min()),
                'mean_absolute_change': float(np.abs(ratios - 1).mean())}
