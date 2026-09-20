"""Experiment class E-LATCH: is the saturated state self-sustaining?

E-VIS-INV closed with the finding that this configuration has two reachable
regimes and nothing between them. Every drive that crosses the boundary, by
current (stage 1) or by recruited cell count (stage 2), lands in full
saturation: descending output about 80x baseline, wing muscle from 0 to
roughly 30,000, DLM flap fraction 0.99. Below the boundary every readout is
the resting baseline exactly.

Two mechanisms produce that shape and they call for opposite fixes.

  Driven saturation -- the network faithfully follows the drive, and the drive
  itself is all-or-nothing because a fixed-threshold cell under steady current
  has no intermediate rate. Remove the drive and activity falls straight back
  to baseline. The fix is a drive with graded statistics, e.g. stochastic or
  rate-coded injection rather than constant current.

  Runaway excitation -- crossing the boundary starts recurrent activity that
  feeds itself. Remove the drive and the network stays lit. The fix is gain
  control: the model has no adaptation, no synaptic depression and no
  inhibitory scaling, so nothing bounds a positive feedback loop.

The measurement that separates them is release. Drive over the boundary, then
remove the drive and watch. This records per-tick spike counts through both
phases, so the answer is a decay curve rather than a summary statistic.

Frozen weights, GPU.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import annotations, digest
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.run_vis_inverse import candidates
from flappy.sensory_probe import TICK_MS, base_frame, readouts
from connectome_sim.photoreceptor import retinal_samples

ROOT = Path(__file__).resolve().parents[1]
# (population, k) pairs taken from E-VIS-INV stage 2: the first count at which
# each one crosses. 'pool' is the two-cell draw that saturated where six other
# pooled cells did nothing.
ARMS = [('LLPC1', 4), ('LC19', 12), ('LC29', 16), ('aMe5', 24), ('LC16', 32)]


def trace(brain, lum, groups, cells, current, drive_ticks, release_ticks):
    """Per-tick spike counts through drive and release. Cold start each call."""
    reset(brain)
    stim = [(np.asarray(cells, dtype=np.int32), current)] if len(cells) else None
    net, dlm, desc, wm = [], [], [], []
    for tick in range(drive_ticks + release_ticks):
        counts, _ = brain.step(lum, TICK_MS,
                               stimulation=stim if tick < drive_ticks else None)
        counts = np.asarray(counts)
        net.append(int(counts.sum()))
        dlm.append(int(counts[groups['dlm']].sum()))
        desc.append(int(counts[groups['descending']].sum()))
        wm.append(int(counts[groups['wing_muscle']].sum()))
    return {'network': net, 'dlm': dlm, 'descending': desc, 'wing_muscle': wm}


def decay(series, drive_ticks, baseline):
    """How the release phase relaxes. `silence_tick` is ticks after release
    until DLM first goes quiet and stays quiet; None means it never did."""
    rel = series['dlm'][drive_ticks:]
    quiet = None
    for i in range(len(rel)):
        if all(c == 0 for c in rel[i:]): quiet = i; break
    net_rel = series['network'][drive_ticks:]
    tail = net_rel[-min(50, len(net_rel)):]
    return {'release_dlm_total': int(sum(rel)),
            'release_dlm_first_tick': int(rel[0]) if rel else 0,
            'release_dlm_last_tick': int(rel[-1]) if rel else 0,
            'silence_tick': quiet,
            'release_network_mean_tail': round(float(np.mean(tail)), 1) if tail else 0.,
            'baseline_network_mean': round(baseline, 1),
            'tail_over_baseline': round(float(np.mean(tail)) / baseline, 4)
                                  if baseline > 0 and tail else None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--drive-ticks', type=int, default=100)
    p.add_argument('--release-ticks', type=int, default=400)
    p.add_argument('--current', type=float, default=12.)
    p.add_argument('--seed', type=int, default=20260919)
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_latch/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_latch/summary.json'))
    p.add_argument('--traces', default=str(ROOT / 'outputs/flappy_latch/traces.npz'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain)
    cands = {c['type']: c for c in candidates(brain)}
    rng = np.random.default_rng(args.seed)
    order = {t: rng.permutation(cands[t]['cells']) for t in cands}
    ann = annotations(brain.ids)
    lum = retinal_samples(base_frame(), brain.uv)
    run_id = str(uuid.uuid4())

    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-LATCH',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'drive_ticks': args.drive_ticks, 'release_ticks': args.release_ticks,
        'current': args.current, 'seed': args.seed, 'graph_sha256': digest(brain.weight),
        'doc': 'docs/sensory-encoding-experiments.md#class-e-latch'})

    # Baseline first: same protocol, nothing driven, so "returns to baseline"
    # is measured rather than inferred from a remembered number.
    plan = [('baseline', np.zeros(0, dtype=np.int32))]
    for pop, k in ARMS:
        plan.append((f'{pop}_k{k}', order[pop][:k]))
    pool = np.concatenate([c['cells'] for c in cands.values()])
    pair = np.random.default_rng(args.seed + 1).choice(pool, size=2, replace=False)
    plan.append(('pool_pair', pair))

    rows, traces = [], {}
    for label, cells in plan:
        s = trace(brain, lum, groups, cells, args.current,
                  args.drive_ticks, args.release_ticks)
        traces[label] = np.array([s['network'], s['dlm'], s['descending'],
                                  s['wing_muscle']], dtype=np.int64)
        if label == 'baseline':
            base_net = float(np.mean(s['network']))
        drive_dlm = sum(s['dlm'][:args.drive_ticks])
        row = {'record': 'arm', 'run_id': run_id, 'arm': label,
               'at': datetime.now(timezone.utc).isoformat(),
               'n_cells': int(len(cells)),
               'cell_types': sorted(set(ann.type.iloc[cells].fillna('?'))) if len(cells) else [],
               'drive_dlm_total': int(drive_dlm),
               'drive_network_mean': round(float(np.mean(s['network'][:args.drive_ticks])), 1),
               **decay(s, args.drive_ticks, base_net)}
        rows.append(row); log.write(row)
        print(json.dumps({k: row[k] for k in ('arm', 'n_cells', 'drive_dlm_total',
              'release_dlm_total', 'silence_tick', 'tail_over_baseline')}), flush=True)

    latched = [r['arm'] for r in rows if r['arm'] != 'baseline' and r['silence_tick'] is None]
    summary = {'run_id': run_id, 'experiment_class': 'E-LATCH',
        'finished': datetime.now(timezone.utc).isoformat(),
        'drive_ticks': args.drive_ticks, 'release_ticks': args.release_ticks,
        'current': args.current, 'baseline_network_mean': round(base_net, 1),
        'latched_arms': latched, 'arms': rows}
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'arms'}})
    log.close()
    out = Path(args.summary); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    np.savez(args.traces, **traces)
    print(json.dumps({'status': 'done', 'arms': len(rows), 'latched': latched}))


if __name__ == '__main__':
    main()
