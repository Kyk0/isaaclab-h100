#!/usr/bin/env bash
# Download the pre-converted Unitree G1 USD (SONIC model), verify its sha256, unpack it into usd/.
#
# Usage:
#   bash scripts/download_usd.sh            # -> usd/g1_sonic/g1_sonic.usd
#   USD_DIR=/some/dir bash scripts/download_usd.sh
#   USD_URL=<URL or file:///path/to/g1_sonic_usd.zip> bash scripts/download_usd.sh
#
# The archive is hosted on Hugging Face: https://huggingface.co/datasets/Kyry10/unitree-g1-usd
# (license notice: docs/05-robot-usd.md and LICENSE-NOTICE.md inside the archive)
set -euo pipefail

USD_URL=${USD_URL:-"https://huggingface.co/datasets/Kyry10/unitree-g1-usd/resolve/main/g1_sonic_usd.zip"}
SHA256=e4084104e4936a6cafa3d33e98ecadcc0473fb643c9e9819a6c6964917fedfa0
ROOT=$(cd "$(dirname "$0")/.." && pwd)
USD_DIR=${USD_DIR:-$ROOT/usd}

if [[ "$USD_URL" == "<"* ]]; then
  echo "USD_URL is not set yet (the archive is not uploaded). Set USD_URL=<url> or convert yourself:" >&2
  echo "  python scripts/convert_robot.py --preset g1_sonic --urdf <SONIC_REPO>/gear_sonic/data/assets/robot_description/urdf/g1/main.urdf --out_dir usd/g1_sonic" >&2
  exit 1
fi
command -v unzip >/dev/null || { echo "unzip is required" >&2; exit 1; }

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -c1-64; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/g1_usd.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
echo "== downloading $USD_URL"
curl -fL --retry 3 -o "$TMP/g1_sonic_usd.zip" "$USD_URL"

got=$(sha "$TMP/g1_sonic_usd.zip")
[ "$got" = "$SHA256" ] || { echo "sha256 mismatch: got $got, expected $SHA256" >&2; exit 1; }
echo "== sha256 OK ($SHA256)"

mkdir -p "$USD_DIR"
[ -e "$USD_DIR/g1_sonic" ] && { echo "$USD_DIR/g1_sonic already exists; remove it first" >&2; exit 1; }
unzip -q "$TMP/g1_sonic_usd.zip" -d "$USD_DIR"
echo "== unpacked: $USD_DIR/g1_sonic/g1_sonic.usd (keep the whole g1_sonic/ directory together)"
echo "   check it: python scripts/convert_robot.py --verify $USD_DIR/g1_sonic/g1_sonic.usd --base_height 0.76"
