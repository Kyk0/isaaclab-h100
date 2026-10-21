#!/usr/bin/env bash
# Print the version table used in docs/02-tested-versions.md.
# Usage: activate your Isaac Lab env first (or pass PYTHON=/path/to/python), then:
#   bash scripts/collect_env.sh
set -uo pipefail

PY=${PYTHON:-python}
command -v "$PY" >/dev/null 2>&1 || PY=python3

row() { printf '| %-22s | %s |\n' "$1" "$2"; }
na() { [ -n "$1" ] && echo "$1" || echo "n/a"; }

gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
drv=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)
cuda=$(nvidia-smi 2>/dev/null | sed -n 's/.*CUDA Version: *\([0-9.]*\).*/\1/p' | head -1)
# shellcheck disable=SC1091
os=$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")
kernel=$(uname -r)

# One Python call for all package versions (importlib.metadata does not import the packages).
pkgs=$("$PY" - <<'EOF' 2>/dev/null
import sys, importlib.metadata as md
print("python", sys.version.split()[0])
for label, names in [("isaacsim", ["isaacsim"]), ("isaaclab", ["isaaclab"]),
                     ("torch", ["torch"]), ("rsl_rl", ["rsl-rl-lib", "rsl_rl"]),
                     ("warp", ["warp-lang"]), ("mujoco", ["mujoco"])]:
    v = ""
    for n in names:
        try:
            v = md.version(n); break
        except md.PackageNotFoundError:
            pass
    print(label, v)
try:
    import torch
    print("torch_cuda", torch.version.cuda or "")
except Exception:
    print("torch_cuda", "")
EOF
)
pv() { echo "$pkgs" | awk -v k="$1" '$1 == k { print $2 }'; }

# Isaac Lab repo version (differs from the inner isaaclab package version)
lab_repo=""
for d in "${ISAACLAB_PATH:-}" "$HOME/IsaacLab"; do
  [ -n "$d" ] && [ -f "$d/VERSION" ] && { lab_repo=$(cat "$d/VERSION"); break; }
done

# Vulkan: Isaac Sim's renderer needs the NVIDIA Vulkan ICD; physics does not.
icd="missing"
for f in /usr/share/vulkan/icd.d/nvidia_icd.json /etc/vulkan/icd.d/nvidia_icd.json; do
  [ -f "$f" ] && { icd="present ($f)"; break; }
done

echo "| Component              | Version |"
echo "|------------------------|---------|"
row "GPU" "$(na "$gpu")"
row "NVIDIA driver" "$(na "$drv")"
row "CUDA (driver)" "$(na "$cuda")"
row "OS" "$(na "$os") (kernel $kernel)"
row "Python" "$(na "$(pv python)")"
row "isaacsim" "$(na "$(pv isaacsim)")"
row "isaaclab (package)" "$(na "$(pv isaaclab)")"
row "Isaac Lab (repo)" "$(na "$lab_repo")"
row "torch" "$(na "$(pv torch)") (CUDA $(na "$(pv torch_cuda)"))"
row "rsl_rl" "$(na "$(pv rsl_rl)")"
row "warp" "$(na "$(pv warp)")"
row "mujoco" "$(na "$(pv mujoco)")"
row "NVIDIA Vulkan ICD" "$icd"
