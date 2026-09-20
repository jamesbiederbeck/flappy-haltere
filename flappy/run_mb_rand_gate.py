"""E-MB-RAND gate run: is shuffling the reconstructed KC->MBON11 weights a
no-op for the learning rule?

Verified in source before running. rule.py:31 computes
  drive = eta*(kc_hz*(gain.T@dmid) - (gain.T@dan_hz)*kmid)
which never reads baseline_plastic. kernel.cpp reads baseline_weight in
exactly one place (line 77, an LTD floor clamp) inside a block gated on
learning_enabled -- and brain.py:125 always calls _neural_step with
learning=False, so that block never executes. The reconstructed weight
values therefore reach the learned pattern only through the closed loop:
weight[edges] = baseline_plastic*(1+memory_w) changes MBON11's synaptic
drive, which changes network activity, which changes the KC and DAN rates
the rule does read.

So there are three possible outcomes and they are declared before running:
  bit-identical      -> scheme A is a no-op; the sweep would be 7 hours of
                        nothing, and the class's result is that finding.
  below float32 noise-> report the magnitude and decide.
  material difference-> the closed loop carries the weights; run the sweep.

Arms are tick-matched (the executed run this repeats was wall-clock bounded,
so its 6,323/6,025 tick counts are not a budget to copy). No checkpoints are
written: MemoryBrain computes initial_weight_sha256 before any harness-side
randomization, so a randomized brain would otherwise checkpoint a digest
asserting reconstructed provenance.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.calibration import calibrated_brain
from flappy.circuit import haltere_afferents, haltere_current_for_velocity, wing_motor_readouts
from flappy.controls import FlapControls
from flappy.dlm_pair_sweep import Log
from flappy.game import Game, FPS
from flappy.training import FlapTraining

ROOT = Path(__file__).resolve().parents[1]


def arm(ticks, seed, shuffle_seed=None):
    brain = calibrated_brain(eta=.001)
    edges = brain.circuit['edges']
    if shuffle_seed is not None:
        rng = np.random.default_rng(shuffle_seed)
        perm = rng.permutation(len(brain.baseline_plastic))
        # Order matters: reset() restores weight[edges] from baseline_plastic.
        brain.baseline_plastic = brain.baseline_plastic[perm].copy()
        brain.weight[edges] = brain.baseline_plastic
    before = float(brain.baseline_plastic.sum())
    training = FlapTraining(brain, enabled=True, reward=True)
    haltere = haltere_afferents(brain)
    readouts = wing_motor_readouts(brain)
    controls = FlapControls(readouts)
    game = Game(seed=seed)
    duration_ms = 1000 / FPS
    for _ in range(ticks):
        obs = game.observation()
        if obs['finished']:
            game.new_episode(); training.new_round(); obs = game.observation()
        current = haltere_current_for_velocity(obs['y_velocity'])
        stim = (haltere, current) if current > 0 else None
        counts, _ = training.step(game.pixels(), duration_ms, haltere_stimulation=stim)
        game.act(controls.decode(counts, duration_ms / 1000)['flap'])
        after = game.observation()
        training.observe(after['struck_pipe'] or after['finished'], after['cleared_pipe'])
    memory_w = np.asarray(brain.memory_w).copy()
    telemetry = training.telemetry()
    game.close()
    return memory_w, telemetry, before


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ticks', type=int, default=200)
    p.add_argument('--seed', type=int, default=41027)
    p.add_argument('--shuffle-seed', type=int, default=0)
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_mb_rand/gate.jsonl'))
    args = p.parse_args()

    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-MB-RAND',
        'stage': 'gate', 'started': datetime.now(timezone.utc).isoformat(),
        'ticks': args.ticks, 'game_seed': args.seed, 'shuffle_seed': args.shuffle_seed,
        'doc': 'docs/sensory-encoding-experiments.md#class-e-mb-rand'})

    ref_w, ref_t, ref_sum = arm(args.ticks, args.seed)
    log.write({'record': 'arm', 'run_id': run_id, 'arm': 'reconstructed',
               'baseline_sum': ref_sum, **{k: ref_t[k] for k in
               ('changed_edges', 'mean_efficacy', 'mean_absolute_change',
                'maximum_efficacy', 'minimum_efficacy')}})
    rnd_w, rnd_t, rnd_sum = arm(args.ticks, args.seed, shuffle_seed=args.shuffle_seed)
    log.write({'record': 'arm', 'run_id': run_id, 'arm': f'shuffled_{args.shuffle_seed}',
               'baseline_sum': rnd_sum, **{k: rnd_t[k] for k in
               ('changed_edges', 'mean_efficacy', 'mean_absolute_change',
                'maximum_efficacy', 'minimum_efficacy')}})

    identical = bool(np.array_equal(ref_w, rnd_w))
    diff = np.abs(ref_w - rnd_w)
    verdict = ('bit_identical' if identical else
               'below_float32_noise' if float(diff.max()) < 1e-6 else 'material')
    out = {'record': 'gate_result', 'run_id': run_id, 'verdict': verdict,
           'bit_identical': identical,
           'baseline_sum_conserved': abs(ref_sum - rnd_sum) < 1e-3,
           'max_abs_diff': float(diff.max()), 'mean_abs_diff': float(diff.mean()),
           'differing_edges': int((diff > 0).sum()), 'plastic_edges': int(len(ref_w)),
           'reconstructed_mean_absolute_change': ref_t['mean_absolute_change'],
           'shuffled_mean_absolute_change': rnd_t['mean_absolute_change'],
           'spearman_note': 'computed in the sweep, not the gate'}
    log.write(out); log.close()
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
