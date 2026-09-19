# Discovering the physical mapping of haltere afferents to axes

A design, not a result. The goal is to get from *effective* axes — "stimulating
this cluster produces that wing response", which `flappy/haltere_cluster_sweep.py`
already measures — to *physical* ones: which cells sense which axis of rotation,
and where on the haltere they sit.

## The constraint that shapes everything

**MaleCNS v1.0 carries no positional information for these cells.** Checked
directly on all 205 haltere afferents:

| field | value |
| --- | --- |
| `entryNerve` | `DMetaN` for all 205 — confirms the haltere nerve, says nothing about position within it |
| `somaLocation`, `tosomaLocation`, `somaNeuromere` | empty for all 205 |
| `mancSerial`, `mcnsSerial`, `serialMotif` | empty for all 205 |
| `instance` | `SApp_L` / `SApp_R` — side only |
| `type` | 148 `SApp`, plus 11 types of 2–8 cells |
| `statusLabel` | **151 "Prelim Roughly traced"**, 54 "Reviewed" |

So the physical mapping cannot be *derived* from this dataset. It can only be
*anchored*: each experiment below proposes a correspondence to external anatomy
and states what would refute it. Nothing here produces ground truth on its own.

The directional tuning of a real haltere afferent is a property of its
campaniform sensillum's position and orientation on the haltere base, and of
stroke phase — Coriolis force is ω × haltere velocity, so selectivity is
time-varying within a beat. None of that is in a CNS connectome.

## E1 — Tracing-quality stratification (gate; run first)

Repeat the cluster sweep restricted to the 54 `Reviewed` cells, then to the 151
preliminary ones separately.

- **Prediction if sound:** cluster boundaries and motor-response signatures
  survive in the reviewed subset.
- **Refutation:** they do not, in which case every experiment below is measuring
  reconstruction noise and the honest answer is "not yet answerable in this
  dataset". Report that outcome rather than proceeding.

Cheap, and it gates the rest. Do not skip it because the full-set result looks
tidy.

## E2 — Cell-count matching against published fields

*Drosophila* haltere campaniform sensilla are organised into named fields (dorsal
and ventral fields, scapal plates, Hicks papillae) with published per-field
counts. Compare our ~102 afferents per side against those.

- **Prediction:** some partition of our clusters sums to published field sizes.
- **Refutation:** our per-side count falls well short of the anatomical total, in
  which case the reconstruction samples the afferent population incompletely and
  count-matching is invalid as an anchor.

Look the counts up from the primary anatomy literature and record the source in
the run output. Do not take them from memory — mine or anyone's.

## E3 — The monosynaptic b1 anchor

There is a well-known, functionally characterised direct connection from haltere
campaniform afferents onto the b1 steering motor neuron. That is a literature
anchor testable in the graph today.

- **Prediction:** exactly one cluster shows strong direct (1-hop) connectivity to
  b1 MN, and that cluster is the candidate for the field described in the source.
- **Refutation:** no cluster does, or several do indistinguishably.

Verify the claim and the field identity against the paper before relying on it;
this is the step where a half-remembered citation becomes a wrong axis label.

## E4 — Antagonist pairing

Dorsal and ventral fields are mechanically antagonistic: a given deflection
strains one and unloads the other.

- **Prediction:** cluster motor-response vectors pair up anticorrelated —
  push/pull structure in the response matrix from the existing sweep.
- **Refutation:** all responses are positively correlated and differ only in
  magnitude, meaning there is one effective channel with a gain, not a set of
  fields.

Uses data the sweep already produces; this is analysis, not new simulation.

## E5 — Symmetric vs antisymmetric drive

The one axis claim with a mechanical basis available today. Pitch loads both
halteres in phase; roll and yaw load them in antiphase.

- **Prediction:** co-stimulating L and R produces a response distinguishable from
  differential L−R stimulation — plausibly power/amplitude change versus steering
  asymmetry.
- **Refutation:** the two are indistinguishable at the motor pool, meaning side
  carries no axis information and the joystick has one channel.

This is the experiment most likely to yield something usable soon, and its result
is honest either way.

## E6 — Cross-dataset replication

Run E1 and E4 against an independent connectome (FlyWire) and compare cluster
structure.

- **Prediction:** structural clusters replicate; reconstruction artifacts do not.
- **Refutation / caveat:** a different animal and a different sex. This project
  already refuses to copy a male sensory map onto female data for the retina; the
  same hazard applies here, so replication is evidence about robustness, not a
  merge of the two datasets.

## E7 — Forward-model anchoring (the only in-silico route to physical axes)

Build the haltere as a mechanical object and predict, per named field, the strain
time-course produced by each rotation axis. Then ask which cluster's measured
response profile best matches which field's predicted profile.

Prerequisites, none of which exist yet:

1. The halteres must actually beat — they currently move 3e-06 rad and no
   actuator commands them.
2. The model must have sensors. It has **zero** (`nsensor == 0`).
3. Field positions and orientations on the haltere base, from external anatomy.

This is the experiment that would justify calling an axis assignment physical,
and it is why "wire up the halteres" is a prerequisite for the mapping question
rather than a separate piece of work. Pre-register the predicted
cluster→field assignment before running it.

## E8 — Ground truth

Targeted physiology, or an EM volume that includes the haltere nerve periphery
and the sensilla themselves. Outside what this project can do; named so that the
ladder above is not mistaken for reaching it.

## What counts as done

If E1–E5 pass and E7 is not run, the result is a set of **effective axes**:
channels named by what they do to the wings, useful as a joystick, and not a
claim about what the fly senses. That is a legitimate deliverable — it is what an
IMU or an airframe needs — but it must be labelled as such everywhere it appears,
the way `haltere_cluster_sweep.py` already labels its own output.

Only E7 with an external anatomical anchor licenses the word *physical*, and even
then it is a correspondence with a stated residual, like the ommatidia
registration.
