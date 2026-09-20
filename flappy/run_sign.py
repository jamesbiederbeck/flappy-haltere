"""Experiment class E-SIGN: does falling faster actually drive more DLM?

The haltere loop is the harness's only closed feedback path. It injects
A(dy) = m*dy^n into the haltere afferents, rectified to zero while level or
rising, so the design intent is plain: a falling bird gets more current, the
wing motor pool fires more, the bird flaps more and stops falling.

E-DECODE measured the opposite. Across its threshold sweep the DLM rate fell
as the bird sat lower and fell faster -- 29.8 spikes per tick at threshold 320,
18.2 at 400, 14.0 at 570. That is the wrong direction for a stabilising loop,
and no amount of tuning downstream of it is worth doing until the sign is
known.

In the game those arms differ in two ways at once: fall speed, and what the
bird is looking at. This separates them. The visual frame is held fixed and
only the injected haltere current changes, so whatever comes out is the loop's
own transfer characteristic rather than a confound with the view.

Two sweeps. The first walks fall speed from 0 to the game's terminal 10 px per
tick through the real A(dy) used in play. The second walks raw current on a
flat grid, to see the afferents' own threshold without the square law
compressing everything into the top of the range.

Frozen weights, GPU.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import digest
from flappy.circuit import haltere_afferents, haltere_current_for_velocity
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.sensory_probe import base_frame, observe, readouts

ROOT = Path(__file__).resolve().parents[1]
VELOCITIES = [0., 1., 2., 3., 4., 5., 6., 7., 8., 9., 10.]
CURRENTS = [0., 2., 4., 6., 7., 8., 10., 14., 20., 40., 80., 175.]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--ticks', type=int, default=120)
    p.add_argument('--haltere-m', type=float, default=1.75)
    p.add_argument('--haltere-n', type=float, default=2.)
    p.add_argument('--velocities', type=float, nargs='+', default=VELOCITIES)
    p.add_argument('--currents', type=float, nargs='+', default=CURRENTS)
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_sign/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_sign/summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain)
    haltere = haltere_afferents(brain)
    frame = base_frame()
    run_id = str(uuid.uuid4())

    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-SIGN',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'haltere_m': args.haltere_m, 'haltere_n': args.haltere_n,
        'haltere_cells': int(np.asarray(haltere).size),
        'graph_sha256': digest(brain.weight),
        'doc': 'docs/sensory-encoding-experiments.md#class-e-sign'})

    def arm(kind, value, current):
        r = observe(brain, frame, groups, args.ticks, reset,
                    stimulation=[(np.asarray(haltere, dtype=np.int32), current)]
                    if current > 0 else None)
        row = {'record': 'arm', 'run_id': run_id, 'kind': kind, 'value': value,
               'current': round(float(current), 3),
               'at': datetime.now(timezone.utc).isoformat(),
               'dlm_per_tick': round(r['dlm_total'] / args.ticks, 3),
               **{k: v for k, v in r.items() if k != 'descending_vector'}}
        log.write(row)
        print(json.dumps({k: row[k] for k in ('kind', 'value', 'current',
              'dlm_total', 'dlm_per_tick', 'dlm_flap_fraction',
              'descending_total', 'wing_muscle_total')}), flush=True)
        return row

    rows = [arm('velocity', v, haltere_current_for_velocity(
                v, m=args.haltere_m, n=args.haltere_n)) for v in args.velocities]
    rows += [arm('current', c, c) for c in args.currents]

    vel = [r for r in rows if r['kind'] == 'velocity']
    rates = [r['dlm_per_tick'] for r in vel]
    rising = sum(1 for a, b in zip(rates, rates[1:]) if b >= a)
    summary = {'run_id': run_id, 'experiment_class': 'E-SIGN',
        'finished': datetime.now(timezone.utc).isoformat(), 'ticks': args.ticks,
        'haltere_m': args.haltere_m, 'haltere_n': args.haltere_n,
        'velocity_monotone_steps': f'{rising}/{len(rates) - 1}',
        'dlm_at_zero_velocity': rates[0], 'dlm_at_terminal_velocity': rates[-1],
        'sign': ('positive' if rates[-1] > rates[0] else
                 'negative' if rates[-1] < rates[0] else 'flat'),
        'arms': rows}
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'arms'}})
    log.close()
    out = Path(args.summary); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in ('velocity_monotone_steps',
          'dlm_at_zero_velocity', 'dlm_at_terminal_velocity', 'sign')}))


if __name__ == '__main__':
    main()
