#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 w4tchd0g (DM5LF)
# SPDX-License-Identifier: CERN-OHL-P-2.0
"""Generates the simplified 3D models in ext_parts/3d/ from datasheet dimensions.

Usage: make_3d_models.py [output directory]   (default: ext_parts/3d next to this script)

Needs build123d (pip install build123d). The models are simple solids for
rendering and collision checks, not mechanical drawings. Coordinates follow
the KiCad convention: origin at the footprint origin, X right, Y up (the
footprint Y axis inverted), Z up from the board surface, units mm.

  LFCN-490+.step        Mini-Circuits LFCN-490+, case FV1206 (datasheet outline drawing)
  EVQ-Q2Y03W.step       Panasonic EVQ-Q2 light touch switch (catalog ANCTB12E), 3.1 mm high
  CONSMA001-SMD-G.step  TE CONSMA001-SMD-G vertical SMA jack (drawing Rev. F)
"""
import os
import sys

from build123d import Align, Box, Color, Compound, Cylinder, Pos, export_step

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "ext_parts", "3d")

BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)

GOLD = Color(0.86, 0.70, 0.32)
TIN = Color(0.82, 0.82, 0.84)
CERAMIC = Color(0.86, 0.84, 0.78)
BLACK = Color(0.10, 0.10, 0.10)
DARK = Color(0.25, 0.25, 0.27)
PTFE = Color(0.95, 0.95, 0.93)
WHITE = Color(0.93, 0.93, 0.91)


def part(shape, label, color):
    shape.label = label
    shape.color = color
    return shape


def save(name, children):
    model = Compound(label=name, children=children)
    path = os.path.join(OUT, name + ".step")
    export_step(model, path)
    print("wrote", os.path.normpath(path))


def box(x0, x1, y0, y1, z0, z1):
    """Axis-aligned box between the given coordinates (any order)."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, z0) * Box(
        x1 - x0, y1 - y0, z1 - z0, align=BOTTOM)


def cyl(d, z0, z1, x=0.0, y=0.0):
    return Pos(x, y, z0) * Cylinder(d / 2, z1 - z0, align=BOTTOM)


def lfcn_490():
    # Outline drawing: A = 3.20 (length), B = 1.60 (width), C = 0.94 (height),
    # D = 0.51 (end termination), E = 0.81 (ground termination), F = 0.23.
    a, b, c, d, e, f = 3.20, 1.60, 0.94, 0.51, 0.81, 0.23
    t = 0.02  # termination thickness
    body = box(-a / 2 + t, a / 2 - t, -b / 2 + t, b / 2 - t, t, c - t)
    terms = []
    for s in (-1, 1):
        # pins 1 and 3: wrap-around end terminations
        terms.append(box(s * a / 2, s * (a / 2 - d), -b / 2, b / 2, 0, c))
        # pins 2 and 4: ground terminations on the long sides
        terms.append(box(-e / 2, e / 2, s * b / 2, s * (b / 2 - f), 0, c))
    termination = terms[0].fuse(*terms[1:])
    body = body.cut(termination)
    index = box(-a / 2 + d + 0.12, -a / 2 + d + 0.42, -0.15, 0.15, c - t, c)
    save("LFCN-490+", [
        part(body, "body", CERAMIC),
        part(termination, "terminals", TIN),
        part(index, "index", DARK),
    ])


def evq_q2():
    # Catalog ANCTB12E, EVQQ2..03W: 6.5 x 6.0 mm, body 1.8 mm high, push plate
    # 3.8 / 3.0 mm diameter, 3.1 mm overall height, terminals span 6.6 mm.
    base = box(-3.0, 3.0, -3.0, 3.0, 0.0, 1.5)
    cover = box(-3.0, 3.0, -3.0, 3.0, 1.5, 1.8)
    stem = cyl(3.8, 1.8, 2.3).fuse(cyl(3.0, 2.3, 3.1))
    pins = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            y = sy * 2.0
            pins.append(box(sx * 2.8, sx * 3.3, y - 0.35, y + 0.35, 0.0, 0.2))
            pins.append(box(sx * 3.0, sx * 3.15, y - 0.35, y + 0.35, 0.2, 0.9))
    terminals = pins[0].fuse(*pins[1:])
    save("EVQ-Q2Y03W", [
        part(base, "base", BLACK),
        part(cover, "cover", TIN),
        part(stem, "push_plate", WHITE),
        part(terminals, "terminals", TIN),
    ])


def consma001():
    # Drawing Rev. F: 7.00 mm square body on four 1.50 mm legs (1.00 mm high,
    # 4.00 mm apart), barrel 5.38 mm, 1/4-36 UNS thread, 10.40 mm overall.
    legs = [box(sx * 2.0, sx * 3.5, sy * 2.0, sy * 3.5, 0.0, 1.0)
            for sx in (-1, 1) for sy in (-1, 1)]
    body = legs[0].fuse(*legs[1:])
    body = body.fuse(box(-3.5, 3.5, -3.5, 3.5, 1.0, 2.5))
    body = body.fuse(cyl(5.38, 2.5, 5.9))
    # thread: rings of 6.35 mm with 0.705 mm pitch (36 tpi)
    z = 5.9
    while z < 9.4 - 0.01:
        body = body.fuse(cyl(6.35, z, min(z + 0.45, 9.4)))
        body = body.fuse(cyl(5.9, min(z + 0.45, 9.4), min(z + 0.705, 9.4)))
        z += 0.705
    body = body.fuse(cyl(5.38, 9.4, 10.4))
    # bore for the PTFE insulator (4.60 mm), insulator recessed 2.54 mm
    body = body.cut(cyl(4.6, 5.36, 10.5))
    insulator = cyl(4.572, 5.36, 7.86).cut(cyl(1.6, 5.36, 7.9))
    # centre contact: slotted socket, flush with the mounting plane
    socket = cyl(1.27, 0.0, 7.86).cut(cyl(0.9, 6.0, 7.9))
    socket = socket.cut(box(-0.12, 0.12, -0.7, 0.7, 6.4, 7.9))
    body = body.cut(cyl(1.9, 0.0, 5.4))
    save("CONSMA001-SMD-G", [
        part(body, "body", GOLD),
        part(insulator, "insulator_PTFE", PTFE),
        part(socket, "socket_contact", GOLD),
    ])


if __name__ == "__main__":
    lfcn_490()
    evq_q2()
    consma001()
