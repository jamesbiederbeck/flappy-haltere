"""Experiment class E-DOPA: does a biologically-calibrated dopamine pulse,
paired with a heat/thermosensory aversive, change anything E-REACH's
disconnection finding didn't already predict?

E-REACH (docs/sensory-encoding-experiments.md, and connectome-lab/findings/
05-plasticity-cannot-reach-the-controller.md) established that the KC->MBON11
plastic edges have zero overlap with DLM's presynaptic set -- no amount of
learning along that route can change flap behaviour. Every prior learning run
(doom_learning_v6, flappy/learn.py) used PPL101 current pulses and sugar-cell
reward with invented magnitudes. This class asks two further questions that
disconnection alone doesn't answer:

  1. Does using a completely different trigger population (heat/thermosensory
     instead of PPL101 directly) or a biologically-calibrated dopamine pulse
     (Huang et al. 2024's own measured shock-evoked PPL101 rate, not an
     invented current) change the behavioural null? (No -- see conditions
     1-4 below; episode lengths are unchanged from an uncalibrated pilot.)
  2. Is the plastic weight trajectory actually driven by the reward/punishment
     events it's gated on, or by something else? (No -- weight change tracks
     whether the haltere reflex is active, not how many conditioning events
     fired: 0 pulses produces MORE depression than 120 in the matched-haltere
     comparison.)

Fresh GPUMemoryBrain per condition (no state carried over, unlike flappy/
learn.py's standing convention -- this class is about isolating condition
effects, not about a continuous run). Aversive event: thermosensory cells
(class=='thermosensory', 25 cells in this graph) at 20 mV, paired with a
PPL101 (DAN) pulse at 4.5 mV -- calibrated in-session against
connectome-sim/research/huang-2024/targets.json's PPL101_shock target
(mean 50.14 Hz) on top of connectome_sim.physiology.calibration.
calibrated_brain's own tonic baseline (MB 9.87 mV, DAN 11.3125 mV,
dan_baseline_hz 20.09), empirically found to produce 50.00 Hz -- see
run_calibration_sweep() below for the sweep that found it.

No appetitive/NPF channel here: none of the four conditions ever score a
pipe (clears=0 throughout), so an appetitive trigger would be untested by
construction, not tested-and-null. That is a separate, open experiment.
"""
import argparse
import json
import numpy as np
from connectome_sim.physiology.gpu_brain import GPUMemoryBrain
from connectome_sim.physiology.common import annotations
from connectome_sim.photoreceptor import retinal_samples
from flappy.game import Game, FPS
from flappy.circuit import haltere_afferents, haltere_current_for_velocity, wing_motor_readouts
from flappy.controls import FlapControls

AVERSIVE_CURRENT = 20.0     # thermosensory, invented, order of E-SIGN's DLM-response range
DOPAMINE_PULSE = 4.5        # calibrated against Huang 2024's PPL101_shock target (see module docstring)
PULSE_MS = 200.0
TICKS = 6000


def run_calibration_sweep():
    """Reproduces the in-session sweep that found 4.5 mV -> 50.00 Hz against
    a 50.14 Hz target. Not run by default; call directly to re-derive."""
    results = []
    for pulse in [4.0, 4.5, 5.0, 5.5, 6.0, 8.0]:
        b = GPUMemoryBrain()
        b.tonic[b.circuit['mb']] = 9.87
        b.tonic[b.circuit['dan']] = 11.3125
        b.dan_baseline_hz[:] = 20.09
        dark = np.zeros(len(b.retina), dtype=np.float32)
        b.step(dark, 500.0, learning=False)
        dan_idx = b.circuit['dan']
        stim = (np.asarray(dan_idx, dtype=np.int64), np.full(len(dan_idx), pulse, dtype=np.float32))
        counts, _ = b.step(dark, 200.0, learning=False, stimulation=stim)
        hz = float(np.asarray(counts)[dan_idx].mean()) / 0.2
        results.append({"pulse_mv": pulse, "ppl101_hz": hz})
    return results


