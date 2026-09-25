"""Flappy Bird boundary: raw rendered pixels in, one discrete button out.

Mirrors doom/game.py's Game class shape (pixels()/act()/observation()/close()/
new_episode()) so flappy/play.py can drive the same Brain/NativeBrain/GPUBrain
without any game-specific code outside this module and vision/retina.py.

`pixels()` does not return the game's own side-on frame. It returns the
world reprojected into the bird's first-person view (flappy/render3d.py):
each pipe becomes a wall standing on the ground, spanning the full lateral
axis and rising to the gap's lower edge -- a hurdle crossing the view
horizontally, placed by distance rather than by screen position. See that
module for why the shipped camera's picture misrepresents what the bird can
actually do about an obstacle.

Only the *lower* pipe is projected: a hurdle has no ceiling above the
runner. The upper pipe still exists in the env and still ends the episode
on collision -- flying too high remains exactly as fatal -- it is simply
not drawn as an obstacle. Game physics, scoring and collision are untouched
throughout; only the picture changes, for both the neural visual input and
the human broadcast view (always the same frame here, matching
doom/game.py's convention).
"""
import math
import numpy as np
import pygame
from flappy_bird_gymnasium.envs.constants import (
    PIPE_HEIGHT, PIPE_VEL_X, PIPE_WIDTH, PLAYER_HEIGHT, PLAYER_WIDTH)
from flappy_bird_gymnasium.envs.flappy_bird_env import FlappyBirdEnv
from flappy.render3d import MIN_DEPTH, render

# The env's only declared tick-rate signal (metadata['render_fps']); not
# enforced by the env itself unless render_mode='human', so this is a chosen
# real-time slice per env.step(), not a measured hardware clock the way
# ViZDoom's 35Hz is for doom/game.py.
FPS = 30


