# 4. Train headless

Two examples: Isaac Lab's own G1 walking task (start here), and fine-tuning NVIDIA's SONIC controller.

## Tips for shared servers

```bash
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv   # who else is on the GPU
export CUDA_VISIBLE_DEVICES=0       # pin to one GPU
export PYTHONUNBUFFERED=1           # live logs, even through tee
export WANDB_MODE=offline           # or online after `wandb login`; never leave it to a prompt
```

Run long jobs in `tmux` or with `nohup ... &`, and always write a log file.

## Flags

| Flag | Where | On H100 |
|---|---|---|
| `--headless` | Isaac Lab scripts (`isaaclab.sh -p .../train.py`) | ✅ always use it |
| `headless=True` | SONIC (`gear_sonic/train_agent_trl.py`, Hydra) | ✅ always use it |
| `--num_envs N` / `num_envs=N` | both | ✅ 4096 is a good start; the H100 has room for more |
| `--video`, `--enable_cameras`, camera sensors | Isaac Lab | skip them; render on an RTX machine |
| `++manager_env.config.render_results=True`, `+manager_env/recorders=render` | SONIC eval | skip them; render on an RTX machine |

## Start here: Isaac Lab's G1 walking task

```bash
cd <ISAACLAB_DIR>
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/train.py \
  --task Isaac-Velocity-Flat-G1-v0 --headless --num_envs 4096 --max_iterations 20
```

This is Isaac Lab's built-in G1 velocity-tracking task, and a quick way to confirm your setup. Its G1 USD is downloaded from NVIDIA's asset server at startup, so the H100 host needs internet access (or a local copy of the assets). Ran successfully on both H100 hosts (shared GPUs) and the RTX 6000; clean benchmarks planned for v0.2.

For a policy that really walks, drop `--max_iterations` and let it run the task's default 1500 iterations. That is how we trained the policy in the README's walking clip.

## Advanced: fine-tune SONIC from the public release checkpoint

This is the command we ran on the H100 to fine-tune SONIC's released G1 policy on a custom motion mixed with control clips. Only the paths are replaced:

```bash
cd <SONIC_REPO>
python gear_sonic/train_agent_trl.py \
  +exp=manager/universal_token/all_modes/sonic_release \
  +checkpoint=sonic_release/last.pt \
  num_envs=4096 headless=True \
  ++manager_env.commands.motion.motion_lib_cfg.motion_file=<MOTION_LIB_DIR> \
  ++manager_env.commands.motion.motion_lib_cfg.smpl_motion_file=dummy \
  ++algo.config.num_learning_iterations=300 \
  ++callbacks.model_save.save_frequency=25 \
  ++exp_var=my_finetune
```

- `+checkpoint=sonic_release/last.pt` starts from the public weights. Each run gets a new run directory under `logs_rl/`.
- `smpl_motion_file=dummy` trains on robot (G1) motions only, with zero SMPL observations. Use it when you have no SMPL data for your clip.
- `<MOTION_LIB_DIR>` is a folder of SONIC motion-lib `.pkl` files. Upstream's `convert_soma_csv_to_motion_lib.py` makes them from CSV. Point it at the folder that contains the robot `.pkl` files (for the sample data, `sample_data/robot_filtered`), not its parent.
- [`scripts/train_headless_example.sh`](../scripts/train_headless_example.sh) wraps this command. It checks the GPU, verifies the release checkpoint hash and logs to a file.
- Each saved checkpoint sits next to a `config.yaml` in the run directory. Keep the two together when you move a checkpoint.

> [!TIP]
> SONIC is a big model, and the H100 handles it comfortably: 8192 environments used about 30 GB.

What a healthy start looks like in the log on an H100 with the compute-only driver:

```
[Error] [gpu.foundation.plugin] No device could be created. Some known system issues:
...
[Error] [omni.kit.renderer.plugin] Graphics plugins not available
[INFO]: Base environment:
	Environment device    : cuda:0
...
	Number of environments: 4096
[INFO]: Time taken for simulation start : 9.097549 seconds
...
                         Learning iteration 100
```

The red lines are the renderer giving up; training carries on. See [troubleshooting](06-troubleshooting.md) for each message.
