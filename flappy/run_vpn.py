"""Executes experiment class E-VPN: drive the fly's own looming-detector
population and ask whether what it SEES changes what the wings do.

E-LOOM established that a visual cue is encoded (6.2% monotone modulation of
network activity) but never reaches the motor pools -- photoreceptors sit 5
hops from DLM carrying 0.0001 of its cumulative anatomical drive. The
discretion analysis found the leverage point two hops out: LPLC4, 97 looming
VPNs, 95 of which synapse onto DNp31, which synapses directly onto DLM.

The test that separates integration from reflex is stage B below. Stage A
just finds a working current. Stage B holds that current FIXED and changes
only the picture. If DLM output moves, the flap is contingent on what the
fly sees, and the injected current is a gain knob rather than the cause. If
DLM output is identical across every picture, driving LPLC4 is the haltere
joystick moved two synapses earlier, and should be reported as such.
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
    p.add_argument('--currents', type=float, nargs='+', default=[4., 6., 8., 10., 12., 16., 20.])
    p.add_argument('--depths', type=float, nargs='+', default=[8., 16., 32., 64., 120.])
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_sensory/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_sensory/vpn_summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain)
    a = annotations(brain.ids); t = a.type.fillna('')
    lplc4 = np.flatnonzero(t.eq('LPLC4')).astype(np.int32)
    if not len(lplc4): raise ValueError('No LPLC4 cells in this graph')
    # Size-matched control pool: other visual projection neurons that are not
    # LPLC4, so a positive result cannot be "injecting into 97 visual cells".
    vpn = np.flatnonzero(a.superclass.fillna('').eq('cb_intrinsic').to_numpy()
                         & t.str.startswith('LC').to_numpy()).astype(np.int32)
    control_pool = np.setdiff1d(vpn, lplc4)
    rng = np.random.default_rng(0)

    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-VPN',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'currents': args.currents, 'depths': args.depths,
        'graph_sha256': digest(brain.weight), 'lplc4_cells': int(len(lplc4)),
        'control_pool_cells': int(len(control_pool)),
        'readout_cells': {k: int(len(v)) for k, v in groups.items()},
        'doc': 'docs/sensory-encoding-experiments.md#class-e-vpn'})

    def rec(stage, r, **f):
        log.write({'record': 'trial', 'run_id': run_id, 'experiment_class': 'E-VPN',
                   'stage': stage, 'at': datetime.now(timezone.utc).isoformat(), **f, **r})
        print(json.dumps({'stage': stage, **f, 'net': r['network_spikes'],
                          'desc': r['descending_total'], 'wm': r['wing_muscle_total'],
                          'dlm': r['dlm_total'], 'flap': r.get('dlm_flap_fraction')}), flush=True)
        return r

    blank = base_frame()
    # Stage A -- current ladder on a blank frame. Finds whether LPLC4 reaches
    # DLM at all, and at what current, with no cue present.
    ladder = {}
    for c in args.currents:
        r = rec('A_current_ladder', observe(brain, blank, groups, args.ticks, reset,
                                            stimulation=[(lplc4, c)]),
                population='LPLC4', current=c, depth=None)
        ladder[c] = r

    # Stage B -- the discretion test. Current held FIXED, only the picture changes.
    working = [c for c, r in ladder.items() if r['dlm_total'] > 0]
    stage_b = {}
    for c in working:
        series = [rec('B_cue_modulation',
                      observe(brain, blank, groups, args.ticks, reset, stimulation=[(lplc4, c)]),
                      population='LPLC4', current=c, depth=None)]
        for d in args.depths:
            frame, radius = looming(d, 'upper')
            series.append(rec('B_cue_modulation',
                              observe(brain, frame, groups, args.ticks, reset,
                                      stimulation=[(lplc4, c)]),
                              population='LPLC4', current=c, depth=d, radius=round(radius, 2)))
        stage_b[c] = series

    # Stage C -- size-matched control. Same cell count, same currents, other LC types.
    control = {}
    for c in working:
        cells = rng.choice(control_pool, min(len(lplc4), len(control_pool)), replace=False).astype(np.int32)
        control[c] = rec('C_size_matched_control',
                         observe(brain, blank, groups, args.ticks, reset, stimulation=[(cells, c)]),
                         population='random_LC', current=c, depth=None)

    summary = {'run_id': run_id, 'experiment_class': 'E-VPN',
               'finished': datetime.now(timezone.utc).isoformat(),
               'lplc4_cells': int(len(lplc4)),
               'ladder': {str(c): {k: r[k] for k in ('network_spikes', 'descending_total',
                                                     'wing_muscle_total', 'dlm_total',
                                                     'dlm_flap_fraction')}
                          for c, r in ladder.items()},
               'working_currents': working,
               'cue_modulation': {str(c): {'depths': [None] + args.depths,
                                           'dlm_total': [r['dlm_total'] for r in s],
                                           'flap_fraction': [r['dlm_flap_fraction'] for r in s],
                                           'wing_muscle': [r['wing_muscle_total'] for r in s],
                                           'descending': [r['descending_total'] for r in s],
                                           'depends_on_picture': len({r['dlm_total'] for r in s}) > 1}
                                  for c, s in stage_b.items()},
               'size_matched_control': {str(c): {k: r[k] for k in
                                        ('dlm_total', 'wing_muscle_total', 'descending_total')}
                                        for c, r in control.items()}}
    log.write({'record': 'summary', **summary}); log.close()
    Path(args.summary).write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'working_currents': working}))


if __name__ == '__main__':
    main()
