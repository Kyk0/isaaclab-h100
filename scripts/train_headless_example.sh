#!/usr/bin/env bash
# Headless SONIC fine-tune from the public release checkpoint (tested on H100; A100 untested, should behave the same).
#
# Usage (inside the activated Isaac Lab conda env):
#   REPO=<SONIC_REPO> MOTION_DIR=<MOTION_LIB_DIR> bash scripts/train_headless_example.sh [--dry-run]
#
# Optional env vars:
#   NUM_ENVS=4096  ITERS=300  SAVE_EVERY=25  RUN_NAME=finetune_<timestamp>
#   LOG_DIR=$PWD/logs  WANDB_MODE=offline  CUDA_VISIBLE_DEVICES=0
#   EXTRA="++key=value ..."   extra Hydra overrides
#   SKIP_HASH=1               skip the release checkpoint hash check
set -euo pipefail

REPO=${REPO:?set REPO to the GR00T-WholeBodyControl checkout}
MOTION_DIR=${MOTION_DIR:?set MOTION_DIR to a folder of robot motion-lib .pkl files}
NUM_ENVS=${NUM_ENVS:-4096}
ITERS=${ITERS:-300}
SAVE_EVERY=${SAVE_EVERY:-25}
RUN_NAME=${RUN_NAME:-finetune_$(date +%Y%m%d_%H%M%S)}
LOG_DIR=${LOG_DIR:-$PWD/logs}
EXTRA=${EXTRA:-}
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# SHA-256 of sonic_release/last.pt from huggingface.co/nvidia/GEAR-SONIC (same on copies downloaded 2026-06-11 .. 2026-09-26).
RELEASE_SHA=e6bdab3f64a39336b3d41877d4f497d05f58af275f288ec0e6746c283ded8909

export PYTHONUNBUFFERED=1
export WANDB_MODE=${WANDB_MODE:-offline}
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
export OMNI_KIT_ACCEPT_EULA=${OMNI_KIT_ACCEPT_EULA:-YES}

[ -f "$REPO/gear_sonic/train_agent_trl.py" ] || { echo "not a SONIC repo: $REPO" >&2; exit 1; }
[ -d "$MOTION_DIR" ] || { echo "no motion dir: $MOTION_DIR" >&2; exit 1; }
MOTION_DIR=$(cd "$MOTION_DIR" && pwd)

echo "== GPU (other processes on it are listed too)"
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader || true
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader || true

CKPT=$REPO/sonic_release/last.pt
[ -f "$CKPT" ] || { echo "missing $CKPT (run: python download_from_hf.py --training)" >&2; exit 1; }
if [ "${SKIP_HASH:-0}" != 1 ]; then
  echo "== checking release checkpoint hash"
  got=$(sha256sum "$CKPT" | cut -c1-64)
  [ "$got" = "$RELEASE_SHA" ] || { echo "hash mismatch: $got (set SKIP_HASH=1 if you use a newer release)" >&2; exit 1; }
fi

cmd=(python gear_sonic/train_agent_trl.py
  +exp=manager/universal_token/all_modes/sonic_release
  +checkpoint=sonic_release/last.pt
  "num_envs=$NUM_ENVS" headless=True
  "++manager_env.commands.motion.motion_lib_cfg.motion_file=$MOTION_DIR"
  ++manager_env.commands.motion.motion_lib_cfg.smpl_motion_file=dummy
  "++algo.config.num_learning_iterations=$ITERS"
  "++callbacks.model_save.save_frequency=$SAVE_EVERY"
  "++exp_var=$RUN_NAME")
# shellcheck disable=SC2206  # EXTRA is meant to split into separate overrides
[ -n "$EXTRA" ] && cmd+=($EXTRA)

mkdir -p "$LOG_DIR"
LOG=$LOG_DIR/$RUN_NAME.log
echo "== command (cwd $REPO, WANDB_MODE=$WANDB_MODE, CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES)"
printf '%q ' "${cmd[@]}"; echo
[ $DRY_RUN = 1 ] && { echo "(dry run, not started)"; exit 0; }

echo "== log: $LOG   (renderer [Error] lines at startup are expected on H100; see docs/06-troubleshooting.md)"
cd "$REPO"
"${cmd[@]}" 2>&1 | tee "$LOG"
