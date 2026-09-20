"""Executes experiment class E-LOOM across its parameter space.

See docs/sensory-encoding-experiments.md for the hypothesis, what the cue is
and is not, and the metrics. This file is the runner only.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import digest
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.sensory_probe import base_frame, looming, observe, readouts, separability

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', default='malecns_v1')
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--ticks', type=int, default=15)
    p.add_argument('--depths', type=float, nargs='+',
                   default=[8., 12., 16., 24., 32., 48., 64., 96., 120.])
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_sensory/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_sensory/loom_summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim' / args.dataset / 'graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain
        brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain
        brain = NativeBrain(path)

    groups = readouts(brain)
    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-LOOM',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'depths': args.depths, 'graph_sha256': digest(brain.weight),
        'readout_cells': {k: int(len(v)) for k, v in groups.items()},
        'doc': 'docs/sensory-encoding-experiments.md#class-e-loom--looming-cue-separability'})

    def record(stage, result, **fields):
        log.write({'record': 'trial', 'run_id': run_id, 'experiment_class': 'E-LOOM',
                   'stage': stage, 'at': datetime.now(timezone.utc).isoformat(),
                   **fields, **result})
        print(json.dumps({'stage': stage, **fields, 'network': result['network_spikes'],
                          'descending': result['descending_total'],
                          'desc_cells': result['descending_active_cells'],
                          'wm': result['wing_muscle_total']}), flush=True)
        return result

    blank = record('control_blank',
                   observe(brain, base_frame(), groups, args.ticks, reset),
                   field=None, depth=None, radius=None)

    series = {}
    for field in ('upper', 'lower'):
        results = []
        for depth in args.depths:
            frame, radius = looming(depth, field)
            results.append(record('loom',
                observe(brain, frame, groups, args.ticks, reset),
                field=field, depth=depth, radius=round(radius, 2)))
        series[field] = results

    summary = {'run_id': run_id, 'experiment_class': 'E-LOOM',
               'finished': datetime.now(timezone.utc).isoformat(),
               'blank': {k: blank[k] for k in
                         ('network_spikes', 'descending_total', 'wing_muscle_total')},
               'depths': args.depths}
    for field, results in series.items():
        summary[field] = {
            'descending_separability': separability([r['descending_vector'] for r in results]),
            'network_spikes': [r['network_spikes'] for r in results],
            'descending_totals': [r['descending_total'] for r in results],
            'wing_muscle_totals': [r['wing_muscle_total'] for r in results],
            'network_differs_from_blank': [r['network_spikes'] != blank['network_spikes']
                                           for r in results]}
    # Do the two fields actually encode different things, or is the retina
    # reporting "a dark blob exists" regardless of where it sits?
    upper = np.array([r['descending_vector'] for r in series['upper']], dtype=float)
    lower = np.array([r['descending_vector'] for r in series['lower']], dtype=float)
    per_depth = []
    for u, l in zip(upper, lower):
        nu, nl = np.linalg.norm(u), np.linalg.norm(l)
        per_depth.append(round(float(1 - np.dot(u / nu, l / nl)), 5) if nu and nl else None)
    summary['upper_vs_lower_distance'] = per_depth
    log.write({'record': 'summary', **summary})
    log.close()
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'log': args.log, 'summary': args.summary}))


if __name__ == '__main__':
    main()
