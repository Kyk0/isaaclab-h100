"""Replay a recorded Isaac Lab rollout in the browser with viser. No GPU rendering on the server.

The robot is drawn by the viewer's browser (WebGL), so this runs on any machine, including an H100/A100 server
with the compute-only driver. Link meshes come from a URDF whose link names match the recorded body names; each
link is placed at its recorded world pose (no joint mapping needed).

  # live: open http://localhost:8080 (from your laptop: ssh -L 8080:localhost:8080 <H100_HOST>)
  uv run --with viser --with trimesh python scripts/replay_viser.py --rollout rollouts/g1_walk.npz --urdf <URDF>

  # mp4 with no GPU rendering: headless Chromium (software WebGL) draws the frames
  uv run --with viser --with trimesh --with playwright --with imageio --with imageio-ffmpeg \
      python scripts/replay_viser.py --rollout rollouts/g1_walk.npz --urdf <URDF> --video g1_walk.mp4 --follow
  (one-time: uv run --with playwright playwright install chromium)

  # save a .viser recording for viser's static web player (embed in a web page, no server at all)
  uv run --with viser --with trimesh python scripts/replay_viser.py --rollout rollouts/g1_walk.npz --urdf <URDF> \
      --save g1_walk.viser --fps 25
"""

import argparse
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import trimesh
import viser

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--rollout", required=True, help=".npz from scripts/record_rollout.py")
p.add_argument("--urdf", required=True, help="URDF whose link names match the recorded body names")
p.add_argument("--env", type=int, default=-1, help="which recorded env to show (-1 = all)")
p.add_argument("--port", type=int, default=8080)
p.add_argument("--fps", type=float, default=25.0, help="playback/recording frame rate (subsamples the rollout)")
p.add_argument("--save", help="write a .viser recording and exit (for the static web player)")
p.add_argument("--video", help="write an mp4 rendered by a headless browser (software WebGL) and exit")
p.add_argument("--size", default="1280x720", help="--video frame size WxH")
p.add_argument("--color", default="#d9dee6", help="robot color for meshes without a URDF color")
p.add_argument("--follow", action="store_true",
               help="keep the (first shown) robot centered and scroll the ground; good for a close fixed camera")
p.add_argument("--max_faces", type=int, default=0,
               help="simplify each mesh to at most this many triangles (needs fast-simplification)")
a = p.parse_args()

d = np.load(a.rollout)
body_names = [str(b) for b in d["body_names"]]
body_pos, body_quat = d["body_pos"], d["body_quat_wxyz"]  # [T, N, B, 3/4]
origins = d["env_origins"]
dt = float(d["dt"])
stride = max(1, int(round(1.0 / (a.fps * dt))))
frames = np.arange(0, body_pos.shape[0], stride)
envs = list(range(body_pos.shape[1])) if a.env < 0 else [a.env]


def rpy_matrix(r, p_, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p_), math.sin(p_), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


def load_link_meshes(urdf_path):
    """{link_name: [(trimesh in link frame, rgb or None)]} from the URDF's <visual> elements."""
    root = ET.parse(urdf_path).getroot()
    base = Path(urdf_path).parent
    materials = {m.get("name"): m.find("color").get("rgba")
                 for m in root.findall("material") if m.find("color") is not None}
    out = {}
    for link in root.findall("link"):
        for vis in link.findall("visual"):
            mesh_el = vis.find("geometry/mesh")
            if mesh_el is None:
                continue
            fname = base / mesh_el.get("filename").replace("package://", "")
            with open(fname, "rb") as fh:
                if fh.read(40).startswith(b"version https://git-lfs"):
                    raise SystemExit(f"{fname} is a Git LFS pointer, not a mesh: run `git lfs pull` in that repo")
            mesh = trimesh.load(fname, force="mesh")
            if a.max_faces and len(mesh.faces) > a.max_faces:
                mesh = mesh.simplify_quadric_decimation(face_count=a.max_faces)
            if mesh_el.get("scale"):
                mesh.apply_scale([float(s) for s in mesh_el.get("scale").split()])
            o = vis.find("origin")
            if o is not None:
                tf = np.eye(4)
                tf[:3, :3] = rpy_matrix(*[float(v) for v in o.get("rpy", "0 0 0").split()])
                tf[:3, 3] = [float(v) for v in o.get("xyz", "0 0 0").split()]
                mesh.apply_transform(tf)
            mat = vis.find("material")
            rgba = None
            if mat is not None:
                c = mat.find("color")
                rgba = c.get("rgba") if c is not None else materials.get(mat.get("name"))
            rgb = tuple(int(255 * float(x)) for x in rgba.split()[:3]) if rgba else None
            out.setdefault(link.get("name"), []).append((mesh, rgb))
    return out


