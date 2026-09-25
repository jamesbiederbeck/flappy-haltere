# Flappy Fly Scores

Appended by `flappy/run_agent_scoreboard.py`. Each block is one invocation; scores across blocks are not comparable if `--ticks`, `--backend` or `--haltere-gain` differ, and are never comparable to run_decode.py's own printed `pipes_cleared` -- see that script's module docstring for why this file accumulates across episode boundaries instead. `git` is the flappy-haltere commit the row was run against; `+dirty` means the working tree had uncommitted changes at run time, so the exact code is not fully pinned by the sha alone.

Both blocks below predate the script's automatic command/sha capture (added in commit `dc36c7a`); the commands and shas were added by hand afterward. `dc36c7a` is the commit whose code reproduces both blocks' numeric results exactly at the given `--seeds`/`--ticks` (nothing in `agent.py`, `circuit.py`, `game.py` or `sensory_probe.py` changed between these runs and that commit) -- the one cosmetic difference is that the current `agents()` labels its threshold configs `integrating T={t}` rather than `integrating T=560 (run_decode.py best-known)`, a label-only change.

## 2026-09-24T23:25:48.986144+00:00 -- backend=gpu, ticks=2000, haltere_gain=1.75

Command: `python -m flappy.run_agent_scoreboard --backend gpu --ticks 2000 --seeds 41027 99`

Git: `dc36c7a` (retrofitted; run predates automatic capture, see note above)

| agent | seed | flap fraction | episodes | longest episode | pipes cleared | pipe strikes | best score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| any-spike (play.py) | 41027 | 0.9925 | 40 | 50 | 0 | 40 | 0 |
| any-spike (play.py) | 99 | 0.9935 | 40 | 50 | 0 | 40 | 0 |
| integrating T=560 (run_decode.py best-known) | 41027 | 0.052 | 30 | 133 | 13 | 28 | 3 |
| integrating T=560 (run_decode.py best-known) | 99 | 0.052 | 33 | 171 | 6 | 32 | 3 |

## 2026-09-24T23:59:23.397627+00:00 -- backend=gpu, ticks=6000, haltere_gain=1.75

Command: `python -m flappy.run_agent_scoreboard --backend gpu --ticks 6000 --seeds 41027 99 --thresholds 480 560 720 --no-any-spike`

Git: `dc36c7a` (retrofitted; run predates automatic capture, see note above)

| agent | seed | flap fraction | episodes | longest episode | pipes cleared | pipe strikes | best score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| integrating T=480 | 41027 | 0.0613 | 107 | 88 | 17 | 106 | 1 |
| integrating T=480 | 99 | 0.0613 | 104 | 93 | 28 | 103 | 1 |
| integrating T=560 | 41027 | 0.0527 | 84 | 213 | 49 | 82 | 5 |
| integrating T=560 | 99 | 0.0525 | 92 | 163 | 42 | 91 | 3 |
| integrating T=720 | 41027 | 0.0408 | 120 | 54 | 0 | 118 | 0 |
| integrating T=720 | 99 | 0.0407 | 120 | 53 | 0 | 119 | 0 |

