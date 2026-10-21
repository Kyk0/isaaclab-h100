# 3. Install

Good news: there is nothing H100-specific to install. We use a plain conda env with pip wheels on all three machines, with no root and no Docker, following the official [Isaac Lab pip installation](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/setup/installation/pip_installation.html). The installed packages on our machines match these commands exactly (checked with `pip list` and `conda-meta/history`).

## Isaac Sim 5.1 + Isaac Lab 2.3.2

```bash
conda create -n env_isaaclab python=3.11 -y
conda activate env_isaaclab

pip install -U torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cu128
pip install "isaacsim[all,extscache]==5.1.0" --extra-index-url https://pypi.nvidia.com

git clone --branch v2.3.2 https://github.com/isaac-sim/IsaacLab.git <ISAACLAB_DIR>
cd <ISAACLAB_DIR>
./isaaclab.sh --install
```

Add these to your shell profile:

```bash
export OMNI_KIT_ACCEPT_EULA=YES   # otherwise the first launch waits for an EULA prompt
export PYTHONUNBUFFERED=1         # otherwise output piped through tee looks like a hang
```

Optional conda-forge extras we installed: `tmux` (our servers had none), `git-lfs` (for SONIC), `cmake make compilers` (one host).

> [!NOTE]
> You will see `libXt.so.6: cannot open shared object file` messages at startup. They are harmless. Installing `xorg-libxt` from conda-forge does not silence them (Kit's plugin loader does not look in `$CONDA_PREFIX/lib`), so there is no need to bother.

## Check

```bash
bash scripts/collect_env.sh
cd <ISAACLAB_DIR>
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/train.py \
  --task Isaac-Velocity-Flat-G1-v0 --headless --num_envs 4096 --max_iterations 20
```

On a compute-only-driver H100 you will see a few red renderer errors first (all harmless, see [troubleshooting](06-troubleshooting.md)), then `Environment device : cuda:0` and 20 learning iterations. That's a working setup.

## SONIC (GR00T-WholeBodyControl)

Follow the upstream [training installation](https://nvlabs.github.io/GR00T-WholeBodyControl/getting_started/installation_training.html). Into the same `env_isaaclab`:

```bash
git clone https://github.com/NVlabs/GR00T-WholeBodyControl.git <SONIC_REPO>
cd <SONIC_REPO>
git lfs pull
pip install -e "gear_sonic[training]"      # no slash: "gear_sonic/[training]" fails
python check_environment.py --training
python download_from_hf.py --training      # ~30 GB: sonic_release/last.pt + SMPL data
python download_from_hf.py --sample        # ~4 MB: sample_data/ (one walking clip)
```

Good to know:

- `pip install -e "gear_sonic[training]"` changes numpy 1.26.0 → 1.26.4 and hydra-core 1.3.5 → 1.3.2. pip also prints conflicts with `isaacsim-core` pins (torchaudio, filelock, fsspec, markupsafe). Isaac Lab and SONIC training work fine afterwards.
- `check_environment.py` reports `TensorRT_ROOT not set`. TensorRT is only for deployment; ignore it for training.
- Run SONIC from the repo root. Asset paths are relative.
- SONIC's `install_scripts/install_*.sh` are for deployment and teleoperation; training does not need them.
- Checkpoint check: the public `sonic_release/last.pt` we used has sha256 `e6bdab3f64a39336b3d41877d4f497d05f58af275f288ec0e6746c283ded8909`. That matches the Hugging Face LFS object of [nvidia/GEAR-SONIC](https://huggingface.co/nvidia/GEAR-SONIC). Our three copies were downloaded on 2026-06-11, 2026-08-24 and 2026-09-26, and all have this hash. A later re-upload by NVIDIA would change it.
