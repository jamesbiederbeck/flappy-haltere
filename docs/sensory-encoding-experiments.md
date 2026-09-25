# Encoding game state into sensory channels

Flappy Bird gives the controller four things worth knowing: distance to the
next upper pipe, distance to the next lower pipe, height above ground, and
vertical velocity. This log tracks the experiments that test whether any
sensory channel of the MaleCNS reconstruction can carry them — not whether
a channel produces spikes, but whether distinct values of a variable arrive
downstream as **distinguishable, ordered** responses.

The failure mode this whole line of work is guarding against is on record in
`flybody-connectome/experiments/LOG.md` (2026-09-19): a Johnston's-organ
potency result had to be withdrawn because driving any large population
ignites the network into a generic saturated state, so the response measured
saturation rather than the channel. Every class here therefore reports
separability across a variable's range, never total spike count, and runs
inside an operating band where the assay still has room to move.

## Status of the four proposed encodings

| proposal | status |
| --- | --- |
| Looming cue in upper / lower visual field | **E-LOOM, running** |
| JO auditory, different input neuron (subtype) | not yet designed |
| JO auditory, different frequency | open — see note |
| JO auditory, phase across L/R indicating direction | **ruled out before testing** |
| Linear acceleration → JO wind_gravity or haltere | not yet designed |

**Phase across L/R is not available in this reconstruction.** Johnston's organ
has 62 L / 52 R auditory cells, but 27 of the right-side cells have zero
outgoing edges against 2 on the left, and the subtypes are wildly asymmetric
(JO-B1_c 9 L / 0 R, JO-CA2 6 L / 0 R, JO-A2 11 L / 2 R). Any left-right
comparison would be reading reconstruction damage as direction. The prior LOG
reached the same conclusion independently for `pooled_auditory_R`, which gives
exactly 0 at every current while the left side gives ~2,500.

**"Different frequency" is not ruled out, but it is not tonotopy.** The engine
injects current into cell indices; there is no cochlea and no frequency axis to
address. What the prior LOG *does* record is a temporal result — with the
membrane time constant at 2 ms, a 218 Hz carrier crosses the first synapse and
JO afferents fire 219 Hz against it, one spike per cycle. So a frequency
encoding would have to be carried in the *modulation of the injected current
over time*, and depends on the opt-in time constants recently added to
`connectome_sim`. Untested here.

---

## Class E-LOOM — looming cue separability

**Hypothesis.** A disc drawn into the upper or lower visual field, whose
angular size grows as the encoded distance shrinks, produces wing-muscle pool
responses that vary monotonically with that distance and differ between the
two fields — so upper-pipe and lower-pipe proximity can be carried on one
retina without a second channel.

**Why this one first.** It needs no current-injection assumption: the cue is a
picture, the retina already samples pictures, and `render3d.py` already owns
the frame. It also avoids the tracing caveat that sits on all 672 JO cells.

**What the cue is, and is not.** A synthetic signal injected into the visual
field, not a rendering of the world. `render3d.py` draws walls because there
are walls; this draws a disc because a number needs a channel. Same engineered
status as the haltere joystick's injected current — no claim that a fly would
see this or that it resembles a natural looming stimulus.

**Parameters.**

| parameter | values |
| --- | --- |
| `field` | `upper`, `lower` |
| `depth` | 8, 12, 16, 24, 32, 48, 64, 96, 120 (world units) |
| `ticks` | 15 game ticks (33.3 ms each), frame held constant |
| `horizon` | 0.55 of frame height |

**Readouts.** Wing-muscle pool (67 cells) summed spike vector — the primary
readout, compared across depths. DLM (10 cells) reported separately: it is the
actuator and saturates early, so it is not evidence of encoding.

**Metrics.** Cosine distance between consecutive normalized response vectors
(does the response move as the variable moves), monotone fraction of the
totals (does it move in a consistent direction), and whether any of it is
distinguishable from the blank-frame control.

**Controls.** Blank frame (sky over ground, no cue) — the zero-signal baseline.
Both fields swept identically, so an upper/lower difference cannot come from
the sweep.

**Results.**

First sweep measured only the wing-muscle pool and returned **zero at every
parameter value, including the blank control**. That is not a null result about
looming — it is the readout's floor. `flappy/circuit.py` already records that no
VNC motor neuron of any kind spikes under plain visual drive. A readout whose
floor and ceiling are both zero cannot distinguish anything, so the class was
re-run with readouts at each stage of the path a cue would have to travel.

Network spikes over 15 ticks, blank control = 318,826:

| depth | 8 | 12 | 16 | 24 | 32 | 48 | 64 | 96 | 120 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| upper | 299,006 | 309,139 | 313,605 | 316,705 | 317,622 | 318,212 | 318,504 | 318,807 | 318,863 |
| lower | 315,968 | 317,290 | 317,822 | 318,580 | 318,827 | 318,683 | 318,826 | 318,826 | 318,826 |

Descending neurons (1,314 cells): 66–69 spikes across **4 active cells** at every
depth in both fields, against 69 for the blank. Wing-muscle pool: 0 throughout.
Descending-vector separability is at the noise floor — mean consecutive cosine
distance 0.00052 (upper) and 0.00049 (lower), and the upper-vs-lower distance
is 0.0 at depth 16, i.e. the two fields are literally indistinguishable there.

**Conclusions.**

1. **The cue is encoded, cleanly.** Upper-field network response is monotone
   across 8 of 9 steps and spans a 6.2% suppression from far to near, saturating
   smoothly back to the blank value at distance. As an encoding of one scalar
   into one channel, this works.

2. **The upper field is roughly seven times more sensitive than the lower.**
   Near-depth suppression is 19,820 spikes above the blank for upper against
   2,858 for lower, and the lower field is indistinguishable from blank beyond
   depth 48. Encoding both pipe distances symmetrically in the two fields would
   give two channels of very unequal resolution. Cause not established here;
   the cue sits above the horizon in one case and over textured ground in the
   other, and the R8 field has 249 cells in the top third against 207 in the
   bottom.

3. **None of it reaches the motor pools, and this is the finding that matters.**
   The visual signal modulates 6% of all network activity and moves the
   descending population not at all — 4 of 1,314 cells active, flat across
   every parameter value. The bottleneck is the brain-to-VNC descending bridge,
   not the retina and not the encoding.

4. **Which means the current harness is a Clever Hans fly, and now we have the
   measurement.** Vision is doing nothing to the wings. Every flap in this
   project is produced by injected haltere current driving DLM through a short
   reflex arc, and the fly's visual system — which does respond, in an ordered
   way, to what is in front of it — has no vote. Adding more sensory channels at
   the periphery cannot fix this; they would all arrive at the same closed
   bridge. The next question is not "which sensory channel" but "where does this
   connectome let the fly decide", which is being investigated separately.

**Status: E-LOOM closed.** The encoding works, the pathway does not. Do not
extend this class to the remaining variables until the descending bottleneck is
understood — four more encodings into a channel that reaches nothing would be
four more nulls.

---

## Class E-VPN — driving the fly's own looming detectors

**Hypothesis.** E-LOOM showed a visual cue is encoded but never reaches the
motor pools: photoreceptors sit 5 hops from DLM carrying 0.0001 of its
cumulative anatomical drive. A topology analysis of where this connectome
allows discretion found the leverage point two hops out — **LPLC4**, 97
looming-detection visual projection neurons, 95 of which synapse onto DNp31,
which synapses directly onto DLM (|w| 353, verified). If the bridge opens
there, and if the fly's own integration sits between the drive point and the
muscle, then what the fly *sees* should change what the wings do at a fixed
injected current.

**The test that matters is stage B.** Stage A only finds a working current.
Stage B holds that current fixed and changes nothing but the picture. If DLM
output tracks the cue, the flap is contingent on vision and the injection is a
gain knob. If DLM output is the same whatever the picture, then driving LPLC4
is the haltere joystick moved two synapses earlier, and it gets reported as
that.

**Parameters.** LPLC4 current 4–20; cue depth blank, 8, 16, 32, 64, 120 in the
upper field (the sensitive one, per E-LOOM); 15 ticks; readouts staged at
network / descending / wing-muscle / DLM. **Control:** a size-matched random
draw of 97 *other* LC-type visual projection neurons at identical currents, so
a positive result cannot be "injecting into 97 visual cells".

**Results.**

Stage A — current ladder on a blank frame:

| current | 4 | 6 | 8 | 10 | 12 | 16 | 20 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| descending | 69 | 70 | 3,253 | 3,501 | 3,737 | 4,153 | 4,651 |
| wing muscle | 0 | 0 | 1,364 | 1,448 | 1,481 | 1,493 | 1,589 |
| DLM | 0 | 0 | 552 | 586 | 557 | 564 | 569 |
| flap fraction | 0.00 | 0.00 | 0.93 | 1.00 | 0.93 | 1.00 | 1.00 |

Stage B — DLM total at fixed current, across pictures:

| current | blank | d=8 | d=16 | d=32 | d=64 | d=120 | range | corr. with depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8 | 552 | 554 | 495 | 562 | 494 | 554 | 12.7% | −0.00 |
| 10 | 586 | 592 | 555 | 606 | 571 | 613 | 9.9% | +0.45 |
| 12 | 557 | 538 | 555 | 547 | 528 | 583 | 10.0% | +0.50 |
| 16 | 564 | 548 | 549 | 568 | 534 | 530 | 6.9% | −0.75 |
| 20 | 569 | 591 | 546 | 540 | 508 | 556 | 15.0% | −0.38 |

Flap fraction was 0.93 or 1.00 at every current and every picture.

Stage C — size-matched random LC draw, 97 cells, currents 8–20: descending 69,
wing muscle 0, DLM 0. Identical to the no-drive baseline at every current.

**Conclusions.**

1. **The bridge opens, and this is the first time in this line of work that the
   visual pathway has moved the wing motor pool at all.** Descending output
   goes 69 → 3,253, wing muscle 0 → 1,364, DLM 0 → 552. E-LOOM's null was a
   statement about where the drive point was, not about vision.

2. **It is specific to LPLC4.** A size-matched draw of other LC visual
   projection neurons, same cell count and same currents, sits at exactly the
   undriven baseline — descending 69, wing muscle 0, DLM 0. This is not generic
   ignition, which is the failure that sank the sibling repo's JO potency
   result.

3. **The threshold is as sharp as the haltere channel's.** Nothing at current
   6, full motor output at 8. `flappy/circuit.py` records the same signature
   for haltere drive (0/150 ticks flapping at 5 mV, 97–99% at 7–10). Two
   completely different entry points into this network, same bang-bang
   actuator.

4. **Stage B fails, and it fails informatively.** DLM totals do move with the
   picture — 7–15% at fixed current, and the simulator is deterministic, so
   that variation is real network dynamics rather than sampling noise. But the
   sign of the correlation with depth flips between currents (−0.00, +0.45,
   +0.50, −0.75, −0.38), so it is not an ordered encoding of distance. And the
   flap fraction — the only thing `FlapControls.decode` actually reads — is
   saturated at every current and every picture. **At any current that opens
   the bridge, DLM is already saturated, and what the fly sees stops mattering.**

5. **So this is Clever Hans moved two synapses earlier**, exactly as the
   module docstring warned it might be. The fly's own integrating machinery is
   now in the loop — 105-odd effective input types at DNae009, a 6,258-node
   recurrent mass between drive point and muscle — and it changes nothing,
   because the actuator downstream of it is a switch.

**Status: E-VPN closed on stage B.** The drive point is right and the
specificity is real; the actuator is the problem.

**Next class, E-VPN-FB.** The pair sweep already found the missing piece: with
IN19B040 as input, **IN06B077** as a feedback channel takes DLM from flap
fraction 1.00 to 0.00 across currents 8→16, monotone, where no size-matched
random feedback set suppresses at all. The experiment is LPLC4 at 8–10 as the
input, IN06B077 swept to find the current that puts flap fraction mid-range,
and only then the picture varied. If the cue is going to reach the wings
anywhere, it is in the band where the actuator is not saturated.

---

## Class E-VPN-FB — LPLC4 input with IN06B077 feedback

**Hypothesis.** E-VPN opened the visual→wing-motor bridge at LPLC4 and proved
it specific, then failed its discretion test for one reason: every current that
opens the bridge saturates DLM, so the picture stops mattering. The pair sweep
independently found IN06B077 takes DLM from flap fraction 1.00 to 0.00 across
feedback currents 8→16, where no size-matched random feedback set suppresses at
all. Put them together and the discretion test runs inside a band where the
actuator can still move.

