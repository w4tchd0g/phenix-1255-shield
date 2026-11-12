#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 w4tchd0g
# SPDX-License-Identifier: CERN-OHL-P-2.0
# Renders 3D images of the PCB for the README.
# Usage: ./scripts/render.sh   (run from anywhere)
set -euo pipefail

cd "$(dirname "$0")/.."

KICAD_CLI="${KICAD_CLI:-$(command -v kicad-cli || echo /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli)}"
KICAD_VERSION="${KICAD_VERSION:-10.0}"
PCB=phenix-1255-shield.kicad_pcb
OUT=docs/img

mkdir -p "$OUT"

# kicad-cli takes the model visibility (THT / SMD / virtual) from the 3D viewer
# settings of the KiCad GUI. Render with a temporary copy of the user config in
# which all models are visible, so the images do not depend on the GUI state.
case "$(uname)" in
  Darwin) CFG_SRC="$HOME/Library/Preferences/kicad" ;;
  *)      CFG_SRC="${XDG_CONFIG_HOME:-$HOME/.config}/kicad" ;;
esac
TMP_CFG=$(mktemp -d)
cleanup() { rm -rf "$TMP_CFG"; rm -f .render-sma-*; }
trap cleanup EXIT
mkdir -p "$TMP_CFG/$KICAD_VERSION"
if [ -d "$CFG_SRC/$KICAD_VERSION" ]; then
  cp -R "$CFG_SRC/$KICAD_VERSION/." "$TMP_CFG/$KICAD_VERSION/"
fi
python3 - "$TMP_CFG/$KICAD_VERSION/3d_viewer.json" <<'EOF'
import json, os, sys
path = sys.argv[1]
cfg = json.load(open(path)) if os.path.exists(path) else {}
render = cfg.setdefault("render", {})
for key in ("show_footprints_normal", "show_footprints_insert", "show_footprints_virtual"):
    render[key] = True
json.dump(cfg, open(path, "w"), indent=2)
EOF
export KICAD_CONFIG_HOME="$TMP_CFG"

# Python for trim.py: needs Pillow or wxPython. KiCad's bundled Python
# (macOS) ships wxPython; otherwise python3 with Pillow.
TRIM_PY="${TRIM_PY:-}"
if [ -z "$TRIM_PY" ]; then
  for py in python3 "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"; do
    if "$py" -c 'import PIL' 2>/dev/null || "$py" -c 'import wx' 2>/dev/null; then TRIM_PY=$py; break; fi
  done
fi
[ -n "$TRIM_PY" ] || { echo "No Python with Pillow or wxPython found (set TRIM_PY)" >&2; exit 1; }

render() {
  local name=$1 board=$2; shift 2
  echo "Rendering $OUT/$name.png"
  "$KICAD_CLI" pcb render "$board" -o "$OUT/$name.png" \
    --width "${WIDTH:-2000}" --height "${HEIGHT:-1300}" --background transparent "$@" >/dev/null 2>&1
}

# Crop to the board (incl. its soft shadow) with a small margin. Images
# trimmed in one call get the same crop box.
trim() {
  "$TRIM_PY" scripts/trim.py 20 "$@" 2>&1 | grep -v -i 'debug' || true
}

render pcb-3d     "$PCB" --quality high --side top --perspective --rotate '-40,0,-30' --zoom 0.9
render pcb-top    "$PCB" --quality basic --side top
render pcb-bottom "$PCB" --quality basic --side bottom
trim "$OUT/pcb-3d.png"
trim "$OUT/pcb-top.png" "$OUT/pcb-bottom.png"

# SMA options for J5/J6: whole board, same camera and same crop, only the
# visible 3D model differs. The temporary boards must sit in the project
# directory so that ${KIPRJMOD} resolves the 3D model paths.
for variant in smd edge; do
  python3 scripts/sma_variant.py "$PCB" ".render-sma-$variant.kicad_pcb" "$variant"
  render "sma-$variant" ".render-sma-$variant.kicad_pcb" --quality high --perspective \
    --rotate '-55,0,-12' --zoom 0.85
done
trim "$OUT/sma-smd.png" "$OUT/sma-edge.png"
