"""Screens pairs of DLM-upstream cell groups as a two-channel motor control:
one group driven as the *input* (the channel meant to make the bird flap) and
a second as the *feedback* (the channel meant to grade that flap back down).

Why pairs at all. flappy/circuit.py records the measured problem this is
trying to solve: DLM firing turns on as a sharp threshold, not a graded
response to a constant current -- 0/150 ticks flap at 5 mV-equivalent,
~97-99% of ticks flap at 7-10 mV, with no tested constant current in
between. A bang-bang actuator is why the haltere joystick cannot hold an
altitude. A pair succeeds here exactly when some (input, feedback) current
combination puts the flap fraction strictly between 0 and 1 and holds it
there -- anything else is the same two-state actuator with extra steps.

What this stage does NOT do. The feedback current here is *constant* within
a trial, which characterizes the 2-D transfer surface but is not feedback in
the control-theory sense. Closing the loop -- computing the feedback current
from the previous tick's measured DLM rate -- is a separate follow-up and a
different script structure. Nothing in this file ran a closed loop.

Candidate pools are computed from the graph every run, never hardcoded:
every connectome type presynaptic to the DLM cells, split by the sign of its
summed weight onto them. That sign is a *modeling assumption* in this
pipeline, not a measurement -- connectome_sim assigns it per cell from
neurotransmitter, and physiology/visual.py already overrides it for one
pathway -- so the sign only picks which pool a group is screened in. Whether
a "feedback" group actually suppresses anything is measured here, by driving
it on top of an already-driven input rather than on a silent network, where
an inhibitory channel would produce nothing and prove nothing.

Every trial, including the controls and the ones that fail, is appended to a
JSONL log as it happens. Failed pairs stay in the log and in the summary --
this repo does not filter unfavorable arms out of its results.
"""
import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from connectome_sim.physiology.common import annotations, digest
from flappy.circuit import DLM_TYPES
from flappy.game import FPS
from flappy.inverse_data import reset

ROOT = Path(__file__).resolve().parents[1]
TICK_MS = 1000 / FPS   # the flap decision's own timescale; see metrics below


def dlm_upstream_groups(brain, minimum_cells=2, minimum_weight=100.):
    """Every connectome type with a direct edge onto a DLM motor neuron,
    with its cell indices and its summed signed weight onto them."""
    a = annotations(brain.ids)
    dlm = np.flatnonzero(a.type.isin(DLM_TYPES)).astype(np.int32)
    if not len(dlm): raise ValueError('No DLM motor neurons found in this graph')
    edges = np.flatnonzero(np.isin(brain.post, dlm))
    pre = np.searchsorted(brain.ptr, edges, side='right') - 1
    frame = pd.DataFrame({'pre': pre, 'w': brain.weight[edges]})
    frame['type'] = a.type.iloc[pre].fillna('(untyped)').to_numpy()
    groups = []
    for name, part in frame.groupby('type'):
        cells = np.unique(part.pre.to_numpy()).astype(np.int32)
        signed = float(part.w.sum())
        if len(cells) < minimum_cells or abs(signed) < minimum_weight: continue
        groups.append({'type': str(name), 'cells': cells, 'n_cells': len(cells),
                       'signed_weight': signed,
                       'superclass': str(a.superclass.iloc[cells[0]]),
                       'entry_nerve': str(a.entryNerve.iloc[cells[0]] or '-'),
                       'negative_edge_fraction': float((part.w < 0).mean())})
    inputs = sorted([g for g in groups if g['signed_weight'] > 0],
                    key=lambda g: -g['signed_weight'])
    feedback = sorted([g for g in groups if g['signed_weight'] < 0],
                      key=lambda g: g['signed_weight'])
    return dlm, inputs, feedback


class Log:
    """Append-only JSONL, flushed per line so a killed sweep keeps every
    trial it finished."""
    def __init__(self, path, header):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open('a')
        self.write({'record': 'run', **header})

    def write(self, row):
        self.handle.write(json.dumps(row) + '\n')
        self.handle.flush()

    def close(self):
        self.handle.close()


def trial(brain, dlm, luminance, pulses, ticks):
    """One independent sample: cold-start the brain, then run `ticks` game
    ticks with the stimulation held constant, recording DLM spikes per tick.

    reset() between every trial is not optional -- inverse_data.reset's
    docstring records five back-to-back trials on a never-reset brain going
    silent/1265/1210/1308, tracking accumulated ramp-up rather than that
    trial's own stimulation.

    Two metrics, deliberately both: `spikes` is the DLM total, `flap_ticks`
    is how many ticks contained at least one DLM spike -- which is exactly
    what FlapControls.decode turns into a button press. A trial can have a
    large total and still flap on every single tick, so only the second one
    is the control problem.
    """
    reset(brain)
    per_tick = []
    start = time.perf_counter()
    for _ in range(ticks):
        counts, _ = brain.step(luminance, TICK_MS, stimulation=pulses or None)
        per_tick.append(int(np.asarray(counts)[dlm].sum()))
    return {'spikes': int(sum(per_tick)), 'per_tick': per_tick,
            'flap_ticks': int(sum(1 for c in per_tick if c > 0)),
            'flap_fraction': round(sum(1 for c in per_tick if c > 0) / ticks, 4),
            'wall_seconds': round(time.perf_counter() - start, 3)}


