# flappy-haltere attribution and license scope

Not affiliated with or endorsed by the MaleCNS collaboration, FlyEM/Janelia,
or the Flappy Bird Gymnasium/FlapPyBird authors.

## This project's own code

`flappy/`, `docs/`, and `outputs/flappy_inverse/` are original work,
MIT licensed under [LICENSE](LICENSE), copyright Victor Biederbeck.

## connectome_sim/ (submodule)

The connectome engine this harness runs on is a separate repository,
included here as a git submodule, with its own dual-copyright MIT license
(original DOOMFLY-derived code plus a separately authored GPU backend) and
its own third-party notices (MaleCNS CC-BY-4.0, Huang et al. 2024, Shiu LIF
framework) — see `connectome_sim/THIRD_PARTY.md`.

## flappybird/ (submodule)

A git submodule of
[markub3327/flappy-bird-gymnasium](https://github.com/markub3327/flappy-bird-gymnasium)
(itself adapted from [sourabhv/FlapPyBird](https://github.com/sourabhv/FlapPyBird)),
copyright Gabriel Nogueira (Talendar) and Martin Kubovcik, MIT licensed per its own
`LICENSE` file. Used unmodified as the game environment.