**Parameters.** LPLC4 at 8 and 10; IN06B077 swept 4→40; cue depths blank, 8,
16, 32, 64, 120 upper field; 15 ticks. **Stage D** re-ran the two strongest
conditions at 60 ticks (flap resolution 0.017 rather than 0.067) across nine
depths. **Control:** size-matched random VNC-intrinsic draws as feedback, same
currents.

**Results.**

Stage A — the feedback channel works under visual drive. At LPLC4=8, rising
feedback took DLM 552 → 75 and flap fraction 0.93 → 0.67; at LPLC4=10, DLM
586 → 60 and flap 1.00 → 0.60. The actuator is out of saturation.

Stage C — size-matched random VNC feedback at the same currents left flap
fraction at 0.93–1.00 and DLM at 484–582 in all eight draws. No suppression
whatever. **IN06B077 is specific in this configuration too.**

Stage B — 9 of 16 conditions showed flap fraction varying with the picture,
but most differences were a single tick (resolution 0.067), so the class was
re-run at higher resolution.

Stage D — 60 ticks, LPLC4=10 / feedback=32:

| depth | 8 | 12 | 16 | 24 | 32 | 48 | 64 | 96 | 120 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DLM | 156 | 365 | 610 | 596 | 608 | 338 | 274 | 644 | 644 |
| flap | 0.483 | 0.717 | 0.917 | 0.950 | 0.917 | 0.650 | 0.683 | 0.933 | 0.933 |

and LPLC4=8 / feedback=28: flap 0.767, 0.717, 0.900, 0.883, 0.900, 0.633,
0.533, 0.933, 0.933. Correlation with depth +0.385 and +0.201 respectively
(DLM: +0.412, +0.356).

**Conclusions.**

1. **Inside the unsaturated band, what the fly sees substantially changes what
   the wings do.** Flap fraction spans 0.48 to 0.95 at fixed injected current
   with nothing varying but the picture — a 0.47 range against a measurement
   resolution of 0.017. This is the first result in this line of work where
   the motor output is not determined by the injected current alone.

2. **The de-saturation is what made it visible, and it is specific.** The same
   cue produced nothing at all in E-VPN, where the actuator was pinned. Random
   size-matched feedback reproduces the pinned state exactly; only IN06B077
   opens the band. Both halves of the configuration are load-bearing.

3. **But it is not an ordered encoding of distance.** The response is
   non-monotone — rising from depth 8 to 24, dipping at 48–64, recovering at
   96–120 — and both current settings produce the *same* shape. The simulator
   is deterministic, so this is a reproducible nonlinear property of the
   encoding-plus-network, not noise. You could not decode distance from flap
   rate, so this is not yet a usable control channel.

4. **The lean is consistently the wrong way round.** Correlation with depth is
   positive in both stage-D conditions and in 12 of 16 stage-B conditions:
   nearer obstacle → *fewer* flaps, farther → more. For obstacle avoidance the
   useful sign is the opposite. Whether that reflects LPLC4's actual looming
   role, the arbitrary choice to put the cue in the upper field, or the
   inverting feedback channel, is not established here.

5. **Depths 96 and 120 give byte-identical output** (DLM 644 both, in both
   conditions). The cue becomes sub-threshold for the retina somewhere past
   depth 64 — a ceiling on the encodable range, not a property of the pathway.

### Stages E and F — what the non-monotonicity actually is

**Stage E, cue geometry ruled out.** Sweeping disc radius directly on its own
grid (0–220 px, 15 steps, 60 ticks), decoupled from the 1/depth projection that
could have bunched the depth samples:

| radius | 0 | 4 | 8 | 12 | 16 | 24 | 32 | 46 | 61 | 80 | 100 | 120 | 150 | 180 | 220 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| upper | .50 | .55 | .75 | .70 | .60 | .92 | .93 | .55 | .92 | .90 | .92 | .78 | .95 | .83 | .72 |
| lower | .50 | .50 | .48 | .63 | .70 | .93 | .90 | .93 | .73 | .95 | .87 | .90 | .73 | .95 | .75 |

**9 of 13 sign reversals in the upper field, 10 of 13 in the lower**, with
near-identical range (0.450 and 0.467). The projection was not the problem and
neither was the choice of field.

**Stage F, sensitive dependence confirmed.** Radius stepped one pixel at a time
(22→34, ~4% area change per step, 60 ticks):

| radius | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 33 | 34 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flap | .60 | .92 | .92 | .93 | .77 | .92 | .93 | .93 | .93 | .90 | .93 | .95 | .93 |

A **single pixel** of radius (22→23) moves flap fraction by 0.317. The span
across this 12-pixel window is 0.350 — **78% of the entire dynamic range
reachable across the full 0–220 pixel sweep.**

### Final conclusions

6. **The pathway is not encoding the cue; it is amplifying it.** Almost the
   whole output range is reachable by a perturbation too small to be a
   meaningful difference in the encoded variable. Combined with the
   determinism check (identical per-tick spikes across repeats), the regime is
   deterministic but effectively unpredictable at this resolution — sensitive
   dependence, not a transfer function.

7. **So conclusion 1 stands but means less than it looked.** Vision does
   genuinely move the wings here, and the injected current no longer determines
   the output. But "not determined by the injection" is not the same as
   "determined by the picture in a way anything could use". The fly is not
   reading the cue; it is being destabilised by it.

8. **Re-encoding cannot fix this, so the sensory-encoding line stops here.**
   A different cue shape, a different field, a different variable mapping all
   sit upstream of the amplification. What would have to change is the
   operating regime itself — lower drive, longer integration than 60 ticks so
   the variance averages, or a readout that is not a per-tick threshold. Those
   are regime experiments, not encoding experiments.

**Status: E-VPN-FB closed.** Three findings survive: the visual→wing-motor
bridge opens at LPLC4 and nowhere else tested; IN06B077 de-saturates the
actuator and no size-matched random set does; and inside that band the network
is in a sensitive-dependence regime that makes the pathway unusable as a
control channel without changing the regime first.

---

## Class E-MB-RAND — randomized KC→MBON11 initialization

**This class is not part of the sensory-encoding line.** E-LOOM, E-VPN and
E-VPN-FB ask whether a game variable can be carried into the fly on a sensory
channel. This one asks a specificity question about the *other* line of work in
this repo — the dopamine-gated KC→MBON11 plasticity in
`connectome_sim/physiology` — and is logged here because this is the file where
this project's controls are pre-registered, not because it extends the classes
above.

**Hypothesis.** The KC→MBON11 plasticity signature recorded in
`outputs/flappy_learn/reward-run-20260919-1302.json` — half the 4,184 plastic
edges moved, efficacies spread 0.571 to 1.180 — is a property of the
reconstructed MaleCNS v1.0 efficacies, such that a same-shape weight matrix
drawn at random would not reproduce it. The rule's own algebra predicts the
opposite, which is why this is worth running rather than assuming.

**Status: QUEUED — not executed.** Everything below the Results heading is a
pre-registration. No run has been made.

**The control being proposed.** `connectome_sim/physiology/circuit.py`
`identify()` selects 4,184 existing KC→MBON11 edges (verified: 4,064 KC cells,
3,623 of them presynaptic to one of the 2 MBON11 cells, 2 PPL101 DAN cells;
plastic weights min 0.275, median 2.200, mean 2.725, max 22.000, sum 11,401.5 —
quantized to multiples of the 0.275 unitary contact). Those efficacies are the
reconstructed MaleCNS v1.0 values. The proposal is to re-run an executed
experiment with them randomized, so that any result attributed to the
reconstruction can be checked against a same-shape weight matrix. This is the
same control class that forced the withdrawal of the sibling repo's
Johnston's-organ potency claim, and the same one E-VPN stage C and E-VPN-FB
stage C passed.

**Which experiment this repeats, and why not the obvious one.**

**Not the behavioural readout of `outputs/flappy_learn/reward-run-20260919-1302.json`.**
That run is a complete null on play — 0 pipes cleared in 12,348 ticks over two
phases, survival gain −0.64, 0 appetitive rewards ever delivered because a pipe
was never cleared. It is also a *structural* null: `flappy/training.py` records
that KC→MBON11 has no engineered path to the DLM cells
`flappy.circuit.wing_motor_readouts` reads, checked directly. A random-weight
arm is therefore guaranteed to return the same null for the same reason, and
the comparison would measure nothing. Repeating that readout is not worth the
compute, and the entry says so rather than running it for completeness.

**The same run does carry one non-null measurement, and that is the target.**
Phase 1 ended with 2,108 of 4,184 edges changed, mean efficacy 1.0027, minimum
0.5711, maximum 1.1804, mean absolute fractional change 0.0207; phase 2 ended
at 2,127 changed, minimum 0.6164, mean absolute change 0.0341. Those numbers
are provenance for *which* run is being repeated — they are not the comparison
baseline, because the executed run was wall-clock bounded (6,323 and 6,025
ticks) and weight change accumulates with ticks. The reconstructed arm is
re-run at a fixed tick budget alongside the random arms and supplies its own
statistic.

So E-MB-RAND repeats `flappy/learn.py` in the reward-run configuration and asks
of the *plasticity* readout what E-VPN stage C asked of the motor readout: is
this a property of the reconstructed KC→MBON11 matrix, or would any matrix of
the same shape produce it?

**No non-null behavioural target exists in this line, and that was checked.**
`outputs/connectome_sim/` holds the doom-side records —
`live-training-v1/weight-integrity.json` (2,007 changed memory edges),
`reward-probe.json` ("does not demonstrate learning"), `bci-validation.json`
(`learning_demonstrated: false`), and every `run-*.json` carrying
`scientifically_validated: false`. All of them report the mechanism running,
none reports a behavioural gain. The only executed experiment in this repo with
a large non-null behavioural effect is E-VPN-FB, and it contains no KC→MBON11
plasticity at all, so "random MB weights" is not a control that can be applied
to it. If the project wants a randomization control over *behaviour*, it has to
build the experiment first; E-MB-RAND cannot supply one.

**What "random initialization" means, precisely.**

The rule constrains this more than it first appears.
`connectome_sim/physiology/rule.py` `advance()` computes

    drive = eta * (kc_hz * (gain.T @ dmid) - (gain.T @ dan_hz) * kmid)

from KC spike rates, DAN spike rates and the DAN→MBON contact fractions.
**`baseline_plastic` does not appear in it.** `u` and `w` are *fractional*
deviations, and `brain.py` applies them as
`weight[edges] = baseline_plastic * (1 + memory_w)`. The reconstructed weights
therefore enter the learning rule only as a scale factor, and influence the
learned pattern only through the closed loop: stronger KC→MBON11 input changes
MBON11 firing, which propagates through the recurrent graph and can come back as
different KC and PPL101 rates. `minimum_fraction`/`maximum_fraction` (0.1–2.0)
bound that deviation, `u, w ∈ [−0.9, +1.0]`, not the absolute efficacy — so
"uniform random within the rule's bounds" is a category error as usually stated,
and is treated below as a distribution choice instead. The kernel's own LTD path
(`kernel.cpp`, the `learning_enabled && dan_index[i]>=0` block, which is the
only place `baseline_weight` is read) is inert here: `brain.step()` always calls
`_neural_step(..., learning=False)`.

Four schemes, testing four different nulls:

| scheme | what is altered | null it controls for | preserved |
| --- | --- | --- | --- |
| **A — shuffle** | permute `brain.baseline_plastic` across the same 4,184 edges; write the permuted vector back into `weight[circuit['edges']]` | "the pairing of a particular KC synapse with a particular efficacy carries the result" | graph, edge set, weight multiset, total drive (11,401.5) exactly |
| **A′ — shuffle within MBON** | permute only inside each MBON11 cell's edge block (2,048 / 2,136 edges) | same, but each postsynaptic cell's total input is exactly conserved, removing a per-cell drive confound | as A, plus per-MBON input totals |
| **B — distribution-matched draw** | resample 4,184 values with replacement from the empirical multiset (preferred over a fitted lognormal, which would break the 0.275 quantization) | "any weight vector with this marginal distribution would do" | distribution shape; **not** the multiset or the exact sum |
| **C — uniform** | draw uniform on [0.275, 22.0], or on [0.1·mean, 2.0·mean] if the rule's fractions are read as a range | "a biologically shaped weight distribution matters at all" | edge set only |
| **D — randomized presynaptic identity** | redraw `circuit['pre']` from the 4,064-cell KC pool, leaving `edges` and the MBON11 postsynaptic side intact | "the identity and subtype mix of the presynaptic KCs (KCg-m 1340, KCab-s 655, KCab-m 533, KCab-c 471, …) carries the result" | edge set, weights |