meshes = load_link_meshes(a.urdf)
missing = [b for b in body_names if b not in meshes]
print(f"[replay_viser] {len(frames)} frames at {1 / (stride * dt):.1f} fps, {len(envs)} env(s), "
      f"{len(body_names)} bodies ({len(missing)} without a mesh)")

server = viser.ViserServer(port=a.port)
server.scene.set_up_direction("+z")
CELL = 0.5
grid = server.scene.add_grid("/ground", width=40.0, height=40.0, cell_size=CELL, plane="xy")
default_rgb = tuple(int(a.color[i:i + 2], 16) for i in (1, 3, 5))

handles = {}  # (env, body index) -> frame handle
for e in envs:
    for bi, name in enumerate(body_names):
        if name not in meshes:
            continue
        frame = server.scene.add_frame(f"/robot{e}/{name}", show_axes=False)
        for k, (mesh, rgb) in enumerate(meshes[name]):
            server.scene.add_mesh_simple(
                f"/robot{e}/{name}/visual{k}", vertices=mesh.vertices.astype(np.float32),
                faces=mesh.faces.astype(np.uint32), color=rgb or default_rgb, flat_shading=False)
        handles[(e, bi)] = frame


def show(fi):
    t = frames[fi]
    shift = np.zeros(3)
    if a.follow:  # move the world, not the camera: robot root stays at the origin, grid scrolls by the same amount
        shift[:2] = body_pos[t, envs[0], 0, :2] + origins[envs[0], :2]
        grid.position = tuple(float(x) for x in (-(shift % CELL)))
    for (e, bi), h in handles.items():
        h.position = body_pos[t, e, bi] + origins[e] - shift
        h.wxyz = body_quat[t, e, bi]


path = (body_pos[:, envs, 0] + origins[envs][None]).reshape(-1, 3)
center = (path.min(0) + path.max(0)) / 2
span = float(np.linalg.norm(path.max(0)[:2] - path.min(0)[:2])) + 2.0
if a.follow:
    center, span = np.zeros(3), 2.4
cam_pos = center + np.array([0.55, -0.85, 0.45]) * max(span, 3.0)
cam_look = center * np.array([1, 1, 0]) + np.array([0.0, 0.0, 0.6])
server.initial_camera.position = tuple(float(x) for x in cam_pos)
server.initial_camera.look_at = tuple(float(x) for x in cam_look)
show(0)

if a.save:
    ser = server.get_scene_serializer()
    for fi in range(len(frames)):
        show(fi)
        ser.insert_sleep(stride * dt)
    Path(a.save).write_bytes(ser.serialize())
    print(f"[replay_viser] saved {a.save} ({Path(a.save).stat().st_size / 1e6:.2f} MB)")
    vec = lambda v: ",".join(f"{x:.2f}" for x in v)  # noqa: E731
    print(f"[replay_viser] static player: <viser-build-client dir>/index.html?playbackPath={Path(a.save).name}"
          f"&initialCameraPosition={vec(cam_pos)}&initialCameraLookAt={vec(cam_look)}")
    server.stop()
    raise SystemExit(0)

if a.video:
    import imageio.v2 as imageio
    from playwright.sync_api import sync_playwright

    W, H = (int(x) for x in a.size.split("x"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                           "--ignore-gpu-blocklist"])
        page = browser.new_page(viewport={"width": W, "height": H})
        page.goto(f"http://localhost:{a.port}")
        while not server.get_clients():
            time.sleep(0.2)
        client = next(iter(server.get_clients().values()))
        client.camera.position = tuple(float(x) for x in cam_pos)
        client.camera.look_at = tuple(float(x) for x in cam_look)
        time.sleep(1.0)
        writer = imageio.get_writer(a.video, fps=1.0 / (stride * dt), codec="libx264", quality=8,
                                    macro_block_size=8)
        t0 = time.time()
        for fi in range(len(frames)):
            show(fi)
            writer.append_data(client.get_render(H, W, transport_format="jpeg", timeout=60))
        writer.close()
        browser.close()
    print(f"[replay_viser] wrote {a.video}: {len(frames)} frames in {time.time() - t0:.0f} s (software WebGL)")
    server.stop()
    raise SystemExit(0)

with server.gui.add_folder("Playback"):
    playing = server.gui.add_checkbox("Playing", True)
    speed = server.gui.add_slider("Speed", min=0.1, max=2.0, step=0.1, initial_value=1.0)
    slider = server.gui.add_slider("Frame", min=0, max=len(frames) - 1, step=1, initial_value=0)
slider.on_update(lambda _: show(slider.value))
print(f"[replay_viser] open http://localhost:{a.port}  (Ctrl+C to stop)")
while True:
    if playing.value:
        slider.value = (slider.value + 1) % len(frames)
    time.sleep(stride * dt / speed.value)
