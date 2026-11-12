#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 w4tchd0g (DM5LF)
# SPDX-License-Identifier: CERN-OHL-P-2.0
# Exports Gerber and drill files (4 layers) and packs them into one zip that
# JLCPCB and PCBWay both accept.
# Usage: ./scripts/gerber.sh   (run from anywhere)
# Output: production/gerber/ and production/phenix-1255-shield-gerber.zip
set -euo pipefail

cd "$(dirname "$0")/.."

KICAD_CLI="${KICAD_CLI:-$(command -v kicad-cli || echo /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli)}"
P=phenix-1255-shield
PCB=$P.kicad_pcb
OUT=production/gerber
ZIP=production/$P-gerber.zip

rm -rf "$OUT" "$ZIP"
mkdir -p "$OUT"

# Abort if the DRC reports errors or unconnected items.
"$KICAD_CLI" pcb drc --severity-error --exit-code-violations -o "$OUT/drc.rpt" "$PCB"
rm -f "$OUT/drc.rpt"

# JLCPCB / PCBWay settings: Protel extensions, silkscreen clipped by the solder mask,
# no X2 attributes / netlist, absolute coordinates, zones refilled if outdated.
"$KICAD_CLI" pcb export gerbers -o "$OUT" \
  -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  --subtract-soldermask --no-x2 --no-netlist --check-zones "$PCB"

# Excellon, mm, decimal, PTH and NPTH in separate files, alternate oval format.
"$KICAD_CLI" pcb export drill -o "$OUT/" --format excellon --drill-origin absolute \
  --excellon-units mm --excellon-zeros-format decimal --excellon-oval-format alternate \
  --excellon-separate-th --generate-map --map-format gerberx2 "$PCB"

# The board uses Altium-style layer names ("Top Layer", "GND", ...), which end up
# in the file names. Rename to the canonical names without spaces.
rename() {
  mv "$OUT/$P-$1" "$OUT/$P-$2"
  sed -i.bak "s|$P-$1|$P-$2|" "$OUT/$P-job.gbrjob" && rm -f "$OUT/$P-job.gbrjob.bak"
}
rename "Top Layer.gtl"      F_Cu.gtl
rename "GND.g1"             In1_Cu.g1
rename "PWR.g2"             In2_Cu.g2
rename "Bottom Layer.gbl"   B_Cu.gbl
rename "Top Paste.gtp"      F_Paste.gtp
rename "Bottom Paste.gbp"   B_Paste.gbp
rename "Top Overlay.gto"    F_Silkscreen.gto
rename "Bottom Overlay.gbo" B_Silkscreen.gbo
rename "Top Solder.gts"     F_Mask.gts
rename "Bottom Solder.gbs"  B_Mask.gbs

# Zip without the drill maps (documentation only, not needed by the fab).
(cd "$OUT" && zip -q "../$(basename "$ZIP")" \
  *.gtl *.g1 *.g2 *.gbl *.gtp *.gbp *.gto *.gbo *.gts *.gbs *.gm1 \
  "$P-PTH.drl" "$P-NPTH.drl" "$P-job.gbrjob")

echo "Created $ZIP"
