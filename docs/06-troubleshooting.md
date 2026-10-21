# 6. Troubleshooting

Seeing scary red text? Search this page for your exact message. Every entry is a real string from our H100 logs (Isaac Sim 5.1, Isaac Lab 2.3.2; timestamps and paths removed), with what it means and what to do.

> [!TIP]
> **Rule of thumb:** if the log goes on to print `Environment device : cuda:0` and then `Learning iteration` blocks, every renderer error above it was harmless. Most of this page is just that.

## Harmless renderer errors (compute-only driver)

What a healthy start looks like on a compute-only H100 (real log, shortened):

<p align="center">
  <img src="../images/h100-startup-log.png" width="720" alt="Terminal log from an H100 training run: red Isaac Sim renderer errors such as 'No device could be created' and 'Invalid getDeviceInfo parameters' and an empty Vulkan GPU table, followed by 'Environment device : cuda:0' and normal Learning iteration blocks">
</p>

All of these come from Kit trying to start the renderer on a machine with no NVIDIA Vulkan driver. They appear on every run with `nvidia-headless-*-server` drivers. **Cause:** no Vulkan ICD (`/usr/share/vulkan/icd.d/nvidia_icd.json` missing). **Fix:** none needed for training. To make them go away, ask the admin for the full driver package (`nvidia-driver-<ver>-open`, which includes `libnvidia-gl-<ver>`); on our H100 that removed every one of them.

### `[Error] [gpu.foundation.plugin] No device could be created. Some known system issues:`

Followed by a list that includes *"Your GPUs do not support RayTracing: DXR or Vulkan ray_tracing"*. Harmless for training.

### `[Error] [gpu.foundation.plugin] The chosen activeGpu index 0 is higher than the available GPUs. An unsupported driver might also prevent it from enumerating your devices properly.`

Kit found zero Vulkan GPUs. It does not mean CUDA cannot see the GPU. Harmless.

### `| Driver Version: 0 | Graphics API: Vulkan` with an empty GPU table

Same cause. The table lists Vulkan devices, not CUDA devices. Harmless.

### `[Error] [gpu.foundation.plugin] Invalid getDeviceInfo parameters.`

Harmless.

### `[Error] [omni.gpu_foundation_factory.plugin] Failed to create any GPU devices, including an attempt with compatibility mode.`

Harmless.

### `[Error] [omni.kit.renderer.plugin] GPU Foundation is not initialized!`

Harmless for training. If it is followed by a `[Fatal]` USD error, see the URDF section below.

### `[Error] [omni.kit.renderer.plugin] Graphics plugins not available`

Harmless.

### `[Error] [omni.ui] Failed to create texture GPU data! [512 x 64, 1 mips]`

Harmless.

### `[Error] [omni.kit.imgui_renderer.plugin] _prepareDefaultWindow: invalid device attached to the default window!`

Harmless.

### `[Warning] [omni.physx.foundation.plugin] PhysXFoundation: Unable to get IGpuFoundation, GpuDevices or Graphics!`

Also `PhysXFoundation: Couldn't get driver version, failed to getDeviceInfo`. Despite the name, PhysX still runs on CUDA (`Environment device : cuda:0`). Harmless.

### `sh: 1: zenity: not found`

Kit tries to show a GUI error dialog. Harmless on a server.

## Other harmless messages

### `Could not load the dynamic library from .../omni.usd.libs-.../bin/libMaterialXRenderGlsl.so. Error: libXt.so.6: cannot open shared object file`

Also for `libMaterialXRenderHw.so` and `libusd_usdBakeMtlx.so`. These are MaterialX rendering plugins; training does not use them. Installing `xorg-libxt` from conda-forge into the env did **not** remove the message for us (Kit does not search `$CONDA_PREFIX/lib`). Harmless.

### `ModuleNotFoundError: No module named 'pxr'`

You imported Isaac Lab or SONIC code from a plain `python -c`. USD bindings only load after Isaac Sim's `AppLauncher` starts. It is not an install problem; run the real training script instead.

## Fatal errors

### `[Fatal] omni.usd: attempted member lookup on NULL TfRefPtr<UsdStage>`

Preceded by:
```
[Error] omni.kit.renderer.plugin: GPU Foundation is not initialized!
[Error] omni.usd: Failed to open layer @/tmp/IsaacLab/usd_*/configuration/pelvis.tmp.usd@
```
Often also preceded by `[isaacsim.asset.importer.urdf] Asset convert failed with error status: Unsupported Format (/meshes/<link>)`.

