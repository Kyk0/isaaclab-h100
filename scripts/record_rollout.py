"""Run a trained Isaac Lab policy headless and record the robot's motion to .npz (no rendering, no cameras).

Runs on any CUDA GPU, including H100/A100 with the compute-only driver. Replay the file in the browser
with scripts/replay_viser.py, or render it with MuJoCo where EGL exists (scripts/render_mujoco.py).

  python scripts/record_rollout.py --task Isaac-Velocity-Flat-G1-Play-v0 \
      --policy <LOG_DIR>/exported/policy.pt --out rollouts/g1_walk.npz --seconds 20

The policy is the TorchScript file Isaac Lab's rsl_rl play.py exports to <run>/exported/policy.pt.
For velocity tasks, --program sets the base-velocity command over time: "vx,vy,wz:seconds;..."

Output (.npz): t [T], dt, joint_names [J], joint_pos [T,N,J], root_pos [T,N,3] (relative to each env origin),
root_quat_wxyz [T,N,4], body_names [B], body_pos [T,N,B,3], body_quat_wxyz [T,N,B,4], env_origins [N,3], task.
"""

import argparse
import os

from isaaclab.app import AppLauncher

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--task", default="Isaac-Velocity-Flat-G1-Play-v0")
p.add_argument("--policy", required=True, help="TorchScript policy (exported/policy.pt)")
p.add_argument("--out", required=True, help="output .npz")
p.add_argument("--num_envs", type=int, default=1)
p.add_argument("--seconds", type=float, default=20.0)
p.add_argument("--program", default="0.8,0,0:7;0.5,0,0.6:6;0.8,0,0:7",
               help="velocity command schedule: 'vx,vy,wz:seconds;...' (ignored if the task has no base_velocity)")
p.add_argument("--asset", default="robot", help="scene entity to record")
AppLauncher.add_app_launcher_args(p)
a = p.parse_args()
a.headless = True  # physics only: no viewport, no cameras
app = AppLauncher(a).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402

cfg = parse_env_cfg(a.task, device=a.device, num_envs=a.num_envs)
cfg.episode_length_s = a.seconds + 10.0
schedule = []
if hasattr(cfg, "commands") and hasattr(cfg.commands, "base_velocity"):
    bv = cfg.commands.base_velocity
    bv.heading_command = False
    bv.resampling_time_range = (1e6, 1e6)
    bv.debug_vis = False
    for part in a.program.split(";"):
        v, dur = part.split(":")
        schedule.append(([float(x) for x in v.split(",")], float(dur)))

env = gym.make(a.task, cfg=cfg)
uenv = env.unwrapped
dt = float(uenv.step_dt)
steps = int(round(a.seconds / dt))
robot = uenv.scene[a.asset]
policy = torch.jit.load(a.policy, map_location=uenv.device)
cmd_term = uenv.command_manager.get_term("base_velocity") if schedule else None


def command_at(t):
    acc = 0.0
    for v, dur in schedule:
        acc += dur
        if t < acc:
            return v
    return schedule[-1][0]


rec = {k: [] for k in ("joint_pos", "root_pos", "root_quat", "body_pos", "body_quat")}
origins = uenv.scene.env_origins
obs, _ = env.reset()
with torch.inference_mode():
    for i in range(steps):
        if cmd_term is not None:
            cmd_term.vel_command_b[:] = torch.tensor(command_at(i * dt), device=uenv.device)
        obs, _, _, _, _ = env.step(policy(obs["policy"]))
        d = robot.data
        rec["joint_pos"].append(d.joint_pos.cpu().numpy())
        rec["root_pos"].append((d.root_pos_w - origins).cpu().numpy())
        rec["root_quat"].append(d.root_quat_w.cpu().numpy())
        rec["body_pos"].append((d.body_pos_w - origins[:, None, :]).cpu().numpy())
        rec["body_quat"].append(d.body_quat_w.cpu().numpy())

os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
np.savez_compressed(
    a.out,
    t=np.arange(steps) * dt, dt=dt, task=a.task,
    joint_names=np.array(robot.joint_names), body_names=np.array(robot.body_names),
    joint_pos=np.stack(rec["joint_pos"]).astype(np.float32),
    root_pos=np.stack(rec["root_pos"]).astype(np.float32),
    root_quat_wxyz=np.stack(rec["root_quat"]).astype(np.float32),
    body_pos=np.stack(rec["body_pos"]).astype(np.float32),
    body_quat_wxyz=np.stack(rec["body_quat"]).astype(np.float32),
    env_origins=origins.cpu().numpy().astype(np.float32),
)
n_j = len(robot.joint_names)
print(f"[record_rollout] {steps} steps x {a.num_envs} env(s), dt={dt:.4f}s, {n_j} joints -> {a.out}", flush=True)
print(f"[record_rollout] joints: {robot.joint_names}", flush=True)
print(f"[record_rollout] RECORD OK device={uenv.device}", flush=True)
env.close()
app.close()
