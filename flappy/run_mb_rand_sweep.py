"""E-MB-RAND sweep: is the reconstructed KC->MBON11 weight pattern special,
or would any shuffle of the same weights over the same edges do?

The gate run answered the prior question -- shuffling is NOT a no-op. Despite
baseline_plastic never entering the rule's drive term (rule.py:31) and the
kernel's only read of baseline_weight sitting in a block that never executes
(kernel.cpp:77, gated on learning_enabled, and brain.py:125 always passes
learning=False), the closed loop carries it: 1,916 of 4,184 edges ended up
different, with a mean difference the same order as the learned change itself.

Scheme A: permute baseline_plastic across the same 4,184 edges. Topology,
weight multiset and total drive (11,401.5) are conserved exactly, so a
difference cannot be blamed on changed total input -- it isolates the pairing
of weights to edges, which is the only thing the reconstruction supplies here.

Pre-registered decision rule, declared before the sweep ran:
  "the reconstruction matters" needs the reconstructed arm's
  mean_absolute_change OUTSIDE the [min,max] of all draws (one-sided rank
  p = 1/21 = 0.048), a secondary statistic agreeing, and median |Spearman rho|
  between reconstructed and random per-edge memory_w below 0.5.
  "any weight matrix would do" is concluded if the statistics fall inside the
  draws' IQR, or median |rho| > 0.9.
  Degeneracy check: if the random arms all pin at a bound or all return zero
  change, the assay is measuring saturation and that is reported instead of a
  p-value.
No outcome here can rescue a behavioural claim -- the run this repeats cleared
zero pipes, and KC->MBON11 has no engineered path to the DLM cells the flap
decision reads. This is a control on the plasticity readout only.

Arms are tick-matched. No checkpoints are written: MemoryBrain computes
initial_weight_sha256 before any harness-side randomization, so a randomized
brain would otherwise checkpoint a digest asserting reconstructed provenance.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from flappy.dlm_pair_sweep import Log
from flappy.run_mb_rand_gate import arm

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ticks', type=int, default=2000)
    p.add_argument('--seed', type=int, default=41027)
    p.add_argument('--draws', type=int, default=20)
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_mb_rand/sweep.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_mb_rand/sweep_summary.json'))
    args = p.parse_args()

    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-MB-RAND', 'stage': 'sweep',
        'started': datetime.now(timezone.utc).isoformat(), 'ticks': args.ticks,
        'game_seed': args.seed, 'draws': args.draws, 'scheme': 'A_permute_baseline_plastic',
        'doc': 'docs/sensory-encoding-experiments.md#class-e-mb-rand'})

    def record(label, w, t, s, **extra):
        row = {'record': 'arm', 'run_id': run_id, 'arm': label,
               'at': datetime.now(timezone.utc).isoformat(), 'baseline_sum': s,
               **{k: t[k] for k in ('changed_edges', 'mean_efficacy', 'mean_absolute_change',
                                    'maximum_efficacy', 'minimum_efficacy')}, **extra}
        log.write(row)
        print(json.dumps({k: row[k] for k in ('arm', 'changed_edges',
              'mean_absolute_change', 'minimum_efficacy', 'spearman_rho') if k in row}), flush=True)
        return row

    ref_w, ref_t, ref_s = arm(args.ticks, args.seed)
    ref = record('reconstructed', ref_w, ref_t, ref_s)

    from scipy.stats import spearmanr
    rows = []
    for d in range(args.draws):
        w, t, s = arm(args.ticks, args.seed, shuffle_seed=d)
        rho = float(spearmanr(ref_w, w).statistic)
        rows.append(record(f'shuffled_{d}', w, t, s, shuffle_seed=d,
                           spearman_rho=round(rho, 5)))

    mac = [r['mean_absolute_change'] for r in rows]
    rhos = [abs(r['spearman_rho']) for r in rows]
    changed = [r['changed_edges'] for r in rows]
    q1, q3 = float(np.percentile(mac, 25)), float(np.percentile(mac, 75))
    degenerate = (len(set(changed)) == 1 and changed[0] in (0, 4184)) or all(m == 0 for m in mac)
    outside = not (min(mac) <= ref['mean_absolute_change'] <= max(mac))
    inside_iqr = q1 <= ref['mean_absolute_change'] <= q3
    summary = {'run_id': run_id, 'experiment_class': 'E-MB-RAND',
        'finished': datetime.now(timezone.utc).isoformat(), 'ticks': args.ticks,
        'draws': args.draws, 'degenerate_assay': bool(degenerate),
        'reconstructed': {k: ref[k] for k in ('mean_absolute_change', 'changed_edges',
                                              'minimum_efficacy', 'maximum_efficacy')},
        'random_mean_absolute_change': {'values': mac, 'min': min(mac), 'max': max(mac),
                                        'q1': q1, 'median': float(np.median(mac)), 'q3': q3},
        'random_changed_edges': {'min': min(changed), 'max': max(changed),
                                 'median': float(np.median(changed))},
        'spearman_abs_rho': {'values': rhos, 'median': float(np.median(rhos)),
                             'min': min(rhos), 'max': max(rhos)},
        'reconstructed_outside_range': bool(outside),
        'reconstructed_inside_iqr': bool(inside_iqr),
        'one_sided_rank_p': round(1 / (args.draws + 1), 4) if outside else None,
        'verdict': ('degenerate_assay' if degenerate else
                    'reconstruction_matters' if (outside and np.median(rhos) < .5) else
                    'any_weight_matrix_would_do' if (inside_iqr or np.median(rhos) > .9) else
                    'inconclusive')}
    log.write({'record': 'summary', **summary}); log.close()
    Path(args.summary).write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'verdict': summary['verdict']}))


if __name__ == '__main__':
    main()