**Recommended primary: A**, with A′ as the immediate confirmatory arm. It is the
smallest perturbation that still destroys the reconstruction's information — it
conserves the multiset, the sum and the topology exactly, so a difference cannot
be attributed to changed total drive, and it isolates the one channel through
which the reconstructed weights can matter at all under this rule. B and C are
follow-ups and answer weaker questions; C is deprioritized because it destroys
the unitary quantization and so confounds "the reconstruction" with "any
plausible synapse-count distribution".

**D is the scheme that actually probes connectome specificity of the rule's
input**, because `pre` is the only circuit array the drive term reads. It is
listed as a follow-up rather than the primary because it is *not* the proposed
experiment — it randomizes identity, not weights — and because it deliberately
breaks an invariant: the kernel would deliver spikes along an edge from cell A
while the rule credits cell B. Any D run must say that in its report.

Note a prediction that falls straight out of the algebra and should be recorded
before running: under A, permuting weights leaves `kc_hz`, `dan_hz` and `gain`
untouched, so the *first* rate bin's `drive` is identical in both arms by
construction. Any divergence at all is closed-loop, and may be zero.

**Gate run before the sweep.**

Because of that, the class opens with a cheap gate, pre-registered with all
three outcomes declared:

Run the reconstructed arm and one scheme-A draw for **200 ticks**, same game
seed 41027, same `--eta 0.001`, and compare `brain.memory_w` element-wise.

1. **Bit-identical** — MBON11's output does not perturb KC or PPL101 counts
   within the run, scheme A is a no-op, and the 20-draw sweep would buy a
   restatement of the algebra. The class reports that as its result (it is a
   real finding about the rule, and a strong one), does not run the sweep, and
   promotes D to primary.
2. **Differs by less than float32 reordering noise** — report the magnitude and
   decide then; do not start the sweep on a difference that could be summation
   order.
3. **Differs materially** — run the sweep as designed.

**Parameters.**

| parameter | value |
| --- | --- |
| harness | `flappy/learn.py`, reward configuration (`--learning`, reward on) |
| brain | `calibration.calibrated_brain(eta=0.001)` — MBON current 9.87, DAN current 11.3125, DAN baseline 20.09 Hz |
| game seed | 41027, fixed across every arm |
| budget | **fixed at 2,000 ticks per arm**, not wall-clock, so arms are tick-matched; phase 1 (`pipes_terminate=True`) only |
| gate budget | 200 ticks |
| randomization seeds | 0–19, one scheme-A draw each |
| arms | 1 reconstructed + 20 scheme-A + (confirmatory) 5 scheme-A′ |
| cost | ≈1.7 ticks/s measured in the executed run → ≈20 min per arm, ≈7 h for the primary sweep |

**Budget floor, pre-registered.** If the reconstructed arm at 2,000 ticks
returns mean absolute change below 0.005 or fewer than 500 changed edges, the
readout has too little room to discriminate; raise the budget to 6,000 ticks and
re-run *every* arm, rather than comparing arms at different budgets.

**Readouts.**

Per arm, at the end of the budget: `MemoryBrain.memory()` and
`FlapTraining.telemetry()` — `changed_edges`, `mean_efficacy`,
`minimum_efficacy`, `maximum_efficacy`, `mean_absolute_change`, and the
per-edge deviation vector `memory_w` (4,184 floats) saved for pattern
comparison. Behaviour (`pipes_cleared`, `pipe_strikes`, `survival.gain`) is
recorded but is a **secondary, pre-declared non-discriminating** readout, for
the structural reason above.

**Metrics.**

- **Primary statistic:** `mean_absolute_change` of the reconstructed arm against
  the 20-draw null distribution, one-sided rank test. With 20 draws the smallest
  attainable one-sided p is 1/21 ≈ 0.048; the reconstructed arm must fall
  outside the full [min, max] of the draws to reach it.
- **Secondary statistics**, same test, reported whether or not the primary
  passes: `changed_edges`/4,184, `minimum_efficacy`, `maximum_efficacy`.
- **Pattern statistic:** Spearman ρ between the reconstructed arm's per-edge
  `memory_w` and each random arm's, edge-indexed (well defined under A and A′,
  which preserve the edge order). This separates "the same amount of plasticity
  happens" from "the same edges change".

**Controls.**

- The reconstructed arm is itself re-run at the fixed budget; the executed run's
  numbers are provenance only.
- `plastic_edge_index_sha256` must be unchanged in every A/A′/B/C arm — it
  certifies that only efficacies, never the edge selection, were touched. Under
  D it must change and `plastic_presynaptic_index_sha256` is the marker.
- A **degeneracy check** before any arm is scored: if the random arms all pin at
  the `minimum_fraction`/`maximum_fraction` bound, or all return zero change,
  the comparison is measuring saturation rather than specificity — the same
  failure mode this whole log exists to guard against — and the class reports
  that instead of a p-value.

**Pre-registered decision rule.**

**"The reconstructed connectome matters"** requires *all* of: the reconstructed
arm's `mean_absolute_change` falls outside the [min, max] of all 20 scheme-A
draws (one-sided rank p ≤ 0.048); at least one secondary statistic does the
same; the median |Spearman ρ| between reconstructed and random `memory_w`
vectors is below 0.5; the effect reproduces in the 5 scheme-A′ arms; and the
degeneracy check passes. Anything less is reported as not established.

**"Any weight matrix of the same shape would do"** is concluded if the
reconstructed arm's primary and secondary statistics all fall inside the
interquartile range of the draws, *or* if the median |Spearman ρ| exceeds 0.9 —
the learned pattern being reproduced whatever the weights are.

**The expected outcome is the second one**, and saying so in advance is the
point. The rule's algebra predicts it: `drive` never reads `baseline_plastic`.
If that prediction holds, the project must stop describing the KC→MBON11 weight
change as a connectome-specific memory trace and describe it as what the
equations say it is — a function of KC firing rates and DAN→MBON contact
fractions, with the reconstructed efficacies entering only as a per-edge scale
factor. `flappy/learn.py`'s existing interpretation line ("Weight change is the
mechanism running, not evidence of improved play") already declines the
behavioural claim; this would additionally decline the anatomical one.

**No outcome of this class can rescue a behavioural claim.** If the arms differ
in `pipes_cleared` or `survival.gain`, that is not learning: there is no path
from KC→MBON11 to DLM, so such a difference would be evidence of a bug or of an
unintended route through the graph, and is pre-registered to be investigated as
one.

**Prerequisites in `connectome_sim/` (not made here).**

`connectome_sim/` is a separate repository and was not modified. Two changes are
needed there before parts of this class can run honestly:

1. **Provenance.** `MemoryBrain.__init__` computes `initial_weight_sha256`, and
   `VisualMemoryBrain.__init__` recomputes it, before any harness-side
   randomization could occur. Mutating `baseline_plastic` and
   `weight[circuit['edges']]` afterwards leaves that digest — and therefore
   `configuration_signature()` and every checkpoint written by the arm —
   asserting reconstructed provenance for a randomized brain. Needed: a
   supported `set_baseline_plastic()` that updates `baseline_plastic`,
   `weight[edges]` and `initial_weight_sha256` together, and a
   `plastic_initialization` field in `configuration_signature()`. **Until that
   exists, E-MB-RAND arms must not write checkpoints**, and the harness must
   record the randomized plastic-weight digest and the draw seed in its own run
   report.
2. **Scheme D only.** `circuit['pre']` is passed to the kernel, so overriding it
   means constructing the brain with a modified `circuit` dict.
   `calibration.calibrated_brain()` accepts only `circuit_spec` and refuses
   anything but the default, so D needs a `circuit=` passthrough there. The
   alternative — building `VisualMemoryBrain` directly and re-applying the
   9.87 / 11.3125 / 20.09 calibration constants in the harness — duplicates
   numbers that `calibration.py`'s own docstring warns do not transfer, and
   should not be done.

Schemes A, A′, B and C need no upstream change beyond (1): they can be applied
by mutating `brain.baseline_plastic` and `brain.weight[brain.circuit['edges']]`
in the harness immediately after `calibrated_brain()` returns and before the
first step. Both must be written, and in that order, because `reset()` restores
`weight[edges]` from `baseline_plastic`.

**Results.** Pending — not executed.

**Conclusions.** Pending — not executed.

**Status: E-MB-RAND executed and closed — see the gate result and the sweep
conclusions below.**

### E-MB-RAND gate result — executed 2026-09-19

The class was designed predicting that scheme A might be a **no-op**, on the
grounds that `baseline_plastic` never enters the rule's drive term
(`rule.py:31`) and the kernel's only read of `baseline_weight` sits in a block
gated on `learning_enabled` (`kernel.cpp:77`) which never executes, because
`brain.py:125` always calls `_neural_step` with `learning=False`. Both source
claims were verified independently before running.

**The prediction is falsified. Verdict: material.** 200 ticks, game seed 41027,
one shuffle draw:

| arm | baseline sum | changed edges | mean abs change | min eff | max eff |
| --- | --- | --- | --- | --- | --- |
| reconstructed | 11,401.5 | 1,901 | 0.015615 | 0.5205 | 1.1419 |
| shuffled (seed 0) | 11,401.5 | 1,841 | 0.018055 | 0.5949 | 1.1922 |

1,916 of 4,184 edges differ between the two learned patterns (max |Δ| 0.201,
mean |Δ| 0.0162). The total drive was conserved *exactly* — 11,401.5 in both
arms — so the difference cannot be attributed to changed total input; it comes
only from which weight sits on which edge.

**What this means mechanically.** The weights reach the learned pattern purely
through the closed loop: `weight[edges] = baseline_plastic*(1+memory_w)` changes
MBON11's synaptic drive, which changes network activity, which changes the KC
and DAN rates the rule *does* read. That loop is not a weak correction — the
mean difference it produces between arms (0.0162) is the same order as the
learned change itself (0.0156). Shuffling the weights alters the learned
pattern about as much as learning alters it from baseline.

**Consequence for the class.** Scheme A is a valid control and the sweep is
worth running, which the gate existed to decide. One draw establishes nothing
about whether the reconstructed arm is *special* — that needs the full draw
distribution, which is now executing at the pre-registered 2,000-tick budget
with 20 draws.

**Results (sweep).** Pending.

**Conclusions.** Pending.

---

## Class E-REGIME — does longer integration recover a transfer function?

**Hypothesis.** E-VPN-FB closed by finding that a one-pixel change in cue
radius moves flap fraction 0.317 — 78% of the range reachable across the whole
0–220 px sweep — and concluded the pathway amplifies the cue rather than
encoding it. That measurement was taken at 60 ticks, and two readings survive
it with opposite predictions about the same quantity:

- **(a) finite-sample variance** — the process is bounded and the per-tick flap
  decision samples it noisily, so the adjacent-radius step should shrink like
  1/√ticks and a stable transfer function should appear underneath.
- **(b) sensitive dependence** — nearby inputs follow genuinely different
  trajectories, so the step stays flat however long you integrate.

**Parameters.** Ticks 60 / 120 / 240 / 480; radii 22–26 (the window where the
one-pixel jump was found); LPLC4 = 10, IN06B077 = 32, upper field. Nothing
about the cue or its encoding varies — E-VPN-FB settled that.

**Readouts.** Flap fraction (the per-tick threshold `FlapControls.decode`
actually reads) and DLM rate per tick (an amplitude readout free of that
threshold, included because the threshold itself could be manufacturing the
instability).

**Results.**

| ticks | flap at r=22…26 | mean adjacent step | span | span/step |
| --- | --- | --- | --- | --- |
| 60 | .600 .917 .917 .933 .767 | 0.1250 | 0.333 | 2.67 |
| 120 | .600 .817 .950 .950 .633 | 0.1667 | 0.350 | 2.10 |
| 240 | .533 .688 .842 .871 .583 | 0.1562 | 0.338 | 2.16 |
| 480 | .558 .579 .700 .704 .569 | 0.0704 | 0.146 | 2.07 |

Observed shrink from 60 to 480 ticks: **0.563**. Pure 1/√n would give 0.354.

DLM rate per tick at 480: 2.71, 3.55, 4.78, 5.44, 2.88.

**Conclusions.**

