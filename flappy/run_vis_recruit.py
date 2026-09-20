"""Experiment class E-VIS-INV, stage 2: is recruitment count the knob?

Stage 1 screened all 77 visual projection populations and found none of them
graded under current injection. The reason was not the cell choice. At currents
4 and 6, 151 of 385 trials returned the unstimulated baseline byte for byte, in
76 of the 77 populations: the drive was sub-rheobase and added no spike
anywhere. Above that point the driven cells fire and the motor pool saturates.
Spike threshold is a hardcoded -45 mV for every neuron in both backends, so a
fixed-threshold cell under steady injected current has no intermediate rate to
ride and current cannot be a knob.

One graded quantity is left: how many cells are driven. Stage 1 also showed the
range is small -- LPT31 drives DLM to 1,251 spikes with 8 cells, essentially
what LLPC1 reaches with 285 -- so this sweeps absolute counts on a log-ish grid
rather than fractions of population size, which would step straight over it.

Arms nest: cells are drawn in one fixed seeded order per population, so the
k = 4 arm's cells are the first four of the k = 8 arm's. The control is a
size-matched random draw from the whole visual candidate pool at the same k,
which separates "these cells" from "this many cells" -- the same specificity
control E-VPN-FB used.

Frozen weights, GPU.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import digest
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.run_vis_inverse import candidates
from flappy.sensory_probe import base_frame, observe, readouts

ROOT = Path(__file__).resolve().parents[1]
POPULATIONS = ['LC16', 'LC19', 'aMe5', 'LC29', 'LLPC1']
COUNTS = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--ticks', type=int, default=300)
    p.add_argument('--current', type=float, default=12.)
    p.add_argument('--counts', type=int, nargs='+', default=COUNTS)
    p.add_argument('--populations', nargs='+', default=POPULATIONS)
    p.add_argument('--seed', type=int, default=20260919)
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_vis_inverse/recruit.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_vis_inverse/recruit_summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain)
    cands = {c['type']: c for c in candidates(brain)}
    missing = [p for p in args.populations if p not in cands]
    if missing: raise SystemExit(f'not visual candidates: {missing}')
    pool = np.concatenate([c['cells'] for c in cands.values()])
    blank = base_frame()
    rng = np.random.default_rng(args.seed)
    order = {p: rng.permutation(cands[p]['cells']) for p in args.populations}
    run_id = str(uuid.uuid4())

    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-VIS-INV', 'stage': 2,
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'current': args.current, 'counts': args.counts,
        'populations': args.populations, 'seed': args.seed,
        'graph_sha256': digest(brain.weight), 'pool_cells': int(pool.size),
        'doc': 'docs/sensory-encoding-experiments.md#stage-2--recruitment-count-as-the-knob'})

    def arm(label, population, k, cells):
        r = observe(brain, blank, groups, args.ticks, reset,
                    stimulation=[(np.asarray(cells, dtype=np.int32), args.current)])
        row = {'record': 'trial', 'run_id': run_id, 'arm': label,
               'at': datetime.now(timezone.utc).isoformat(), 'population': population,
               'k': int(k), **{key: v for key, v in r.items() if key != 'descending_vector'}}
        log.write(row)
        print(json.dumps({key: row[key] for key in
              ('arm', 'population', 'k', 'dlm_total', 'dlm_active_cells',
               'dlm_flap_fraction')}), flush=True)
        return row

    rows = [arm('baseline', 'none', 0, np.zeros(0, dtype=np.int32))]
    for pop in args.populations:
        for k in args.counts:
            if k > cands[pop]['n']: break
            rows.append(arm('population', pop, k, order[pop][:k]))
    control = np.random.default_rng(args.seed + 1)
    for k in args.counts:
        rows.append(arm('random_pool', 'random', k,
                        control.choice(pool, size=k, replace=False)))

    summary = {'run_id': run_id, 'experiment_class': 'E-VIS-INV', 'stage': 2,
        'finished': datetime.now(timezone.utc).isoformat(), 'ticks': args.ticks,
        'current': args.current, 'counts': args.counts, 'populations': args.populations,
        'flap_resolution': round(1. / args.ticks, 6),
        'trials': [{key: r[key] for key in ('arm', 'population', 'k', 'dlm_total',
                    'dlm_active_cells', 'dlm_flap_fraction', 'descending_total',
                    'wing_muscle_total')} for r in rows]}
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'trials'}})
    log.close()
    out = Path(args.summary); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'trials': len(rows)}))


if __name__ == '__main__':
    main()
