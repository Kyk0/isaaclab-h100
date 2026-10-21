# 7. Alternatives

Isaac Lab 2.x is not the only way to put an H100 to work. A few good options:

## mjlab

[mjlab](https://github.com/mujocolab/mjlab) puts Isaac Lab's manager-based API on top of MuJoCo Warp. It needs no Kit and no RTX renderer: simulation is CUDA through Warp, and videos come from MuJoCo. We train BeyondMimic-style motion-tracking policies with it on the compute-only-driver H100 at 4096 envs, with a perfectly clean log. Videos render with MuJoCo on any machine with EGL or a display.

If your task doesn't need Isaac Sim specifically (USD scenes, RTX cameras, PhysX features), this is the simplest way to use an H100.

## Isaac Lab 3.0 (no Isaac Sim, Newton physics)

Isaac Lab 3.0.0 came out on 2026-10-20. Its standard installation runs without Isaac Sim, uses Python 3.12 and installs the Newton physics backend by default (Warp-based, with a MuJoCo-Warp solver). With no Kit in the loop, the renderer questions in this guide go away; the 3.0 docs say *"Headless Newton simulation does not require RTX hardware."* PhysX workflows still go through Isaac Sim, now 6.2 (the 3.0 docs list Isaac Sim 5.1 and older as unsupported), and the same "no RT cores, not supported" line applies to it there. See the [3.0.0 installation guide](https://isaac-sim.github.io/IsaacLab/v3.0.0/source/isaaclab/installation.html) and [physics backends](https://isaac-sim.github.io/IsaacLab/v3.0.0/source/concepts/physics_backends.html).

Many projects (SONIC included) are built on Isaac Lab 2.x and will stay there for a while, which is why this guide focuses on 2.x. A 3.x section is on the roadmap for v0.3. If you try it on an H100 first, we would love a [GPU report](https://github.com/Kyk0/isaaclab-h100/issues/new?template=gpu-report.md).

## Docker / Apptainer (Singularity)

Isaac Lab ships a Docker setup and a cluster guide that turns the image into a Singularity/Apptainer image for Slurm or PBS clusters: [2.3.2 cluster guide](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/deployment/cluster.html), [3.0.0 HPC clusters](https://isaac-sim.github.io/IsaacLab/v3.0.0/source/features/hpc_clusters.html). We went with conda + pip because our servers have no Docker and no root, and containers are planned for v0.3. Inside a container the same rules apply: training needs only CUDA (`--gpus` / `--nv`), and rendering also needs the NVIDIA graphics libraries exposed in the container (with the NVIDIA Container Toolkit, `NVIDIA_DRIVER_CAPABILITIES=all`). TorchRL's [Isaac Lab knowledge-base page](https://docs.pytorch.org/rl/stable/reference/generated/knowledge_base/ISAACLAB.html) lists the EGL/Vulkan packages and checks (`vulkaninfo --summary`) for headless camera rendering in minimal CUDA images.

## Slurm

[`scripts/slurm_example.sbatch`](../scripts/slurm_example.sbatch) is a starting template that runs the same headless command as a batch job. Adjust partition, account, time and module loads for your cluster. It has not been run on a cluster yet; if you use it, tell us how it went.
