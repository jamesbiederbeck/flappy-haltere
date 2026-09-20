"""Geometry checks for flappy/render3d.py's first-person projection, as pure
function tests -- no game env needed."""
import numpy as np
import pytest
from flappy.render3d import render

SIZE = (512, 288)
PALETTE = {'sky': np.array([0, 0, 255], np.uint8), 'ground': np.array([200, 160, 80], np.uint8),
           'stripe': np.array([160, 130, 60], np.uint8), 'hurdle': np.array([0, 255, 0], np.uint8)}


def band(frame):
    """Rows showing a wall, as (first, last+1). The test palette makes these
    identifiable through the distance haze: only the hurdle color has a zero
    red channel with green in it, and blending toward the (pure blue) sky
    keeps both of those true."""
    left = frame[:, 0].astype(int)
    hit = np.flatnonzero((left[:, 0] == 0) & (left[:, 1] > 0))
    return (int(hit[0]), int(hit[-1]) + 1) if len(hit) else None


def test_horizon_splits_sky_from_ground_at_eye_level():
    frame = render(SIZE, eye_y=100., ground_y=400., hurdles=[], travel=0., palette=PALETTE)
    assert frame.shape == (512, 288, 3)
    assert frame.dtype == np.uint8
    # nothing but sky above the middle row, nothing but sky-free ground below
    assert np.array_equal(frame[:256, :], np.broadcast_to(PALETTE['sky'], (256, 288, 3)))
    assert not np.array_equal(frame[256:, :], np.broadcast_to(PALETTE['sky'], (256, 288, 3)))