def graded(result):
    """A pair is interesting only if the flap fraction lands strictly
    between never and always. Saturated and silent are both failures."""
    return 0. < result['flap_fraction'] < 1.


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', default='malecns_v1')
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu',
                    help='Frozen-weight simulation, not a learning run -- defaults to gpu.')
    p.add_argument('--ticks', type=int, default=15, help='Game ticks per trial (33.3 ms each)')
    p.add_argument('--input-currents', type=float, nargs='+', default=[4., 6., 8., 10., 12.])
    p.add_argument('--feedback-currents', type=float, nargs='+', default=[2., 4., 8., 12., 16.])
    p.add_argument('--inputs', type=int, default=6, help='How many input candidates to pair')
    p.add_argument('--feedbacks', type=int, default=6, help='How many feedback candidates to pair')
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_dlm_pairs/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_dlm_pairs/summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim' / args.dataset / 'graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain
        brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain
        brain = NativeBrain(path)

    dlm, inputs, feedback = dlm_upstream_groups(brain)
    luminance = np.zeros(len(brain.retina), dtype=np.float32)
    run_id = str(uuid.uuid4())
    log = Log(args.log, {
        'run_id': run_id, 'started': datetime.now(timezone.utc).isoformat(),
        'dataset': args.dataset, 'backend': args.backend, 'ticks': args.ticks,
        'tick_ms': TICK_MS, 'graph_sha256': digest(brain.weight),
        'dlm_cells': int(len(dlm)),
        'input_candidates': [{k: v for k, v in g.items() if k != 'cells'} for g in inputs],
        'feedback_candidates': [{k: v for k, v in g.items() if k != 'cells'} for g in feedback],
        'input_currents': args.input_currents, 'feedback_currents': args.feedback_currents,
        'note': 'Constant-current characterization. No closed loop was run.'})

    def record(stage, result, **fields):
        row = {'record': 'trial', 'run_id': run_id, 'stage': stage,
               'at': datetime.now(timezone.utc).isoformat(), **fields,
               **{k: v for k, v in result.items() if k != 'per_tick'},
               'per_tick': result['per_tick'], 'graded': graded(result)}
        log.write(row)
        print(json.dumps({k: row[k] for k in
              ('stage', 'input', 'feedback', 'input_current', 'feedback_current',
               'spikes', 'flap_fraction', 'graded') if k in row}), flush=True)
        return row

    rows = []
    # Control arm 1: each input alone. This is the baseline a pair has to
    # beat, and it is where each input's saturating current is measured.
    for g in inputs[:args.inputs]:
        for current in args.input_currents:
            rows.append(record('input_alone',
                trial(brain, dlm, luminance, [(g['cells'], current)], args.ticks),
                input=g['type'], input_current=current, feedback=None, feedback_current=0.))

    # Control arm 2: each feedback alone on an undriven network. Expected to
    # do nothing; if one of these drives DLM, the sign that put it in the
    # feedback pool does not describe its measured effect and the pairs
    # below have to be read accordingly.
    for g in feedback[:args.feedbacks]:
        for current in args.feedback_currents:
            rows.append(record('feedback_alone',
                trial(brain, dlm, luminance, [(g['cells'], current)], args.ticks),
                input=None, input_current=0., feedback=g['type'], feedback_current=current))

    # Pairs: hold the input at the lowest current that saturated it alone
    # (the regime the bang-bang problem actually lives in), sweep feedback.
    saturating = {}
    for g in inputs[:args.inputs]:
        hits = [r for r in rows if r['stage'] == 'input_alone' and r['input'] == g['type']
                and r['flap_fraction'] >= 1.]
        if hits: saturating[g['type']] = min(h['input_current'] for h in hits)

    for g in inputs[:args.inputs]:
        current = saturating.get(g['type'])
        if current is None:
            log.write({'record': 'skip', 'run_id': run_id, 'input': g['type'],
                       'reason': 'never saturated alone at any tested current; '
                                 'nothing for a feedback channel to grade down'})
            continue
        for f in feedback[:args.feedbacks]:
            for fc in args.feedback_currents:
                rows.append(record('pair',
                    trial(brain, dlm, luminance, [(g['cells'], current), (f['cells'], fc)], args.ticks),
                    input=g['type'], input_current=current,
                    feedback=f['type'], feedback_current=fc))

    wins = [r for r in rows if r['stage'] == 'pair' and r['graded']]
    summary = {
        'run_id': run_id, 'finished': datetime.now(timezone.utc).isoformat(),
        'backend': args.backend, 'ticks_per_trial': args.ticks,
        'trials': len(rows), 'graded_pairs': len(wins),
        'saturating_currents': saturating,
        # Every arm is reported, including the ones that found nothing.
        'pairs': [{k: r[k] for k in ('input', 'input_current', 'feedback',
                                     'feedback_current', 'spikes', 'flap_fraction', 'graded')}
                  for r in rows if r['stage'] == 'pair'],
        'interpretation': 'A graded pair is a candidate two-channel actuator, not a '
                          'validated one: the feedback current here is constant, so this '
                          'measures a transfer surface, not a closed loop. No claim is made '
                          'that any of these correspond to a real fly control pathway.',
    }
    out = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'pairs'}})
    log.close()
    print(json.dumps({'status': 'done', 'trials': len(rows), 'graded_pairs': len(wins),
                      'log': args.log, 'summary': args.summary}))


if __name__ == '__main__':
    main()
