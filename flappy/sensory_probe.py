"""Probes whether a game variable encoded into a sensory channel arrives
downstream as something a motor pool could actually distinguish.

The question is not "does this channel drive spikes" -- almost anything
does, and flybody-connectome's Johnston's-organ work had to withdraw a
potency result for exactly that reason (experiments/LOG.md, 2026-09-19:
stimulating any large population ignites the network into a generic
saturated state, so the table "says nothing specific about JO"). The
question is whether distinct values of the encoded variable produce
distinguishable, ordered responses. So the metric here is separability
across a variable's range, never total spike count, and every class runs
inside an operating band established first by the control below.

Honesty note on the visual channel. flappy/render3d.py is careful that what
it draws is a *rendering of the world*: pipes become walls because that is
where the pipes are. A looming disc drawn into the visual field purely to
signal "an obstacle is N units away" is not that -- it is a synthetic cue
injected into the retina, the visual equivalent of the haltere joystick's
injected current, and it carries the same "engineered, not biological"
status. It is not a claim that a fly would see this, or that the encoding
resembles any natural looming stimulus.

Readouts follow the same split the pair sweep settled on: the 67-cell
wing-muscle pool is the primary population readout (a vector, compared
across variable values), and DLM is reported separately because it is the
actuator and saturates early.
"""
import numpy as np
from connectome_sim.photoreceptor import retinal_samples
from connectome_sim.physiology.common import annotations
from flappy.circuit import DLM_TYPES
from flappy.game import FPS

TICK_MS = 1000 / FPS
FRAME = (512, 288)          # the env's own frame size, as render3d expects
SKY = np.array([78, 192, 202], dtype=np.uint8)
GROUND = np.array([222, 216, 149], dtype=np.uint8)
CUE = np.array([84, 56, 71], dtype=np.uint8)


def pools(brain):
    """Wing-muscle pool (population readout) and DLM (actuator readout)."""
    a = annotations(brain.ids)
    wm = np.flatnonzero(a.subclass == 'wm').astype(np.int32)
    dlm = np.flatnonzero(a.type.isin(DLM_TYPES)).astype(np.int32)
    if not len(wm) or not len(dlm): raise ValueError('Missing wing-muscle or DLM readout')
    return wm, dlm


def readouts(brain):
    """Readouts at each stage of the path a visual cue would have to travel:
    the whole network, the descending neurons that are the only bridge from
    brain to VNC, and the motor pools at the far end.

    The first E-LOOM sweep measured only the far end and got zeros at every
    parameter value, including the blank control -- which is exactly what
    flappy/circuit.py already documents (no VNC motor neuron spikes under
    plain visual drive). A readout whose floor and ceiling are both zero
    cannot distinguish anything, so the stages are now measured separately
    and the bottleneck is reported rather than hidden in a null."""
    a = annotations(brain.ids)
    wm, dlm = pools(brain)
    sup = a.superclass.fillna('-').to_numpy()
    return {'descending': np.flatnonzero(sup == 'descending_neuron').astype(np.int32),
            'wing_muscle': wm, 'dlm': dlm}


def base_frame(horizon=.55):
    """Sky over ground, no obstacle -- the blank the cue is drawn onto and
    the zero-signal control."""
    h, w = FRAME
    frame = np.empty((h, w, 3), dtype=np.uint8)
    split = int(h * horizon)
    frame[:split] = SKY
    frame[split:] = GROUND
    return frame


def looming(depth, field, horizon=.55, near=8., far=120.):
    """A disc whose angular size grows as `depth` shrinks -- the synthetic
    proximity cue. `field` places it in the upper or lower visual field,
    which is the only thing distinguishing the two encoded variables.

    Radius is the pinhole projection of a fixed-size object: r ~ 1/depth,
    normalized so `far` is barely visible and `near` fills much of the
    field. Not calibrated to any real object size.
    """
    if field not in ('upper', 'lower'): raise ValueError("field must be 'upper' or 'lower'")
    if not np.isfinite(depth) or depth <= 0: raise ValueError('Positive depth required')
    frame = base_frame(horizon)
    h, w = FRAME
    radius = float(np.clip((near / max(depth, near / 8.)) * (h * .18), 2., h * .45))
    cx = w / 2
    cy = h * (.22 if field == 'upper' else .88)
    y, x = np.ogrid[:h, :w]
    frame[((x - cx) ** 2 + (y - cy) ** 2) <= radius ** 2] = CUE
    return frame, radius


def disc(radius, field, horizon=.55):
    """The same cue as `looming`, but parameterized by angular size directly
    instead of through the 1/depth projection. E-VPN-FB found a non-monotone
    response across depth; sweeping radius on its own grid separates "the
    pathway has a complex tuning curve" from "the 1/depth mapping bunched the
    samples up", which the depth sweep cannot distinguish."""
    if field not in ('upper', 'lower'): raise ValueError("field must be 'upper' or 'lower'")
    frame = base_frame(horizon)
    h, w = FRAME
    r = float(radius)
    if r <= 0: return frame, 0.
    cx, cy = w / 2, h * (.22 if field == 'upper' else .88)
    y, x = np.ogrid[:h, :w]
    frame[((x - cx) ** 2 + (y - cy) ** 2) <= r ** 2] = CUE
    return frame, r


def observe(brain, frame, groups, ticks, reset_fn, stimulation=None):
    """One independent sample: cold start, then hold the frame for `ticks`
    game ticks, summing spikes per readout group.

    `stimulation` is passed through to the engine unchanged, so a cue can be
    probed on top of a driven baseline as well as on a resting one."""
    reset_fn(brain)
    lum = retinal_samples(frame, brain.uv)
    totals = {k: np.zeros(len(v), dtype=np.int64) for k, v in groups.items()}
    network = 0
    dlm_per_tick = []
    for _ in range(ticks):
        counts, _ = brain.step(lum, TICK_MS, stimulation=stimulation)
        counts = np.asarray(counts)
        network += int(counts.sum())
        for k, idx in groups.items(): totals[k] += counts[idx]
        if 'dlm' in groups: dlm_per_tick.append(int(counts[groups['dlm']].sum()))
    out = {'network_spikes': network}
    for k, v in totals.items():
        out[f'{k}_total'] = int(v.sum())
        out[f'{k}_active_cells'] = int((v > 0).sum())
    out['descending_vector'] = totals['descending'].tolist() if 'descending' in totals else []
    if dlm_per_tick:
        out['dlm_flap_fraction'] = round(sum(1 for c in dlm_per_tick if c > 0) / ticks, 4)
    return out


def separability(vectors):
    """How well an ordered series of response vectors distinguishes its own
    steps. Cosine distance between consecutive normalized vectors, plus
    whether the total is monotone across the series. A channel that returns
    the same vector at every value of the variable is not an encoding,
    however many spikes it produces."""
    v = [np.asarray(x, dtype=float) for x in vectors]
    norms = [x / n if (n := np.linalg.norm(x)) > 0 else x for x in v]
    steps = [float(1 - np.dot(a, b)) for a, b in zip(norms, norms[1:])]
    totals = [float(x.sum()) for x in v]
    rising = sum(1 for a, b in zip(totals, totals[1:]) if b >= a)
    return {'step_distances': [round(s, 5) for s in steps],
            'mean_step_distance': round(float(np.mean(steps)), 5) if steps else 0.,
            'max_step_distance': round(float(max(steps)), 5) if steps else 0.,
            'totals': totals,
            'monotone_fraction': round(max(rising, len(totals) - 1 - rising) / max(1, len(totals) - 1), 3),
            'all_silent': all(t == 0 for t in totals)}
