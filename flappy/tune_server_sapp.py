"""Tunable live web UI driving just the two responsive SApp haltere afferents.

Two independent sliders (voltage_l, voltage_r) inject a constant mV-equivalent
current directly into SApp_L (body_id 136883) and SApp_R (body_id 101048) --
the only two cells, out of SApp's 148-cell undifferentiated bulk, found to
respond alone (flybody-connectome/experiments/LOG.md's 2026-09-19 single-cell
sweep; connectome-lab/experiments-summary.tsv). Their individually-measured DC
thresholds are 18mV (L) and 15mV (R) (2026-09-20 threshold sweep, same log),
which is why the sliders default there.

Unlike tune_server.py's haltere activation curve, current here is NOT derived
from the bird's fall speed -- each slider holds its own cell at whatever
voltage it says, every tick, independent of game state. This is a
stimulation/readout tool over these two specific cells (mirroring the SApp
lab in the Android app, minus its frequency/phase/duty-cycle controls, which
don't have a web-UI equivalent here), not a haltere-to-flight controller --
the Flappy Bird game underneath is a live, familiar readout surface, not the
point.

Streams coordinates the same way tune_server.py does; see that module for the
shared design notes (frozen weights, GET-only mutating endpoints, /reset also
resetting the connectome via Brain.reset(), etc) -- this is a copy rather than
an import of that structure because the two differ in exactly the stimulation
model and the params being tuned, and duplicating ~250 lines of a self-
contained script for a materially different tool is more legible than
threading a shared base class through both for two knobs.
"""
import argparse
import json
import signal
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import numpy as np
from connectome_sim.native import NativeBrain
from flappy.circuit import wing_motor_readouts
from flappy.controls import FlapControls
from flappy.game import Game, FPS
from connectome_sim.vision.retina import BilinearLuminance

ROOT = Path(__file__).resolve().parents[1]
latest = {'status': 'starting', 'generated_at_ms': 0}
# Plain dict item assignment/read is atomic under the GIL, same convention
# doom/server.py and flappy/server.py already rely on for `latest`.
SAPP_BODY_IDS = {'L': '136883', 'R': '101048'}
params = {'voltage_l': 18.0, 'voltage_r': 15.0}
PARAM_BOUNDS = {'voltage_l': (0., 30.), 'voltage_r': (0., 30.)}
stop = threading.Event()
reset_requested = threading.Event()


def sapp_indices(brain):
    """Graph indices for SApp_L/SApp_R, resolved by body_id -- same technique
    connectome_sim/export_android.py's sapp_pair export and
    flybody-connectome's haltere_sapp_pulse.py/haltere_sapp_threshold.py use.
    """
    ids = brain.ids.astype(str)
    out = {}
    for side, body_id in SAPP_BODY_IDS.items():
        matches = np.flatnonzero(ids == body_id)
        if len(matches) != 1:
            raise ValueError(f'expected exactly one graph index for SApp_{side} '
                             f'(body_id {body_id}), got {len(matches)}')
        out[side] = int(matches[0])
    return out