def test_a_wall_spans_the_full_width_at_every_distance():
    # eye just above the wall's top edge, as when the bird is clearing it
    for depth in [100., 200., 900.]:
        frame = render(SIZE, 250., 400., [(depth, 300.)], 0., PALETTE)
        rows = band(frame)
        assert rows is not None, depth
        first, last = rows
        # every row of the band is a single color all the way across
        for row in (first, (first + last) // 2, last - 1):
            assert len(np.unique(frame[row], axis=0)) == 1, (depth, row)


def test_a_nearer_wall_is_thicker_and_lower_in_view():
    thickness, tops = [], []
    for depth in [800., 400., 200., 100.]:
        first, last = band(render(SIZE, 250., 400., [(depth, 300.)], 0., PALETTE))
        thickness.append(last - first)
        tops.append(first)
    assert thickness == sorted(thickness), thickness  # swells as it approaches
    assert tops == sorted(tops), tops  # and sinks away from the horizon


def test_a_wall_above_the_eye_rises_past_the_horizon():
    # eye below the wall's top edge (y grows downward): it towers over the bird
    assert band(render(SIZE, 350., 400., [(200., 250.)], 0., PALETTE))[0] < 256
    # eye above it: the whole wall sits below the horizon
    assert band(render(SIZE, 100., 400., [(200., 250.)], 0., PALETTE))[0] > 256


def test_nearer_walls_occlude_farther_ones():
    near, far = (300., -500.), (900., -2000.)
    far_only = render(SIZE, 100., 400., [far], 0., PALETTE)
    near_only = render(SIZE, 100., 400., [near], 0., PALETTE)
    both = render(SIZE, 100., 400., [near, far], 0., PALETTE)
    assert band(far_only) is not None  # the far wall does draw on its own
    assert not np.array_equal(far_only, near_only)
    np.testing.assert_array_equal(near_only, both)  # but the near one hides all of it


def test_distance_haze_separates_stacked_walls():
    frame = render(SIZE, 100., 400., [(150., 300.), (400., 280.), (900., 260.)], 0., PALETTE)
    first, last = band(frame)
    assert len({tuple(frame[r, 0]) for r in range(first, last)}) >= 3  # not one flat mass


def test_ground_stripes_move_with_travel():
    a = render(SIZE, 100., 400., [], 0., PALETTE)
    b = render(SIZE, 100., 400., [], 30., PALETTE)
    assert not np.array_equal(a[256:], b[256:])  # optic flow exists
    c = render(SIZE, 100., 400., [], 120., PALETTE)  # two full stripe periods
    np.testing.assert_array_equal(a[256:], c[256:])


def test_walls_at_or_behind_the_eye_are_not_drawn():
    frame = render(SIZE, 100., 400., [(0., 300.), (-50., 300.)], 0., PALETTE)
    assert band(frame) is None


def test_rejects_degenerate_geometry():
    with pytest.raises(ValueError):
        render(SIZE, 100., 400., [], 0., PALETTE, focal=0.)
    with pytest.raises(ValueError):
        render(SIZE, float('nan'), 400., [], 0., PALETTE)
    with pytest.raises(ValueError):
        render((1, 0), 100., 400., [], 0., PALETTE)


def test_overhang_hangs_from_the_top_of_the_frame():
    """An upper pipe has no top edge in the world, so its projection runs from
    the frame's first row down to its lower edge."""
    frame = render(SIZE, 250., 400., [], 0., PALETTE, overhangs=[(200., 150.)])
    first, last = band(frame)
    assert first == 0
    # bottom edge at centre + focal*(150-250)/200 = 256 - 75
    assert last == pytest.approx(181, abs=1)


def wall_rows(frame):
    """Rows of the left column showing pipe, as a boolean mask. Ground is not
    pipe, so callers must not treat everything-but-pipe as the gap."""
    left = frame[:, 0].astype(int)
    return (left[:, 0] == 0) & (left[:, 1] > 0)


def gap_rows(frame):
    """The sky visible between an overhang and the hurdle below it: the run of
    non-pipe rows that starts where the overhang ends and stops where the
    hurdle begins. Ground rows below the hurdle are excluded by construction,
    since they come after the second band."""
    wall = wall_rows(frame)
    assert wall[0], 'expected an overhang reaching the top row'
    below = np.flatnonzero(~wall)
    first = int(below[0])
    after = np.flatnonzero(wall[first:])
    assert len(after), 'expected a hurdle below the gap'
    return np.arange(first, first + int(after[0]))


def test_overhang_and_hurdle_leave_the_gap_as_sky():
    """The two halves of a pipe pair bound a gap; between them the fly must
    see through, which is the whole point of drawing both."""
    frame = render(SIZE, 250., 400., [(200., 300.)], 0., PALETTE, overhangs=[(200., 200.)])
    gap = gap_rows(frame)
    # overhang bottom projects to 256 + 150*(200-250)/200 = 218.5
    # hurdle top projects to 256 + 150*(300-250)/200 = 293.5
    assert gap[0] == pytest.approx(219, abs=2)
    assert gap[-1] == pytest.approx(292, abs=2)
    assert frame[gap[len(gap) // 2], 0, 2] > frame[0, 0, 2], 'gap should be skyward of the pipe'


def test_gap_falls_in_the_view_as_the_bird_climbs():
    """The cue the fly needs: where the gap sits in the image encodes whether
    to climb or descend. Rising (smaller y) must move it down the frame."""
    def centre_of_gap(eye_y):
        frame = render(SIZE, eye_y, 400., [(200., 300.)], 0., PALETTE,
                       overhangs=[(200., 200.)])
        return float(np.mean(gap_rows(frame)))
    # eye_y is downward-positive, so climbing is *decreasing* y.
    centres = [centre_of_gap(y) for y in (280., 250., 220., 180.)]
    assert all(b > a for a, b in zip(centres, centres[1:])), centres


def test_a_farther_pair_is_visible_only_through_the_nearer_gap():
    """Occlusion applies to the ceiling as well as the floor: the far pair may
    show through the near pair's gap, and nowhere else."""
    near, near_over = (100., 300.), (100., 200.)
    far, far_over = (600., 260.), (600., 240.)
    both = render(SIZE, 250., 400., [near, far], 0., PALETTE,
                  overhangs=[near_over, far_over])
    near_only = render(SIZE, 250., 400., [near], 0., PALETTE, overhangs=[near_over])
    differs = np.flatnonzero(np.any(both != near_only, axis=(1, 2)))
    gap = gap_rows(near_only)
    assert len(differs), 'the far pair should be visible somewhere'
    assert set(differs) <= set(gap.tolist()), 'far pair leaked outside the near gap'


def test_overhangs_default_to_none():
    """Callers written before overhangs existed must render unchanged."""
    a = render(SIZE, 250., 400., [(200., 300.)], 0., PALETTE)
    b = render(SIZE, 250., 400., [(200., 300.)], 0., PALETTE, overhangs=[])
    assert np.array_equal(a, b)
