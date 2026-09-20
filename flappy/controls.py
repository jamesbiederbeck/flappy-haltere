"""Flappy Bird's binary action decoded from spikes.

There is no biological "flap" readout -- flies do not play Flappy Bird. This
reuses the same boolean-trigger pattern connectome_sim/engine.py's NeuralControls
already uses for its own discrete action (attack, off the MN9 readout): flap
fires exactly when the chosen readout type spikes at all this tick. Same
"joystick gains, not biology" honesty as the rest of this project's motor
mapping -- an arbitrary but explicit and auditable engineering choice, not a
claimed correspondence.

The default readout type is 'DLMn' (dorsal longitudinal flight power-muscle
motor neurons), built by flappy.circuit.wing_motor_readouts -- an actual
retained wing motor neuron, unlike doom's MN9 (superclass cb_motor, a
central-brain motor neuron, not VNC/wing). See flappy/circuit.py for why
those cells need external haltere stimulation to ever spike at all.
"""
import math
import numpy as np


class FlapControls:
    """Decodes wing motor-neuron spikes into the game's one button.

    Two decoders. `threshold=None` is the original: a flap whenever any DLM
    cell spikes in a tick. E-HOLD showed why that cannot play the game -- the
    pool fires on almost every tick, so the button is effectively held down,
    and the game's only altitude-holding flap rate is 1/19 = 0.053.

    A numeric `threshold` selects an integrating decoder instead: sum DLM
    spikes, fire when the running total crosses T, and carry the remainder.
    Flap fraction is then about R/T for a DLM rate of R spikes per tick, which
    both lands in the playable range and varies with R rather than saturating.
    This is a harness change, not a connectome one -- scores under it are not
    comparable to any recorded before it."""

    def __init__(self, readouts, flap_readout_type='DLMn', threshold=None):
        self.readouts = readouts
        self.flap_readout_type = flap_readout_type
        self.rates = np.zeros(len(readouts))
        if threshold is not None and not (math.isfinite(threshold) and threshold > 0):
            raise ValueError('Positive flap threshold required')
        self.threshold = threshold
        self.accumulator = 0.

    def decode(self, counts, seconds):
        if seconds <= 0: raise ValueError('Positive time required')
        raw = np.asarray([counts[r['index']] / seconds for r in self.readouts])
        self.rates = self.rates * math.exp(-seconds / .1) + raw * (1 - math.exp(-seconds / .1))
        spikes = sum(int(counts[r['index']]) for r in self.readouts
                     if r['type'] == self.flap_readout_type)
        if self.threshold is None:
            flap = spikes > 0
        else:
            self.accumulator += spikes
            flap = self.accumulator >= self.threshold
            if flap: self.accumulator -= self.threshold
        return {'flap': bool(flap), 'flap_spikes': int(spikes),
                'accumulator': round(float(self.accumulator), 3), 'readouts': [
            {**r, 'spikes': int(counts[r['index']]), 'rate_hz': round(float(rate), 3)}
            for r, rate in zip(self.readouts, self.rates)]}
