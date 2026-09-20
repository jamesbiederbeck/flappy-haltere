"""Standalone Flappy Bird learning-run driver: dopamine-gated KC->MBON11
plasticity enabled (doom_learning_v6's rule and VisualMemoryBrain, reused
unmodified), driven by a two-valence reward model -- a sugar pulse when the
bird clears a pipe without touching it, a PPL101 dopamine pulse when it
strikes one or crashes. See flappy/training.py for the currents, the
windows, and why neither is a measured quantity.

Nothing about the reward model is learned: it is two fixed event->current
mappings. The only learning is the existing plasticity rule.

The brain is never reset. A crash resets the game (game.new_episode()) and
the brain object, its weights, its traces and any pulse in flight all carry
straight through into the next episode -- this repo's standing convention,
and the reason FlapTraining.new_round() cancels nothing.

Weights genuinely change over a run (see the final memory() delta below);
there is no established path from KC->MBON11 to the DLM wing motor neurons
flappy.circuit.wing_motor_readouts reads for the flap decision, so this does
not and cannot demonstrate improved flap timing or survival -- adding an
appetitive channel does not change that. Same "mechanism enabled, not
validated" stance as doom/training.py and the v6 README. The survival
statistics below are reported so the null result is on the record, not
because a gain is expected.

--fallback-after runs the second phase the reward model was asked to fall
back to: if survival has not improved by then, pipes stop terminating the
episode (flappy.game.Game(pipes_terminate=False)) and the simulation runs
continuously from that point, with the brain again carried over unbroken.
Pipe strikes still fire the aversive pulse; only the reset goes away.

This is a local script, not a server -- no checkpointing or audit-archive
machinery, matching flappy/play.py's scope.
"""
import argparse
import json
import sys
import time
from pathlib import Path
import numpy as np
from connectome_sim.physiology.calibration import calibrated_brain
from flappy.circuit import haltere_afferents, haltere_current_for_velocity, wing_motor_readouts
from flappy.controls import FlapControls
from flappy.game import Game, FPS
from flappy.training import FlapTraining

ROOT = Path(__file__).resolve().parents[1]


def survival(lengths):
    """Mean ticks survived over the first and last third of the episodes --
    the crudest before/after split that does not need a model. Fewer than
    six episodes is not enough to halve, so it reports None rather than a
    number that would read as evidence."""
    if len(lengths) < 6: return {'episodes': len(lengths), 'early_mean': None, 'late_mean': None, 'gain': None}
    third = len(lengths) // 3
    early = float(np.mean(lengths[:third])); late = float(np.mean(lengths[-third:]))
    return {'episodes': len(lengths), 'early_mean': round(early, 2), 'late_mean': round(late, 2),
            'gain': round(late - early, 2)}


def phase(game, training, brain, controls, haltere, dlm, ticks, seconds, haltere_m, haltere_n,
          name='', progress_every=100):
    """One phase of the run, bounded by whichever of ticks/seconds comes
    first. The brain and training adapter are passed in and never rebuilt --
    a phase boundary is a game-side change only."""
    duration_ms = 1000 / FPS
    lengths, flaps, dlm_spikes, tick = [], 0, 0, 0
    strikes = clears = 0
    start = time.perf_counter()
    while (ticks is None or tick < ticks) and (seconds is None or time.perf_counter() - start < seconds):
        before = game.observation()
        if before['finished']:
            lengths.append(before['tick'])
            game.new_episode()
            training.new_round()   # does not touch the brain; see its docstring
            before = game.observation()
        frame = game.pixels()
        current = haltere_current_for_velocity(before['y_velocity'], m=haltere_m, n=haltere_n)
        haltere_stim = (haltere, current) if current > 0 else None
        counts, _ = training.step(frame, duration_ms, haltere_stimulation=haltere_stim)
        action = controls.decode(counts, duration_ms / 1000)
        flaps += int(action['flap'])
        dlm_spikes += int(counts[dlm].sum())
        game.act(action['flap'])
        after = game.observation()
        strikes += int(after['struck_pipe']); clears += int(after['cleared_pipe'])
        # Aversive on any pipe contact, not only a terminal one: with
        # pipes_terminate=False a strike no longer ends the episode, and the
        # signal has to survive that change for the two phases to be comparable.
        training.observe(after['struck_pipe'] or after['finished'], after['cleared_pipe'])
        tick += 1
        # Live line so the two questions that decide whether the run is worth
        # anything -- is it progressing, is the sugar channel ever firing --
        # are answerable without waiting for the final report.
        if progress_every and tick % progress_every == 0:
            print(f'[{name}] tick {tick} episodes {len(lengths)} strikes {strikes} '
                  f'cleared {clears} elapsed {time.perf_counter() - start:.0f}s',
                  file=sys.stderr, flush=True)
    lengths.append(game.observation()['tick'])
    wall = time.perf_counter() - start
    return {'ticks': tick, 'wall_seconds': round(wall, 3),
            'ticks_per_second': round(tick / wall, 3) if wall > 0 else None,
            'flaps': flaps, 'dlm_spikes': dlm_spikes,
            'pipe_strikes': strikes, 'pipes_cleared': clears,
            'episode_lengths': lengths, 'survival': survival(lengths),
            'memory': training.telemetry()}


