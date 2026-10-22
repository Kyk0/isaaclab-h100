"""Render a recorded Isaac Lab rollout to mp4 with MuJoCo (kinematic replay, Isaac Lab physics).

MuJoCo only draws here: every link is a mocap body placed at its recorded pose; nothing is simulated.
Needs an OpenGL context: on a headless Linux server that means MUJOCO_GL=egl, which works only with the
full NVIDIA driver (libEGL_nvidia), not with the compute-only driver. On a laptop the default backend works.

  MUJOCO_GL=egl uv run --with mujoco --with trimesh --with imageio --with imageio-ffmpeg \
      python scripts/render_mujoco.py --rollout rollouts/g1_walk.npz --urdf <URDF> --out g1_walk_mujoco.mp4
"""

import argparse
import math
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np
import trimesh

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--rollout", required=True, help=".npz from scripts/record_rollout.py")
p.add_argument("--urdf", required=True, help="URDF whose link names match the recorded body names")
p.add_argument("--out", required=True, help="output .mp4")
p.add_argument("--env", type=int, default=0)
p.add_argument("--fps", type=float, default=30.0)
p.add_argument("--size", default="1280x720")
p.add_argument("--distance", type=float, default=3.0, help="camera distance (tracks the robot)")
p.add_argument("--azimuth", type=float, default=135.0)
p.add_argument("--elevation", type=float, default=-15.0)
a = p.parse_args()

d = np.load(a.rollout)
body_names = [str(b) for b in d["body_names"]]
body_pos = d["body_pos"][:, a.env] + d["env_origins"][a.env]
body_quat = d["body_quat_wxyz"][:, a.env]
dt = float(d["dt"])
stride = max(1, int(round(1.0 / (a.fps * dt))))


def rpy_matrix(r, p_, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p_), math.sin(p_), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


def build_model(urdf_path, tmp):
    """MJCF with one mocap body per recorded link that has a visual mesh (meshes baked into link frames)."""
    root = ET.parse(urdf_path).getroot()
    base = Path(urdf_path).parent
    assets, bodies, mocap_of = [], [], {}
    for link in root.findall("link"):
        name = link.get("name")
        if name not in body_names:
            continue
        geoms = []
        for k, vis in enumerate(link.findall("visual")):
            mesh_el = vis.find("geometry/mesh")
            if mesh_el is None:
                continue
            mesh = trimesh.load(base / mesh_el.get("filename").replace("package://", ""), force="mesh")
            o = vis.find("origin")
            if o is not None:
                tf = np.eye(4)
                tf[:3, :3] = rpy_matrix(*[float(v) for v in o.get("rpy", "0 0 0").split()])
                tf[:3, 3] = [float(v) for v in o.get("xyz", "0 0 0").split()]
                mesh.apply_transform(tf)
            f = Path(tmp) / f"{name}_{k}.stl"
            mesh.export(f)  # binary STL
            c = vis.find("material/color")
            rgba = c.get("rgba") if c is not None else "0.85 0.87 0.9 1"
            assets.append(f'<mesh name="{name}_{k}" file="{f}"/>')
            geoms.append(f'<geom type="mesh" mesh="{name}_{k}" rgba="{rgba}" contype="0" conaffinity="0"/>')
        if geoms:
            mocap_of[name] = len(bodies)
            bodies.append(f'<body name="{name}" mocap="true">{"".join(geoms)}</body>')
    xml = f"""<mujoco><visual><global offwidth="1920" offheight="1080"/><quality shadowsize="4096"/></visual>
      <asset><texture name="sky" type="skybox" builtin="gradient" rgb1="0.35 0.42 0.52" rgb2="0.08 0.1 0.14" width="256"
        height="256"/><texture name="grid" type="2d" builtin="checker" rgb1="0.24 0.26 0.3" rgb2="0.2 0.22 0.26"
        width="512" height="512" mark="edge" markrgb="0.38 0.42 0.48"/>
        <material name="grid" texture="grid" texrepeat="40 40" reflectance="0.05"/>{"".join(assets)}</asset>
      <worldbody><light pos="0 0 6" dir="0 0 -1" directional="true" diffuse="0.8 0.8 0.8"/>
        <geom type="plane" size="50 50 0.1" material="grid"/>{"".join(bodies)}</worldbody></mujoco>"""
    return mujoco.MjModel.from_xml_string(xml), mocap_of


with tempfile.TemporaryDirectory() as tmp:
    model, mocap_of = build_model(a.urdf, tmp)
data = mujoco.MjData(model)
W, H = (int(x) for x in a.size.split("x"))
renderer = mujoco.Renderer(model, height=H, width=W)
cam = mujoco.MjvCamera()
cam.distance, cam.azimuth, cam.elevation = a.distance, a.azimuth, a.elevation
idx = {n: body_names.index(n) for n in mocap_of}
root_i = 0  # first recorded body = articulation root (pelvis)

writer = imageio.get_writer(a.out, fps=1.0 / (stride * dt), codec="libx264", quality=8, macro_block_size=8,
                            ffmpeg_params=["-pix_fmt", "yuv420p"])
for t in range(0, body_pos.shape[0], stride):
    for name, m in mocap_of.items():
        data.mocap_pos[m] = body_pos[t, idx[name]]
        data.mocap_quat[m] = body_quat[t, idx[name]]
    mujoco.mj_forward(model, data)
    cam.lookat[:] = body_pos[t, root_i] * np.array([1, 1, 0]) + np.array([0, 0, 0.6])
    renderer.update_scene(data, camera=cam)
    writer.append_data(renderer.render())
writer.close()
print(f"[render_mujoco] wrote {a.out} ({len(mocap_of)} links, {1 / (stride * dt):.0f} fps)")