class Game:
    def __init__(self, seed=41027, score_limit=None, no_pipes=False, perspective=True,
                 pipes_terminate=True):
        self.env = FlappyBirdEnv(render_mode='rgb_array', use_lidar=False, score_limit=score_limit)
        if no_pipes:
            # Park every generated pipe far off both the visible screen and
            # the collision check, forever, instead of patching the vendored
            # submodule -- there is no constructor flag for this upstream.
            # Ground/ceiling boundaries are untouched and still terminate an
            # episode; only the pipe obstacle is removed.
            self.env._get_random_pipe = lambda: [{'x': -9999, 'y': -9999}, {'x': -9999, 'y': -9999}]
        self._no_pipes = no_pipes
        self._pipes_terminate = bool(pipes_terminate)
        if not self._pipes_terminate:
            # Pass-through pipes: the bird still sees them, still has to clear
            # them to score, but hitting one no longer ends the episode, so the
            # simulation is never reset on a pipe strike. Ground and ceiling
            # remain fatal -- without them the bird falls out of the world and
            # the visual input stops meaning anything. Same host-side patching
            # technique as the no_pipes path above; the vendored submodule and
            # the pipe geometry are untouched, only the termination test is.
            self.env._check_crash = self._ground_collision
        self._perspective = perspective
        self._colors = None
        self._seed = seed
        # flappy_bird_env only ever draws randomness for _get_random_pipe's
        # gap index (flappy_bird_gymnasium/envs/flappy_bird_env.py:420), via
        # self.np_random. Gymnasium's reset(seed=None) does not reseed --
        # it continues that same generator from wherever it was left. So
        # passing seed once at episode 0 and None thereafter (as this used
        # to do, mirroring doom/game.py) makes every episode after the first
        # inherit whatever RNG state episode 1 happened to consume, which
        # depends on how many ticks episode 1 ran for -- itself a function
        # of the neural policy's timing, which is not run-to-run identical
        # on the GPU backend (see AGENTS.md / README on that). The result:
        # at a fixed --seed, only episode 1's pipe course was ever
        # reproducible; episode 2 onward silently varied with policy
        # timing, and every multi-episode metric taken from a "fixed seed"
        # run inherited that. A dedicated generator, seeded once from
        # `seed`, hands each episode boundary its own draw so every
        # episode's course is a fixed function of (seed, episode index)
        # alone -- episode 0 keeps passing `seed` directly, unchanged from
        # before, so single-episode results are unaffected.
        self._episode_rng = np.random.default_rng(seed)
        self.episode = 0
        self.new_episode()

    def new_episode(self):
        episode_seed = self._seed if self.episode == 0 else int(
            self._episode_rng.integers(0, 2**31 - 1))
        self.env.reset(seed=episode_seed)
        self._frame = self.env.render()
        self.episode += 1
        self.tick = 0
        self._finished = False
        self._score = 0
        self._in_pipe = False
        self._struck_pipe = False
        self._cleared_pipe = False
        self._struck_since_score = False
        self.pipe_strikes = 0
        self.pipes_cleared = 0

    def pixels(self):
        if self._finished: raise RuntimeError('Episode finished; reset is required')
        if not self._perspective: return self._frame.copy()
        env = self.env
        return render((env._screen_height, env._screen_width),
                      float(env._player_y) + PLAYER_HEIGHT / 2, float(env._ground['y']),
                      self._hurdles(), self.tick * abs(PIPE_VEL_X), self._palette(),
                      overhangs=self._overhangs())

    def _hurdles(self):
        """(depth ahead, top edge y) for every lower pipe still in front of
        the bird -- the walls it has to clear."""
        # reset() keeps its own x values for the opening pipes and only takes
        # y from _get_random_pipe, so the no_pipes parking trick leaves them
        # at real depths with a sentinel height -- which would project as a
        # wall taller than the world. There is nothing to clear; say so.
        if self._no_pipes: return []
        player_x = self.env._player_x
        return [(float(pipe['x']) - player_x, float(pipe['y'])) for pipe in self.env._lower_pipes
                if float(pipe['x']) - player_x >= MIN_DEPTH]

    def _overhangs(self):
        """(depth ahead, bottom edge y) for every upper pipe still in front of
        the bird -- the ceilings it has to stay under.

        The env stores an upper pipe by the y of its *top*, which is off the
        top of the screen; the edge that matters is PIPE_HEIGHT below that.
        Same no_pipes guard as _hurdles: parked pipes keep real x values with
        a sentinel y, which would project as a ceiling covering the world."""
        if self._no_pipes: return []
        player_x = self.env._player_x
        return [(float(pipe['x']) - player_x, float(pipe['y']) + PIPE_HEIGHT)
                for pipe in self.env._upper_pipes
                if float(pipe['x']) - player_x >= MIN_DEPTH]

    def _palette(self):
        # Sampled once from the game's own sprites and background rather than
        # hardcoded, so the view tracks whatever colors the env was built with.
        if self._colors is None:
            pipe = pygame.surfarray.array3d(self.env._images['pipe'][0])
            ground = self._frame[min(int(self.env._ground['y']) + 20, self._frame.shape[0] - 1), 5]
            self._colors = {
                'sky': self._frame[0, 0].astype(np.uint8),
                'hurdle': pipe[pipe.shape[0] // 2, pipe.shape[1] // 2].astype(np.uint8),
                'ground': ground.astype(np.uint8),
                'stripe': (ground * .82).astype(np.uint8),
            }
        return self._colors

    def _ground_collision(self):
        """The env's own ground test, lifted verbatim from
        FlappyBirdEnv._check_crash so the pass-through mode keeps exactly the
        boundary behavior it had."""
        return self.env._player_y + PLAYER_HEIGHT >= self.env._ground['y'] - 1

    def _pipe_collision(self):
        """Pipe overlap only, computed the same way the env does. Reported
        independently of termination so the aversive signal survives
        pipes_terminate=False -- a pipe strike is still a pipe strike when it
        no longer ends the episode."""
        env = self.env
        player = pygame.Rect(env._player_x, env._player_y, PLAYER_WIDTH, PLAYER_HEIGHT)
        return any(player.colliderect(pygame.Rect(pipe['x'], pipe['y'], PIPE_WIDTH, PIPE_HEIGHT))
                   for pipe in [*env._upper_pipes, *env._lower_pipes])

    def act(self, flap):
        # The adapter is the only caller of env.step. No human keystrokes.
        score_before = self._score
        _, reward, terminated, truncated, info = self.env.step(int(bool(flap)))
        self.tick += 1
        self._finished = terminated or truncated
        self._score = info['score']
        # Rising edge only: a pass-through bird overlaps the same pipe for
        # several consecutive ticks, which is one strike, not several.
        inside = self._pipe_collision()
        self._struck_pipe = inside and not self._in_pipe
        self._in_pipe = inside
        self.pipe_strikes += int(self._struck_pipe)
        self._struck_since_score = self._struck_since_score or inside
        # The env scores on x-passage alone, so with pipes_terminate=False a
        # bird that ploughs straight through still scores. "Cleared" means
        # scored *and* never touched that pipe -- the actual avoidance event.
        # With terminating pipes a strike ends the episode anyway, so the two
        # coincide and this costs nothing.
        self._cleared_pipe = self._score > score_before and not self._struck_since_score
        if self._score > score_before:
            self._struck_since_score = inside
            self.pipes_cleared += int(self._cleared_pipe)
        if not self._finished:
            self._frame = self.env.render()
        return float(reward)

    def observation(self):
        # _player_y/_player_vel_y/_player_rot are private env attributes (no
        # public accessor exists); vel_y positive = falling, negative = rising,
        # range [PLAYER_MIN_VEL_Y, PLAYER_MAX_VEL_Y] per
        # flappy_bird_gymnasium.envs.constants.
        return {'episode': self.episode, 'tick': self.tick, 'finished': self._finished,
                'score': self._score, 'struck_pipe': self._struck_pipe, 'cleared_pipe': self._cleared_pipe,
                'in_pipe': self._in_pipe, 'pipe_strikes': self.pipe_strikes,
                'pipes_cleared': self.pipes_cleared,
                'y_velocity': float(self.env._player_vel_y),
                'y': float(self.env._player_y), 'rotation': float(self.env._player_rot)}

    def obstacles(self):
        """Nearest lower-pipe hurdle and upper-pipe overhang ahead of the
        bird, as {'distance', 'angle'} dicts measured from the bird's own
        eye (the same eye_y `pixels()` projects from) -- angle in radians,
        0 level, positive downward (the pipe edge sits below eye height).
        None for a side with nothing in view (no_pipes mode, or nothing
        within MIN_DEPTH).

        This is the literal env geometry `pixels()`'s 3D projection is built
        from, exposed directly (not by reaching into `_hurdles`/`_overhangs`
        from outside this class) so other modules can wire raw game
        telemetry into non-visual neuron populations -- see flappy/agent.py.
        """
        eye_y = float(self.env._player_y) + PLAYER_HEIGHT / 2

        def nearest(pairs):
            if not pairs: return None
            depth, edge_y = min(pairs, key=lambda p: p[0])
            return {'distance': float(depth), 'angle': float(math.atan2(edge_y - eye_y, depth))}

        return {'lower': nearest(self._hurdles()), 'upper': nearest(self._overhangs())}

    def geometry(self):
        """Fixed screen/sprite dimensions for a coordinate-only renderer (no
        video frame) to draw the bird itself; static for the env's lifetime."""
        return {'screen_width': self.env._screen_width, 'screen_height': self.env._screen_height,
                'ground_y': self.env._ground['y'], 'player_x': self.env._player_x,
                'player_width': PLAYER_WIDTH, 'player_height': PLAYER_HEIGHT}

    def close(self):
        self.env.close()
