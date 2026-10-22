# Changelog

## v0.2.0: End to end on H100 (2026-10-21)

Train on the H100, watch in your browser. Isaac Lab still does the physics; nothing needs an RTX GPU.

- `scripts/record_rollout.py`: run a trained policy headless and record every link's pose to `.npz` (physics only, no cameras). Tested on H100 with the compute-only driver.
- `scripts/replay_viser.py`: replay a recording in the browser with viser (the viewer's browser draws, the server never renders). `--follow` keeps the robot centered. `--save` writes a `.viser` file for viser's static player. `--video` renders an mp4 in headless Chromium with software WebGL, on the CPU.
- `scripts/render_mujoco.py`: kinematic MuJoCo replay to mp4 (fast; needs EGL, so the full driver on servers).
- `docs/08-no-rtx-pipeline.md`: the whole workflow, what works where (compute-only H100, full-driver H100, laptop), and the limits.
- `render_mujoco.py --heading`: the camera turns with the robot. New dark scene that matches the website.
- New name and look: **Isaac Lab, end to end on H100**. Logo, social preview, and a hero video that was trained, recorded and drawn on H100s.
- Website: an interactive 3D replay of our G1 walking policy (click to load), the train → record → watch pipeline, doc 08 card, theme toggle, 404 page.

## v0.1.0 (2026-10-21)

First release: run Isaac Lab 2.x (Isaac Sim 5.x) headless on H100. Why it works, every startup error explained, install and training notes (Isaac Lab G1 walking, SONIC fine-tune), a pre-converted Unitree G1 USD on Hugging Face, and a website.
