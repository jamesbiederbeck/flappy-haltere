"""Experiment class E-REGIME: does longer integration recover a transfer
function from the sensitive-dependence regime?

E-VPN-FB closed on this. Inside the unsaturated band the picture moves the
actuator hard -- flap fraction spans 0.48-0.95 -- but a ONE PIXEL change in
cue radius moves it 0.317, which is 78% of the range reachable across the
whole 0-220px sweep. The pathway amplifies the cue rather than encoding it.

That measurement was taken at 60 ticks. Two readings are consistent with it:

  (a) Finite-sample variance. The process is bounded and the per-tick flap
      decision is a noisy sample of it, so integrating longer averages the
      variance away and a stable transfer function appears underneath.
  (b) Genuine sensitive dependence. Nearby inputs diverge into different
      trajectories, and integrating longer does not help because the
      trajectories are different, not noisy.

These make opposite predictions about the SAME measurement. Under (a) the
adjacent-radius difference |flap(r) - flap(r+1)| shrinks as ticks rise, on
the order of 1/sqrt(ticks). Under (b) it stays flat.

This is the experiment that decides whether the regime can be fixed by a
cheaper readout or whether the drive point has to change. Nothing about the
cue or its encoding is varied -- that was E-VPN-FB's job and it is settled.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import annotations, digest
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.sensory_probe import disc, observe, readouts

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--tick-counts', type=int, nargs='+', default=[60, 120, 240, 480])
    p.add_argument('--radii', type=float, nargs='+', default=[22., 23., 24., 25., 26.])
    p.add_argument('--input-current', type=float, default=10.)
    p.add_argument('--feedback-current', type=float, default=32.)
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_sensory/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_sensory/regime_summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain); a = annotations(brain.ids); t = a.type.fillna('')
    lplc4 = np.flatnonzero(t.eq('LPLC4')).astype(np.int32)
    fb = np.flatnonzero(t.eq('IN06B077')).astype(np.int32)
    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-REGIME',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'tick_counts': args.tick_counts, 'radii': args.radii,
        'input_current': args.input_current, 'feedback_current': args.feedback_current,
        'graph_sha256': digest(brain.weight),
        'doc': 'docs/sensory-encoding-experiments.md#class-e-regime'})

    series = {}
    for ticks in args.tick_counts:
        flaps, dlms = [], []
        for r in args.radii:
            frame, _ = disc(r, 'upper')
            res = observe(brain, frame, groups, ticks, reset,
                          stimulation=[(lplc4, args.input_current), (fb, args.feedback_current)])
            log.write({'record': 'trial', 'run_id': run_id, 'experiment_class': 'E-REGIME',
                       'stage': 'integration_length', 'at': datetime.now(timezone.utc).isoformat(),
                       'ticks': ticks, 'radius': r, 'field': 'upper',
                       'input_current': args.input_current,
                       'feedback_current': args.feedback_current, **res})
            flaps.append(res['dlm_flap_fraction']); dlms.append(res['dlm_total'])
        steps = [abs(b - a_) for a_, b in zip(flaps, flaps[1:])]
        # DLM rate per tick -- the amplitude readout, free of the per-tick threshold.
        rates = [d / ticks for d in dlms]
        rate_steps = [abs(b - a_) / max(1e-9, np.mean(rates)) for a_, b in zip(rates, rates[1:])]
        series[ticks] = {'flap_fraction': flaps, 'dlm_total': dlms,
                         'dlm_rate_per_tick': [round(x, 4) for x in rates],
                         'mean_adjacent_flap_step': round(float(np.mean(steps)), 4),
                         'max_adjacent_flap_step': round(float(max(steps)), 4),
                         'mean_adjacent_rate_step_normalized': round(float(np.mean(rate_steps)), 4),
                         'flap_span': round(max(flaps) - min(flaps), 4)}
        print(json.dumps({'ticks': ticks, **{k: series[ticks][k] for k in
              ('flap_fraction', 'mean_adjacent_flap_step',
               'mean_adjacent_rate_step_normalized')}}), flush=True)

    base = series[args.tick_counts[0]]['mean_adjacent_flap_step']
    predicted = {str(tc): round(base * (args.tick_counts[0] / tc) ** .5, 4)
                 for tc in args.tick_counts}
    observed = {str(tc): series[tc]['mean_adjacent_flap_step'] for tc in args.tick_counts}
    longest = args.tick_counts[-1]
    shrink = observed[str(longest)] / max(1e-9, base)
    sqrt_shrink = (args.tick_counts[0] / longest) ** .5
    summary = {'run_id': run_id, 'experiment_class': 'E-REGIME',
        'finished': datetime.now(timezone.utc).isoformat(),
        'series': {str(k): v for k, v in series.items()},
        'observed_mean_adjacent_flap_step': observed,
        'predicted_if_finite_sample_noise': predicted,
        'observed_shrink_factor': round(shrink, 4),
        'sqrt_n_shrink_factor': round(sqrt_shrink, 4),
        'verdict': ('finite_sample_noise' if shrink <= sqrt_shrink * 1.5 else
                    'sensitive_dependence' if shrink > .7 else 'partial')}
    log.write({'record': 'summary', **summary}); log.close()
    Path(args.summary).write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'verdict': summary['verdict'],
                      'observed_shrink': summary['observed_shrink_factor'],
                      'sqrt_n_shrink': summary['sqrt_n_shrink_factor']}))


if __name__ == '__main__':
    main()
