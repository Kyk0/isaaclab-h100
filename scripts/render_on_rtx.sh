#!/usr/bin/env bash
# Isaac Lab native render of a SONIC checkpoint on an RTX GPU (needs RT cores + Vulkan; fails on H100, A100 untested).
#
# Usage (inside the activated Isaac Lab conda env, on the RTX machine):
#   REPO=<SONIC_REPO> bash scripts/render_on_rtx.sh CHECKPOINT.pt MOTION_LIB_DIR OUT_DIR
#
# Writes OUT_DIR/video/000000.mp4 (first motion), OUT_DIR/metrics_eval.json, OUT_DIR/eval.log.
# Keep the run's config.yaml next to the checkpoint (copy both with sync_checkpoints.sh).
set -euo pipefail

[ $# -eq 3 ] || { sed -n '2,8p' "$0"; exit 1; }
REPO=${REPO:?set REPO to the GR00T-WholeBodyControl checkout}
abspath() { (cd "$(dirname "$1")" && echo "$(pwd)/$(basename "$1")"); }
CKPT=$(abspath "$1"); MOTION_DIR=$(abspath "$2"); OUT=$3
mkdir -p "$OUT"; OUT=$(abspath "$OUT")

[ -f "$CKPT" ] || { echo "no checkpoint: $CKPT" >&2; exit 1; }
[ -f "$(dirname "$CKPT")/config.yaml" ] || echo "warning: no config.yaml next to $CKPT" >&2
if [ ! -f /usr/share/vulkan/icd.d/nvidia_icd.json ] && [ ! -f /etc/vulkan/icd.d/nvidia_icd.json ]; then
  echo "warning: no NVIDIA Vulkan ICD found; Isaac Sim rendering will most likely fail here" >&2
fi

export PYTHONUNBUFFERED=1 OMNI_KIT_ACCEPT_EULA=${OMNI_KIT_ACCEPT_EULA:-YES}
cd "$REPO"
echo "== rendering $CKPT on $MOTION_DIR -> $OUT (log $OUT/eval.log)"
python gear_sonic/eval_agent_trl.py \
  "+checkpoint=$CKPT" +headless=True \
  ++eval_callbacks=im_eval ++run_eval_loop=False ++num_envs=1 \
  ++manager_env.config.render_results=True "++manager_env.config.save_rendering_dir=$OUT/video" \
  ++manager_env.config.env_spacing=10.0 \
  "~manager_env/recorders=empty" "+manager_env/recorders=render" \
  ++manager_env.observations.policy.enable_corruption=False \
  ++manager_env.observations.tokenizer.enable_corruption=False \
  "+manager_env/terminations=tracking/eval" \
  "++manager_env.commands.motion.motion_lib_cfg.motion_file=$MOTION_DIR" \
  ++manager_env.commands.motion.motion_lib_cfg.smpl_motion_file=dummy \
  "++eval_output_dir=$OUT" > "$OUT/eval.log" 2>&1 || { echo "eval failed, see $OUT/eval.log" >&2; exit 1; }

ls -la "$OUT/video"
[ -f "$OUT/metrics_eval.json" ] && python - "$OUT/metrics_eval.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
print("success %.2f  mpjpe_l %.1f mm  mpjpe_g %.1f mm" % (
    d["eval/success/success_rate"], d["eval/all/mpjpe_l"], d["eval/all/mpjpe_g"]))
EOF
