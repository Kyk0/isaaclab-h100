# 8. No RTX at all: train on H100, watch in your browser

Docs 01–07 split the work: train on the H100, render on an RTX machine. This page removes the RTX machine.

Isaac Lab still does all the physics on the H100. We record what the robot does, then **draw it somewhere that doesn't need RT cores**:

| Viewer | Who draws | H100, compute-only driver | H100, full driver | Laptop |
|---|---|---|---|---|
| **viser, live** (interactive, in the browser) | the viewer's browser (WebGL) | ✅ server runs, open via `ssh -L` | ✅ | ✅ |
| **viser, saved `.viser`** (a static web page, no server) | the viewer's browser | ✅ file made on the server | ✅ | ✅ |
| **viser → mp4** (headless Chromium, software WebGL) | the CPU | ✅ (see the note on `nss`) | ✅ | ✅ |
| **MuJoCo → mp4** (kinematic replay) | OpenGL / EGL | ❌ no EGL in the compute-only driver | ✅ | ✅ |

All four rows were run on our machines (H100 NVL with the compute-only and with the full driver, plus a MacBook).

> [!NOTE]
> This shows **what Isaac Lab simulated**: every link is placed at the pose PhysX computed. It is a replay, not Isaac Sim's RTX renderer, so it looks simpler. It is perfect for watching and sharing state-based policies (walking, motion tracking). Policies that *use* simulated camera images still need an RTX GPU.

## 1. Record a rollout (on the H100)

[`scripts/record_rollout.py`](../scripts/record_rollout.py) runs a trained policy headless and saves the pose of every link at every step:

```bash
cd <ISAACLAB_DIR>
./isaaclab.sh -p <THIS_REPO>/scripts/record_rollout.py --task Isaac-Velocity-Flat-G1-Play-v0 \
  --policy <RUN_DIR>/exported/policy.pt --out rollouts/g1_walk.npz --seconds 20
```

- `--policy` is the TorchScript file that Isaac Lab's `rsl_rl/play.py` writes to `<RUN_DIR>/exported/policy.pt`.
- For velocity tasks, `--program "vx,vy,wz:seconds;..."` scripts the walking command (default: walk, turn, walk).
- Our 20 s G1 recording took 71 s on the compute-only H100 (1 robot) and is a 1.2 MB `.npz`.
- No cameras, no `--enable_cameras`: this runs on any CUDA GPU.

## 2. Pick a robot model whose link names match

The viewers place one mesh per link, matched **by name** to the recorded bodies (no joint mapping). Print the recorded names with `python -c "import numpy as np; print(np.load('rollouts/g1_walk.npz')['body_names'])"`.

For Isaac Lab's built-in G1 tasks (the older G1 with three-finger hands), NVIDIA's SONIC repo has a matching URDF: `gear_sonic/data/robots/g1/old/g1_unitree.urdf` in [GR00T-WholeBodyControl](https://github.com/NVlabs/GR00T-WholeBodyControl). All 44 recorded bodies match; 43 have meshes (`imu_link` is an invisible sensor frame). Run `git lfs pull` in that repo first; without it the meshes are 130-byte placeholder files and the scripts stop with a clear message.

## 3. Watch it live in your browser

Run [`scripts/replay_viser.py`](../scripts/replay_viser.py) anywhere, the H100 server included. It needs no GPU:

```bash
uv run --with viser --with trimesh python scripts/replay_viser.py \
  --rollout rollouts/g1_walk.npz --urdf <SONIC_REPO>/gear_sonic/data/robots/g1/old/g1_unitree.urdf --follow
# on your laptop: ssh -L 8080:localhost:8080 <H100_HOST>, then open http://localhost:8080
```

Play, pause, speed and a frame slider are in the panel. `--follow` keeps the robot centered and scrolls the floor, so you can keep the camera close.

## 4. Share it as a web page (no server)

Save a `.viser` recording and open it with viser's static player. That is one HTML file with no external requests:

```bash
uv run --with viser --with trimesh --with fast-simplification python scripts/replay_viser.py \
  --rollout rollouts/g1_walk.npz --urdf <URDF> --follow --max_faces 3000 --save g1_walk.viser
uv run --with viser viser-build-client --out-dir viewer/      # writes viewer/index.html (~0.8 MB)
cp g1_walk.viser viewer/ && (cd viewer && python -m http.server 8000)
# open the URL the script printed, e.g.
# http://localhost:8000/?playbackPath=g1_walk.viser&initialCameraPosition=1.65,-2.55,1.35&initialCameraLookAt=0,0,0.6
```

- Our 20 s G1 recording is **1.65 MB** with `--max_faces 3000` (3.2 MB at full mesh detail).
- Add `&darkMode` to the URL for a dark background. Any static host works (GitHub Pages included); the replay on [this project's website](https://kyry.me/isaaclab-h100/) is exactly this.

## 5. Make an mp4

**Option A: viser + headless Chromium (works everywhere, including the compute-only H100).** A headless browser with software WebGL draws each frame on the CPU:

```bash
uv run --with playwright playwright install chromium-headless-shell        # one time
uv run --with viser --with trimesh --with fast-simplification --with playwright --with imageio --with imageio-ffmpeg \
  python scripts/replay_viser.py --rollout rollouts/g1_walk.npz --urdf <URDF> --follow --max_faces 3000 --video g1_walk.mp4
```

- On a server without system browser libraries, Chromium stops with `libnspr4.so: cannot open shared object file`. Without root, install them into a separate conda env and point the loader at it: `conda create -y -p <ENV> -c conda-forge nss nspr`, then `export LD_LIBRARY_PATH=<ENV>/lib`.
- It is slow but GPU-free: 500 frames at 1280×720 took 174 s on a MacBook and 735 s (about 12 minutes) on the compute-only H100 server, all on the CPU.

**Option B: MuJoCo (fast, needs EGL).** [`scripts/render_mujoco.py`](../scripts/render_mujoco.py) turns every link into a MuJoCo mocap body and renders with a tracking camera:

```bash
MUJOCO_GL=egl uv run --with mujoco --with trimesh --with imageio --with imageio-ffmpeg \
  python scripts/render_mujoco.py --rollout rollouts/g1_walk.npz --urdf <URDF> --out g1_walk_mujoco.mp4
```

- 20 s on the full-driver H100. On the compute-only driver it fails with `AttributeError: 'NoneType' object has no attribute 'eglQueryString'` (no EGL; see [doc 01](01-why-it-works.md)). On a laptop, drop `MUJOCO_GL=egl`.

## What this doesn't do

- **Camera-based RL.** Policies that read simulated camera images need Isaac Sim's renderer, which needs RT cores. (For depth-like data without the renderer, look at Isaac Lab's ray-caster sensors.)
- **Photoreal images.** These viewers draw the robot's meshes with simple lighting.
- **Your own robot out of the box.** You need a URDF (or meshes) whose link names match the recorded bodies. If your Isaac Lab robot was converted from a URDF, that URDF is it.
