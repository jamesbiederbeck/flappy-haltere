"""Executes experiment class E-VPN-FB: LPLC4 as the visual input channel,
IN06B077 as the feedback channel that keeps the actuator out of saturation.

E-VPN opened the visual->wing-motor bridge at LPLC4 and proved it specific,
then failed its discretion test for one reason: at every current that opens
the bridge, DLM is saturated (flap fraction 0.93-1.00) and the picture stops
mattering. The pair sweep independently found the missing piece -- IN06B077
takes DLM from flap 1.00 to 0.00 across feedback currents 8->16, monotone,
where no size-matched random feedback set suppresses at all.

This class puts them together. Stage A finds the feedback current that lands
the actuator mid-range under LPLC4 drive. Stage B is the same discretion test
E-VPN failed, re-run inside that unsaturated band: current held fixed on both
channels, only the picture changes. Stage C repeats the random-feedback
control in this configuration, because a suppression that any 7 cells could
produce would not be IN06B077 doing anything.

If stage B still shows no ordered dependence on the cue, the conclusion is
not "wrong feedback cell" -- it is that this reconstruction does not route
looming information to flight power in a way the actuator can express, and
the sensory-encoding line should stop rather than try a sixth channel.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import annotations, digest
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.sensory_probe import base_frame, looming, observe, readouts

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--ticks', type=int, default=15)
    p.add_argument('--input-currents', type=float, nargs='+', default=[8., 10.])
    p.add_argument('--feedback-currents', type=float, nargs='+',
                   default=[4., 8., 12., 16., 20., 24., 28., 32., 40.])
    p.add_argument('--depths', type=float, nargs='+', default=[8., 16., 32., 64., 120.])
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_sensory/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_sensory/vpn_fb_summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain)
    a = annotations(brain.ids); t = a.type.fillna('')
    lplc4 = np.flatnonzero(t.eq('LPLC4')).astype(np.int32)
    fb = np.flatnonzero(t.eq('IN06B077')).astype(np.int32)
    if not len(lplc4) or not len(fb): raise ValueError('Missing LPLC4 or IN06B077')
    vnc = np.flatnonzero(a.superclass.fillna('').eq('vnc_intrinsic').to_numpy()).astype(np.int32)
    control_pool = np.setdiff1d(vnc, fb)
    rng = np.random.default_rng(0)

    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-VPN-FB',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'input_currents': args.input_currents,
        'feedback_currents': args.feedback_currents, 'depths': args.depths,
        'graph_sha256': digest(brain.weight), 'lplc4_cells': int(len(lplc4)),
        'feedback_cells': int(len(fb)),
        'doc': 'docs/sensory-encoding-experiments.md#class-e-vpn-fb'})

    def rec(stage, r, **f):
        log.write({'record': 'trial', 'run_id': run_id, 'experiment_class': 'E-VPN-FB',
                   'stage': stage, 'at': datetime.now(timezone.utc).isoformat(), **f, **r})
        print(json.dumps({'stage': stage, **f, 'desc': r['descending_total'],
                          'wm': r['wing_muscle_total'], 'dlm': r['dlm_total'],
                          'flap': r['dlm_flap_fraction']}), flush=True)
        return r

    blank = base_frame()
    # Stage A -- find the feedback current that lands the actuator mid-range.
    ladders = {}
    for ic in args.input_currents:
        row = {}
        for fc in args.feedback_currents:
            row[fc] = rec('A_feedback_ladder',
                          observe(brain, blank, groups, args.ticks, reset,
                                  stimulation=[(lplc4, ic), (fb, fc)]),
                          input_current=ic, feedback_current=fc, depth=None)
        ladders[ic] = row

    # Stage B -- the discretion test, inside the unsaturated band only.
    bands = {ic: [fc for fc, r in row.items() if 0. < r['dlm_flap_fraction'] < 1.]
             for ic, row in ladders.items()}
    stage_b = {}
    for ic, fcs in bands.items():
        for fc in fcs:
            series = [rec('B_cue_in_band',
                          observe(brain, blank, groups, args.ticks, reset,
                                  stimulation=[(lplc4, ic), (fb, fc)]),
                          input_current=ic, feedback_current=fc, depth=None)]
            for d in args.depths:
                frame, radius = looming(d, 'upper')
                series.append(rec('B_cue_in_band',
                                  observe(brain, frame, groups, args.ticks, reset,
                                          stimulation=[(lplc4, ic), (fb, fc)]),
                                  input_current=ic, feedback_current=fc, depth=d,
                                  radius=round(radius, 2)))
            stage_b[f'{ic}_{fc}'] = series

    # Stage C -- size-matched random feedback in this configuration.
    stage_c = {}
    for ic, fcs in bands.items():
        for fc in fcs[:2]:
            for draw in range(2):
                cells = rng.choice(control_pool, len(fb), replace=False).astype(np.int32)
                stage_c[f'{ic}_{fc}_{draw}'] = rec('C_random_feedback',
                    observe(brain, blank, groups, args.ticks, reset,
                            stimulation=[(lplc4, ic), (cells, fc)]),
                    input_current=ic, feedback_current=fc, depth=None,
                    feedback=f'random_vnc_{draw}')

    def depth_trend(series):
        d = [0.] + args.depths
        dlm = [r['dlm_total'] for r in series]
        flap = [r['dlm_flap_fraction'] for r in series]
        corr = float(np.corrcoef(d, dlm)[0, 1]) if len(set(dlm)) > 1 else None
        return {'depths': d, 'dlm_total': dlm, 'flap_fraction': flap,
                'dlm_range_pct': round(100 * (max(dlm) - min(dlm)) / max(1, np.mean(dlm)), 2),
                'corr_dlm_vs_depth': round(corr, 3) if corr is not None else None,
                'flap_varies': len(set(flap)) > 1,
                'flap_range': [min(flap), max(flap)]}

    summary = {'run_id': run_id, 'experiment_class': 'E-VPN-FB',
        'finished': datetime.now(timezone.utc).isoformat(),
        'feedback_ladder': {str(ic): {str(fc): {k: r[k] for k in
                            ('descending_total', 'wing_muscle_total', 'dlm_total',
                             'dlm_flap_fraction')} for fc, r in row.items()}
                            for ic, row in ladders.items()},
        'unsaturated_bands': {str(ic): v for ic, v in bands.items()},
        'cue_in_band': {k: depth_trend(v) for k, v in stage_b.items()},
        'random_feedback_control': {k: {kk: r[kk] for kk in
                                    ('dlm_total', 'dlm_flap_fraction', 'wing_muscle_total')}
                                    for k, r in stage_c.items()}}
    log.write({'record': 'summary', **summary}); log.close()
    Path(args.summary).write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'bands': {str(k): v for k, v in bands.items()}}))


if __name__ == '__main__':
    main()
