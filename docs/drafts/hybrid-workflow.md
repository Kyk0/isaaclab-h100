# Hybrid workflow: RTX ↔ H100 (draft for v0.2)

> **Draft, not part of v0.1.** The scripts it uses (`sync_checkpoints.sh`, `render_on_rtx.sh`) are tested; the v0.2 write-up will add viser browser replay.

The split we use: the H100 does everything headless (training, evaluation metrics, state recording); the RTX machine does everything that draws.

```
 RTX machine (<RTX_HOST>)                     H100 machine (<H100_HOST>)
 ───────────────────────                      ──────────────────────────
 1. assets: URDF → USD (only if needed) ───►  2. train headless
    visual checks of the motion data             evaluate (metrics only)
                                                 optionally record states (.npz)
 4. render ◄──────────────────────────────── 3. checkpoint + config.yaml (+ .npz)
    Isaac Lab native video                       sha256 verified on arrival
    or MuJoCo replay video
```

In our lab the two servers cannot reach each other over SSH, so every copy goes through a laptop that can reach both. `scripts/sync_checkpoints.sh` handles that case.

## 1. Assets (RTX side)

Convert URDF → USD on the RTX machine and copy the whole output directory to the H100; see [05-robot-usd.md](../05-robot-usd.md). Motion data conversion (CSV → motion-lib `.pkl`) is CPU-only and runs on either machine.

## 2. Train on the H100

See [04-train-headless.md](../04-train-headless.md).

## 3. Checkpoints back, verified

```bash
# from a machine that can reach both (or from either host if they can see each other)
bash scripts/sync_checkpoints.sh \
  <H100_HOST>:<RUN_DIR> <RTX_HOST>:<DATA_DIR>/ckpt_step250 \
  model_step_000250.pt config.yaml
```

The script computes sha256 at the source, copies with rsync (through a local staging directory when both ends are remote), and runs `sha256sum -c` at the destination. Always copy `config.yaml` with a SONIC checkpoint. We kept the pair together for every checkpoint we evaluated or rendered.

## 4. Render on the RTX machine

### Option A: Isaac Lab native render

Replays the policy in Isaac Lab on the RTX GPU and writes an mp4 through SONIC's render recorder:

```bash
bash scripts/render_on_rtx.sh <DATA_DIR>/ckpt_step250/model_step_000250.pt <MOTION_LIB_DIR> <DATA_DIR>/render_step250
# -> <DATA_DIR>/render_step250/video/000000.mp4 and metrics_eval.json
```

On our RTX 6000 this took about 5 minutes for a 22-second clip (1 env), including startup. On SONIC's public sample folder (`sample_data/robot_filtered/210531`, two 40-second clips) with the stock release checkpoint, it took 14.5 minutes. It produced an 80-second 1920×1088 video and success 1.00, mpjpe_l 16.7 mm, mpjpe_g 86.8 mm.

All motions in the folder are played one after another into the same `000000.mp4`. Use a folder with only the clip you want to see.

### Option B: record on the H100, render with MuJoCo

1. On the H100, run the evaluation headless and save per-step robot states (joint positions, root pose) to an `.npz`. We did this with a small wrapper around SONIC's `eval_agent_trl.py` that also saves the states the `im_eval` callback already computes.
2. Copy the `.npz` to the RTX machine.
3. Replay it in MuJoCo with offscreen rendering (`MUJOCO_GL=egl`, or `MUJOCO_GL=glfw` with a logged-in X display).

Option B keeps all Isaac work on the H100 and only needs MuJoCo on the rendering side. A full-driver H100 can even render MuJoCo itself (our smoke test passed); a compute-only one cannot.

## Why not render on the H100

- Compute-only driver: no Vulkan, no EGL, so nothing renders.
- Full driver: MuJoCo EGL works. Isaac Sim's RTX renderer is unsupported without RT cores, and we have not tested it.
