# To do

Rough next-step ideas, not yet experiment classes. Promote one to a
`## Class E-<NAME>` entry in `sensory-encoding-experiments.md` (with
Hypothesis/Parameters/Readouts/Metrics/Controls/Results/Conclusions/Status)
once it's actually run, per `.claude/agents/connectome-experimenter.md`.

Ordered by what currently blocks a score. As of 2026-09-19 the record is still
0 pipes cleared, but the reason changed: E-DECODE put the bird in the playing
field, so it no longer dies by leaving the screen. It dies at the first pipe,
at around tick 50, from mid-screen.

## Next

- **Check the sign and gain of the haltere loop.** E-DECODE found R (DLM
  spikes per tick) *falls* as the bird sits lower and falls faster — 29.8 at
  threshold 320, 18.2 at 400, 14.0 at 570. The haltere loop scales injected
  current by fall speed, so a falling bird should drive more DLM activity, not
  less. This is the harness's only closed feedback path and it appears to have
  the wrong sign, or to be swamped by something else. Measure it directly:
  hold the bird at a fixed velocity, sweep velocity, record R. Nothing
  downstream is worth tuning until the controller's sign is known. **This is
  the top item.**

- **Render the upper pipe in the fly's view.** `render3d.py` projects only the
  *lower* pipe ("a hurdle has no ceiling above the runner"), so the upper pipe
  still ends the episode on collision but is never drawn. This was a nice-to-
  have when the bird was pinned to the ceiling and never reached a pipe. Now
  that E-DECODE has it dying at the first pipe from mid-screen, the fly is
  being asked to thread a gap it can only see the floor half of. Draw it as a
  ceiling/overhang obstacle, not a second ground-level hurdle.

- **Re-tune T against the R the game loop actually produces.** The E-DECODE
  grid was built around R ≈ 13.6 measured in a 120-tick transient. At 600 ticks
  R settles near 29.5, which puts the hover threshold at T ≈ 19 × 29.5 ≈ 560 —
  the top of the grid, not its middle. But R itself drops to 14 by T = 570, so
  threshold and rate interact and the fixed point has to be found rather than
  computed. Sweep 450–700 and find where flap fraction actually lands on 0.053.
  Keep T a tuned constant: see the note in E-DECODE on why it must not track R.

- **One stronger-drive arm for E-GAIN.** E-GAIN swept adaptation from 0.125 to
  16 mV and found no setting where the driven arm differs from its own resting
  arm. But the drive point was LLPC1 at k = 4, the weakest E-VIS-INV found. The
  honest claim is that adaptation kills the *weakest* drive at any strength, not
  that adaptation and drive cannot coexist. One arm at a strong drive point
  (LLPC1 k = 32, or LC4 which had the lowest rheobase) settles it either way.

## Still open, lower priority

- **Try SNpp12 as the stimulation point**, instead of the full 205-cell
  haltere afferent population. `flybody-connectome/experiments/LOG.md` found
  the usable haltere interface in that sibling repo is about seven named cells
  (SNpp12, SNpp23 and neighbours), not the full afferent population or the ten
  structural clusters — "cluster" was the wrong unit there. Worth checking
  whether narrowing the drive to SNpp12 (single cell, both sides, matching
  `haltere-axis-mapping-experiments.md`'s homology-pair protocol) transfers to
  this harness. Pairs naturally with the sign-and-gain item above, since both
  are about what the haltere interface actually does.

- **Reduce haltere current.** The current demo/render gain is 1.75 (`m` in
  `A(dy) = m·dy^n`). `flappy/circuit.py` documents a sharp DLM firing threshold
  and notes no tested constant current gives an intermediate rate. E-VIS-INV
  since explained that threshold: it is the injected cell's own rheobase, and
  spike threshold is a hardcoded -45 mV global constant for all 166,700
  neurons, so a fixed-threshold cell under steady current has no intermediate
  rate to find. Sweeping gain lower will therefore not produce a graded
  response — but it may still change *which* cells cross, which is the part
  worth testing. Reframe accordingly before running it.

## Answered, kept for the record

- *Is there a graded drive band at some visual population?* No. E-VIS-INV
  screened all 77 and both drive parameters (current, recruitment count) are
  switches because the network is a switch.
- *Is the saturated state self-sustaining?* Yes. E-LATCH: drive removed for
  400 ticks and activity does not decay, converging within 0.22% from five
  different drive points.
- *What flap rate does the game need?* 1/19 = 0.053, exactly, because a flap
  sets vertical velocity rather than adding to it. E-HOLD.