1. **Reading (b) is too strong, and E-VPN-FB conclusion 6 needs correcting.**
   There *is* reproducible structure here: every tick count shows the same
   unimodal shape — lowest at r=22, peaking at r=24–25, falling at r=26 — and
   it sharpens rather than dissolves as integration lengthens. At 480 ticks the
   amplitude readout is a clean tuning curve (2.71 → 5.44 → 2.88). Calling this
   pure amplification with no encoding was wrong.

2. **Reading (a) is also wrong.** The step shrinks, but at 0.563 against a
   1/√n prediction of 0.354, and non-monotonically — 120 and 240 ticks are
   *noisier* than 60. This is not finite-sample variance averaging out.

3. **The practical conclusion from E-VPN-FB nevertheless stands, for a
   different reason than I gave.** Integration shrinks the adjacent-radius step
   (0.125 → 0.070) but shrinks the useful span with it (0.333 → 0.146), so
   discriminability — span divided by step — is flat at 2.1–2.7 and if anything
   *declines* with longer integration. Four-fold more integration buys no
   resolution. The channel does not become usable.

4. **What it actually is: a narrow tuning peak, not a distance encoding.** The
   structure spans radii 24–25 and falls away on both sides, so even read
   perfectly it reports "the cue is about this size" and not "the obstacle is
   this far". For Flappy Bird that is the wrong shape of signal regardless of
   how cleanly it is measured.

5. **The per-tick threshold is not the culprit.** The amplitude readout, which
   bypasses it entirely, carries the same shape and a comparable normalized
   adjacent-step (0.28–0.47 across tick counts, no downward trend). Replacing
   `FlapControls.decode` with a rate readout would not rescue this.

**Status: E-REGIME closed.** Longer integration and a non-threshold readout
were the two cheap fixes E-VPN-FB proposed, and both are now ruled out
empirically. What remains untested from that list is lower drive — working
below the current that opens the bridge at all, which stage A of E-VPN showed
is a hard threshold between 6 and 8, so there may be no such band. If there
is not, the drive point has to change rather than the regime.

---

## Class E-BAND — is there a sub-threshold drive band at LPLC4?

**Hypothesis.** E-VPN stage A stepped LPLC4 current 4, 6, 8, … and found a
wall: nothing at 6, full motor output at 8. Nothing between was tested. If some
current opens the bridge *partially* on its own, there is an unsaturated regime
needing no feedback channel — and the cue could be tested there without a
second injection confounding it. If the threshold is a genuine step, the last
cheap fix from the E-VPN-FB list is exhausted.

**Parameters.** LPLC4 current 6.00 → 8.00 in 0.25 steps, blank frame, 60 ticks;
then cue radii 0/16/24/32/61/100 at every in-band current. GPU, frozen weights.

**Results.**

| current | 6.00 | 6.25 | 6.50 | 6.75 | **7.00** | 7.25 | 7.50 | 7.75 | 8.00 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| descending | 276 | 281 | 295 | 359 | **23,529** | 23,889 | 20,494 | 23,078 | 14,116 |
| wing muscle | 0 | 4 | 7 | 35 | **5,830** | 5,958 | 6,007 | 5,966 | 5,990 |
| DLM | 0 | 0 | 1 | 6 | **1,638** | 1,688 | 1,985 | 1,750 | 2,525 |
| flap | 0 | 0 | .017 | .017 | **.967** | .983 | .983 | .983 | .983 |

**Conclusions.**

1. **The threshold is a step, and a violent one.** Between 6.75 and 7.00,
   descending output rises **65-fold** (359 → 23,529) and DLM **273-fold**
   (6 → 1,638). A 3.7% change in drive current moves the motor pool from
   essentially silent to essentially saturated. There is no graded band.

2. **Sub-threshold, the cue can trip the threshold rather than modulate it.**
   At current 6.75 a radius-32 cue gives flap fraction 0.35 against 0.017 at
   every other radius — a 0.333 span. The picture is not being read, it is
   occasionally pushing the system over the edge, and only at one radius. Same
   sensitive-dependence signature E-REGIME characterised, now visible from
   below the threshold instead of above it.

3. **Above threshold there is nothing left to modulate.** Flap fraction is
   0.983 at every current from 7.25 up and at every cue radius, span 0.000 in
   four of six conditions.

4. **So the last cheap fix is exhausted.** Longer integration (E-REGIME),
   a non-threshold readout (E-REGIME), and a sub-threshold band (here) were the
   three regime fixes on the list. None works. **The drive point has to change,
   not the regime.**

**Status: E-BAND closed.** LPLC4 is a switch, not a knob, and no amount of
current shaping changes that. What has never been done is a systematic search
over *which* visual population to drive — every class so far took LPLC4 because
the topology analysis ranked it first, and tested one alternative (random LC
cells) only as a negative control. That search is E-VIS-INV.

## Class E-VIS-INV — which visual population is worth driving

**Hypothesis.** Every class up to E-BAND drove LPLC4 because the topology
analysis ranked it first. If LPLC4's switch behaviour is a property of *that*
population rather than of the network, some other visual projection population
should convert drive into graded motor output. Screen all of them.

**Parameters.** Stage 1 screen, executed 2026-09-19
(`run_id edc2238c-ba2f-4e1c-be1f-4186ab25f6c7`, graph
`d95171c2d59cfe3ebef2e5bd52be779b8f74754d718fc8941a93b8f2921c632b`).
Candidates are cell types matching `^(LC\d|LPLC|LLPC|LT\d|LPT|MeTu|aMe)` with at
least 8 cells: **77 types, 6,574 cells**. Each is driven alone at currents
4, 6, 8, 12, 16 for 30 ticks on a blank frame. GPU backend, frozen weights.

**Readouts.** Network spikes, descending total and active cells, wing muscle
total and active cells, DLM total and active cells, DLM flap fraction.

**Results.** `outputs/flappy_vis_inverse/{trials.jsonl,screen_summary.json,screen.npz}`.

1. **51 of 77 populations reach DLM at all; 26 never do.**

2. **151 of the 385 trials are the unstimulated baseline.** Every trial at
   current 4 or 6, across 76 of the 77 populations, returns *the same* network
   total (634,894 spikes), the same descending total (138 spikes over 4 cells)
   and zero DLM. Not similar — identical, which in a deterministic simulator
   means the injection did nothing at all.

3. **LC4 is the single exception.** At current 4 it produces 634,895 network
   spikes, exactly one spike above baseline, and by current 6 it is fully driven
   (775 DLM spikes, flap fraction 0.900).

4. **The screen's own `knob_like` count of 14 is too generous.** That classifier
   counts any flap fraction strictly between 0 and 1 as graded, so 0.9333
   qualifies. At 30 ticks the flap metric has resolution 1/30 = 0.033, so 0.900,
   0.9333 and 0.9667 are one-tick neighbours near the ceiling, not a curve.
   Filtering instead for any flap fraction in 0.2–0.8 leaves **10 populations**,
   and only four of those (LC16, LC19, aMe5, LC29) have a genuinely intermediate
   point — each at a single current.

5. **Above threshold, response is non-monotone in current.** LC16 gives DLM
   646 → 345 → 1188 at currents 8 → 12 → 16, with network totals 733k → 992k →
   819k. Same shape E-REGIME characterised as sensitive dependence.

**Conclusions.**

1. **E-BAND's step was the injected cells' own firing threshold, not an LPLC4
   property.** The 6.75 → 7.00 cliff sits in the same place as the 6 → 8 cliff
   here, and here it appears in 76 of 77 populations at once. Below it the drive
   is sub-rheobase and literally no spike is added anywhere; above it the driven
   cells fire and the motor pool saturates. Three classes attributed that step
   to LPLC4's connectivity. It belongs to the injection.

2. **The uniformity is the simulator's, not the fly's.** Spike threshold is a
   hardcoded global constant of -45 mV for all 166,700 neurons in both backends
   (`connectome_sim/engine.py:28`, `connectome_sim/gpu.py:124`). Every neuron
   has the same rheobase because the model gives them the same rheobase. This is
   the same class of caveat as the sign-from-transmitter assignment: a modelling
   choice that reads like a result.

3. **Current is not the knob, because per cell it is all or nothing.** A
   constant-threshold LIF cell under constant injected current either never
   fires or fires; there is no intermediate rate to ride. Sweeping current finer
   (E-BAND) cannot fix that, which is why it did not.

4. **Eight cells are enough to saturate the motor pool.** LPT31 has 8 cells and
   reaches DLM 1,251 with flap fraction 0.9333 — within noise of what LLPC1
   reaches with 285. Whatever the usable dynamic range is, it lives in a handful
   of cells, not in population size.

**Status: E-VIS-INV stage 1 closed.** It answers its question in the negative:
no visual population is a knob under current injection, and the reason is the
drive mode rather than the cell choice. Conclusion 4 says where to look next —
hold current fixed well above threshold and vary **how many cells are
recruited**, which is the one graded quantity a constant-threshold model still
offers. That is stage 2.

### Stage 2 — recruitment count as the knob (queued)

**Hypothesis.** With current fixed supra-threshold, DLM output varies with the
number of driven cells, and does so gradually enough to read a cue from.

**Parameters.** Current fixed at 12. Recruited cell count k over
1, 2, 3, 4, 6, 8, 12, 16, 24, 32 — absolute counts, not fractions of N, because
conclusion 4 puts the whole range below k = 8 and a fractional sweep of LLPC1's
285 cells would step over it. 300 ticks per arm so the flap metric resolves to
1/300 instead of 1/30. Populations: LC16, LC19, aMe5, LC29 from the mid-band
shortlist, plus LLPC1 as a large-population contrast to separate cell identity
from cell count. Cells drawn in a fixed seeded order so arms nest.

**Controls.** Size-matched random draws from the full visual candidate pool at
each k, same seeds — the same specificity control E-VPN-FB used.

**Results.** Executed 2026-09-19, `outputs/flappy_vis_inverse/{recruit.jsonl,recruit_summary.json}`.
58 arms, 300 ticks each, current 12, flap resolution 0.0033.

| population | k where it first fires | flap below | flap at | flap above |
| --- | --- | --- | --- | --- |
| LLPC1 | 4 | 0.0000 | 0.9833 | 0.9900–0.9967 |
| LC19 | 12 | 0.0000 | 0.9900 | — |
| LC29 | 16 | 0.0000 | 0.9200 | 0.9933 |
| aMe5 | 24 | 0.0000 | 0.6633 | 0.9567 |
| LC16 | 32 | 0.0000 | 0.8433 | — |

1. **Recruitment count is a switch too.** Every population goes from exactly
   zero DLM spikes to 7,122–10,545 in a single step of k. Below its transition
   the descending total sits at the unstimulated baseline of 1,384 spikes with
   zero wing muscle activity; above it, descending jumps to 97,878–126,821, a
   factor of about 80. Three of the five give one intermediate flap reading at
   the transition step itself (aMe5 0.6633, LC16 0.8433, LC29 0.9200) and
   nothing in between anywhere else.

2. **The transition k is not population size.** LLPC1 flips at 4 cells out of
   285; LC16 needs 32 out of 182. Bigger populations do not need more cells.

3. **The random control destroys the count story outright.** The pooled draws
   are independent per k rather than nested, and they are not monotone: 2 cells
   (LC31b, LC12) saturate the motor pool, while 3, 4 and 6 cells drawn from the
   same pool leave it at exactly zero. Six cells including LPLC2 do nothing;
   two other cells flip everything. **Which cells, not how many.**

4. **The network has two states, not a range.** Across all 58 arms every
   readout is either the resting baseline or full saturation. Wing muscle
   output is 0 in every sub-threshold arm and 21,361–32,665 in every
   supra-threshold one. There is no arm anywhere in this sweep that sits
   between.

**Conclusions.**

1. **Stage 2's hypothesis is falsified.** Recruitment count is not a knob. It
   fails the same way current did in stage 1, and for a reason that is now
   clearly not about the drive parameter: both parameters are switches because
   *the network* is a switch.

2. **This reframes the whole sensory line.** E-LOOM through E-BAND each
   explained an absence of graded control with a local cause — the wrong
   population, the wrong current, the wrong integration window, the wrong
   readout. Five classes, five local explanations. The common cause is that
   this configuration has exactly two reachable regimes, quiescent and
   saturated, and every drive that crosses the boundary lands in the second
   one. A control channel needs the space between, and there is none.

