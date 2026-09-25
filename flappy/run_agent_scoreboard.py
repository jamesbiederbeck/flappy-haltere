"""Plays the ConnectomeAgent configurations already established elsewhere in
this repo through real Flappy Bird episodes and appends the results to
flappy_fly_scores.md, so flappy/agent.py's framework has one running,
human-readable scoreboard instead of only the one-off smoke checks it was
built with.

Not new agents: `any-spike` is flappy/play.py's original decoder and
`integrating T=560` is flappy/run_decode.py's best-known configuration
(README.md "Best known agent"), both re-expressed as ConnectomeAgent so they
share one play loop and one results table with anything built on the new
framework going forward.

Methodology note: run_decode.py's own `arm()` reports `game.pipes_cleared`
and `game.pipe_strikes` once, after the tick loop -- but `Game.new_episode()`
resets both counters to 0, so that call only reports the *last* (often still
in-progress) episode's count, not the run's total across every episode it
contained. At ~30 episodes per 2,000-tick run (see README's episode counts)
that under-reports substantially. This script instead accumulates both
counters at every episode boundary, so the totals here are not directly
comparable to run_decode.py's own printed numbers -- flagged rather than
silently reconciled, same stance as every other methodology change in this
repo's history (see README.md's "Two harness changes" note).

Run-to-run results are not identical even at a fixed seed on the GPU backend
(a cupy reduction-order effect, ~a few flaps per 600 ticks -- see README.md
and connectome-lab/CAVEATS.md). Quote a distribution over several seeds, not
a single run; `--seeds` defaults to more than one for exactly this reason.
"""
import argparse
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from flappy.agent import ConnectomeAgent, Wiring, OutputChannel
from flappy.circuit import haltere_current_for_velocity
from flappy.game import FPS, Game

ROOT = Path(__file__).resolve().parents[1]
SCOREBOARD = ROOT / 'flappy_fly_scores.md'
DEFAULT_LOG = ROOT / 'outputs/flappy_scoreboard/trials.jsonl'


def git_info(root):
    """(short sha, dirty) for `root`'s working tree, so a scoreboard row
    always says exactly what code produced it -- a plain HEAD sha is not
    enough on its own if the tree had uncommitted changes at run time."""
    try:
        sha = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=root,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(['git', 'status', '--porcelain'], cwd=root,
                                    capture_output=True, text=True, check=True).stdout.strip())
        return sha, dirty
    except Exception:
        return 'unknown', True


def agents(brain, haltere_gain=1.75, thresholds=(560.,), include_any_spike=True):
    """`brain` is shared across configurations -- callers must `agent.reset()`
    (done in `play()` below) between runs, since brain state carries.

    `any-spike` is flappy/play.py's original decoder, included by default for
    comparison but not worth spending long-tick-count runs on once it's been
    seen to fail (E-HOLD's saturated-button result, confirmed again in
    flappy_fly_scores.md's first block) -- pass `include_any_spike=False` to
    skip it. Each of `thresholds` is flappy/run_decode.py's integrating
    decoder at that T; 560 is README.md's best-known value, not the only one
    ever tried (see THRESHOLDS in run_decode.py) -- passing several lets a
    long run actually screen around it instead of re-confirming one point."""
    wiring = lambda: [Wiring('haltere', 'y_velocity',
                              lambda v: haltere_current_for_velocity(v, m=haltere_gain),
                              label='haltere<-y_velocity')]
    out = {}
    if include_any_spike:
        out['any-spike (play.py)'] = ConnectomeAgent(
            brain, wirings=wiring(),
            outputs=[OutputChannel('dlm', threshold=None, label='DLM')])
    for t in thresholds:
        out[f'integrating T={t:g}'] = ConnectomeAgent(
            brain, wirings=wiring(),
            outputs=[OutputChannel('dlm', threshold=t, label='DLM')])
    return out