def run_loop(args):
    global latest
    try:
        path = ROOT / 'outputs/connectome_sim' / args.dataset / 'graph.npz'
        if args.backend == 'gpu':
            from connectome_sim.gpu import GPUBrain, GPU_BUILD
            brain = GPUBrain(path); build = GPU_BUILD
        else:
            from connectome_sim.native import BUILD
            brain = NativeBrain(path); build = BUILD
        sapp = sapp_indices(brain)
        l_idx = np.array([sapp['L']], dtype=np.int32)
        r_idx = np.array([sapp['R']], dtype=np.int32)
        dlm = wing_motor_readouts(brain)
        controls = FlapControls(dlm)
        game = Game(seed=args.seed, no_pipes=True)
        geometry = game.geometry()
        retina = BilinearLuminance()
        run_id = str(uuid.uuid4())
        duration_ms = 1000 / FPS
        total_spikes, best_survival = 0, 0
        seq = 0
        start = time.monotonic()
        print(json.dumps({'status': 'running', 'run_id': run_id, 'port': args.port,
                          'sapp_indices': sapp}), flush=True)
        while not stop.is_set():
            obs = game.observation()
            if reset_requested.is_set():
                # Same split as tune_server.py: only the manual reset clears
                # the connectome (Brain.reset()); a crash-triggered new
                # episode below does not, matching every other frozen-weight
                # run script here.
                brain.reset()
                best_survival = max(best_survival, obs['tick'])
                game.new_episode()
                reset_requested.clear()
                obs = game.observation()
            elif obs['finished']:
                best_survival = max(best_survival, obs['tick'])
                game.new_episode()
                obs = game.observation()
            frame = game.pixels()
            light = retina.sample(frame, brain.uv)
            vl, vr = params['voltage_l'], params['voltage_r']
            stimulation = [pair for pair in [(l_idx, vl), (r_idx, vr)] if pair[1] > 0] or None
            counts, neural_wall = brain.step(light, duration_ms, sugar=False, stimulation=stimulation)
            action = controls.decode(counts, duration_ms / 1000)
            game.act(action['flap'])
            total_spikes += int(counts.sum())
            seq += 1
            wall_seconds = time.monotonic() - start
            obs = game.observation()
            latest = {
                'schema': 1, 'status': 'running', 'run_id': run_id, 'sequence': seq,
                'generated_at_ms': int(time.time() * 1000), 'backend': args.backend,
                'geometry': geometry,
                'bird': {'y': obs['y'], 'rotation': obs['rotation'], 'y_velocity': obs['y_velocity']},
                'flap': action['flap'],
                'params': {'voltage_l': vl, 'voltage_r': vr},
                'game': {'episode': obs['episode'], 'tick': obs['tick'],
                         'best_survival_ticks': max(best_survival, obs['tick'])},
                'dlm_spikes': int(sum(int(counts[r['index']]) for r in dlm)),
                'sapp_spikes': {'L': int(counts[sapp['L']]), 'R': int(counts[sapp['R']])},
                'clocks': {
                    'wall_seconds': round(wall_seconds, 3),
                    'neural_seconds': round(brain.sim_ms / 1000, 4),
                    'speed': round((brain.sim_ms / 1000) / wall_seconds, 4) if wall_seconds > 0 else 0,
                    'brain_step_ms': round(neural_wall * 1000, 3),
                },
                'total_spikes': total_spikes,
            }
    except Exception:
        latest = {'status': 'error', 'generated_at_ms': int(time.time() * 1000),
                   'message': 'The simulation stopped. No live data is available.'}
        import traceback; traceback.print_exc()
    finally:
        try: game.close()
        except Exception: pass


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>SApp stimulation tuner</title>
<style>
body{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:0;display:flex;gap:24px;padding:20px;flex-wrap:wrap}
canvas{background:#4ec0e0;border:1px solid #333;border-radius:4px}
.panel{min-width:260px}
label{display:block;margin-top:14px;font-size:13px;color:#aaa}
input[type=range]{width:100%}
.val{font-family:monospace;color:#7fd}
.stat{font-family:monospace;font-size:13px;margin:2px 0}
.dead{color:#f66}
.alive{color:#7f7}
.flap{color:#ff7}
h1{font-size:16px;margin:0 0 4px}
.sub{font-size:11px;color:#888;margin-bottom:10px}
button{margin-top:14px;padding:8px 14px;font-size:13px;background:#333;color:#eee;border:1px solid #555;border-radius:4px;cursor:pointer}
button:hover{background:#444}
button:active{background:#555}
</style></head>
<body>
<canvas id="c" width="288" height="512"></canvas>
<div class="panel">
<h1>SApp stimulation tuner</h1>
<div class="sub">SApp_L body_id 136883 (threshold ~18mV) &middot; SApp_R body_id 101048 (threshold ~15mV)</div>
<label>SApp_L voltage (mV) = <span class="val" id="vlval"></span>
  <input type="range" id="voltage_l" min="0" max="30" step="0.5" value="18">
</label>
<label>SApp_R voltage (mV) = <span class="val" id="vrval"></span>
  <input type="range" id="voltage_r" min="0" max="30" step="0.5" value="15">
</label>
<button id="resetBtn">Reset bird + connectome</button>
<hr style="border-color:#333;margin-top:18px">
<div class="stat" id="status">connecting...</div>
<div class="stat">tick: <span id="tick"></span> &nbsp; episode: <span id="episode"></span></div>
<div class="stat">y_velocity: <span id="vy"></span></div>
<div class="stat">flap: <span id="flapind"></span></div>
<div class="stat">DLM spikes/tick: <span id="dlm"></span></div>
<div class="stat">SApp_L spikes/tick: <span id="sappL"></span> &nbsp; SApp_R spikes/tick: <span id="sappR"></span></div>
<div class="stat">survived this episode: <span id="survived"></span> ticks</div>
<div class="stat">best survival: <span id="best"></span> ticks</div>
<div class="stat">sim speed: <span id="speed"></span>x realtime</div>
</div>
<script>
const $ = id => document.getElementById(id);
const ctx = $('c').getContext('2d');
let pending = null;

function pushParams() {
  const vl = $('voltage_l').value, vr = $('voltage_r').value;
  $('vlval').textContent = vl; $('vrval').textContent = vr;
  clearTimeout(pending);
  pending = setTimeout(() => fetch(`/params?voltage_l=${vl}&voltage_r=${vr}`), 80);
}
$('voltage_l').oninput = pushParams; $('voltage_r').oninput = pushParams;
$('resetBtn').onclick = () => fetch('/reset');

function draw(s) {
  const g = s.geometry, b = s.bird;
  ctx.clearRect(0, 0, g.screen_width, g.screen_height);
  ctx.fillStyle = '#4ec0e0'; ctx.fillRect(0, 0, g.screen_width, g.screen_height);
  ctx.fillStyle = '#ded895'; ctx.fillRect(0, g.ground_y, g.screen_width, g.screen_height - g.ground_y);
  ctx.save();
  ctx.translate(g.player_x + g.player_width / 2, b.y + g.player_height / 2);
  ctx.rotate(-b.rotation * Math.PI / 180);
  ctx.fillStyle = s.flap ? '#ffd23f' : '#f2a413';
  ctx.beginPath();
  ctx.ellipse(0, 0, g.player_width / 2, g.player_height / 2, 0, 0, 2 * Math.PI);
  ctx.fill();
  ctx.restore();
}

async function poll() {
  try {
    const r = await fetch('/state'); const s = await r.json();
    if (s.status !== 'running') { $('status').textContent = s.status; return; }
    $('status').innerHTML = '<span class="alive">running</span>';
    $('tick').textContent = s.game.tick;
    $('episode').textContent = s.game.episode;
    $('vy').textContent = s.bird.y_velocity.toFixed(2);
    $('flapind').innerHTML = s.flap ? '<span class="flap">FLAP</span>' : '&mdash;';
    $('dlm').textContent = s.dlm_spikes;
    $('sappL').textContent = s.sapp_spikes.L;
    $('sappR').textContent = s.sapp_spikes.R;
    $('survived').textContent = s.game.tick;
    $('best').textContent = s.game.best_survival_ticks;
    $('speed').textContent = s.clocks.speed;
    draw(s);
  } catch (e) { $('status').textContent = 'disconnected'; }
}
pushParams();
setInterval(poll, 150);
poll();
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/':
            self._send(200, PAGE.encode(), 'text/html; charset=utf-8')
        elif parsed.path == '/state':
            self._send(200, json.dumps(latest, separators=(',', ':')).encode(), 'application/json')
        elif parsed.path == '/params':
            query = urllib.parse.parse_qs(parsed.query)
            for key in ('voltage_l', 'voltage_r'):
                if key not in query: continue
                try:
                    value = float(query[key][0])
                except ValueError:
                    self.send_error(400, 'Invalid numeric parameter'); return
                lo, hi = PARAM_BOUNDS[key]
                if not (lo <= value <= hi):
                    self.send_error(400, f'{key} out of bounds [{lo}, {hi}]'); return
                params[key] = value
            self._send(200, json.dumps(params).encode(), 'application/json')
        elif parsed.path == '/reset':
            # Requests a fresh episode (position/velocity reset) AND a full
            # connectome reset on the next tick without waiting for a crash;
            # does not touch voltage_l/voltage_r.
            reset_requested.set()
            self._send(200, b'{"ok":true}', 'application/json')
        else:
            self.send_error(404)

    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError): pass

    def log_message(self, *args): pass


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=8772)
    p.add_argument('--bind', default='127.0.0.1')
    p.add_argument('--dataset', default='malecns_v1')
    p.add_argument('--seed', type=int, default=41027)
    p.add_argument('--backend', choices=['native', 'gpu'], default='native')
    args = p.parse_args()

    def shutdown_signal(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, shutdown_signal)
    worker = threading.Thread(target=run_loop, args=(args,), daemon=True)
    worker.start()
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set(); server.shutdown()


if __name__ == '__main__':
    main()
