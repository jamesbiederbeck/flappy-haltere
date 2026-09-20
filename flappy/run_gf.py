"""Experiment class E-GF: fire the giant fibre by hand and see what it recruits.

E-SWAT showed the escape circuit never activates from an approaching object:
the looming detectors stay at zero and DNp01 never fires. That is a statement
about the *input* half of the pathway. It says nothing about whether the output
half works, because the output half was never tested -- nothing has ever fired
DNp01 in this project.

So fire it directly. If DNp01 drives the jump muscle, the escape circuit is
intact from the giant fibre down and the failure is purely upstream. If it does
not, the circuit is broken at both ends and the swatter null means less than it
looked.

Anatomy first, measured on this graph: DNp01 is 2 cells with out-degree 313 and
342. It synapses directly onto **TTMn**, the tergotrochanteral motor neuron that
drives the jump, with summed |w| 25. It does **not** synapse onto DLM, which is
correct -- the giant fibre triggers the leg jump, and the power muscles are
driven separately.

Frozen weights, GPU.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import annotations, digest
from connectome_sim.photoreceptor import retinal_samples
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.sensory_probe import TICK_MS, base_frame, readouts

ROOT = Path(__file__).resolve().parents[1]
CURRENTS = [0., 2., 4., 6., 7., 8., 10., 14., 20., 40.]


def groups_for(brain):
    a = annotations(brain.ids); t = a.type.fillna('')
    g = dict(readouts(brain))
    g['dnp01'] = np.flatnonzero((t == 'DNp01').to_numpy()).astype(np.int32)
    g['ttm'] = np.flatnonzero(t.isin(['TTMn', 'STTMm']).to_numpy()).astype(np.int32)
    g['vnc_motor'] = np.flatnonzero(
        (a.superclass == 'vnc_motor').to_numpy()).astype(np.int32)
    g['leg_motor'] = np.flatnonzero(
        ((a.superclass == 'vnc_motor') & a.subclass.isin(['fl', 'ml', 'hl'])).to_numpy()
    ).astype(np.int32)
    return g


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--ticks', type=int, default=60)
    p.add_argument('--currents', type=float, nargs='+', default=CURRENTS)
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_gf/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_gf/summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    g = groups_for(brain)
    lum = retinal_samples(base_frame(), brain.uv)
    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-GF',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'currents': args.currents,
        'dnp01_cells': int(g['dnp01'].size), 'ttm_cells': int(g['ttm'].size),
        'graph_sha256': digest(brain.weight),
        'doc': 'docs/sensory-encoding-experiments.md#class-e-gf'})

    rows = []
    for c in args.currents:
        reset(brain)
        totals = {k: 0 for k in g}
        network = 0
        for _ in range(args.ticks):
            counts, _ = brain.step(lum, TICK_MS,
                                   stimulation=[(g['dnp01'], c)] if c > 0 else None)
            counts = np.asarray(counts)
            network += int(counts.sum())
            for k, idx in g.items():
                totals[k] += int(counts[idx].sum())
        row = {'record': 'arm', 'run_id': run_id, 'current': c,
               'at': datetime.now(timezone.utc).isoformat(),
               'network_spikes': network,
               **{f'{k}_per_tick': round(v / args.ticks, 3) for k, v in totals.items()}}
        rows.append(row); log.write(row)
        print(json.dumps({k: row[k] for k in ('current', 'dnp01_per_tick',
              'ttm_per_tick', 'dlm_per_tick', 'leg_motor_per_tick',
              'vnc_motor_per_tick', 'descending_per_tick')}), flush=True)

    summary = {'run_id': run_id, 'experiment_class': 'E-GF',
        'finished': datetime.now(timezone.utc).isoformat(),
        'ticks': args.ticks, 'arms': rows}
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'arms'}})
    log.close()
    out = Path(args.summary); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done'}))


if __name__ == '__main__':
    main()
