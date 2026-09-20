"""Experiment class E-PULSE: rate-coded haltere drive instead of a DC current.

Every stimulation in this project has been a constant current held for a whole
game tick. E-VIS-INV explains why that can never be a knob: spike threshold is a
hardcoded global constant, so a cell under steady injected current either never
fires or fires, with no intermediate rate to ride. Sweeping amplitude finer does
not help, and E-BAND spent a class establishing that.

A pulse train has a control variable that curve does not: **rate**. Each pulse is
still all-or-nothing, but pulses per second is continuous, and the postsynaptic
membrane integrates them. That is how a real haltere afferent encodes -- spikes
locked to the stroke, not a DC offset -- and it is the one input parameterisation
this project has never tried.

The comparison that matters is against the same *mean* current. A 250 Hz train
of 1 ms pulses at 8 mV delivers a mean of 2 mV; so does a constant 2 mV. If the
two produce the same DLM output, rate coding buys nothing here and the wall is
downstream. If the pulsed arm produces more, or produces a graded response where
the constant arm is a switch, then the drive parameterisation was the problem and
not the network.

Amplitude is fixed at 8 mV throughout, the peak E-SIGN measured, so that every
pulse is supra-threshold and only rate varies.

Frozen weights, GPU.
"""
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from connectome_sim.physiology.common import digest
from connectome_sim.photoreceptor import retinal_samples
from flappy.circuit import haltere_afferents
from flappy.dlm_pair_sweep import Log
from flappy.inverse_data import reset
from flappy.sensory_probe import TICK_MS, base_frame, readouts

ROOT = Path(__file__).resolve().parents[1]
RATES = [0., 10., 25., 50., 75., 100., 150., 200., 250., 300.]


