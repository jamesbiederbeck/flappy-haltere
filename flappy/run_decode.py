"""Experiment class E-DECODE: put the flap rate in the playable range and play.

E-HOLD established the target the whole sensory line was missing. The game has
exactly one altitude-holding flap rate, 1/19 = 0.053, because a flap sets
vertical velocity to -9 instead of adding to it. Every configuration ever run
here sat between 0.48 and 0.99, so the bird left through the top of the screen
within about 50 ticks and no pipe was reachable.

The cause is the decoder, not the connectome. `FlapControls` fired a flap
whenever any DLM cell spiked in a tick, and the pool spikes on nearly every
tick, so the button was effectively held down. `FlapControls(threshold=T)`
integrates instead: sum DLM spikes, fire and carry the remainder when the total
crosses T. Flap fraction becomes about R/T for a DLM rate of R, which both
lands in the playable range and varies with R rather than saturating.

This sweeps T with the real brain and the real game in the loop, and counts
pipes. Frozen weights, GPU.
"""
import argparse, json, time, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.vision.retina import BilinearLuminance
from flappy.circuit import haltere_afferents, haltere_current_for_velocity, wing_motor_readouts
from flappy.controls import FlapControls
from flappy.dlm_pair_sweep import Log
from flappy.game import FPS, Game

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = [1, 60, 120, 240, 360, 480, 570, 720, 960, 1440]


def lamina_map(brain):
    """Which photoreceptors reach each lamina cell, from the CSR adjacency.
    Driving the lamina directly bypasses the photoreceptor transfer function,
    which compresses a large luminance change into a few percent of current."""
    import collections
    pos = {int(i): k for k, i in enumerate(np.asarray(brain.retina))}
    inc = collections.defaultdict(list)
    for i in pos:
        for e in range(int(brain.ptr[i]), int(brain.ptr[i + 1])):
            inc[int(brain.post[e])].append(pos[i])
    lam = [j for j in (int(x) for x in np.asarray(brain.lamina)) if j in inc]
    per = np.array([len(inc[j]) for j in lam], dtype=np.int64)
    flat = np.concatenate([np.array(inc[j], dtype=np.int64) for j in lam])
    return (np.array(lam, dtype=np.int32), flat,
            np.concatenate([[0], np.cumsum(per)]), per)


def arm(brain, haltere, readouts, threshold, ticks, seed, gain, no_pipes,
        lamina=None, inject=0., reference=0.53, scale=0.3):
    controls = FlapControls(readouts, threshold=threshold)
    game = Game(seed=seed, no_pipes=no_pipes)
    retina = BilinearLuminance()
    duration_ms = 1000 / FPS
    flaps = episodes = dlm = 0
    heights, lengths, length = [], [], 0
    for _ in range(ticks):
        obs = game.observation()
        if obs['finished']:
            episodes += 1; lengths.append(length); length = 0
            game.new_episode(); obs = game.observation()
        light = retina.sample(game.pixels(), brain.uv)
        current = haltere_current_for_velocity(obs['y_velocity'], m=gain) if gain else 0.
        stim = [(haltere, current)] if current > 0 else []
        if lamina is not None and inject:
            cells, flat, offsets, per = lamina
            mean_lum = np.add.reduceat(np.asarray(light)[flat], offsets[:-1]) / per
            stim = stim + [(cells, (inject * (mean_lum - reference) / scale).astype(np.float32))]
        counts, _ = brain.step(light, duration_ms, stimulation=stim or None)
        action = controls.decode(counts, duration_ms / 1000)
        dlm += action['flap_spikes']; flaps += int(action['flap'])
        heights.append(obs['y']); length += 1
        game.act(action['flap'])
    lengths.append(length)
    final = game.observation()
    out = {'threshold': threshold, 'seed': seed, 'ticks': ticks,
           'flaps': flaps, 'flap_fraction': round(flaps / ticks, 4),
           'dlm_spikes': dlm, 'dlm_per_tick': round(dlm / ticks, 2),
           'episodes': episodes, 'longest_episode': int(max(lengths)),
           'mean_height': round(float(np.mean(heights)), 1),
           'pipes_cleared': int(game.pipes_cleared), 'pipe_strikes': int(game.pipe_strikes),
           'best_score': int(final['score'])}
    game.close()
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--thresholds', type=float, nargs='+', default=THRESHOLDS)
    p.add_argument('--ticks', type=int, default=600)
    p.add_argument('--seed', type=int, default=41027)
    p.add_argument('--haltere-gain', type=float, default=1.75)
    p.add_argument('--no-pipes', action='store_true')
    p.add_argument('--inject-lamina', type=float, default=0.,
                   help='Drive the lamina directly at this peak current, from the '
                        'mean luminance of each cell\'s own presynaptic '
                        'photoreceptors, instead of relying on the photoreceptor '
                        'transfer function to carry the picture.')
    p.add_argument('--lamina-reference', type=float, default=0.53)
    p.add_argument('--lamina-scale', type=float, default=0.3)
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_decode/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_decode/summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)
    haltere = haltere_afferents(brain)
    readouts = wing_motor_readouts(brain)
    lamina = lamina_map(brain) if args.inject_lamina else None
    run_id = str(uuid.uuid4())

    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-DECODE',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'seed': args.seed, 'haltere_gain': args.haltere_gain,
        'no_pipes': args.no_pipes, 'thresholds': args.thresholds,
        'inject_lamina': args.inject_lamina,
        'hover_flap_fraction': round(1 / 19, 4),
        'doc': 'docs/sensory-encoding-experiments.md#class-e-decode'})

    rows = []
    for t in args.thresholds:
        started = time.perf_counter()
        # threshold 1 reproduces the original any-spike decoder closely enough
        # to serve as its control, since a tick with any DLM spike crosses it.
        row = arm(brain, haltere, readouts, None if t <= 1 else t,
                  args.ticks, args.seed, args.haltere_gain, args.no_pipes,
                  lamina=lamina, inject=args.inject_lamina,
                  reference=args.lamina_reference, scale=args.lamina_scale)
        row.update({'record': 'arm', 'run_id': run_id, 'threshold': t,
                    'decoder': 'any-spike' if t <= 1 else 'integrating',
                    'wall_seconds': round(time.perf_counter() - started, 1)})
        rows.append(row); log.write(row)
        print(json.dumps({k: row[k] for k in ('threshold', 'flap_fraction', 'dlm_per_tick',
              'episodes', 'longest_episode', 'mean_height', 'pipes_cleared')}), flush=True)

    best = max(rows, key=lambda r: (r['pipes_cleared'], r['longest_episode']))
    summary = {'run_id': run_id, 'experiment_class': 'E-DECODE',
        'finished': datetime.now(timezone.utc).isoformat(), 'ticks': args.ticks,
        'seed': args.seed, 'haltere_gain': args.haltere_gain, 'no_pipes': args.no_pipes,
        'hover_flap_fraction': round(1 / 19, 4), 'best': best, 'arms': rows}
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'arms'}})
    log.close()
    out = Path(args.summary); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'best': best}))


if __name__ == '__main__':
    main()
