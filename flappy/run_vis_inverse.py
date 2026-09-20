"""Experiment class E-VIS-INV, stage 1: which visual population is worth driving?

The haltere inverse-dynamics work (flappy/inverse_*.py) learned a map from a
desired wing-muscle response to the haltere stimulation that produces it,
using the simulation as the oracle. This extends that idea to the visual
subsystem, with a deliberately lower bar: the goal is not to model fly vision,
it is to find visual inputs worth driving.

Motivation, from the experiments that precede this. Every sensory class so far
drove LPLC4, chosen because a topology analysis ranked it first. E-BAND then
showed LPLC4 is a switch, not a knob -- between currents 6.75 and 7.00 the
descending output rises 65-fold and DLM 273-fold, with nothing in between and
saturation above. Three regime fixes (longer integration, non-threshold
readout, sub-threshold band) all failed. So the drive point has to change, and
nobody has actually searched the alternatives: 77 visual projection types are
fully reconstructed here and only one has ever been driven.

Stage 1 is a forward screen that scores every candidate on the three properties
that make a drive point usable, rather than on how many spikes it produces:

  reach        -- does it move the wing motor pool at all?
  gradedness   -- how many currents put the actuator strictly between silent
                  and saturated? LPLC4 scores near zero here by construction.
  step_ratio   -- largest single-step jump in DLM as a fraction of its range.
                  A switch scores ~1.0; a knob scores low.

It also stores each population's descending-neuron response vector, which is
the training data stage 2 would need to invert (desired response -> which
cells to drive), and which answers a separate question: whether two populations
are distinguishable downstream, i.e. whether several channels could coexist.

Frozen weights, GPU. Runs alongside CPU learning work without contending --
MemoryBrain is a NativeBrain subclass and there is no GPU plasticity path.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from connectome_sim.physiology.common import annotations, digest
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.sensory_probe import base_frame, observe, readouts

ROOT = Path(__file__).resolve().parents[1]
VPN_PATTERN = r'^(LC\d|LPLC|LLPC|LT\d|LPT|MeTu|aMe)'


def candidates(brain, minimum_cells=8):
    """Visual projection types that leave the optic lobe, big enough to drive
    and with no unreconstructed cells. Zero-out-degree cells are excluded
    rather than averaged over -- a population that looks silent because it is
    untraced would score as a failed drive point and poison the ranking."""
    a = annotations(brain.ids); t = a.type.fillna('')
    idx = np.flatnonzero(t.str.match(VPN_PATTERN).to_numpy())
    out = []
    for ty, part in pd.DataFrame({'type': t.iloc[idx].to_numpy(), 'i': idx}).groupby('type'):
        cells = part.i.to_numpy().astype(np.int32)
        if len(cells) < minimum_cells: continue
        if any(brain.ptr[i + 1] == brain.ptr[i] for i in cells): continue
        out.append({'type': str(ty), 'cells': cells, 'n': len(cells)})
    return sorted(out, key=lambda g: -g['n'])


def score(currents, dlm, flap):
    rng = max(dlm) - min(dlm)
    steps = [abs(b - a) for a, b in zip(dlm, dlm[1:])]
    return {'reaches': max(dlm) > 0,
            'graded_currents': int(sum(1 for f in flap if 0. < f < 1.)),
            'step_ratio': round(max(steps) / rng, 4) if rng > 0 else None,
            'dlm_max': max(dlm), 'flap_max': max(flap)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--ticks', type=int, default=30)
    p.add_argument('--currents', type=float, nargs='+', default=[4., 6., 8., 12., 16.])
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_vis_inverse/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_vis_inverse/screen_summary.json'))
    p.add_argument('--dataset', default=str(ROOT / 'outputs/flappy_vis_inverse/screen.npz'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain)
    cands = candidates(brain)
    blank = base_frame()
    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-VIS-INV', 'stage': 1,
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'currents': args.currents, 'graph_sha256': digest(brain.weight),
        'candidate_types': len(cands), 'candidate_cells': int(sum(c['n'] for c in cands)),
        'vpn_pattern': VPN_PATTERN,
        'doc': 'docs/sensory-encoding-experiments.md#class-e-vis-inv'})

    results, vectors = [], []
    for gi, cand in enumerate(cands):
        dlm, flap, desc = [], [], []
        for c in args.currents:
            r = observe(brain, blank, groups, args.ticks, reset,
                        stimulation=[(cand['cells'], c)])
            log.write({'record': 'trial', 'run_id': run_id, 'experiment_class': 'E-VIS-INV',
                       'stage': 'screen', 'at': datetime.now(timezone.utc).isoformat(),
                       'population': cand['type'], 'n_cells': cand['n'], 'current': c,
                       **{k: v for k, v in r.items() if k != 'descending_vector'}})
            dlm.append(r['dlm_total']); flap.append(r['dlm_flap_fraction'])
            desc.append(r['descending_vector'])
        s = score(args.currents, dlm, flap)
        row = {'population': cand['type'], 'n_cells': cand['n'],
               'dlm_total': dlm, 'flap_fraction': flap, **s}
        results.append(row); vectors.append(desc)
        log.write({'record': 'population', 'run_id': run_id, **row})
        print(json.dumps({'i': gi, **{k: row[k] for k in
              ('population', 'n_cells', 'reaches', 'graded_currents',
               'step_ratio', 'dlm_max')}}), flush=True)

    reaching = [r for r in results if r['reaches']]
    knobs = sorted([r for r in reaching if r['graded_currents'] >= 2 and
                    (r['step_ratio'] or 1.) < .8],
                   key=lambda r: (-r['graded_currents'], r['step_ratio'] or 1.))
    summary = {'run_id': run_id, 'experiment_class': 'E-VIS-INV', 'stage': 1,
        'finished': datetime.now(timezone.utc).isoformat(), 'ticks': args.ticks,
        'currents': args.currents, 'candidates': len(results),
        'reaching_motor_pool': len(reaching),
        'knob_like': [{k: r[k] for k in ('population', 'n_cells', 'graded_currents',
                                         'step_ratio', 'dlm_max', 'flap_fraction')}
                      for r in knobs],
        'all': results,
        'note': 'A screen at 30 ticks; flap resolution is 0.033, so single-tick '
                'gradedness is not evidence. Shortlisted populations need re-running longer.'}
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'all'}})
    log.close()
    out = Path(args.summary); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    np.savez(args.dataset, descending=np.array(vectors, dtype=np.int32),
             populations=np.array([r['population'] for r in results]),
             n_cells=np.array([r['n_cells'] for r in results]),
             currents=np.array(args.currents), ticks=args.ticks)
    print(json.dumps({'status': 'done', 'candidates': len(results),
                      'reaching': len(reaching), 'knob_like': len(knobs)}))


if __name__ == '__main__':
    main()