3. **The obstacle is now a property to characterise, not a parameter to
   tune.** The next question is what makes it bistable, and the cheapest
   discriminating measurement is whether the saturated state is self-sustaining:
   drive the network over the boundary, remove the drive, and see whether it
   falls back. If it does not, this is runaway excitation and the missing
   ingredient is gain control, not a better drive point. That is E-LATCH.

**Status: E-VIS-INV closed, both stages.** No visual population is a usable
drive point under current injection or recruitment count, and the reason is
upstream of both.

## Class E-LATCH — is the saturated state self-sustaining?

**Hypothesis.** E-VIS-INV closed on the finding that this configuration has two
reachable regimes and nothing between them. Two mechanisms produce that shape
and they call for opposite fixes. Under *driven saturation* the network follows
the drive faithfully and the drive is all-or-nothing because a fixed-threshold
cell under steady current has no intermediate rate; remove the drive and
activity falls back, and the fix is a drive with graded statistics. Under
*runaway excitation* crossing the boundary starts recurrent activity that feeds
itself; remove the drive and the network stays lit, and the fix is gain
control. Release separates them.

**Parameters.** Executed 2026-09-19, `flappy/run_latch.py`, GPU, frozen
weights. Drive 100 ticks at current 12, then release for 400 ticks with no
drive at all, recording per-tick spike counts through both phases. Arms are the
five (population, k) pairs at which E-VIS-INV stage 2 saw each population first
cross, plus a two-cell pooled draw and a baseline arm that is never driven, so
"returns to baseline" is measured in the same protocol rather than compared to
a remembered number.

**Metrics.** `silence_tick` (ticks after release until DLM goes quiet and stays
quiet, `null` if it never does), release DLM total, and tail network rate over
the last 50 ticks as a multiple of the measured baseline.

**Results.** `outputs/flappy_latch/{trials.jsonl,summary.json,traces.npz}`.

| arm | cells | DLM during 100-tick drive | DLM during 400-tick release | silence tick | tail / baseline |
| --- | --- | --- | --- | --- | --- |
| baseline | 0 | 0 | 0 | 0 | 0.9998 |
| LLPC1 | 4 | 2,769 | 11,959 | never | 2.8475 |
| LC19 | 12 | 2,467 | 11,673 | never | 2.8427 |
| LC29 | 16 | 3,332 | 11,911 | never | 2.8475 |
| aMe5 | 24 | 2,518 | 11,788 | never | 2.8452 |
| LC16 | 32 | 2,345 | 11,752 | never | 2.8413 |
| pooled pair | 2 | 0 | 0 | 0 | 1.0002 |

1. **Every arm that crossed stayed lit.** All five run the full 400 release
   ticks without DLM ever going quiet. Per tick, DLM output is unchanged or
   slightly higher after the drive is removed than during it: LC16 gives 23.4
   spikes per tick while driven and 30.1 per tick four hundred ticks after
   release.

2. **The plateau is identical either side of release.** Measured at the
   boundary rather than as a phase mean, the ten ticks before release and the
   ten after are 60,324 → 60,189 (LLPC1), 60,285 → 60,223 (LC29) and
   60,182 → 60,418 (LC16) network spikes per tick. Removing the drive changes
   nothing. (Phase means mislead here: LC16 averages 30,080 over its drive
   window only because it did not cross until tick 84, so that mean is a ramp
   compared against a plateau. Crossing ticks were 8, 14, 15, 68 and 84.)

3. **All five converge on the same total rate.** Tail rates are 60,388,
   60,288, 60,390, 60,341 and 60,257 spikes per tick, a spread of 0.22% across
   drive points that differ in population and in cell count from 4 to 32.
   Measured baseline is 21,208 per tick, so the attractor sits at 2.85x rest.
   Note this is a scalar: `traces.npz` stores group totals, so two states with
   equal total rate and different spatial patterns are not distinguished here.
   Network-wide, 60,300 spikes per tick over 166,700 neurons is about 22 Hz
   mean against 7.6 Hz at baseline — seizure-like, but not a numerical
   blow-up.

4. **The pooled two-cell draw never crossed**, so it is a null arm here, not a
   reproduction of stage 2's potent pair. Stage 2's control drew k=1 before
   k=2 from the same generator; this arm draws two directly and gets different
   cells. It is reported as what it is.

**Conclusions.**

1. **It is runaway excitation, not driven saturation.** Result 1 settles it:
   the drive can be removed for four hundred ticks and the state does not
   decay at all. What the model does have is a 2.2 ms refractory period, a
   20 ms membrane time constant and a 5 ms synaptic one
   (`connectome_sim/engine.py:14,46`). A refractory period caps the peak firing
   rate but does not pull recurrent gain below unity, so it bounds the ceiling
   without preventing the attractor. What is missing is anything
   activity-dependent: no synaptic depression, no inhibitory gain scaling, and
   spike-frequency adaptation that exists in the CPU physiology kernel but is
   gated to Kenyon cells by `kc_mask` (`connectome_sim/physiology/kernel.cpp:47`)
   and is absent from the GPU path this ran on.

2. **The attractor looks the same from every drive point, at least in total
   rate.** Five populations driven with cell counts from 4 to 32 end within
   0.22% of each other. That is a scalar measurement and does not rule out
   differing spatial patterns; comparing descending response vectors over the
   tail with `separability()` would settle it and has not been run. The program
   conclusion does not depend on which way that goes: a network pinned at 2.85x
   rest with DLM firing about 30 spikes per tick cannot produce graded flap
   output whatever its pattern.

3. **This retires the drive-point search.** E-LOOM, E-VPN, E-VPN-FB, E-REGIME,
   E-BAND and both E-VIS-INV stages each searched for a better place or a
   better way to inject. All seven were searching inside a dynamical regime
   that has no graded states to find. Continuing to search it is the wrong
   move.

4. **The honest framing is that this is a model limitation, not a fly
   result.** Real flies have adaptation and inhibitory gain control; this graph
   plus a fixed -45 mV threshold and KC-only adaptation does not. The
   bistability belongs to the simulation, in the same category as the global
   threshold and the transmitter-derived synaptic sign.

**Status: E-LATCH closed.** The next work is gain control, not drive points.
The cheapest version is already half-built: `adaptation` is a per-neuron array
and the kernel already decays it for any neuron carrying a value, with only the
jump gated by `kc_mask`. Widening that mask turns network-wide
spike-frequency adaptation on. The experiment is to sweep adaptation strength,
find where the attractor stops being reachable, and only then re-run one
retired sensory class to see whether a graded band exists once the network can
hold one. That is E-GAIN. Until it lands, no cue-to-flap channel is reachable,
and note this path runs on the CPU physiology kernel rather than GPU.

---

## Class E-GAIN — does network-wide adaptation remove the attractor?

**Hypothesis.** E-LATCH found the saturated state is self-sustaining and that
nothing in the model bounds recurrent gain. Spike-frequency adaptation is the
cheapest missing ingredient to add, because the machinery already exists: the
`adaptation` array is per-neuron and the kernel already decays it for any
neuron carrying a value. Only the jump was gated, to Kenyon cells, by
`kc_mask`. If adaptation is what is missing, widening that gate should make the
attractor unreachable at some strength.

**The second question is the one that matters.** An adaptation strong enough to
kill the attractor by killing all activity has not created a usable regime, it
has created a quiet one. So the undriven baseline is measured at every
strength, not only the driven arms, and an arm only counts as a success if the
driven condition comes down *and* the resting condition does not.

**Engine change.** `physiology/kernel.cpp` previously gated both the adaptation
jump and the plasticity eligibility trace behind `kc_mask`. These are now
separate: a new `adapt_mask` argument carries the adaptation gate, and
`MemoryBrain` takes an `adaptation_mask` keyword defaulting to `kc_mask`. With
the default, `if(adapt_mask[i])` and `if(kc_mask[i])` test the same array, so
the dynamics are unchanged by construction. `adaptation_mask` is also added to
`configuration_signature()`, which means checkpoints written before this change
no longer validate — nothing in flappy-haltere depends on one.

**Parameters.** CPU physiology kernel, frozen weights, blank frame. Drive
LLPC1 at k = 4 and current 12 for 30 ticks (the weakest drive point E-VIS-INV
stage 2 found), then release for 90. Adaptation jump 0, 2, 4, 8, 16 mV at
tau 200 ms, mask widened to all 166,700 cells. Jump 0 is the no-adaptation
control and reproduces E-LATCH on this backend. Default KC-only scope covers
4,064 cells, for contrast.

**Metrics.** `silence_tick` (ticks after release until DLM goes quiet and stays
quiet, `null` if never), release DLM total, tail network rate in the driven
condition as a multiple of the tail rate in the resting condition at the same
adaptation strength.

**Results.** In progress, `outputs/flappy_gain/`.

The backend replication landed first and is worth recording on its own. At
jump 0 the CPU physiology kernel reproduces both states: resting activity of
**21,189** network spikes per tick with zero DLM, against **21,208** measured
on GPU in E-LATCH, and the driven arm latches with DLM never going quiet.
Two independent backends agreeing to 0.09% on the resting rate, and agreeing
that the driven state does not decay, rules out the attractor being an artifact
of one implementation.

**Coarse sweep, jump 0/2/4/8/16 mV at tau 200 ms, mask widened to all
166,700 cells.** `outputs/flappy_gain/{trials.jsonl,summary.json,traces.npz}`.

| jump (mV) | rest, network/tick | driven, network/tick | driven DLM | latched |
| --- | --- | --- | --- | --- |
| 0 | 21,212 | 39,517 | 2,429 | **yes** |
| 2 | 7,880 | 7,880 | 0 | no |
| 4 | 4,915 | 4,915 | 0 | no |
| 8 | 2,949 | 2,949 | 0 | no |
| 16 | 1,858 | 1,858 | 0 | no |

1. **Adaptation does remove the attractor.** At every strength above zero the
   driven arm goes quiet and stays quiet.

2. **It removes it the useless way.** From jump 2 upward the driven arm is not
   merely unlatched, it is *identical to its own resting arm* — 7,880.1 against
   7,879.6 network spikes per tick, with zero DLM. The drive stopped reaching
   threshold at all. This is the failure mode the paired rest arms were built to
   catch, and it would have read as a clean success without them.

3. **Resting activity collapses too.** Jump 2 takes the undriven network from
   21,212 to 7,880 spikes per tick, 37% of its unadapted rate, and jump 16 takes
   it to 1,858, under 9%.

4. **The grid is too coarse.** The interesting transition is entirely inside
   0 < jump < 2: at 0 the network latches, at 2 it cannot be driven. A finer
   sweep at 0.125, 0.25, 0.5 and 1 mV is running.

**Fine sweep, jump 0.125/0.25/0.5/1 mV, same mask and drive point.**
`outputs/flappy_gain/{fine.jsonl,fine_summary.json}`.

| jump (mV) | rest, network/tick | driven, network/tick | driven DLM | latched |
| --- | --- | --- | --- | --- |
| 0.125 | 19,334 | 19,336 | 0 | no |
| 0.25 | 17,770 | 17,772 | 0 | no |
| 0.5 | 15,211 | 15,212 | 0 | no |
| 1 | 11,664 | 11,665 | 0 | no |

5. **There is no window at this drive point.** At every strength tested, down
   to 0.125 mV, the driven arm is within 2 spikes per tick of its own resting
   arm and DLM output is exactly zero. The drive stops reaching the motor pool
   the moment any adaptation exists at all.

6. **Resting activity falls smoothly and immediately.** 21,212 per tick at
   jump 0, then 19,334 at 0.125 and 11,664 at 1. There is no flat region near
   zero where adaptation is present but harmless.

**Conclusions.**

1. **Adaptation removes the attractor, and at every strength tested it also
   removes the response.** The sweep found no setting where the driven arm
   differs from the undriven one. Both sweeps together cover 0.125 to 16 mV and
   the answer is the same across two orders of magnitude.

2. **What this does and does not establish.** The drive point here is LLPC1 at
   k = 4, the *weakest* one E-VIS-INV stage 2 found. So the honest claim is
   that adaptation at any strength kills the weakest drive, not that adaptation
   cannot coexist with any drive. A stronger drive under adaptation is untested
   and is the obvious follow-up.

3. **The paired rest arms are the reason this reads correctly.** Every arm
   from 0.125 upward would have been recorded as "attractor removed" by the
   driven arm alone. Only the comparison to its own resting arm shows that
   nothing was being driven in the first place.

