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

## Setup

```sh
git submodule update --init --recursive
```

## Stimulation is engineered, not biological

Every haltere stimulation here is host-side current injected into the
`drive[]` array before the connectome engine's kernel runs — the audited
kernel itself is never modified. This is an "engineered joystick," not a
claim about how a real fly's haltere-to-wing-motor pathway actually works;
see the circuit docstrings and the experiment write-up for what's measured
versus assumed.

See [THIRD_PARTY.md](THIRD_PARTY.md) for attribution.