**When:** URDF → USD conversion (at launch with `UrdfFileCfg`, or with `scripts/convert_robot.py`) on H100 host B (compute-only driver). It is reproducible there for SONIC's G1 URDF: with CPU or GPU physics, with or without capsules, and with absolute mesh paths. H100 host A converted the same URDF at launch while it had the same compute-only driver, so it depends on the host. Root cause not found. Isaac Sim may still exit with status 0. **Fix:** convert on an RTX machine and load the USD with `UsdFileCfg`, or download the provided G1 USD (`scripts/download_usd.sh`). Copy the whole USD directory, not only the top `.usd` file. Details: [05-robot-usd.md](05-robot-usd.md#why-conversion-can-fail-on-a-compute-only-h100).

### `convert_robot.py --verify` (or your own script) hangs after the run at 100 % CPU

Seen with Isaac Sim 5.1 headless: after stepping physics, `sim.stop()` (which `app.close()` also calls) never returned. **Fix:** call `sim.clear_all_callbacks()` and `sim.clear_instance()` before `app.close()`; `scripts/convert_robot.py` does this.

### `AttributeError: 'NoneType' object has no attribute 'eglQueryString'`

MuJoCo with `MUJOCO_GL=egl` on a compute-only-driver machine: no `libEGL_nvidia.so`. **Fix:** render on an RTX machine, or get the full driver installed (`libnvidia-gl-<ver>`); after that, MuJoCo EGL worked on our H100. `MUJOCO_GL=osmesa` was no help: there was no OSMesa on the server, and conda-forge has no `libosmesa` package (`PackagesNotFoundInChannelsError: ... libosmesa`).

### `UsageError: No API key configured`

wandb waiting for a login choice under `nohup` or a pipe. **Fix:** set `WANDB_MODE=offline` (sync later with `wandb sync`) or `WANDB_MODE=online` after `wandb login`.

### `Failed to initialize NVML: Driver/library version mismatch`

`nvidia-smi` and new CUDA processes fail after the driver packages were upgraded without a reboot (an unattended upgrade did this to us). **Fix:** reboot (admin). Ask for driver packages to be held on training servers.

## If you try to render on an H100/A100 anyway (reported by others)

These come from other users' reports, not our logs. With a full driver, Kit can start the renderer on these GPUs, but camera rendering is reported to crash or look wrong. Seen in Isaac Lab issues:

| Message | GPU | Source |
|---|---|---|
| `[Error] [carb.graphics-vulkan.plugin] VkResult: ERROR_DEVICE_LOST`, then `[gpu.foundation.plugin] A GPU crash occurred` | H100, tiled camera | [IsaacLab#4271](https://github.com/isaac-sim/IsaacLab/issues/4271) |
| `[Error] [rtx.postprocessing.plugin] createDLSSContext error: unable to initialize context.`, then a crash in `librtx.postprocessing.plugin.so` (turning DLSS off did not help) | A100, `--enable_cameras` | [IsaacLab#3421](https://github.com/isaac-sim/IsaacLab/issues/3421) |
| `[Warning] [rtx.postprocessing.plugin] DLSS-RR is not supported in the current build due to some known bugs with this GPU`, noisy low-quality images | A100 | [IsaacLab#1519](https://github.com/isaac-sim/IsaacLab/issues/1519) |

An Isaac Lab contributor's answer in #4271: H100s "are currently incompatible with the tiled camera. They can still train state-based tasks." For depth or semantic images only, `MultiMeshRayCaster` works without the renderer. For RGB, render on an RTX GPU.

## SONIC-specific

### `IndexError` on `loaded_data["root_trans_offset"].shape[0]`

The motion path points at a folder that contains SMPL files (for example `sample_data/` instead of `sample_data/robot_filtered/`). **Fix:** point `motion_file` at the robot motion folder.

### Training "hangs" with no output

Output piped through `tee` is buffered. **Fix:** `export PYTHONUNBUFFERED=1`.

### `pip install -e "gear_sonic/[training]"` fails

The slash makes it an invalid requirement. Use `"gear_sonic[training]"`.

### Eval progress bar shows `Succ rate: 0.000` and a huge `Mpjpe`

Seen during `eval_agent_trl.py` with `im_eval`, for example `Succ rate: 0.000 | Mpjpe: 72726.517` after the first motion. These are intermediate values. The same run ended with success 1.00 and mpjpe_g 86.8 mm in `metrics_eval.json`. Read the JSON, not the progress bar. `Terminated: 0` in the bar is the useful live signal (no falls so far).

### Hydra override silently ignored

A `++` override with the wrong key path is accepted without error. Check the resolved `config.yaml` in the run directory. The working key for the motion folder is `++manager_env.commands.motion.motion_lib_cfg.motion_file=...`.