**Status: E-GAIN closed as designed, with one clear gap.** Network-wide
spike-frequency adaptation does not produce a usable regime at the weakest
drive point, at any strength between 0.125 and 16 mV. Whether it does at a
stronger drive is open, and is the one arm worth adding before the class is
retired for good.

---

## Class E-HOLD — what flap rate does the game actually need?

**Hypothesis.** Every class before this one measured what the connectome can be
made to do. None of them asked what the game wants. The harness has never
cleared a pipe, and nobody had established what flap rate clearing one would
require, so the neural side has been optimised against an unknown target.

**The physics are fixed and small.** From
`flappy_bird_gymnasium.envs.constants`: gravity adds 1 px/tick to downward
velocity, a flap **sets** velocity to -9 rather than adding to it, and velocity
is clipped to [-8, 10]. Because a flap resets rather than accumulates, flapping
once every N ticks displaces the bird by

    -9N + N(N-1)/2

over that period, which is zero at **N = 19**. So there is exactly one flap
rate that holds altitude, **1/19 = 0.0526**, and it is a point rather than a
band.

**Parameters.** `flappy/run_hold.py`, real environment, no connectome in the
loop. 2,000 ticks, seeds 41027/7/99, pipes parked (`--no-pipes`) so only the
ceiling and ground end an episode and altitude control is isolated from pipe
avoidance. Flap rate driven two ways: fixed period (flap every Nth tick) and
Bernoulli at probability p, since the decoder produces something closer to the
second.

**Results.** `outputs/flappy_hold/{nopipes.jsonl,nopipes_summary.json}`.

| period | flap fraction | ticks survived | mean height | drift over run |
| --- | --- | --- | --- | --- |
| 1 | 1.0000 | 2,000 | -71 | -323 |
| 2 | 0.5000 | 2,000 | -66 | -311 |
| 8 | 0.1250 | 2,000 | -41 | -267 |
| 16 | 0.0625 | 2,000 | +7 | -143 |
| 18 | 0.0560 | 2,000 | +30 | -255 |
| **19** | **0.0530** | **2,000** | **+214** | **-26** |
| 20 | 0.0500 | 280 | +281 | +145 |
| 26 | 0.0385 | 52 | +268 | +145 |

1. **The arithmetic is exactly right.** Period 19 drifts 26 px over 2,000 ticks
   and sits at mid-screen. Period 20 falls and dies at 280 ticks. Period 18
   climbs.

2. **Above the hover rate the bird does not die, it leaves.** Every arm from
   period 1 to 18 "survives" all 2,000 ticks at a *negative* mean height — it is
   pinned above the visible world, where no pipe can be cleared because the bird
   is not in the playing field. Survival time is not a fitness signal here.

3. **The equilibrium is a knife edge, not a window.** One tick of period either
   side of 19 is the difference between hovering at mid-screen and either
   leaving the top or hitting the ground. This follows from flap setting
   velocity rather than adding to it, so error accumulates instead of
   self-correcting.

**Conclusions.**

1. **The harness has never cleared a pipe because the fly flaps roughly 18
   times too often.** The recorded best run flapped 6,118 times in 6,323 ticks,
   a flap fraction of **0.97**. E-VPN-FB's much-celebrated modulated band was
   **0.48–0.95**. Hovering needs **0.053**. The entire reachable range of every
   experiment in this document sits between 9x and 18x above the only rate that
   keeps the bird in the playing field.

2. **So five classes of sensory work were modulating a control variable that
   was already pinned far outside its usable range.** Getting flap fraction to
   vary with the picture was never going to produce a score while every value it
   varied between flies the bird into the ceiling inside 50 ticks.

3. **This is a decoder problem before it is a connectome problem.**
   `FlapControls.decode` fires a flap when *any* DLM cell spikes in a tick
   (`flappy/controls.py:31`). With a motor pool firing about 30 spikes per tick,
   that decoder is an always-on button by construction. No change to the drive
   point, the regime or the gain control can fix it, because the saturation is
   in the mapping from spikes to button, not in the spikes.

4. **The fix is arithmetic and it restores gradedness for free.** An
   integrating decoder — accumulate DLM spikes, flap and reset when the
   accumulator crosses a threshold T — produces a flap fraction of R/T for a
   DLM rate of R. At R = 30 spikes per tick, T ≈ 570 lands on the hover rate,
   and flap fraction then varies *linearly* with DLM rate instead of saturating.
   That is a control channel built out of the saturated output the network
   already produces.

**Status: E-HOLD closed.** It supplies the target every earlier class was
missing: 0.053, not "more" or "modulated". The next class, E-DECODE, builds the
integrating decoder, sweeps T with the real brain in the loop to land the flap
fraction on the hover rate, and then plays the actual game and counts pipes.
Note for the record that changing the decoder is an engineered-harness change,
so scores after it are not comparable to earlier entries.

---

## Class E-DECODE — put the flap rate in the playable range and play

**Hypothesis.** E-HOLD showed the game has exactly one altitude-holding flap
rate, 1/19 = 0.053, and that every configuration ever run here sat between 0.48
and 0.99, so the bird left through the top of the screen within about 50 ticks.
The cause is the decoder: `FlapControls` fired whenever *any* DLM cell spiked
in a tick, and the pool spikes on nearly every tick, so the button was
effectively held down. An integrating decoder — sum DLM spikes, fire and carry
the remainder when the total crosses a threshold T — should give a flap
fraction of about R/T for a DLM rate of R, landing the bird in the playing
field.

**Engine change.** `FlapControls` takes an optional `threshold`. Passing
`None` keeps the original any-spike decoder exactly. This is a harness change,
not a connectome one, so scores under it are not comparable to earlier
entries. T is a hand-tuned constant and deliberately does *not* track R: if the
threshold chased the rate, then R drifting up and R being driven up would look
identical at the button, and learning would be unmeasurable at the output.

**Parameters.** `flappy/run_decode.py`, GPU, frozen weights, real game in the
loop, haltere gain 1.75, seed 41027, 600 ticks per arm. T swept over 1 (the
any-spike control), 120, 180, 210, 240, 260, 280, 320, 400, 570.

**Results.** `outputs/flappy_decode/{trials.jsonl,summary.json}`.

| T | flap fraction | R (DLM/tick) | episodes | longest episode | mean height | pipes cleared |
| --- | --- | --- | --- | --- | --- | --- |
| 1 (any-spike) | 0.9517 | 26.31 | 11 | 50 | 45.4 | 0 |
| 120 | 0.2450 | 29.56 | 11 | 50 | 64.9 | 0 |
| 180 | 0.1633 | 29.70 | 11 | 50 | 82.8 | 0 |
| 210 | 0.1400 | 29.42 | 11 | 50 | 95.0 | 0 |
| 240 | 0.1233 | 29.76 | 11 | 50 | 103.9 | 0 |
| 260 | 0.1117 | 29.34 | 11 | 50 | 110.8 | 0 |
| 280 | 0.1033 | 29.13 | 11 | 50 | 118.5 | 0 |
| 320 | 0.0917 | 29.80 | 11 | 50 | 128.9 | 0 |
| 400 | 0.0450 | 18.18 | 12 | 55 | 194.4 | 0 |
| 570 | 0.0233 | 14.03 | 14 | 46 | 233.4 | 0 |

1. **The decoder does what it was built to do.** Flap fraction falls smoothly
   from 0.95 to 0.023 across the sweep, and mean height rises correspondingly
   from 45 (pinned near the ceiling) to 233 (mid-screen). The bird is now in the
   playing field instead of above it.

2. **Survival did not improve.** Longest episode is 50 ticks at the any-spike
   control and 46 to 55 ticks everywhere else. Pipes cleared is 0 in every arm.
   Episode count actually rises slightly at the highest T, meaning episodes got
   *shorter* on average.

3. **R is not constant across the sweep, and moves the wrong way.** It holds
   near 29.5 from T = 120 to 320, then drops to 18.2 at T = 400 and 14.0 at
   T = 570 — falling as the bird sits lower and falls more. The haltere loop
   scales injected current by fall speed, so a falling bird should drive *more*
   DLM activity, not less. Whatever sets R here, it is not the feedback path
   the harness was built around.

**Conclusions.**

1. **The decoder fix is necessary and not sufficient.** It removes a failure
   that made every earlier experiment unscoreable, and it changes nothing about
   the score. Both halves of that are worth stating: the bird stopped flying out
   of the world, and it still cannot pass a pipe.

2. **The failure mode moved.** Before, episodes ended because the bird left
   the screen. Now, at T = 570, the bird sits at mid-screen and still dies at
   46 ticks — into the first pipe. That is the failure the entire sensory line
   was trying to fix, and it is now the only one left.

3. **Result 3 undercuts an assumption nobody had tested.** The haltere loop is
   the harness's one closed feedback path, and across this sweep its output
   moves opposite to the direction the design implies. That is a defect in the
   controller, not in the decoder, and it is cheap to check directly.

**Status: E-DECODE closed on its own question, and it opens a better one.**
The next thing to measure is the sign and gain of the haltere loop itself:
whether fall speed actually raises R, and if not, why. Chasing pipe-avoidance
cues before the altitude controller has the right sign is premature.

---

## Class E-SIGN — does falling faster actually drive more DLM?

**Hypothesis.** The haltere loop is the harness's only closed feedback path.
It injects `A(dy) = m·dy^n` (default m=1.75, n=2) into the haltere afferents,
rectified to zero while level or rising, so the design intent is that a falling
bird gets more current, DLM fires more, and the bird flaps and stops falling.
E-DECODE measured the opposite — the DLM rate fell from 29.8 to 14.0 spikes per
tick as the bird sat lower and fell faster. In the game those arms differ in
fall speed *and* in what the bird is looking at, so this separates them.

**Parameters.** `flappy/run_sign.py`, GPU, frozen weights, 120 ticks per arm.
The visual frame is held fixed at `base_frame()` and only the injected haltere
current changes, so the result is the loop's own transfer characteristic rather
than a confound with the view. Two sweeps: fall speed 0 to the game's terminal
10 px/tick through the real `A(dy)`, and raw current on a flat grid, because
the square law compresses everything interesting into the bottom of the
velocity range.

**Results.** `outputs/flappy_sign/{trials.jsonl,summary.json}`.

| fall speed | injected current | DLM/tick | flap fraction | descending total |
| --- | --- | --- | --- | --- |
| 0 | 0.00 | 0.000 | 0.0000 | 553 |
| 1 | 1.75 | 0.000 | 0.0000 | 553 |
| **2** | **7.00** | **28.658** | 0.9500 | 47,098 |
| 3 | 15.75 | 9.483 | 0.8917 | 47,899 |
| 4 | 28.00 | 7.167 | 0.9083 | 51,031 |
| 5 | 43.75 | 5.825 | 0.8250 | 52,494 |
| 6 | 63.00 | 2.283 | 0.6167 | 55,002 |
| 7 | 85.75 | 1.408 | 0.4667 | 56,938 |
| 8 | 112.00 | 0.533 | 0.2500 | 58,611 |
| 9 | 141.75 | 0.567 | 0.2417 | 59,948 |
| 10 | 175.00 | 0.175 | 0.0917 | 61,033 |

Flat current grid, same frame: 0 DLM at currents 0, 2, 4 and 6; **29.383 at
current 8**, the peak; then 26.233 at 10, 15.275 at 14, 7.633 at 20, 6.358 at
40, 1.267 at 80, 0.192 at 175.

1. **The loop is inverted above its threshold.** DLM output peaks at current
   7–8 and decreases monotonically from there to near silence, a factor of
   **150** between the peak and terminal fall speed.

2. **In the units the game uses, it is positive feedback on falling.** A bird
   falling at 2 px/tick gets maximum flapping; a bird falling at 10 gets almost
   none. Under gravity of 1 px/tick² the bird crosses from 2 to 10 in eight
   ticks, so the loop hands over its entire useful authority almost
   immediately and then actively withdraws it.

3. **Descending activity rises while DLM falls.** Across the same sweep the
   descending total climbs monotonically from 553 to 61,033 spikes. The brain
   is getting busier, not quieter, so the suppression is inhibition being
   recruited onto the motor pool rather than drive failing to arrive. That is
   consistent with E-VPN-FB, where 7 GABAergic VNC interneurons (IN06B077)
   pulled DLM from flap fraction 1.00 to 0.00 on their own.

4. **The summary's own `sign` field is wrong and is kept as a lesson.** It
   compares the endpoints, 0.175 against 0.000, and reports "positive". The
   curve is non-monotone with a peak in the second arm, and only 3 of its 10
   steps rise. An endpoint comparison is not a sign test for a curve that turns
   over.