def pulsed(brain, lum, groups, cells, amplitude, rate_hz, pulse_ms, ticks):
    """Run `ticks` game ticks with a pulse train, cutting each tick at every
    pulse edge so the kernel sees the drive switch on and off."""
    reset(brain)
    totals = {k: 0 for k in groups}
    network, dlm_per_tick = 0, []
    period = (1000. / rate_hz) if rate_hz > 0 else None
    phase = 0.  # ms since the last pulse onset, carried across ticks
    for _ in range(ticks):
        t, dlm_this_tick = 0., 0
        while t < TICK_MS - 1e-9:
            if period is None:
                on, span = False, TICK_MS - t
            else:
                on = phase < pulse_ms
                # Time until this pulse ends, or until the next one starts.
                span = (pulse_ms - phase) if on else (period - phase)
            span = min(span, TICK_MS - t)
            if span <= 1e-9:
                phase = 0.; continue
            stim = [(cells, amplitude)] if on else None
            counts, _ = brain.step(lum, span, stimulation=stim)
            counts = np.asarray(counts)
            network += int(counts.sum())
            for k, idx in groups.items():
                totals[k] += int(counts[idx].sum())
            dlm_this_tick += int(counts[groups['dlm']].sum())
            t += span
            if period is not None:
                phase = (phase + span) % period
        dlm_per_tick.append(dlm_this_tick)
    duty = (rate_hz * pulse_ms / 1000.) if rate_hz > 0 else 0.
    return {'network_spikes': network,
            **{f'{k}_total': v for k, v in totals.items()},
            'dlm_per_tick': round(totals['dlm'] / ticks, 3),
            'dlm_flap_fraction': round(sum(1 for c in dlm_per_tick if c > 0) / ticks, 4),
            'duty_cycle': round(duty, 5),
            'mean_current': round(amplitude * duty, 4)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['native', 'gpu'], default='gpu')
    p.add_argument('--ticks', type=int, default=60)
    p.add_argument('--fixed-amplitude', type=float, default=None,
                   help='Hold pulse amplitude here and let the mean follow the '
                        'rate. This is the actual rate-code test: every pulse is '
                        'supra-threshold by construction, so the only variable '
                        'left is how many arrive per second. Sweeping --means '
                        'instead forces amplitude down as rate rises, which '
                        'measures pulse size rather than rate.')
    p.add_argument('--means', type=float, nargs='+', default=[2., 4., 8., 16.],
                   help='target mean current per arm; pulse amplitude is derived '
                        'from it and the rate, so every pulsed arm delivers the '
                        'same charge as its constant control')
    p.add_argument('--pulse-ms', type=float, default=1.)
    p.add_argument('--rates', type=float, nargs='+', default=RATES)
    p.add_argument('--log', default=str(ROOT / 'outputs/flappy_pulse/trials.jsonl'))
    p.add_argument('--summary', default=str(ROOT / 'outputs/flappy_pulse/summary.json'))
    args = p.parse_args()

    path = ROOT / 'outputs/connectome_sim/malecns_v1/graph.npz'
    if args.backend == 'gpu':
        from connectome_sim.gpu import GPUBrain; brain = GPUBrain(path)
    else:
        from connectome_sim.native import NativeBrain; brain = NativeBrain(path)

    groups = readouts(brain)
    cells = np.asarray(haltere_afferents(brain), dtype=np.int32)
    lum = retinal_samples(base_frame(), brain.uv)
    run_id = str(uuid.uuid4())
    log = Log(args.log, {'run_id': run_id, 'experiment_class': 'E-PULSE',
        'started': datetime.now(timezone.utc).isoformat(), 'backend': args.backend,
        'ticks': args.ticks, 'means': args.means, 'pulse_ms': args.pulse_ms,
        'rates_hz': args.rates, 'haltere_cells': int(cells.size),
        'graph_sha256': digest(brain.weight),
        'doc': 'docs/sensory-encoding-experiments.md#class-e-pulse'})

    rows = []
    for mean in args.means:
      for rate in args.rates:
        if rate <= 0:
            continue
        # Amplitude follows from the mean and the duty cycle. A brief strong
        # pulse is what an afferent spike looks like to a postsynaptic cell; a
        # brief weak one cannot charge a 20 ms membrane to threshold at all.
        duty = rate * args.pulse_ms / 1000.
        if duty >= 1.:
            continue
        amplitude = args.fixed_amplitude if args.fixed_amplitude else mean / duty
        r = pulsed(brain, lum, groups, cells, amplitude, rate, args.pulse_ms, args.ticks)
        row = {'record': 'arm', 'run_id': run_id, 'arm': 'pulsed', 'rate_hz': rate,
               'target_mean': mean, 'amplitude': round(amplitude, 3),
               'at': datetime.now(timezone.utc).isoformat(), **r}
        rows.append(row); log.write(row)
        print(json.dumps({k: row[k] for k in ('arm', 'rate_hz', 'amplitude',
              'mean_current', 'dlm_per_tick', 'dlm_flap_fraction',
              'descending_total')}), flush=True)
        # Matched control: the same mean current, delivered flat. This is the
        # whole comparison -- identical charge, different time structure.
        c = _constant(brain, lum, groups,
                      [(cells, r['mean_current'])] if r['mean_current'] > 0 else None,
                      args.ticks)
        crow = {'record': 'arm', 'run_id': run_id, 'arm': 'constant',
                'rate_hz': rate, 'target_mean': mean, 'amplitude': r['mean_current'],
                'at': datetime.now(timezone.utc).isoformat(), **c}
        rows.append(crow); log.write(crow)
        print(json.dumps({k: crow[k] for k in ('arm', 'rate_hz', 'amplitude',
              'mean_current', 'dlm_per_tick', 'dlm_flap_fraction',
              'descending_total')}), flush=True)

    summary = {'run_id': run_id, 'experiment_class': 'E-PULSE',
        'finished': datetime.now(timezone.utc).isoformat(),
        'ticks': args.ticks, 'means': args.means, 'pulse_ms': args.pulse_ms,
        'arms': rows}
    log.write({'record': 'summary', **{k: v for k, v in summary.items() if k != 'arms'}})
    log.close()
    out = Path(args.summary); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': 'done', 'arms': len(rows)}))


def _constant(brain, lum, groups, stim, ticks):
    """Flat current for the same number of ticks, as the matched control."""
    reset(brain)
    totals = {k: 0 for k in groups}
    network, dlm_per_tick = 0, []
    for _ in range(ticks):
        counts, _ = brain.step(lum, TICK_MS, stimulation=stim)
        counts = np.asarray(counts)
        network += int(counts.sum())
        for k, idx in groups.items():
            totals[k] += int(counts[idx].sum())
        dlm_per_tick.append(int(counts[groups['dlm']].sum()))
    return {'network_spikes': network,
            **{f'{k}_total': v for k, v in totals.items()},
            'dlm_per_tick': round(totals['dlm'] / ticks, 3),
            'dlm_flap_fraction': round(sum(1 for c in dlm_per_tick if c > 0) / ticks, 4),
            'duty_cycle': 1.0,
            'mean_current': round(float(stim[0][1]), 4) if stim else 0.}


if __name__ == '__main__':
    main()
