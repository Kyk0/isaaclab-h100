"""Convert a robot URDF to USD with Isaac Lab 2.x (headless), or check that a USD loads and simulates.

Run inside the Isaac Lab 2.x conda env (Isaac Sim 5.x). Works headless; no renderer needed.

  # preset = the exact UrdfConverterCfg settings of the upstream robot config
  python scripts/convert_robot.py --preset g1_sonic \
      --urdf <SONIC_REPO>/gear_sonic/data/assets/robot_description/urdf/g1/main.urdf --out_dir usd/g1_sonic

  # your own robot (add --capsules / --fix_base as your UrdfFileCfg had them)
  python scripts/convert_robot.py --urdf my_robot.urdf --out_dir usd/my_robot

  # load a USD with sim_utils.UsdFileCfg, step physics for 1 s, print joints/bodies/base height
  python scripts/convert_robot.py --verify usd/g1_sonic/g1_sonic.usd --base_height 0.76
"""

import argparse
import os

from isaaclab.app import AppLauncher

# Converter settings copied from the upstream ArticulationCfg spawn block (UrdfFileCfg):
#   g1_sonic: GR00T-WholeBodyControl gear_sonic/envs/manager_env/robots/g1.py (G1_CYLINDER_MODEL_12_DEX_CFG)
# Everything not listed keeps the Isaac Lab UrdfConverterCfg default (recorded in <out_dir>/config.yaml).
PRESETS = {
    "g1_sonic": dict(name="g1_sonic.usd", fix_base=False, capsules=True),
}

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--urdf", help="URDF to convert")
parser.add_argument("--out_dir", help="output directory (copy this whole directory, not only the .usd)")
parser.add_argument("--preset", choices=sorted(PRESETS), help="use the settings of a known robot config")
parser.add_argument("--name", help="output file name (default: <preset>.usd or <urdf name>.usd)")
parser.add_argument("--fix_base", action="store_true", help="fix the root link to the world")
parser.add_argument("--capsules", action="store_true", help="replace_cylinders_with_capsules=True")
parser.add_argument("--verify", metavar="USD", help="load this USD and step physics instead of converting")
parser.add_argument("--base_height", type=float, default=1.0, help="--verify: initial base height in m")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.headless = True
if not args.verify and not (args.urdf and args.out_dir):
    parser.error("give --urdf and --out_dir to convert, or --verify USD")

app = AppLauncher(args).app

import isaaclab.sim as sim_utils  # noqa: E402  (needs the app running)


def convert():
    p = dict(PRESETS.get(args.preset, {}))
    fix_base = p.get("fix_base", args.fix_base)
    capsules = p.get("capsules", args.capsules)
    name = args.name or p.get("name") or os.path.splitext(os.path.basename(args.urdf))[0] + ".usd"
    cfg = sim_utils.UrdfConverterCfg(
        asset_path=os.path.abspath(args.urdf),
        usd_dir=os.path.abspath(args.out_dir),
        usd_file_name=name,
        fix_base=fix_base,
        replace_cylinders_with_capsules=capsules,
        force_usd_conversion=True,
        joint_drive=sim_utils.UrdfConverterCfg.JointDriveCfg(
            gains=sim_utils.UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=0, damping=0)
        ),
    )
    usd_path = sim_utils.UrdfConverter(cfg).usd_path
    print(f"[convert_robot] preset={args.preset} fix_base={fix_base} replace_cylinders_with_capsules={capsules}")
    print(f"[convert_robot] USD: {usd_path}")
    print(f"[convert_robot] full converter settings: {os.path.join(os.path.dirname(usd_path), 'config.yaml')}")


def verify():
    from isaaclab.actuators import ImplicitActuatorCfg
    from isaaclab.assets import Articulation, ArticulationCfg

    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=args.device))
    ground = sim_utils.GroundPlaneCfg()
    ground.func("/World/ground", ground)
    robot = Articulation(
        ArticulationCfg(
            prim_path="/World/Robot",
            spawn=sim_utils.UsdFileCfg(
                usd_path=os.path.abspath(args.verify),
                activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(disable_gravity=False, max_depenetration_velocity=1.0),
                articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                    enabled_self_collisions=True, solver_position_iteration_count=8, solver_velocity_iteration_count=4
                ),
            ),
            init_state=ArticulationCfg.InitialStateCfg(pos=(0.0, 0.0, args.base_height)),
            # stiff PD on all joints, holding the default pose, only so the check is repeatable
            actuators={"all": ImplicitActuatorCfg(joint_names_expr=[".*"], stiffness=200.0, damping=10.0)},
        )
    )
    sim.reset()
    z0 = float(robot.data.root_pos_w[0, 2])
    for _ in range(200):  # 1 s
        robot.write_data_to_sim()
        sim.step()
        robot.update(sim.get_physics_dt())
    z1 = float(robot.data.root_pos_w[0, 2])
    print(f"[convert_robot] device={sim.device} joints={robot.num_joints} bodies={robot.num_bodies}")
    print(f"[convert_robot] joint names: {robot.joint_names}")
    print(f"[convert_robot] base height {z0:.3f} m -> {z1:.3f} m after 1 s")
    print("[convert_robot] VERIFY OK", flush=True)
    # Release the simulation before app.close(). With Isaac Sim 5.1 headless, sim.stop() (also called
    # inside app.close()) hung at 100 % CPU after this physics run; clearing the context avoids it.
    sim.clear_all_callbacks()
    sim.clear_instance()


try:
    verify() if args.verify else convert()
finally:
    app.close()