**Conclusions.**

1. **E-DECODE's anomaly was the controller, not noise.** The DLM rate falling
   as the bird sat lower is exactly what this transfer function produces. It
   was flagged and not chased at the time; chasing it took one experiment.

2. **The usable band is fall speed 2 to 3 and nothing above it.** Every arm
   above dy = 3 produces less flapping than the one below it, which is the
   wrong direction for a stabiliser at every point in the range the bird
   actually occupies.

3. **This is an engineering defect in the joystick, not a finding about
   flies.** `A(dy) = 1.75·dy²` was chosen by interactive search in
   `tune_server.py` and, per its own docstring, is not derived from anything but
   this harness's runs. The square law makes it worse: it reaches the inverted
   region faster than a linear map would.

4. **It also makes the earlier sensory work harder to interpret than it
   looked.** Several classes ran with this loop live underneath them. It does
   not invalidate the visual-drive results, which drove cells directly, but any
   arm whose fall speed varied had an uncontrolled inverted feedback term in it.

**Status: E-SIGN closed.** The fix is cheap and belongs before any further cue
work: clamp the injected current at the peak, or choose m and n so that the
whole reachable fall-speed range maps below it. Re-running E-DECODE's threshold
sweep against a corrected loop is the first thing worth doing afterwards,
because that sweep's operating point moved for this reason.

---

## Class E-FIX — clamp the loop, re-sweep the decoder, and finally score

**Hypothesis.** E-SIGN showed the haltere loop inverts above an injected
current of 7–8 mV, so the bird flapped *less* the faster it fell. Clamping the
current at the measured peak should remove the inversion, hold R stable across
the decoder sweep, and let the threshold set the operating point predictably.

**Engine change.** `haltere_current_for_velocity` gained a `ceiling` argument
defaulting to `CURRENT_CEILING = 8.`, the measured peak.
`A(dy) = min(1.75·dy², 8)`. Passing `ceiling=None` restores the original
unbounded behaviour. With the clamp this is a threshold controller, not a
proportional one: below dy = 2.14 the current is sub-rheobase and produces no
DLM spikes, above it the current pins at the peak. That is forced by the
measurement — E-SIGN found no monotone rising region wide enough to be
proportional over.

**Parameters.** `flappy/run_decode.py`, GPU, frozen weights, real game,
seed 41027, 600 ticks per arm, T over 1/60/120/180/240/300/360/420/480/560.
Then 7 confirmation runs of 2,000 ticks at T = 560 across five seeds.

**Results.** `outputs/flappy_decode/{clamped.jsonl,repeats.jsonl}`.

| T | flap fraction | R (DLM/tick) | longest episode | strikes | cleared |
| --- | --- | --- | --- | --- | --- |
| 1 | 0.9767 | 29.05 | 50 | 1 | 0 |
| 120 | 0.2467 | 29.61 | 50 | 1 | 0 |
| 240 | 0.1217 | 29.23 | 50 | 1 | 0 |
| 360 | 0.0817 | 29.76 | 50 | 1 | 0 |
| 420 | 0.0700 | 29.67 | 56 | 0 | 0 |
| 480 | 0.0617 | 29.81 | 68 | 0 | 0 |
| **560** | **0.0517** | 29.44 | **134** | 0 | **1** |

1. **The clamp fixed R.** It now holds between 28.63 and 29.81 across the
   entire threshold sweep. In the unclamped sweep it collapsed from 29.8 to
   14.0 over the same range. The operating point is stable, so T maps to flap
   fraction the way the arithmetic says it should.

2. **Survival rises monotonically once flap fraction approaches hover.**
   Longest episode is flat at 50 for every arm down to T = 360, then 56, 68 and
   134. The turn happens exactly where flap fraction crosses below about 0.07.

3. **The first pipe was cleared at T = 560**, flap fraction 0.0517 against the
   theoretical hover rate of 0.0526.

4. **It did not reproduce on the immediate re-run.** Same seed, same
   configuration, 0 cleared and a longest episode of 92 instead of 134. The GPU
   backend varies by a few flaps per 600 ticks (a cupy reduction-order effect),
   and at 31 flaps in 600 ticks that is enough to change the trajectory
   entirely.

5. **So the claim is a distribution, not a run.** Seven runs of 2,000 ticks
   across five seeds: **2 pipes cleared in 14,000 ticks, all in one run of
   seven.** Longest episode per run 96, 163, 181, 127, 178, 131, 133 — every
   one above the previous record of 50. Flap fraction 0.0520–0.0525 in all
   seven.

**Conclusions.**

1. **Altitude hold is solved and pipe avoidance is untouched.** The robust
   result is survival: 7 of 7 runs beat the old record, the worst by 1.9x and
   the best by 3.6x. The sparse result is scoring: 6 of 7 runs still clear
   nothing. The bird holds a fixed altitude and does not avoid anything, so a
   pipe clears when a gap happens to line up with the hold altitude. Calling
   this pipe avoidance would be wrong.

2. **Two harness fixes did what five classes of sensory work could not, and
   that is not a compliment to the harness.** Neither change touches the
   connectome, the weights or the plasticity rule. Both repaired defects in the
   engineered joystick — an inverted feedback loop and a decoder that held the
   button down. Those defects were present underneath every earlier experiment
   in this document.

3. **Single runs are not evidence here.** Result 4 is the methodological point
   worth carrying forward: this configuration flaps about 104 times per 2,000
   ticks, so a two-flap difference is a 2% change in the control signal and a
   total change in outcome. Every future claim needs several runs.

4. **The next blocker is informational, not dynamical.** `render3d.py` draws
   only the lower pipe, so the fly cannot see the gap it has to thread even in
   principle. That is now the cheapest remaining item, and it is a rendering
   change rather than another search over drive points.

**Status: E-FIX closed.** Record moved from 0 to 2 pipes cleared, under a
changed harness and at a rate consistent with chance alignment rather than
avoidance. README's "Best known agent" section is updated with the same numbers
and caveats, per `AGENTS.md`.

---

## E-MB-RAND sweep result — executed 2026-09-19

**Parameters.** 21 arms of 2,000 ticks on the CPU physiology kernel: the
reconstructed KC→MBON11 weights, plus 20 shuffled draws. Total wall time about
four hours. `outputs/flappy_mb_rand/sweep.jsonl`.

**Results.**

| | mean absolute change | changed edges |
| --- | --- | --- |
| reconstructed | 0.01476 | 2,013 |
| random, min | 0.01404 | 1,931 |
| random, Q1 | 0.08343 | — |
| random, median | 0.09876 | 1,956 |
| random, Q3 | 0.12797 | — |
| random, max | 0.18622 | 2,023 |

Spearman |rho| against the learned weights: reconstructed arm aside, the 20
shuffles ran 0.015 to 0.173, median 0.122.

**Conclusions.**

1. **The reconstructed weights change less under learning than almost every
   shuffle, but not less than all of them.** At 0.01476 the reconstructed arm
   sits below the random first quartile and above the random minimum of
   0.01404. Exactly one of twenty shuffles moved less.

2. **So the one-sided rank test gives p = 2/21 = 0.095**, which is suggestive
   and not significant at any conventional threshold. The summary's `verdict`
   field says `inconclusive` and that is the correct reading. The runner left
   `one_sided_rank_p` as null; it is computed here rather than left implied.

3. **Twenty draws cannot resolve this.** With 20 shuffles the smallest
   achievable one-sided p is 1/21 = 0.048, so the design had almost no headroom
   to reach significance even if the effect were real. That is a design defect,
   not a finding: the draw count should have been chosen from the p-value it
   could produce.

4. **The result it does support is narrow.** Shuffling genuinely destroys the
   learned structure (median |rho| 0.122, and the gate already showed about
   1,950 of 4,184 edges differ), so the arms are doing what they claim. What is
   unresolved is whether the reconstructed connectivity is *special* with
   respect to how much the plasticity rule moves it.

**Status: E-MB-RAND closed as inconclusive.** Re-running at 100+ draws would
settle it, but see the class below first — there is a structural reason this
may not be worth the compute.

---

## Class E-REACH — can the plastic edges reach the flap decision at all?

**Hypothesis.** Every learning run in this repo makes KC→MBON11 edges plastic,
and `flappy/learn.py`'s own report says "KC→MBON11 has no engineered path to
the DLM cells the flap decision reads." That sentence has been carried in the
outputs as an assertion since the first reward run. It is checkable against the
graph, so it should be checked rather than repeated.

**Method.** Forward breadth-first search from the 2 MBON11 cells over the real
CSR adjacency, and a direct accounting of DLM's presynaptic partners.

**Results.**

1. **MBON11 first reaches DLM at hop 3.** Hop 1 reaches 1,345 cells, hop 2
   reaches 24,902, hop 3 reaches 135,357 and includes all 10 DLM cells.

2. **Hop 3 is 81% of the network.** 135,357 of 166,700 neurons. "Reaches DLM
   in three hops" is not a statement about a pathway; at that fan-out nearly
   everything reaches nearly everything.

3. **There is no short path at all.** DLM has 1,084 direct presynaptic cells
   with a summed |w| of 24,628.7. **Zero** of MBON11's 1,345 first-order
   targets are among them, and MBON11 does not synapse onto DLM itself. The
   share of DLM's anatomical drive contributed by MBON11's immediate targets is
   exactly 0.0000%.

**Conclusions.**

1. **The assertion in the learn.py reports is correct, and stronger than it
   was stated.** It is not merely that no path was engineered — there is no
   two-hop path in the reconstruction either, and the three-hop connection is
   indistinguishable from the network's general connectedness.

2. **So no learning run in this repo can change the flap decision through the
   plastic edges.** Every reward run to date modified 4,184 edges whose
   influence on the controller is, structurally, nil. Weight change was never
   going to become behaviour change along this route.

3. **This reframes E-MB-RAND.** Asking whether randomising KC→MBON11 changes
   play is asking whether randomising a disconnected subgraph changes the
   output. Running it at 100 draws would measure the question more precisely
   without making it a better question.

4. **What would have to change.** Either make something on DLM's actual
   presynaptic list plastic, or insert an engineered path from MBON11 to the
   motor pool and label it as engineered. The first is more honest to the
   connectome and is the one worth designing.

**Status: E-REACH closed.** It answers a question that had been sitting
unexamined in the reports, and it retires the current learning configuration as
a route to a better score.

---

## Class E-LIGHT — the photoreceptor operating point was wrong

**Executed 2026-09-20 in `connectome-sim`; recorded here because it changes
every visual result in this document.**

**The defect.** Luminance reached the network through `30·L/(0.02 + L)`, a
Naka-Rushton curve with a **fixed** semisaturation of 0.02. Measured against a
lit scene whose median receptor luminance is 0.53, that puts every receptor 27x
past semisaturation, on the flat top of the curve.

| luminance | sensitivity (mV per unit L) |
| --- | ---: |
| 0.02 (semisaturation) | 375.00 |
| 0.30 | 5.86 |
| **0.53 (scene median)** | **1.96** |
| 1.00 | 0.58 |

**192x less sensitive at the operating point the scene occupies.** A 44% change
in the picture arrived as a 2.8% change in injected current. `engine.py` already
carried the caveat: "This is NOT a calibrated phototransduction or
light-adaptation model."

**The fix.** `connectome_sim/photoreceptor.py` gains `adapted_drive`; all four
backends call it. Semisaturation follows a slow per-receptor running mean of
luminance (500 ms), floored at the original 0.02. On by default;
`retinal_adaptation_ms=None` restores the fixed constant exactly.

**Effect here.** Re-measuring the record configuration (T=560, clamped haltere
loop) across six runs of 2,000 ticks: flap fraction 0.0520–0.0525 and
**R = 29.12–29.60 spikes/tick, unchanged**. Longest episode rose to 122–235
from 96–181. Pipes cleared: 0 across 12,000 ticks, against 2 across 14,000
before — not a distinguishable difference at those counts, since the earlier
rate predicts about 1.7 events in 12,000 and observing none has probability
0.18.

**Conclusion.** R is set by the haltere injection, not by vision, so fixing the
photoreceptors does not move the score. That is consistent with every class in
this document and is the cleanest confirmation of it: a 4–8x improvement in
early visual signal changed the motor output by nothing measurable.

**Status: E-LIGHT closed.** Results in this document recorded before 2026-09-20
used the fixed constant. Absolute spike counts are not comparable across the
change — receptors now sit near 15 mV rather than pinned near 28 — though the
conclusions all survive it.

