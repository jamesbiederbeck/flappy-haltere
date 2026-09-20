"""Experiment class E-BAND: is there a sub-threshold drive band at LPLC4?

E-VPN stage A stepped LPLC4 current 4, 6, 8, 10, 12, 16, 20 and found a wall:
nothing at all at 6 (descending 70, wing muscle 0, DLM 0), full motor output
at 8 (descending 3,253, wing muscle 1,364, DLM 552, flap 0.93). Nothing in
between was tested.

That gap matters because E-VPN-FB only reached an unsaturated actuator by
adding IN06B077 as a second channel, and E-REGIME then showed the resulting
band is a narrow size-tuning peak with discriminability flat at ~2.1. If a
current between 6 and 8 opens the bridge *partially* on its own, there is an
unsaturated regime that needs no feedback channel at all, and the cue can be
tested there without the second injection confounding it.

If there is no such current -- if the threshold is genuinely a step -- then
the last cheap fix from the E-VPN-FB list is exhausted and the conclusion
becomes that the drive point has to change rather than the regime.

Frozen weights, GPU backend. This runs alongside CPU learning runs without
contending: MemoryBrain is a NativeBrain subclass and there is no GPU
plasticity path, so learning work never touches the card.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import annotations, digest
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.sensory_probe import base_frame, disc, observe, readouts

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--ticks', type=int, default=60)
    p.add_argument('--currents', type=float, nargs='+',
                   default=[6.0, 6.25, 6.5, 6.75, 7.0, 7.25, 7.5, 7.75, 8.0])
    p.add_argument('--radii', type=float, nargs='+', default=[0., 16., 24., 32., 61., 100.])
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_sensory/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_sensory/band_summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain); a = annotations(brain.ids); t = a.type.fillna('')
    lplc4 = np.flatnonzero(t.eq('LPLC4')).astype(np.int32)
    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-BAND',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'currents': args.currents, 'radii': args.radii,
        'graph_sha256': digest(brain.weight), 'lplc4_cells': int(len(lplc4)),
        'doc': 'docs/sensory-encoding-experiments.md#class-e-band'})

    def rec(stage, r, **f):
        log.write({'record': 'trial', 'run_id': run_id, 'experiment_class': 'E-BAND',
                   'stage': stage, 'at': datetime.now(timezone.utc).isoformat(), **f, **r})
        print(json.dumps({'stage': stage, **f, 'desc': r['descending_total'],
                          'wm': r['wing_muscle_total'], 'dlm': r['dlm_total'],
                          'flap': r['dlm_flap_fraction']}), flush=True)
        return r

    blank = base_frame()
    ladder = {}
    for c in args.currents:
        ladder[c] = rec('A_fine_ladder',
                        observe(brain, blank, groups, args.ticks, reset,
                                stimulation=[(lplc4, c)]),
                        current=c, radius=None)

    # A current is in-band if it moves the motor pool without pinning the
    # actuator -- silent and saturated are both outside.
    band = [c for c, r in ladder.items()
            if r['dlm_total'] > 0 and 0. < r['dlm_flap_fraction'] < 1.]
    cue = {}
    for c in band:
        series = []
        for radius in args.radii:
            frame = blank if radius == 0 else disc(radius, 'upper')[0]
            series.append(rec('B_cue_in_band',
                              observe(brain, frame, groups, args.ticks, reset,
                                      stimulation=[(lplc4, c)]),
                              current=c, radius=radius))
        flap = [r['dlm_flap_fraction'] for r in series]
        dlm = [r['dlm_total'] for r in series]
        cue[str(c)] = {'radii': args.radii, 'flap_fraction': flap, 'dlm_total': dlm,
                       'flap_varies': len(set(flap)) > 1,
                       'flap_span': round(max(flap) - min(flap), 4)}

    summary = {'run_id': run_id, 'experiment_class': 'E-BAND',
        'finished': datetime.now(timezone.utc).isoformat(), 'ticks': args.ticks,
        'ladder': {str(c): {k: r[k] for k in ('descending_total', 'wing_muscle_total',
                                              'dlm_total', 'dlm_flap_fraction')}
                   for c, r in ladder.items()},
        'band': band, 'band_exists': bool(band), 'cue_in_band': cue,
        'verdict': ('no_band_threshold_is_a_step' if not band else
                    'band_exists_without_feedback_channel')}
    log.write({'record': 'summary', **summary}); log.close()
    Path(args.summary).write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'verdict': summary['verdict'], 'band': band}))


if __name__ == '__main__':
    main()
