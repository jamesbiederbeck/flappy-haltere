"""Experiment class E-GAIN: does network-wide adaptation remove the attractor?

E-LATCH showed this configuration has two reachable states and that the
saturated one is self-sustaining: drive removed for 400 ticks and DLM keeps
firing about 30 spikes per tick, with all five drive points converging on the
same total rate within 0.22%. Nothing in the model bounds recurrent gain. A
2.2 ms refractory period caps peak rate without pulling gain below unity, and
there is no synaptic depression or inhibitory scaling.

Spike-frequency adaptation does exist in the CPU physiology kernel, but the
jump was gated to Kenyon cells by `kc_mask`. That gate is now a separate
`adaptation_mask` parameter defaulting to `kc_mask`, so unmodified callers get
identical dynamics and this class can widen it to the whole graph.

The sweep asks two things at once, and the second is the one that matters:

  Does adaptation remove the attractor? Drive over the boundary, release, and
  see whether activity comes back down.

  Does it do so without silencing the network? An adaptation strong enough to
  kill the attractor by killing all activity has not created a usable regime,
  it has created a quiet one. So the undriven baseline is measured at every
  strength, not just the driven arms.

CPU only -- the GPU path has no adaptation at all. Costs roughly a second per
tick, so arms are short by comparison with the GPU classes.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import digest
from connectome_sim.photoreceptor import retinal_samples
from flappy.dlm_pair_sweep import Log
from flappy.run_vis_inverse import candidates
from flappy.sensory_probe import TICK_MS, base_frame, readouts

ROOT = Path(__file__).resolve().parents[1]
JUMPS = [0., 2., 4., 8., 16.]


def drive_cells(brain, population, k, seed):
    """Same seeded draw E-LATCH used, so the arms are comparable."""
    cands = {c['type']: c for c in candidates(brain)}
    rng = np.random.default_rng(seed)
    order = {t: rng.permutation(cands[t]['cells']) for t in cands}
    return order[population][:k]


def trace(brain, lum, groups, cells, current, drive_ticks, release_ticks):
    brain.reset()
    stim = [(np.asarray(cells, dtype=np.int32), current)] if len(cells) else None
    net, dlm = [], []
    for tick in range(drive_ticks + release_ticks):
        counts, _ = brain.step(lum, TICK_MS,
                               stimulation=stim if tick < drive_ticks else None)
        counts = np.asarray(counts)
        net.append(int(counts.sum())); dlm.append(int(counts[groups['dlm']].sum()))
    return net, dlm


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jumps', type=float, nargs='+', default=JUMPS)
    p.add_argument('--tau', type=float, default=200.)
    p.add_argument('--population', default='LLPC1')
    p.add_argument('--k', type=int, default=4)
    p.add_argument('--current', type=float, default=12.)
    p.add_argument('--drive-ticks', type=int, default=40)
    p.add_argument('--release-ticks', type=int, default=120)
    p.add_argument('--seed', type=int, default=20260919)
    p.add_argument('--scope', choices=['all', 'kc'], nargs='+', default=['all'])
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_gain/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_gain/summary.json'))
    p.add_argument('--traces', default=str(ROOT / 'outputs/flappy_gain/traces.npz'))
    args = p.parse_args()

    from connectome_sim.physiology.brain import MemoryBrain
    graph = str(ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz')
    probe = MemoryBrain(graph)
    groups = readouts(probe)
    cells = drive_cells(probe, args.population, args.k, args.seed)
    lum = retinal_samples(base_frame(), probe.uv)
    kc_mask = np.asarray(probe.adaptation_mask, dtype=np.uint8).copy()
    wide = np.ones(probe.n, dtype=np.uint8)
    run_id = str(uuid.uuid4())
    del probe

    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-GAIN',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': 'native-physiology',
        'jumps': args.jumps, 'tau': args.tau, 'population': args.population, 'k': args.k,
        'current': args.current, 'drive_ticks': args.drive_ticks,
        'release_ticks': args.release_ticks, 'seed': args.seed,
        'kc_cells': int(kc_mask.sum()), 'total_cells': int(wide.sum()),
        'doc': 'docs/sensory-encoding-experiments.md#class-e-gain'})

    rows, traces = [], {}
    for scope in args.scope:
        mask = wide if scope == 'all' else kc_mask
        for jump in args.jumps:
            brain = MemoryBrain(graph, adaptation_jump=jump, adaptation_tau=args.tau,
                                adaptation_mask=mask)
            brain.weights_frozen = True
            for label, sel in (('rest', np.zeros(0, dtype=np.int32)), ('driven', cells)):
                net, dlm = trace(brain, lum, groups, sel, args.current,
                                 args.drive_ticks if label == 'driven' else 0,
                                 args.release_ticks if label == 'driven'
                                 else args.drive_ticks + args.release_ticks)
                arm = f'{scope}_jump{jump:g}_{label}'
                traces[arm] = np.array([net, dlm], dtype=np.int64)
                rel = dlm[args.drive_ticks:] if label == 'driven' else dlm
                quiet = next((i for i in range(len(rel))
                              if all(c == 0 for c in rel[i:])), None)
                row = {'record': 'arm', 'run_id': run_id, 'arm': arm, 'scope': scope,
                       'adapting_cells': int(mask.sum()), 'jump': jump, 'tau': args.tau,
                       'condition': label,
                       'at': datetime.now(timezone.utc).isoformat(),
                       'network_mean': round(float(np.mean(net)), 1),
                       'network_tail_mean': round(float(np.mean(net[-40:])), 1),
                       'dlm_total': int(sum(dlm)),
                       'release_dlm_total': int(sum(rel)),
                       'silence_tick': quiet,
                       'latched': label == 'driven' and quiet is None}
                rows.append(row); log.write(row)
                print(json.dumps({k: row[k] for k in ('arm', 'network_mean',
                      'network_tail_mean', 'dlm_total', 'silence_tick', 'latched')}),
                      flush=True)
            del brain

    rest = {r['arm']: r for r in rows if r['condition'] == 'rest'}
    for r in rows:
        if r['condition'] != 'driven': continue
        b = rest.get(r['arm'].replace('_driven', '_rest'))
        r['tail_over_rest'] = (round(r['network_tail_mean'] / b['network_tail_mean'], 4)
                               if b and b['network_tail_mean'] > 0 else None)
    summary = {'run_id': run_id, 'experiment_class': 'E-GAIN',
        'finished': datetime.now(timezone.utc).isoformat(),
        'jumps': args.jumps, 'tau': args.tau, 'scope': args.scope,
        'population': args.population, 'k': args.k, 'current': args.current,
        'drive_ticks': args.drive_ticks, 'release_ticks': args.release_ticks,
        'arms': rows}
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'arms'}})
    log.close()
    out = Path(args.summary); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    np.savez(args.traces, **traces)
    print(json.dumps({'status': 'done', 'arms': len(rows)}))


if __name__ == '__main__':
    main()