**Related.** The same fix in `flybody-connectome` gave 4.0x more signal at the
photoreceptors and 8.1x at the lamina for an approaching object, and left the
looming detectors at exactly zero. See that repo's LOG for 2026-09-20.

---

## Class E-SAPP — what the haltere drive is actually hitting

**Executed 2026-09-20.** A structural analysis, not a simulation run: the
question is what `haltere_afferents` selects and where its output goes.

**What the population is.** `haltere_afferents` returns every cell with
`subclass == 'haltere'`: **205 cells**, all receiving the same injected current
on every tick. `somaSide` and `somaNeuromere` are null for all 205, so there is
no side or segment label at that level. By type it is dominated by one cluster:

| type | cells |
| --- | ---: |
| **SApp** | **148** |
| SNpp34 | 8 |
| SNpp25 | 7 |
| SNpp23 / SNpp35 / SNpp14 / SNpp15 / SNpp20 | 6 each |
| SNpp21 | 4 |
| others / untyped | remainder |

So 72% of the "haltere joystick" is a single type.

**SApp is sided after all, and this corrects an earlier claim in this
document.** `somaSide` is null, but `instance` is not: **SApp_L 75 cells,
SApp_R 73**. Side-differential haltere stimulation is therefore available for
the SApp majority, and was described as unavailable earlier on the basis of
`somaSide` alone. The smaller SNpp types were not re-checked this way.

**It is well reconstructed.** Out-degree median 122, minimum 67, maximum 311,
and **no cell with zero outgoing edges** — unlike the Johnston's-organ
asymmetry that ruled out a phase encoding.

**Where it goes.** Summed |w| over all outgoing edges is 21,865. Top targets:

| target | summed &#124;w&#124; |
| --- | ---: |
| AN08B010 | 669 |
| **SApp** (recurrent) | **625** |
| IN01A031 | 300 |
| IN06B014 | 287 |
| IN06B017 | 277 |
| w-cHIN | 273 |
| IN08B091 | 268 |

The second-largest target is itself: SApp is strongly recurrent.

**And this is the mechanism for the inverted loop.** SApp does not contact DLM
directly — 2,689 cells at one hop, none of them DLM. But of DLM's **1,084**
direct presynaptic cells, **207 are SApp's one-hop targets**, carrying
**2,687 of DLM's 24,629 total drive — 10.9%**. Signed:

| | summed weight onto DLM |
| --- | ---: |
| excitatory | +1,426 |
| inhibitory | −1,261 |
| **net** | **+164** |

**The haltere pathway is push-pull onto the motor pool, and it nearly
cancels.** 6% net from 100% of the magnitude. That is exactly the shape that
produces E-SIGN's 150-fold inversion: two opposed arms in near-balance, with
different effective thresholds, so which one dominates depends on drive level
and the net can change sign across the range. It is not a weak stabiliser that
happens to be backwards; it is a balanced circuit whose balance point the drive
sweeps through.

**Conclusions.**

1. **Driving all 205 cells uniformly drives both arms at once**, which is the
   worst possible way to use a push-pull circuit. Any useful haltere channel
   has to break that symmetry — by side (now known to be possible for SApp), by
   type, or by targeting the excitatory arm's interneurons specifically.

2. **The near-cancellation explains why amplitude was never a knob.** The net
   is a small difference of two large numbers, so it is dominated by whichever
   arm's recruitment curve is steeper at the current operating point.

3. **The `IN06B` family appears on both lists.** IN06B014 and IN06B017 are
   among SApp's largest targets; IN06B077 is the 7-cell set E-VPN-FB found
   could pull DLM from flap fraction 1.00 to 0.00 on its own. Whether SApp
   reaches IN06B077 specifically, and with what weight, is the obvious next
   query.

**Caveat.** This annotation set carries no neurotransmitter column, so
excitatory and inhibitory here mean the sign of the reconstructed weight, which
is assigned per cell from a transmitter label upstream of this repo. The
standing caveat about sign applies unchanged.

**Status: E-SAPP closed as a structural result.** It gives the first mechanistic
account of the inverted haltere loop and it names the correction that follows:
stop driving 205 cells with one number.

---

## Class E-GF — fire the giant fibre by hand

**Hypothesis.** E-SWAT showed the escape circuit never activates from an
approaching object: the looming detectors stay at zero and DNp01 never fires.
That is a statement about the *input* half. Nothing in this project had ever
fired DNp01, so the output half was untested. Fire it directly.

**Anatomy, measured on this graph.** DNp01 is 2 cells with out-degree 313 and
342. It synapses directly onto **TTMn**, the tergotrochanteral motor neuron
that drives the jump, summed |w| **25**. It does **not** synapse onto DLM,
which is correct: the giant fibre triggers the leg jump, and the power muscles
are driven separately.

**Parameters.** `flappy/run_gf.py`, GPU, frozen weights, blank frame, 60 ticks
per arm, current injected into the 2 DNp01 cells only.

**Results.** `outputs/flappy_gf/`. Per tick:

| current | DNp01 | TTM | DLM | leg motor | all VNC motor | descending |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0–7 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.3 |
| 8 | 1.50 | **0.00** | 0.00 | 0.00 | 0.00 | 5.8 |
| 10 | 2.53 | **0.00** | 0.00 | 0.00 | 0.00 | 6.8 |
| 14 | 4.57 | **0.00** | 0.00 | 0.00 | 0.00 | 9.7 |
| 20 | 6.53 | **0.90** | 0.00 | 0.18 | 3.72 | 12.5 |
| 40 | **0.63** | 2.27 | 25.48 | 54.72 | 248.43 | 378.4 |

1. **The link is real.** Firing DNp01 does recruit TTM. The escape pathway is
   intact from the giant fibre down, so the swatter null is genuinely an input
   failure rather than a circuit that does not exist.

2. **It is expensive.** DNp01 has to reach about 6.5 spikes per tick before TTM
   responds at all. At 1.5, 2.5 and 4.6 spikes per tick the jump muscle stays at
   exactly zero. A 2-cell to 2-cell connection with summed |w| 25 is thin
   against DLM's 24,629 of total presynaptic drive, and it shows.

3. **Pushing harder collapses the giant fibre itself.** At current 40, DNp01's
   own rate falls to 0.63 while everything downstream explodes — DLM 25.5, leg
   motor 54.7, all VNC motor 248.4, descending 378.4. That is the saturated
   attractor of E-LATCH, and the same recruitment-of-inhibition signature
   E-SIGN found in the haltere pathway: the driven cell goes quiet while the
   network lights up.

**Conclusions.**

1. **The escape pathway is intact downstream and unreachable upstream.**
   Combined with E-SWAT this localises the whole failure: photoreceptors see an
   approaching object, the visual projection layer does not pass it on, the
   looming detectors never fire, but if the giant fibre is fired by hand the
   jump muscle does respond.

2. **The operating window is narrow and on the wrong side of saturation.** TTM
   first responds at current 20, and by 40 the network is in the attractor. So
   the usable band is roughly 20–40 and it sits above, not below, the regime
   where the rest of the motor pool stays quiet.

3. **This is the first place a named behavioural circuit has been driven
   end-to-end in this project**, even if only by injecting into its final
   descending stage.

**Status: E-GF closed.** The obvious follow-up is embodied: fire DNp01 in
`flybody-connectome` with the leg motor map active and measure whether the body
actually leaves the ground, which is what TTM recruitment is supposed to mean.

---

## Class E-DOPA — does a calibrated dopamine pulse or a different trigger population change the E-REACH null?

**Hypothesis.** E-REACH established that the plastic KC->MBON11 edges have
zero overlap with DLM's presynaptic set -- no learning along that route can
change flap behaviour. Every prior learning run used PPL101 current pulses
and sugar-cell reward with invented magnitudes (`flappy/training.py`:
"+4 mV-equivalent", "+30"). This asks two further questions disconnection
alone doesn't settle: does a completely different aversive trigger
population (heat/thermosensory instead of PPL101 directly), or a
biologically-calibrated dopamine pulse (Huang et al. 2024's own measured
shock-evoked PPL101 rate, not an invented current), change the behavioural
null? And separately: is the plastic weight trajectory actually driven by
the reward/punishment events it's gated on, or by something else?

**Parameters.** Fresh `GPUMemoryBrain` per condition (state not carried
over between conditions, unlike `flappy/learn.py`'s standing convention --
this class isolates condition effects). Each brain calibrated to Huang et
al. 2024's measured baseline (`connectome_sim.physiology.calibration.
calibrated_brain`'s own tonic: MB 9.87 mV, DAN 11.3125 mV, `dan_baseline_hz`
20.09). Aversive event (ground/ceiling contact, or a pipe strike where
pipes are present): thermosensory cells (`class=='thermosensory'`, 25
cells) at 20 mV, paired with a PPL101 pulse at 4.5 mV -- calibrated
in-session by sweeping pulse current against
`connectome-sim/research/huang-2024/targets.json`'s `PPL101_shock` target
(mean 50.14 Hz): 4.5 mV on top of the tonic baseline gives 50.00 Hz, a near
exact match. 6,000 ticks (~200 s) per condition. Four conditions: pipes +
haltere reflex on; no pipes + haltere on; no pipes + haltere off + dark
retina; no pipes + haltere off + real `game.pixels()` visual input.

**Metrics.** Episode-length survival (`early_mean`/`late_mean`/`gain`,
matching `flappy/learn.py`'s own `survival()`), pipe strikes/clears, DLM
total spikes, and `brain.memory()`'s plastic-edge change count and mean
efficacy before/after.

**Results.**

| condition | dopamine pulses delivered | episode lengths | edges changed | mean efficacy |
| --- | ---: | --- | ---: | ---: |
| pipes + haltere | 120 | all 120 episodes exactly 50 ticks, gain 0.0 | 2,009 | 0.928 |
| no pipes + haltere | 0 (never crashed) | 6,000/6,000, no crash | 2,042 | **0.940** |
| no pipes, no haltere, dark | 1 | [31, 5969] | 1,993 | 0.885 |
| no pipes, no haltere, real vision | 1 | **[31, 5969]** | 2,013 | 0.889 |

An uncalibrated pilot (invented thermosensory-only aversive, no dopamine
pulse, zero tonic/`dan_baseline_hz`) produced the identical episode lengths
in every one of these four conditions -- see
`connectome-lab/findings/10-the-teacher-does-not-move-the-hand.md` for that
comparison table.

**Conclusions.**

1. **Behaviour is unchanged from the uncalibrated pilot, condition for
   condition.** Using the real paper-calibrated dopamine pulse instead of an
   invented current, and a completely different sensory trigger (heat)
   instead of driving PPL101 directly, rules out "the stimulus was just too
   weak or badly tuned" as an explanation for E-REACH's null. It is the
   topology, not the magnitude.

2. **Real, dynamically-changing visual input during actual gameplay
   produces literally identical episode lengths to permanent darkness** --
   [31, 5969] both times, to the tick. Independent confirmation of
   `findings/01-vision-stops-at-the-descending-neurons.md` and
   `findings/08-the-swatter.md` from a new angle: a live game frame, not
   just an injected or naturally-lit static scene, still doesn't reach
   anything that matters within this timeframe.

3. **Weight change tracks whether the haltere reflex is active, not how many
   conditioning events fired.** 0 dopamine pulses (no-pipes+haltere)
   produces *less* depression than 120 (pipes+haltere), which produces less
   than 1 (no-haltere conditions). The plastic weight trajectory is not
   responding to the reward/punishment signal it's supposedly gated on --
   it's responding to whatever ambient KC/DAN activity level the rest of the
   network sits at.

4. **The dopamine baseline matters for interpreting past runs.** This run's
   depression (mean efficacy 0.885-0.940) is milder than the uncalibrated
   pilot's (0.862-0.880), most likely because the pilot left
   `dan_baseline_hz` at its zero default -- computing the anti-Hebbian error
   term against a biologically wrong zero dopamine baseline instead of
   Huang et al.'s measured ~20 Hz tonic rate. The qualitative conclusion
   (weight change insensitive to reward timing) holds under either baseline;
   the magnitude does not.

**Status: E-DOPA closed, negative on both questions.** No dopamine
calibration or trigger-population change reaches DLM, and the plasticity
mechanism's own weight trajectory does not track the conditioning signal it
is gated on. Two independent, sufficient reasons this mechanism has never
produced learned behaviour, now confirmed together in one run.