def report_text(report):
    return json.dumps(report, indent=2)


def run(ticks, seed, eta, learning, haltere_m, haltere_n, no_pipes, perspective=True,
        reward=True, seconds=None, fallback_after=None, gain_threshold=1., out=None):
    brain = calibrated_brain(eta=eta)
    training = FlapTraining(brain, enabled=learning, reward=reward)
    haltere = haltere_afferents(brain)
    readouts = wing_motor_readouts(brain)
    controls = FlapControls(readouts)
    dlm = np.array([r['index'] for r in readouts], dtype=np.int32)
    game = Game(seed=seed, no_pipes=no_pipes, perspective=perspective)
    memory_before = training.telemetry()
    first_limit = fallback_after if fallback_after is not None else seconds
    phases = [{'name': 'resetting', 'pipes_terminate': True,
               **phase(game, training, brain, controls, haltere, dlm,
                       ticks, first_limit, haltere_m, haltere_n, 'resetting')}]
    fell_back = False

    def assemble(complete):
        return {
            'seed': seed, 'eta': eta, 'learning': learning, 'reward': reward,
            'haltere_m': haltere_m, 'haltere_n': haltere_n, 'no_pipes': no_pipes,
            'perspective': perspective, 'fallback_after': fallback_after,
            'gain_threshold': gain_threshold, 'fell_back': fell_back,
            'complete': complete, 'phases': phases,
            'memory_before': memory_before, 'memory_after': training.telemetry(),
            'weights_changed': training.telemetry()['changed_edges'] > 0,
            'interpretation': 'Weight change is the mechanism running, not evidence of improved play. '
                              'KC->MBON11 has no engineered path to the DLM cells the flap decision reads.',
        }

    def flush(complete):
        # Phase 1 is a result in its own right -- whether a gain appeared, and
        # whether the sugar channel ever fired. Write it before the second
        # phase starts so an hour of work cannot be lost to a later crash.
        if out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(report_text(assemble(complete)) + '\n')
    flush(fallback_after is None)
    if fallback_after is not None:
        gain = phases[0]['survival']['gain']
        fell_back = gain is None or gain < gain_threshold
        flush(not fell_back)
        if fell_back:
            # Same brain, same weights, same traces -- only the game changes.
            game.close()
            game = Game(seed=seed, no_pipes=no_pipes, perspective=perspective, pipes_terminate=False)
            remaining = None if seconds is None else max(0., seconds - phases[0]['wall_seconds'])
            phases.append({'name': 'continuous', 'pipes_terminate': False,
                           **phase(game, training, brain, controls, haltere, dlm,
                                   ticks, remaining, haltere_m, haltere_n, 'continuous')})
    game.close()
    report = assemble(True)
    flush(True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ticks', type=int, default=600, help='Per-phase tick budget; --seconds may end a phase sooner')
    p.add_argument('--seconds', type=float, default=None, help='Wall-clock budget for the whole run')
    p.add_argument('--fallback-after', type=float, default=None,
                    help='Seconds of resetting play before, absent a survival gain, pipes stop terminating the episode')
    p.add_argument('--gain-threshold', type=float, default=1.,
                    help='Ticks of mean-survival improvement that counts as a gain and cancels the fallback')
    p.add_argument('--seed', type=int, default=41027)
    p.add_argument('--eta', type=float, default=.001)
    p.add_argument('--learning', dest='learning', action='store_true', default=True)
    p.add_argument('--no-learning', dest='learning', action='store_false',
                    help='Freeze weights (control run): traces still decay, nothing is written')
    p.add_argument('--no-reward', dest='reward', action='store_false', default=True,
                    help='Aversive channel only (control run): no sugar pulse on a cleared pipe')
    p.add_argument('--haltere-m', type=float, default=1.75)
    p.add_argument('--haltere-n', type=float, default=2.)
    p.add_argument('--no-pipes', action='store_true')
    p.add_argument('--flat', dest='perspective', action='store_false', default=True,
                    help="Feed the game's own side-on camera instead of the bird's first-person view")
    p.add_argument('--out', type=Path, default=None, help='Write the report here as well as to stdout')
    args = p.parse_args()
    ticks = None if args.seconds or args.fallback_after else args.ticks
    report = run(ticks, args.seed, args.eta, args.learning, args.haltere_m, args.haltere_n,
                 args.no_pipes, args.perspective, args.reward, args.seconds,
                 args.fallback_after, args.gain_threshold, args.out)
    print(report_text(report))


if __name__ == '__main__':
    main()
