"""Experiment class E-HOLD: what flap rate does the game actually need?

Every class so far measured what the connectome can be made to do and never
asked what the game wants. That is backwards, and it left an obvious question
unasked: the harness has never cleared a pipe, but nobody has established what
flap rate clearing one would require.

The physics are fixed by flappy_bird_gymnasium: gravity adds 1 px/tick to
downward velocity, a flap *sets* velocity to -9 rather than adding to it, and
velocity is clipped to [-8, 10]. Because a flap resets rather than accumulates,
flap rate maps to a vertical drift rate, and there is exactly one rate that
holds altitude.

This sweeps flap rate against the real environment with no connectome in the
loop, both as a fixed period (flap every Nth tick) and as a Bernoulli process
at probability p, since the decoder produces something closer to the latter.
What comes out is the target band the neural side has to hit, which every
earlier class was optimising without.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from flappy.dlm_pair_sweep import Log
from flappy.game import Game

ROOT = Path(__file__).resolve().parents[1]


def episode(seed, decide, ticks, no_pipes=False):
    game = Game(seed=seed, no_pipes=no_pipes)
    heights, flaps = [], 0
    for tick in range(ticks):
        flap = decide(tick)
        flaps += int(bool(flap))
        game.act(flap)
        s = game.observation()
        heights.append(s['y'])
        if s['finished']: break
    return {'ticks': tick + 1, 'flaps': flaps, 'flap_fraction': round(flaps / (tick + 1), 4),
            'pipes_cleared': int(game.pipes_cleared), 'pipe_strikes': int(game.pipe_strikes),
            'mean_height': round(float(np.mean(heights)), 1),
            'drift': round(float(heights[-1] - heights[0]), 1)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ticks', type=int, default=2000)
    p.add_argument('--seeds', type=int, nargs='+', default=[41027, 7, 99])
    p.add_argument('--periods', type=int, nargs='+',
                   default=[1, 2, 3, 4, 6, 8, 12, 16, 18, 19, 20, 22, 26, 32, 48])
    p.add_argument('--probabilities', type=float, nargs='+',
                   default=[.02, .03, .04, .05, .06, .08, .1, .15, .25, .5, .75, .95])
    p.add_argument('--no-pipes', action='store_true',
                   help='Park the pipes so only the ceiling and ground can end an episode, '
                        'which isolates altitude control from pipe avoidance')
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_hold/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_hold/summary.json'))
    args = p.parse_args()

    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-HOLD',
        'started': datetime.now(timezone.utc).isoformat(), 'ticks': args.ticks,
        'seeds': args.seeds, 'no_pipes': args.no_pipes, 'periods': args.periods, 'probabilities': args.probabilities,
        'doc': 'docs/sensory-encoding-experiments.md#class-e-hold'})

    rows = []
    def record(kind, value, results):
        row = {'record': 'arm', 'run_id': run_id, 'kind': kind, 'value': value,
               'at': datetime.now(timezone.utc).isoformat(),
               'flap_fraction': round(float(np.mean([r['flap_fraction'] for r in results])), 4),
               'mean_ticks': round(float(np.mean([r['ticks'] for r in results])), 1),
               'max_ticks': int(max(r['ticks'] for r in results)),
               'pipes_cleared': int(sum(r['pipes_cleared'] for r in results)),
               'pipe_strikes': int(sum(r['pipe_strikes'] for r in results)),
               'mean_height': round(float(np.mean([r['mean_height'] for r in results])), 1),
               'mean_drift': round(float(np.mean([r['drift'] for r in results])), 1)}
        rows.append(row); log.write(row)
        print(json.dumps({k: row[k] for k in ('kind', 'value', 'flap_fraction',
              'mean_ticks', 'pipes_cleared', 'mean_drift')}), flush=True)

    for n in args.periods:
        record('period', n, [episode(s, lambda t, n=n: t % n == 0, args.ticks, args.no_pipes)
                             for s in args.seeds])
    for q in args.probabilities:
        out = []
        for s in args.seeds:
            rng = np.random.default_rng(s)
            out.append(episode(s, lambda t, rng=rng, q=q: rng.random() < q, args.ticks, args.no_pipes))
        record('bernoulli', q, out)

    best = max(rows, key=lambda r: (r['pipes_cleared'], r['mean_ticks']))
    summary = {'run_id': run_id, 'experiment_class': 'E-HOLD',
        'finished': datetime.now(timezone.utc).isoformat(), 'ticks': args.ticks,
        'seeds': args.seeds, 'best': best, 'arms': rows}
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'arms'}})
    log.close()
    out = Path(args.summary); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'best': best}))


if __name__ == '__main__':
    main()
