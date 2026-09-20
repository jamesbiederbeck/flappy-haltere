"""First-person perspective view of the Flappy Bird world, rendered from the
bird's own eye instead of the game's side-on camera.

The camera the game ships shows two axes: screen-x is the bird's direction of
travel (how far ahead the next obstacle is) and screen-y is height. The axis a
pipe is actually infinite along -- lateral, wing to wing, the one the bird
cannot move in -- is the axis that camera looks straight down, so it never
appears. Sampling that frame with the retina hands the fly a picture in which
an obstacle is a narrow post with open sky on both flanks: an arrangement that
only makes sense if you could go around it, which a bird fixed at one lateral
position cannot.

This module rebuilds the same world as the fly would see flying into it: a
pinhole camera at the bird's eye looking along the direction of travel, with
each pipe as a wall standing on the ground, spanning the whole lateral axis --
hence the full width of the view at every distance -- and rising to the gap's
lower edge. A hurdle: crossing the view horizontally, sitting near the horizon
while it is far off, swelling and sinking as it is approached. Distance is
carried by where the bar sits and how thick it is, not by where it sits
left-to-right.

The upper pipe is the same wall hung from above: an overhang, spanning the
lateral axis and descending from out of sight down to the gap's upper edge.
It was not drawn at all until 2026-09-19, which meant the view showed only the
floor half of a gap the bird has to thread while the undrawn ceiling still
ended the episode on contact. A gap is defined by both of its edges, and an
agent shown one of them is being asked to infer the other from nothing.

The ground carries depth stripes because an untextured plane projects to a
constant split at the horizon no matter how high you are -- it would give the
fly no altitude or speed cue at all, while altitude is the single thing it
controls. The stripes are what make height above the ground and forward speed
visible, the same ground optic flow real flies use to hold altitude.

The camera does not pitch with the bird's sprite rotation (real flies stabilize
gaze against body pitch), and the focal length is chosen for a usable field of
view rather than measured from fly optics -- same declared-convention footing
as the retina's uv layout in doom/prepare.py.
"""
import numpy as np

# Sets the field of view for the frame the game renders at (288x512):
# ~88 degrees horizontal, ~119 degrees vertical. Not fly optics.
FOCAL_PX = 150.
# World units (game pixels) between ground stripe edges.
STRIPE_PERIOD = 60.
# Nearer than this a wall's projection diverges; it is already a collision.
MIN_DEPTH = 1.
# Successive walls stack up toward the horizon and, drawn in one flat color,
# merge into a single mass that carries no depth at all -- the retina samples
# luminance, so identical luminance means identical meaning. Fading them
# toward the sky with distance (aerial perspective) is what separates them.
HAZE_SCALE = 400.


def hazed(color, sky, depth, scale=HAZE_SCALE):
    """Blend a surface toward the sky with distance."""
    fade = 1. - np.exp(-max(depth, 0.) / scale)
    return (np.asarray(color, np.float64) * (1 - fade) + np.asarray(sky, np.float64) * fade).astype(np.uint8)


def render(size, eye_y, ground_y, hurdles, travel, palette,
           focal=FOCAL_PX, stripe_period=STRIPE_PERIOD, haze_scale=HAZE_SCALE,
           overhangs=()):
    """Project the world into the bird's own view.

    size: (height, width) of the frame to produce.
    eye_y: the bird's eye height, in the game's downward-positive y pixels.
    ground_y: the ground plane, same units; must be below the eye.
    hurdles: (depth, top_y) per wall -- depth ahead of the eye, and the y of
        the wall's top edge (the height that has to be cleared).
    travel: how far the bird has flown, for the ground stripe phase.
    palette: 'sky', 'ground', 'stripe' and 'hurdle' colors as uint8 triples.
    overhangs: (depth, bottom_y) per ceiling slab -- depth ahead of the eye,
        and the y of its lower edge (the height that has to be stayed under).
        Drawn in the same color as a hurdle because it is the same pipe;
        what separates them in the view is which side of the gap they bound.
        Defaults to none, so callers written before overhangs existed render
        exactly as they did.
    """
    height, width = size
    if height < 2 or width < 1: raise ValueError('Frame too small to project into')
    if not all(np.isfinite(x) for x in (eye_y, ground_y, travel, focal, stripe_period)):
        raise ValueError('Finite geometry required')
    if focal <= 0 or stripe_period <= 0 or haze_scale <= 0:
        raise ValueError('Positive focal length, stripe period and haze scale required')
    frame = np.empty((height, width, 3), np.uint8)
    frame[:] = palette['sky']
    # A flat plane's vanishing line sits at eye level, which with no camera
    # pitch is the middle row; everything below it is ground, above it sky.
    centre = height / 2.
    horizon = int(np.ceil(centre))
    drop = ground_y - eye_y
    if drop > 0 and horizon < height:
        rows = np.arange(horizon, height, dtype=np.float64) + .5
        depth = focal * drop / (rows - centre)
        striped = np.floor((travel + depth) / stripe_period) % 2 == 0
        near = np.where(striped[:, None], palette['stripe'], palette['ground']).astype(np.float64)
        fade = (1. - np.exp(-depth / haze_scale))[:, None]
        frame[horizon:, :] = (near * (1 - fade) + np.asarray(palette['sky'], np.float64) * fade)[:, None, :]
    # Back to front, so a near wall hides what stands behind it. Hurdles and
    # overhangs share one ordering: the two halves of a pipe pair sit at the
    # same depth, and a nearer pair has to occlude a farther one on both sides
    # of the gap, not just the floor side.
    walls = [(d, 'hurdle', y) for d, y in hurdles] + [(d, 'overhang', y) for d, y in overhangs]
    for depth, kind, edge_y in sorted(walls, key=lambda w: -w[0]):
        if not (np.isfinite(depth) and np.isfinite(edge_y)) or depth < MIN_DEPTH: continue
        edge = centre + focal * (edge_y - eye_y) / depth
        if kind == 'hurdle':
            # Stands on the ground: from its top edge down to the ground plane.
            far_edge = centre + focal * (ground_y - eye_y) / depth
            first, last = edge, far_edge
        else:
            # Hangs from above: from out of frame down to its bottom edge. The
            # slab has no top in the world, so the frame's top row is the limit.
            first, last = 0., edge
        first = int(np.clip(np.floor(first), 0, height))
        last = int(np.clip(np.ceil(last), 0, height))
        if last > first: frame[first:last, :] = hazed(palette['hurdle'], palette['sky'], depth, haze_scale)
    return frame
