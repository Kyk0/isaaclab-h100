# 2. Tested versions

Everything in this guide ran on these three machines (output of [`scripts/collect_env.sh`](../scripts/collect_env.sh), collected 2026-10-20). All three are shared lab servers, so this is a real-world setup, not a dedicated benchmark box.

| Component | H100 host A | H100 host B | RTX host |
|---|---|---|---|
| GPU | NVIDIA H100 NVL (94 GB) | NVIDIA H100 NVL (94 GB) | Quadro RTX 6000 (24 GB) |
| NVIDIA driver | 595.99.02 (`nvidia-driver-595-open`, full) | 580.173.02 (`nvidia-headless-580-server-open`, compute-only) | 570.211.01 |
| CUDA (driver) | 13.2 | 13.0 | 12.8 |
| OS | Ubuntu 24.04.5, kernel 6.8 | Ubuntu 24.04.4, kernel 6.8 | Ubuntu 24.04.5, kernel 6.17 |
| Python | 3.11.16 | 3.11.15 | 3.11.15 |
| isaacsim | 5.1.0.0 | 5.1.0.0 | 5.1.0.0 |
| isaaclab (package) | 0.54.4 | 0.54.4 | 0.54.4 |
| Isaac Lab (repo) | 2.3.2 | 2.3.2 | 2.2.1 |
| torch | 2.7.0+cu128 | 2.7.0+cu128 | 2.7.0+cu128 |
| rsl_rl | 5.0.1 | 5.0.1 | 2.3.3 |
| warp | 1.17.0 | 1.16.0 | 1.14.0 |
| mujoco | 3.13.0 | 3.12.0 | 3.9.0 |
| NVIDIA Vulkan ICD | present | **missing** | present |
| SONIC (GR00T-WholeBodyControl) | `a0732b6` (v1.1) | older checkout | `a9d20b2` |

Notes:

- The Isaac Lab repo version (2.3.2) and the inner `isaaclab` package version (0.54.4) differ by design.
- **H100 host A changed drivers during this work.** Until 2026-10-16 it ran the compute-only `nvidia-headless-580-server-open` (580.173.02), the same setup as host B. The SONIC G1 fine-tune in [04](04-train-headless.md) ran on that driver. Then the admin installed the full `nvidia-driver-595-open` and rebooted. Since then, Kit finds a Vulkan device and logs no renderer errors, and MuJoCo EGL works. Training behaves the same on both drivers.
- Good news on drivers: the [Isaac Sim 5.1 requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html) list Linux driver 580.65.06. Our 570, 580 and 595 drivers all trained without problems.
- On host A in October 2026, an unattended driver upgrade without a reboot broke `nvidia-smi` (NVML driver/library version mismatch) until the machine was rebooted. That is an ordinary driver issue, not an Isaac one. If you run long jobs on a shared server, it is worth asking the admins to hold driver packages.

## What works, per machine

Host A is listed under the driver it has now (full). Before 2026-10-16 it had the compute-only driver, and the September SONIC run happened then; that run is counted in the compute-only column.

| Task | H100, compute-only driver<br>(`nvidia-headless-*-server`) | H100, full driver<br>(`nvidia-driver-595-open`) | RTX 6000 (reference) |
|---|---|---|---|
| Headless RL training (PhysX on CUDA) | ✅ renderer errors at startup are harmless | ✅ no errors | ✅ |
| Isaac Lab G1 locomotion (`Isaac-Velocity-Flat-G1-v0`) | ✅ host B | ✅ host A, incl. the full 1500-iteration run behind the README clip | ✅ |
| SONIC G1 fine-tune from the release checkpoint | ✅ host A (Sept 2026), 4096 envs | not run yet | ✅ |
| URDF → USD conversion | ❌ host B: STL import fails ([details](06-troubleshooting.md#fatal-omniusd-attempted-member-lookup-on-null-tfrefptrusdstage)); ✅ host A at launch (Sept 2026) | ✅ at launch | ✅ |
| Loading the pre-converted G1 USD ([robot USD](05-robot-usd.md)) | ✅ host B | not run yet | ✅ |
| Isaac Sim rendering: `--video`, cameras, viewport | ❌ the renderer never initializes | ➖ outside NVIDIA support (no RT cores); we render on RTX | ✅ |
| MuJoCo offscreen rendering (`MUJOCO_GL=egl`) | ❌ no EGL library | ✅ | ✅ |
| mjlab (MuJoCo Warp) training | ✅ host B | not run yet | not run yet |

## Not covered yet: your report helps

- **A100:** no RT cores either, so it should behave just like the H100.
- **H200, B200, L40S** and other GPUs.
- **Isaac Sim 4.x / 6.x and Isaac Lab 3.x** (3.x is on the v0.3 roadmap).
- **Docker / Apptainer** (see [alternatives](07-alternatives.md)).

Running one of these? Please [send a GPU report](https://github.com/Kyk0/isaaclab-h100/issues/new?template=gpu-report.md) with the output of `scripts/collect_env.sh`. Every report goes into the table above, with credit.