def survival(lengths):
    if len(lengths) < 6:
        return {"episodes": len(lengths), "early_mean": None, "late_mean": None, "gain": None, "lengths": lengths}
    third = len(lengths) // 3
    early, late = float(np.mean(lengths[:third])), float(np.mean(lengths[-third:]))
    return {"episodes": len(lengths), "early_mean": round(early, 2), "late_mean": round(late, 2),
            "gain": round(late - early, 2), "min": int(min(lengths)), "max": int(max(lengths))}


def run_condition(pipes, haltere, vision):
    brain = GPUMemoryBrain()  # fresh -- no carried-over state between conditions
    brain.tonic[brain.circuit['mb']] = 9.87
    brain.tonic[brain.circuit['dan']] = 11.3125
    brain.dan_baseline_hz[:] = 20.09
    ids = brain.ids
    ann = annotations(ids)
    thermosensory = np.flatnonzero((ann["class"] == "thermosensory").to_numpy()).astype(np.int64)
    dan_idx = np.asarray(brain.circuit['dan'], dtype=np.int64)

    haltere_idx = haltere_afferents(brain) if haltere else None
    dlm_readouts = wing_motor_readouts(brain)
    dlm = np.asarray([r['index'] for r in dlm_readouts], dtype=np.int64)
    controls = FlapControls(dlm_readouts)
    game = Game(no_pipes=not pipes)
    dark = np.zeros(len(brain.retina), dtype=np.float32)
    duration_ms = 1000.0 / FPS

    aversive_until = 0
    lengths, strikes, clears, dlm_spikes = [], 0, 0, 0
    mem0 = brain.memory()

    for tick in range(TICKS):
        before = game.observation()
        if before['finished']:
            lengths.append(before['tick'])
            game.new_episode()
            before = game.observation()

        stim = []
        if haltere:
            current = haltere_current_for_velocity(before['y_velocity'])
            if current > 0:
                stim.append((haltere_idx, np.full(len(haltere_idx), current, dtype=np.float32)))
        if tick < aversive_until:
            stim.append((thermosensory, np.full(len(thermosensory), AVERSIVE_CURRENT, dtype=np.float32)))
            stim.append((dan_idx, np.full(len(dan_idx), DOPAMINE_PULSE, dtype=np.float32)))

        lum = retinal_samples(game.pixels(), brain.uv) if vision else dark
        counts, _ = brain.step(lum, duration_ms, learning=True, stimulation=stim if stim else None)
        counts = np.asarray(counts)
        action = controls.decode(counts, duration_ms / 1000)
        dlm_spikes += int(counts[dlm].sum())
        game.act(action['flap'])
        after = game.observation()
        aversive_event = after['finished'] or (pipes and after['struck_pipe'])
        if aversive_event:
            aversive_until = tick + round(PULSE_MS / duration_ms)
            strikes += 1
        if pipes and after['cleared_pipe']:
            clears += 1

    lengths.append(game.observation()['tick'])
    mem1 = brain.memory()
    return {
        "protocol": {"ticks": TICKS, "pipes": pipes, "haltere": haltere, "vision": vision,
                    "aversive": "thermosensory 20mV + PPL101 dopamine 4.5mV (Huang 2024 shock-calibrated), paired",
                    "tonic_calibration": "Huang 2024 baseline (MB 9.87mV, DAN 11.3125mV, dan_baseline_hz 20.09)",
                    "backend": "fresh GPUMemoryBrain, learning=True"},
        "strikes": strikes, "clears": clears, "dlm_spikes_total": dlm_spikes,
        "survival": survival(lengths), "memory_before": mem0, "memory_after": mem1,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pipes", action="store_true")
    p.add_argument("--haltere", action="store_true")
    p.add_argument("--vision", action="store_true")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    result = run_condition(args.pipes, args.haltere, args.vision)
    print(json.dumps(result, indent=2))
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
