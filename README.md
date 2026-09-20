# flappy-haltere

A Flappy Bird harness for the MaleCNS v1.0 connectome simulation, plus a
haltere-inverse-dynamics research thread: given a target set of wing-muscle
motor-neuron spikes, propose which haltere sensory afferents to stimulate to
produce it, validated by round-tripping proposals back through the real
simulation (treated as the oracle).

Split out of [androsophila](https://github.com/jamesbiederbeck/androsophila),
which started as a fork of [nftechie/doomfly](https://github.com/nftechie/doomfly)
and grew a second, unrelated game harness. See
[docs/haltere-inverse-dynamics-experiment.md](docs/haltere-inverse-dynamics-experiment.md)
for the full experiment history.

## Layout

| Path | Contents |
| --- | --- |
| `flappy/game.py`, `render3d.py`, `controls.py`, `play.py`, `server.py`, `tune_server.py` | The Flappy Bird game harness and live-tunable web UI |
| `flappy/circuit.py`, `learn.py` | Haltere↔wing-motor reflex circuit and the dopamine-gated learning run |
| `flappy/haltere_cluster_sweep.py`, `fly_regions.py` | Structural haltere-cluster and motor-region mapping used by the Android export |
| `flappy/inverse_data*.py`, `inverse_train.py`, `inverse_infer.py` | Training-data generators, MLP trainer and inference/validation for the inverse-dynamics model |
| `flappybird/` | Flappy Bird Gymnasium, as a submodule |
| `connectome_sim/` | The connectome engine (native/GPU LIF simulator, connectome import, photoreceptor sampling), as a submodule |
| `docs/`, `outputs/flappy_inverse/` | Experiment write-up and training data/model checkpoints (the `.npz` files are gitignored — regenerate them with the `inverse_data*.py` scripts, or copy them over manually) |

## Best known agent

**Record: 0 pipes cleared under the current engine. A superseded configuration
scored 2, and the two are not comparable.**

On 2026-09-19 the harness cleared its first pipes: 2 across 14,000 ticks, one
scoring run in seven. On 2026-09-20 the photoreceptor transfer function was
fixed (light adaptation, see `connectome_sim/photoreceptor.py`), which changes
the visual front end of every run. Re-measured under it:

| seed | flap fraction | R (DLM/tick) | episodes | longest episode | pipes cleared |
| --- | --- | --- | --- | --- | --- |
| 41027 | 0.0525 | 29.42 | 32 | 173 | 0 |
| 41027 | 0.0525 | 29.49 | 28 | **235** | 0 |
| 99 | 0.0525 | 29.60 | 29 | 174 | 0 |
| 7 | 0.0525 | 29.52 | 26 | 209 | 0 |
| 1234 | 0.0520 | 29.38 | 31 | 131 | 0 |
| 2026 | 0.0520 | 29.12 | 33 | 122 | 0 |

Six runs of 2,000 ticks, `outputs/flappy_decode/adapt.jsonl`.

**Do not read 2 → 0 as a regression.** The 2 pipes were 2 events in 14,000
ticks with six of seven runs scoring nothing, which was already described as
chance alignment rather than avoidance. At that rate about 1.7 events are
expected in 12,000 ticks, and observing none has probability 0.18. The two
samples are not distinguishable. What would distinguish them is a run long
enough to make the rate itself measurable, which has not been done.

**Survival is the number that did move, and it moved up.** Longest episode per
run is now 122–235 against 96–181 before, on a previous record of 50.

**R is unchanged at 29.1–29.6.** The DLM rate is set by the haltere injection,
not by vision — which is consistent with everything in
`docs/sensory-encoding-experiments.md` and is why the visual fix did not change
the score.

**What is solid.** Survival improved in every run. The previous record's
longest episode was 50 ticks; the worst run here is 96 and the best is 181.
Flap fraction sits at 0.0520–0.0525 against the theoretical hover rate of
1/19 = 0.0526, so the bird now holds altitude instead of pinning itself to the
ceiling.

**What is thin.** Two cleared pipes in 14,000 ticks, all in one run of seven.
Six of seven runs still score zero. The bird holds a fixed altitude and does
not avoid anything; a pipe clears when a gap happens to line up with the hold
altitude. This is not pipe avoidance and should not be described as it.

**Two harness changes, so this is not comparable to earlier entries.** Per
`AGENTS.md`, both are called out rather than folded in:

1. `haltere_current_for_velocity` now clamps injected current at 8 mV
   (`circuit.py`'s `CURRENT_CEILING`). E-SIGN measured DLM output peaking at
   current 7–8 and then falling 150-fold to terminal fall speed, so the
   feedback loop was inverted over nearly the whole range the bird occupies:
   falling faster produced *less* flapping. Pass `ceiling=None` for the old
   unbounded behaviour every run before this date used.
2. `FlapControls` takes a `threshold`, switching it from "flap if any DLM cell
   spiked this tick" to an integrating decoder. The old decoder held the button
   down, which E-HOLD showed cannot play the game at all.

Neither change touches the connectome, the weights or the plasticity rule.
They are both fixes to the engineered joystick.

**Reproduce it:**

```sh
python -m flappy.run_decode --ticks 2000 --thresholds 560 --seed 99 \
  --log outputs/flappy_decode/repeats.jsonl \
  --summary outputs/flappy_decode/summary.json
```

**Run-to-run results are not identical even at a fixed seed.** The GPU backend
varies by a few flaps per 600 ticks from a cupy reduction-order effect, and at
roughly 104 flaps per 2,000 ticks that is enough to change a trajectory
completely. The first T=560 run scored 1 pipe and the immediate re-run at the
same seed scored 0. Quote a distribution over several runs, never a single run.

**Previous record, for comparison**, `outputs/flappy_learn/reward-run-20260919-1302.json`
(seed 41027, two phases of one hour, unclamped loop and any-spike decoder):
6,323 ticks over 127 episodes with a longest episode of 50 ticks, 126 pipe
strikes and **0 pipes cleared**; then 6,025 ticks in one continuous episode,
159 strikes, 0 cleared. That run had learning enabled and 2,127 of 4,184
plastic KC→MBON11 edges changed, which is the mechanism running rather than
evidence of better play. Reproduce with:

```sh
python -m flappy.learn --seed 41027 --eta 0.001 \
  --haltere-m 1.75 --haltere-n 2.0 \
  --fallback-after 3600 --gain-threshold 1.0 \
  --out outputs/flappy_learn/reward-run-$(date +%Y%m%d-%H%M).json
```

**What still blocks a real score.** The bird has no pipe information. The
fly's view (`render3d.py`) draws only the *lower* pipe, so it cannot see the
gap it has to thread even in principle, and
`docs/sensory-encoding-experiments.md` records why no visual drive point yields
graded motor output. Altitude hold is solved; avoidance is untouched.

## Where to run this from

Every command here runs from the **repository root** — the directory holding
`connectome_sim/`, not from inside it and not from the parent.

The engine resolves its paths relative to the consuming repo, not to its own
checkout: `connectome_sim/prepare.py` takes `parents[1]` and
`connectome_sim/physiology/common.py` takes `parents[2]`, and both land on this
repo's root. So `connectome_data/` is read from here and
`outputs/connectome_sim/` is written here. Run from anywhere else and the paths
resolve outside the checkout, usually to a `FileNotFoundError` naming a
directory one level up. `python -m ...` also needs the root on `sys.path`,
which is what running from there gives you.

## Setup

```sh
git submodule update --init --recursive
```

## Mapping neurons to axes

`docs/haltere-axis-mapping-experiments.md` designs the experiments that would
take this from effective axes (what a cluster does to the wings) to physical ones
(what it senses), and states the dataset limits that make the second hard.

## Stimulation is engineered, not biological

Every haltere stimulation here is host-side current injected into the
`drive[]` array before the connectome engine's kernel runs — the audited
kernel itself is never modified. This is an "engineered joystick," not a
claim about how a real fly's haltere-to-wing-motor pathway actually works;
see the circuit docstrings and the experiment write-up for what's measured
versus assumed.

See [THIRD_PARTY.md](THIRD_PARTY.md) for attribution.
