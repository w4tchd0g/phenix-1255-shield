#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 w4tchd0g (DM5LF)
# SPDX-License-Identifier: CERN-OHL-P-2.0
"""Crops rendered PNGs (transparent background) to their content plus a margin.

Usage: trim.py MARGIN_PX IMAGE.png [IMAGE.png ...]

All images given in one call get the same crop box (the union of their
contents), so views rendered with the same camera stay aligned. Pixels count
as content from alpha >= 8, which keeps the soft floor shadow complete.

Needs Pillow or wxPython (KiCad's bundled Python ships wxPython). Only used by
render.sh.
"""
import sys

ALPHA_MIN = 8

margin = int(sys.argv[1])
files = sys.argv[2:]

try:
    from PIL import Image

    def load(path):
        img = Image.open(path).convert("RGBA")
        return img, img.width, img.height, img.getchannel("A").tobytes()

    def save(img, box, path):
        img.crop((box[0], box[1], box[2] + 1, box[3] + 1)).save(path)

except ImportError:
    import wx

    app = wx.App(False)

    def load(path):
        img = wx.Image(path)
        if not img.HasAlpha():
            img.InitAlpha()
        return img, img.GetWidth(), img.GetHeight(), bytes(img.GetAlphaBuffer())

    def save(img, box, path):
        sub = img.GetSubImage(wx.Rect(box[0], box[1], box[2] - box[0] + 1, box[3] - box[1] + 1))
        sub.SaveFile(path, wx.BITMAP_TYPE_PNG)


# map alpha to 0/1 so a row can be searched with find()/rfind()
mask = bytes(1 if v >= ALPHA_MIN else 0 for v in range(256))
images, box = [], None
for path in files:
    img, w, h, alpha = load(path)
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        row = alpha[y * w:(y + 1) * w].translate(mask)
        first = row.find(1)
        if first >= 0:
            x0, x1 = min(x0, first), max(x1, row.rfind(1))
            y0, y1 = min(y0, y), y
    if x1 < 0:
        sys.exit(f"{path}: image is empty")
    box = (x0, y0, x1, y1) if box is None else (min(box[0], x0), min(box[1], y0), max(box[2], x1), max(box[3], y1))
    images.append((path, img, w, h))

for path, img, w, h in images:
    b = (max(box[0] - margin, 0), max(box[1] - margin, 0), min(box[2] + margin, w - 1), min(box[3] + margin, h - 1))
    save(img, b, path)
    print(f"{path}: {w}x{h} -> {b[2] - b[0] + 1}x{b[3] - b[1] + 1}")
