# Finding which haltere clusters carry which rotation axis

A protocol, not a result. `flappy/haltere_cluster_sweep.py` already measures what
each cluster does to the wings when driven alone. This asks the next question:
which clusters are *antagonist pairs*, and which pairs carry which axis.

## What the dataset already settles

Two things that would otherwise need arguing, checked directly on all 205
haltere afferents in MaleCNS v1.0:

**The typed clusters are reviewed.** `statusLabel` is `Reviewed` for 51 of the 53
cells in the ten named `SNpp*`/`SNxx*` types. All 148 preliminary cells are the
undifferentiated `SApp` bulk, which is not a candidate cluster. Tracing quality
is not a confound for this experiment.

**Cross-side homology is given by construction.** Every type is bilaterally
near-symmetric — `SNpp14` 3/3, `SNpp34` 4/4, `SNpp21` 2/2, and so on — so the
left and right members of a type are the same cluster on opposite sides. `L-A`
and `R-A` need no matching step, which is what keeps the combinatorics small.

Ten typed clusters per side, ~3 cells each, plus the `SApp` bulk of ~74.

## The protocol

Pick a candidate antagonist pair `A`, `B` from the ten types. Because homology is
given, that fixes all four groups: `L-A`, `L-B`, `R-A`, `R-B`. Drive them with a
tonic baseline modulated at wingbeat frequency, in four sign conditions:

| condition | L-A | L-B | R-A | R-B | drive symmetry |
| --- | --- | --- | --- | --- | --- |
| 1 | + | − | + | − | symmetric |
| 2 | + | − | − | + | antisymmetric |
| 3 | − | + | + | − | antisymmetric (negation of 2) |
| 4 | − | + | − | + | symmetric (negation of 1) |

Conditions 3 and 4 are the sign-negations of 2 and 1. That redundancy is the
point: it is the falsification test.

The symmetry of the drive is the mechanical anchor. A pitch rotation loads both
halteres in phase; roll and yaw load them in antiphase. So conditions 1/4 are the
pitch-like drive and 2/3 the roll/yaw-like drive, and a correct pairing should
show that separation in the motor response.

## Four things this needs pinned down

**A tonic baseline.** Afferent current cannot go negative, so `+`/`−` mean `B±Δ`
around a baseline. Campaniform afferents are tonically active, so this is
biologically reasonable — but the haltere response is non-monotonic in current
(see `AGENTS.md`), so characterise each cluster's response curve first and pick
`B` and `Δ` inside a monotonic region. Record the curve alongside the result.

**Modulation phase.** Coriolis force is ω × v_haltere, so it peaks at maximum
stroke *velocity* — 90° out of phase with stroke position. Modulate accordingly,
and state the convention in the output, because a phase error here inverts the
interpretation rather than degrading it.

**Brain step rate.** `play.py` steps the brain at 30 Hz, which cannot carry a 218
Hz modulation. `Brain.dt` is 0.1 ms so the rate is resolvable; the loop needs
stepping at ~1–2 kHz for these trials.

**No body in the search.** What is being measured is a motor response to an
injected drive — connectome only, no MuJoCo. Keeping the body out makes each
trial cheap and removes a live confound (the fly does not currently generate
lift). Bring the body back only to confirm that a winning pairing produces the
expected wing kinematics.

## Deciding whether a pairing is correct

Record, per condition, the wing motor response as a vector over muscles and
sides (`b1`/`b2`/`hg1` L and R, plus DLM), with both rate and phase at the
modulation frequency. Three criteria, all falsifiable:

1. **Sign inversion.** response(1) ≈ −response(4) and response(2) ≈ −response(3).
   Measure as cosine similarity; a correct antagonist pair approaches −1. A pair
   that fails this is not an antagonist pair, whatever else it does.
2. **Symmetry separation.** Project each response onto the symmetric (L+R) and
   antisymmetric (L−R) subspaces. A correct pairing puts conditions 1/4 mostly in
   the symmetric subspace and 2/3 mostly in the antisymmetric one. Cross-talk
   between the two is the quantitative form of "the brain thinks it is being
   twisted rather than rotated".
3. **Phase consistency.** Response phase at the modulation frequency should be
   stable within a condition and flip with the drive sign. Scattered phase means
   the drive is not being read as a rhythmic signal at all.

## Cost

45 pairings × 4 conditions = 180 trials, plus the per-cluster response curves.
Each trial is ~10 wingbeats (~46 ms) of connectome simulation at ~1-2 kHz
stepping. Fresh `NativeBrain` per condition — state carries, and reusing one
across amplitudes has already produced a wrong answer in this project.

## What the outcomes mean

**Several pairings pass all three criteria.** Then the ones that separate
symmetric from antisymmetric are the axis-carrying pairs, and the assignment of
which antisymmetric pair is roll versus yaw needs one more discriminator — most
naturally the sign of the steering response, checked against the direction a fly
corrects in.

**Exactly one passes.** Strongest outcome, and the one to be most suspicious of.
Check it against the known monosynaptic haltere-afferent→b1 motor neuron
connection: the winning pair should show that connectivity in the graph.

**None passes.** Either the antagonist structure is not recoverable from
connectivity alone, or the modulation is not reaching the motor pool. Distinguish
those with a positive control: drive a single cluster at the same modulation and
confirm a phase-locked motor response exists at all.

## What this licenses calling it

An axis assignment that passes all three criteria is a **functional** mapping:
these clusters behave as an antagonist pair carrying a symmetric or antisymmetric
signal, and driving them produces the motor pattern a rotation about that axis
should. It is not a claim about which campaniform field each cluster innervates
or where on the haltere base it sits — that needs external anatomy, and nothing
in a CNS connectome supplies it.

For a joystick, an IMU or an airframe, the functional mapping is the useful one.
Label it as functional wherever it appears.