def play(agent, ticks, seed):
    agent.reset()
    game = Game(seed=seed)
    duration_ms = 1000 / FPS
    flaps = total_pipes_cleared = total_pipe_strikes = episodes = 0
    lengths, length = [], 0
    best_score = 0
    for _ in range(ticks):
        obs = game.observation()
        if obs['finished']:
            # score, like pipes_cleared/pipe_strikes, resets in new_episode();
            # take the max across episode boundaries, not just whichever
            # episode happens to be live at the final tick.
            best_score = max(best_score, obs['score'])
            total_pipes_cleared += game.pipes_cleared
            total_pipe_strikes += game.pipe_strikes
            episodes += 1
            lengths.append(length); length = 0
            game.new_episode()
        r = agent.step(game, duration_ms)
        flaps += int(r['flap'])
        game.act(r['flap'])
        length += 1
    best_score = max(best_score, game.observation()['score'])
    total_pipes_cleared += game.pipes_cleared
    total_pipe_strikes += game.pipe_strikes
    lengths.append(length)
    game.close()
    return {'ticks': ticks, 'seed': seed, 'flaps': flaps,
            'flap_fraction': round(flaps / ticks, 4),
            'episodes': episodes + 1, 'longest_episode': max(lengths),
            'pipes_cleared': total_pipes_cleared, 'pipe_strikes': total_pipe_strikes,
            'best_score': int(best_score)}


def append_scoreboard(path, rows, backend, ticks, haltere_gain, started, command, sha, dirty):
    lines = []
    if not path.exists():
        lines += ['# Flappy Fly Scores', '',
                  'Appended by `flappy/run_agent_scoreboard.py`. Each block is one '
                  'invocation; scores across blocks are not comparable if `--ticks`, '
                  '`--backend` or `--haltere-gain` differ, and are never comparable to '
                  'run_decode.py\'s own printed `pipes_cleared` -- see that script\'s '
                  'module docstring for why this file accumulates across episode '
                  'boundaries instead. `git` is the flappy-haltere commit the row was run '
                  'against; `+dirty` means the working tree had uncommitted changes at run '
                  'time, so the exact code is not fully pinned by the sha alone.', '']
    dirty_tag = '+dirty' if dirty else ''
    lines += [f'## {started.isoformat()} -- backend={backend}, ticks={ticks}, '
              f'haltere_gain={haltere_gain}', '',
              f'Command: `{command}`', '', f'Git: `{sha}{dirty_tag}`', '',
              '| agent | seed | flap fraction | episodes | longest episode | '
              'pipes cleared | pipe strikes | best score |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['agent']} | {r['seed']} | {r['flap_fraction']} | "
                      f"{r['episodes']} | {r['longest_episode']} | {r['pipes_cleared']} | "
                      f"{r['pipe_strikes']} | {r['best_score']} |")
    lines.append('')
    with path.open('a') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--dataset', default='malecns_v1')
    p.add_argument('--ticks', type=int, default=2000)
    p.add_argument('--seeds', type=int, nargs='+', default=[41027, 99])
    p.add_argument('--haltere-gain', type=float, default=1.75)
    p.add_argument('--thresholds', type=float, nargs='+', default=[560.])
    p.add_argument('--no-any-spike', action='store_true',
                   help='Skip the any-spike (play.py) decoder -- already known to '
                        'saturate the button; not worth long-tick-count reruns.')
    p.add_argument('--log', default=str(DEFAULT_LOG))
    p.add_argument('--scoreboard', default=str(SCOREBOARD))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim' / args.dataset / 'graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    started = datetime.now(timezone.utc)
    log_path = Path(args.log); log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open('a')
    rows = []
    configs = agents(brain, args.haltere_gain, thresholds=args.thresholds,
                     include_any_spike=not args.no_any_spike)
    for name, agent in configs.items():
        for seed in args.seeds:
            t0 = time.perf_counter()
            result = play(agent, args.ticks, seed)
            result.update({'agent': name, 'backend': args.backend,
                            'haltere_gain': args.haltere_gain,
                            'wall_seconds': round(time.perf_counter() - t0, 1)})
            rows.append(result)
            log.write(json.dumps(result) + '\n'); log.flush()
            print(json.dumps({k: result[k] for k in
                  ('agent', 'seed', 'flap_fraction', 'episodes', 'longest_episode',
                   'pipes_cleared', 'best_score')}), flush=True)
    log.close()
    sha, dirty = git_info(ROOT)
    command = 'python -m flappy.run_agent_scoreboard ' + shlex.join(sys.argv[1:])
    append_scoreboard(Path(args.scoreboard), rows, args.backend, args.ticks,
                      args.haltere_gain, started, command, sha, dirty)
    print(json.dumps({'status': 'done', 'scoreboard': str(args.scoreboard)}))


if __name__ == '__main__':
    main()
