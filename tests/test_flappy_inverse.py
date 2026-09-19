"""Findings the inverse-dynamics pipeline rests on, pinned as tests.

Two kinds here.  The artifact tests read `outputs/flappy_inverse/*.npz` and skip
when it is absent (it is gitignored), asserting facts that a graph rebuild or an
engine change would silently invalidate.  The rest need nothing.

The cluster potency and threshold numbers were re-derived independently in
`flybody-connectome/experiments/haltere_axis_pairs.py`, which drives pairs of
clusters rather than one at a time and on the native backend rather than GPU.
Both runs agree on which clusters do anything, which is why they are worth
pinning: it is a property of the graph, not of one script.
"""
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "outputs/flappy_inverse/cluster_sweep.npz"

# Of the ten named bilateral haltere types, only these drive the wing-muscle
# pool at any tested current.  SApp is the 148-cell undifferentiated bulk and is
# excluded -- it is not a candidate cluster and is the only group that is merely
# "Prelim Roughly traced" in MaleCNS v1.0.
POTENT = {"SNpp12", "SNpp23"}
SILENT = {"SNpp35", "SNpp14", "SNpp15", "SNpp20", "SNpp21", "SNxx25"}


def _sweep():
    if not SWEEP.exists():
        pytest.skip(f"{SWEEP} not generated (npz is gitignored)")
    d = np.load(SWEEP, allow_pickle=True)
    totals = d["responses"].sum(axis=2)  # (group, current)
    names = [str(n).split("_")[0] for n in d["group_names"]]
    return names, totals, d["currents"]


def test_only_two_typed_clusters_drive_the_motor_pool():
    names, totals, _ = _sweep()
    fired = {n for n, t in zip(names, totals) if t.sum() > 100 and n not in ("SApp", "none")}
    assert fired == POTENT, (
        f"Expected only {sorted(POTENT)} to drive the pool, got {sorted(fired)}. "
        "If this changed, every cluster-identity claim in docs/ needs rechecking.")


def test_six_typed_clusters_are_identically_silent():
    names, totals, _ = _sweep()
    for n in SILENT:
        t = totals[names.index(n)]
        assert t.sum() == 0, f"{n} fired {t.sum()} spikes; it was silent at every current"


def test_direct_wiring_does_not_predict_effect():
    """SNpp14 is the only cluster with a direct 1-hop synapse onto the DLM/DVM
    power muscles, and it never fires the pool at any current, while SNpp12 and
    SNpp23 -- with zero direct synapses onto any wing-muscle motor neuron -- are
    the only two that do.  Static connectivity is not a usable predictor here,
    which is why the sweep exists at all."""
    names, totals, _ = _sweep()
    assert totals[names.index("SNpp14")].sum() == 0
    assert all(totals[names.index(n)].sum() > 100 for n in POTENT)


def test_recruitment_threshold_sits_between_8_and_10_mV():
    """The reflex is sharp-threshold, and experiments must pick currents above
    it on *both* sides of any baseline +/- delta design.  An axis-pair sweep in
    flybody-connectome used 11 +/- 3 and so drove its 'low' condition at 8 mV --
    below threshold, making the four conditions on/off rather than a sign flip.
    """
    names, totals, currents = _sweep()
    below = currents < 8
    assert totals[:, below].sum() == 0, "something fired below 8 mV"
    lo = totals[names.index("SNpp12")][list(currents).index(8.0)]
    hi = totals[names.index("SNpp12")][list(currents).index(10.0)]
    assert lo < 100 < hi, f"SNpp12 threshold moved: {lo} at 8 mV, {hi} at 10 mV"


@pytest.mark.parametrize("name", ["dataset-train.npz", "dataset-clustered.npz"])
def test_dataset_cannot_represent_graded_simultaneous_drive(name):
    """One scalar amplitude per trial, and a binary per-cell mask.

    So a trial where two clusters are driven at *different* currents at the same
    time is unrepresentable in this schema.  That is exactly the regime a
    multi-axis IMU produces, and the regime the axis-pair experiment uses, so
    this is the gap to close before either can contribute training data --
    stuffing them in as-is would give identical labels to different responses.
    """
    f = ROOT / "outputs/flappy_inverse" / name
    if not f.exists():
        pytest.skip(f"{f} not generated (npz is gitignored)")
    d = np.load(f, allow_pickle=True)
    assert d["stim"].dtype == np.uint8 and set(np.unique(d["stim"])) <= {0, 1}
    assert d["amplitude"].ndim == 1, (
        "amplitude became per-cell -- the graded-drive gap may now be closed; "
        "update this test and the loaders in inverse_train.load_dataset")
    assert d["stim"].shape[0] == d["amplitude"].shape[0] == d["response"].shape[0]


def test_train_writes_where_infer_reads():
    """A bare retrain must not write a file inference never loads.

    `inverse_train.py` defaulted to --hidden 10000 (the configuration the doc
    records as overfitting, val BCE 0.688 against a 0.6485 baseline) and wrote
    inverse_model.npz, while all three `inverse_infer.py` subcommands load
    inverse_model_h512.npz -- so retraining appeared to do nothing.
    """
    import re

    train = (ROOT / "flappy/inverse_train.py").read_text()
    infer = (ROOT / "flappy/inverse_infer.py").read_text()
    hidden = re.search(r"--hidden.*?default=(\d+)", train)
    assert hidden and int(hidden.group(1)) == 512, "train default is not the accepted 512"
    out = set(re.findall(r"inverse_model[\w]*\.npz", train))
    read = set(re.findall(r"inverse_model[\w]*\.npz", infer))
    assert out <= read, f"train writes {out - read}, which inverse_infer never loads"
