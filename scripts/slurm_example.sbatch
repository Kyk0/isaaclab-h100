#!/bin/bash
# UNTESTED TEMPLATE. We have not run this on a Slurm cluster.
# It runs the same headless command we use interactively (scripts/train_headless_example.sh).
# Adapt partition/account/time/modules to your cluster before use.
#
#SBATCH --job-name=isaaclab-headless
#SBATCH --partition=<GPU_PARTITION>
#SBATCH --account=<ACCOUNT>
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=%x-%j.out

set -euo pipefail

# module load cuda   # usually not needed: the pip torch/isaacsim wheels bring their own CUDA runtime
# shellcheck disable=SC1091
source "<CONDA_DIR>/etc/profile.d/conda.sh"
conda activate env_isaaclab

export OMNI_KIT_ACCEPT_EULA=YES
export PYTHONUNBUFFERED=1
export WANDB_MODE=offline
# Kit writes caches under $HOME by default; on clusters with small home quotas point them elsewhere, e.g.:
# export XDG_CACHE_HOME="<SCRATCH_DIR>/.cache"

nvidia-smi

REPO="<SONIC_REPO>" MOTION_DIR="<MOTION_LIB_DIR>" NUM_ENVS=4096 ITERS=300 \
  LOG_DIR="<SCRATCH_DIR>/logs" RUN_NAME="finetune_${SLURM_JOB_ID}" \
  bash "<THIS_REPO>/scripts/train_headless_example.sh"
