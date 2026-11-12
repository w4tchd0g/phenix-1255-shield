#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 w4tchd0g
# SPDX-License-Identifier: CERN-OHL-P-2.0
"""Writes a copy of the PCB with the 3D models of J5/J6 switched to one SMA option.

Usage: sma_variant.py <input.kicad_pcb> <output.kicad_pcb> smd|edge

  smd   shows the CONSMA001-SMD-G model (vertical SMD jack), hides the Samtec model
  edge  shows the Samtec SMA-J-P-H-ST-EM1 model (edge mount), hides the CONSMA model

Only used by render.sh; the PCB itself is not changed.
"""
import re
import sys

src, dst, variant = sys.argv[1:4]
if variant not in ("smd", "edge"):
    sys.exit("variant must be 'smd' or 'edge'")


def switch_models(footprint):
    if not re.search(r'\(property "Reference" "J[56]"', footprint):
        return footprint

    def model(m):
        text, name = m.group(0), m.group(1)
        visible = ("CONSMA001" in name) if variant == "smd" else ("Samtec" in name)
        text = text.replace("\n\t\t\t(hide yes)", "")
        if not visible:
            text = text.replace("\n", "\n\t\t\t(hide yes)\n", 1)
        return text

    return re.sub(r'\(model "([^"]+)".*?\n\t\t\)', model, footprint, flags=re.S)


board = open(src, encoding="utf-8").read()
board = re.sub(r"\n\t\(footprint .*?\n\t\)(?=\n)", lambda m: switch_models(m.group(0)), board, flags=re.S)
open(dst, "w", encoding="utf-8").write(board)
