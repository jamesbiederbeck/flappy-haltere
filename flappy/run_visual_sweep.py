"""Experiment class E-VISUAL-SWEEP: characterizes connectome behavior across
different game-to-connectome VISUAL PROJECTION SCHEMES, each at several
intensities, against the same underlying picture (a looming obstacle cue at
`--depths`, via sensory_probe.looming).

An earlier version of this script picked one neuron population (LoVP92) and
ran an E-VPN-style current ladder on it. That was the wrong shape for the
question and the wrong population: LoVP92's own `synonyms` annotation cites
Cachero 2010 / Yu 2010, both fruitless/doublesex courtship-circuit papers
identifying pIP-b/pIP8, a male P1-cluster interneuron -- not a visual cell.
Its `visual_projection` superclass label in this graph is misleading; do not
trust that column alone to mean "this cell sees." LPLC4 (used below, and in
run_vpn.py) carries standard fly visual-system nomenclature and no such
contradicting cross-reference.

Three schemes, all driven by the same rendered frame:

  photoreceptor  Real vision: the frame goes through the measured
                 photoreceptor transfer function (connectome_sim.photoreceptor,
                 already corrected for the connectome_sim/flappy_bird_env
                 fluid-density-style unit mismatches documented elsewhere in
                 this project). "Intensity" here is `lamina_bias`, the
                 photoreceptor->lamina gain `brain.step` already exposes as a
                 real, undocumented-until-now dial -- not an injected
                 current, a property of the existing pathway.
  lamina_direct  Bypasses the photoreceptor transfer function: each lamina
                 cell's own mean upstream luminance drives an injected
                 current directly into it (flappy.run_decode.lamina_map,
                 reused here rather than reimplemented). "Intensity" is the
                 injected current's peak scale.
  vpn_current    Bypasses vision entirely: a fixed-size synthetic current,
                 gated only by the picture's *interpretation* as a depth
                 value (not the picture itself), injected into LPLC4 --
                 the engineered-joystick end of the spectrum, included so the
                 other two schemes have something to be compared against.
                 "Intensity" is the injected current amplitude.

None of these is "the" correct way to get game state into the connectome;
that is the point of running all three side by side rather than picking one.
Frozen weights throughout.
"""
import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import annotations, digest
from flappy.agent import resolve_neurons
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.run_decode import lamina_map
from flappy.sensory_probe import base_frame, looming, observe, readouts

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vpn-target', default='LPLC4',
                   help='flappy.agent.resolve_neurons spec for the vpn_current '
                        "scheme's population, e.g. 'LPLC4', 'LC17', 'LC4'")
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--dataset', default='malecns_v1')
    p.add_argument('--ticks', type=int, default=15)
    p.add_argument('--depths', type=float, nargs='+', default=[8., 16., 32., 64., 120.])
    p.add_argument('--field', choices=['upper', 'lower'], default='upper')
    p.add_argument('--lamina-biases', type=float, nargs='+', default=[6., 12., 24., 48.])
    p.add_argument('--lamina-currents', type=float, nargs='+', default=[2., 4., 8.])
    p.add_argument('--lamina-reference', type=float, default=.53)
    p.add_argument('--lamina-scale', type=float, default=.3)
    p.add_argument('--vpn-currents', type=float, nargs='+', default=[8., 12., 16., 20.])
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_sensory/visual_sweep_trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_sensory/visual_sweep_summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim' / args.dataset / 'graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain)
    lamina = lamina_map(brain)
    vpn_idx = resolve_neurons(brain, args.vpn_target)

    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-VISUAL-SWEEP',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'schemes': ['photoreceptor', 'lamina_direct', 'vpn_current'],
        'vpn_target': args.vpn_target, 'vpn_target_cells': int(len(vpn_idx)),
        'ticks': args.ticks, 'depths': args.depths, 'field': args.field,
        'graph_sha256': digest(brain.weight),
        'readout_cells': {k: int(len(v)) for k, v in groups.items()},
        'doc': 'docs/sensory-encoding-experiments.md#class-e-vpn (generalised across schemes)'})

    def rec(scheme, intensity, depth, r, **f):
        row = {'scheme': scheme, 'intensity': intensity, 'depth': depth, **r}
        log.write({'record': 'trial', 'run_id': run_id, 'experiment_class': 'E-VISUAL-SWEEP',
                   'at': datetime.now(timezone.utc).isoformat(), **f, **row})
        print(json.dumps({'scheme': scheme, 'intensity': intensity, 'depth': depth,
                          'net': r['network_spikes'], 'desc': r['descending_total'],
                          'wm': r['wing_muscle_total'], 'dlm': r['dlm_total'],
                          'flap': r.get('dlm_flap_fraction')}), flush=True)
        return row

    def proximity(depth, near=8.):
        """1 at the closest depth this sweep uses, falling toward 0 as depth
        grows, 0 for the blank/no-obstacle control -- the only thing that
        connects vpn_current's injected current to the picture at all, since
        that scheme otherwise never looks at a single pixel."""
        if depth is None: return 0.
        return float(np.clip(near / max(depth, near), 0., 1.))

    blank = base_frame()
    depths_with_blank = [None] + args.depths

    def frame_for(depth):
        return blank if depth is None else looming(depth, args.field)[0]

    results = {'photoreceptor': [], 'lamina_direct': [], 'vpn_current': []}

    # Scheme A -- real photoreceptor vision, no injected current, sweeping
    # the pathway's own lamina_bias gain.
    for bias in args.lamina_biases:
        for depth in depths_with_blank:
            r = observe(brain, frame_for(depth), groups, args.ticks, reset, lamina_bias=bias)
            results['photoreceptor'].append(rec('photoreceptor', bias, depth, r))

    # Scheme B -- bypass the photoreceptor transfer function, inject each
    # lamina cell's own upstream mean luminance directly as current. Needs
    # the same photoreceptor sampling `observe` uses internally, computed
    # here directly rather than reaching into observe's internals.
    from connectome_sim.photoreceptor import retinal_samples
    cells, flat, offsets, per = lamina
    for current in args.lamina_currents:
        for depth in depths_with_blank:
            frame = frame_for(depth)
            lum = retinal_samples(frame, brain.uv)
            mean_lum = np.add.reduceat(np.asarray(lum)[flat], offsets[:-1]) / per
            inject = (current * (mean_lum - args.lamina_reference) / args.lamina_scale).astype(np.float32)
            r = observe(brain, frame, groups, args.ticks, reset, stimulation=(cells, inject))
            results['lamina_direct'].append(rec('lamina_direct', current, depth, r))

    # Scheme C -- bypass vision entirely: current into a named VPN
    # population, scaled by `proximity(depth)` -- the only sense in which
    # this scheme "sees" anything; the rendered frame itself is never
    # sampled. 0 at the blank/no-obstacle control, matching what "nothing
    # there" means in the other two schemes.
    for current in args.vpn_currents:
        for depth in depths_with_blank:
            scaled = current * proximity(depth)
            stim = (vpn_idx, scaled) if scaled > 0 else None
            r = observe(brain, blank, groups, args.ticks, reset, stimulation=stim)
            results['vpn_current'].append(rec('vpn_current', current, depth, r))

    def summarize(rows):
        by_intensity = {}
        for row in rows:
            by_intensity.setdefault(row['intensity'], []).append(row)
        out = {}
        for intensity, rs in by_intensity.items():
            dlm = [r['dlm_total'] for r in rs]
            out[str(intensity)] = {
                'depths': [r['depth'] for r in rs], 'dlm_total': dlm,
                'flap_fraction': [r.get('dlm_flap_fraction') for r in rs],
                'depends_on_picture': len(set(dlm)) > 1}
        return out

    summary = {'run_id': run_id, 'experiment_class': 'E-VISUAL-SWEEP',
               'finished': datetime.now(timezone.utc).isoformat(),
               'vpn_target': args.vpn_target, 'vpn_target_cells': int(len(vpn_idx)),
               'schemes': {name: summarize(rows) for name, rows in results.items()}}
    log.write({'record': 'summary', **summary}); log.close()
    Path(args.summary).write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'schemes': list(results)}))


if __name__ == '__main__':
    main()
