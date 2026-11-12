# CLAUDE.md

Working notes for phenix-1255-shield: an SX1255 RF shield for the NXP FRDM-MCXN947 (KiCad 10). It is the hardware part of [phenix-1255-sw](https://github.com/w4tchd0g/phenix-1255-sw) and a modified version of [Phenix-1255-HW](https://github.com/labdvm/Phenix-1255-HW) by Z32IT. `README.md` covers what the project is, the circuit, the pin assignment, fabrication and bring-up. This file holds everything else: conventions, settled decisions, known warnings, layout details and the background of the RF calculations.

## Conventions

- The user writes in German. Answer in German.
- Write all repository content in English: README, CLAUDE.md, comments in scripts and in the design rules.
- Keep the README limited to what matters for building and using the board. Put layout conventions, tool details and derivations here.
- After every layout change, run `./scripts/gerber.sh` and `./scripts/render.sh` and update the README where needed. Commit only when the user asks.

## Tools

- `kicad-cli`: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (not on `PATH`). The scripts find it on their own.
- Python with the `pcbnew` module: `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`. The assertion `create wxApp before calling this` on stderr is harmless. Without a wxApp, text bounding boxes of rotated text are not reliable; calculate them by hand (stroke font: 1.0 mm text ≈ 1.14 mm high including stroke, "S1" ≈ 2.27 mm wide).
- The shell is zsh: `set -- $var` does not split words there. Use `bash -c` for loops of that kind.
- Checks:
  - ERC: `kicad-cli sch erc --severity-all phenix-1255-shield.kicad_sch`
  - DRC: `kicad-cli pcb drc --schematic-parity --severity-all phenix-1255-shield.kicad_pcb`
- Visual check of silkscreen and mask: `kicad-cli pcb export svg --layers F.Mask,F.SilkS,Edge.Cuts --mode-single --exclude-drawing-sheet` (without `--fit-page-to-board`, so SVG coordinates are board coordinates), then set the `viewBox` to the area of interest and convert with `rsvg-convert` (Homebrew).

### Scripts

- `scripts/gerber.sh`: runs the DRC (aborts on errors or unconnected items), exports Gerber with JLCPCB settings (Protel extensions, `--subtract-soldermask`, no X2, no netlist, `--check-zones`) and Excellon drill files (mm, decimal, PTH/NPTH separate, alternate oval format), renames the Altium-style layer names (`Top Layer`, `GND`, `PWR`, …) to `F_Cu`, `In1_Cu`, … and zips everything except the drill maps into `production/phenix-1255-shield-gerber.zip`. JLCPCB and PCBWay both take this file set (Protel extensions, `.g1`/`.g2` for the inner layers).
- `scripts/render.sh`: renders `docs/img/` with `kicad-cli pcb render`. It uses a temporary copy of the KiCad configuration in which all 3D model types are visible, so the images do not depend on the GUI settings. For the SMA images, `scripts/sma_variant.py` writes temporary copies of the board (`.render-sma-*.kicad_pcb`, in the project directory so that `${KIPRJMOD}` resolves) in which only the visible 3D model of J5/J6 differs. The PCB itself keeps the CONSMA001-SMD-G model visible. `scripts/trim.py` crops each image to the board and its shadow (needs Pillow or wxPython; on macOS the KiCad Python is used). Images trimmed in one call get the same crop box.
- `scripts/rf_calc.py`: all RF numbers (see [RF calculation details](#rf-calculation-details)).
- `scripts/make_3d_models.py`: generates the own 3D models (see [External components](#external-components)).

### Editing the board file directly

- All footprints are locked. Edits by script or `sed` are fine, but read the affected block first.
- In a footprint, the `at` of a property or text is footprint-relative (rotated with the footprint), but its angle is absolute. Example: S1–S3 are rotated 180°, and their reference is at `(at 4.3 0 90)`.
- When the graphics of a footprint change on the board, make the same change in the library footprint in `ext_parts/`, otherwise *Update footprints from library* reverts it. Exception: reference positions only live on the board; do not tick *Reset text positions* when updating.

## Settled decisions (do not flag again)

- **SX_RST** (IC1.9 → J1.6) has no pull resistor. The SX1255 datasheet requires it to be left open; the MCU drives it high only to reset.
- **38.4 MHz TCXO** is outside the SX1255 FXOSC range but has been tested by the user and works. Mention it neutrally at most.
- **Buttons S1–S3 and jumpers JP1–JP3** use the MCU internal pull-downs; no external pull-downs.
- **Display DS1** has on-board I²C pull-ups.
- **`~PA_EN`**: 100 kΩ pull-up to `+3v3` (FRDM domain), driven by an MCU GPIO. U2 is the TPS22917L with active-low enable.
- **Headers J1–J4, J8, J9** come from the template. Footprint, library and field issues on them are out of scope.
- **Missing MPNs / part numbers** (FL1, FL2, J5, J6, DS1, and the PCB-side `MPN` fields) are not part of reviews.
- Reference designators were re-annotated on 2026-11-04. Identify parts by net and value when reading older notes.

## Known ERC/DRC warnings

- **ERC:** no errors.
  - Warnings come from unused template labels and wire stubs at the headers (`isolated_pin_label`, `unconnected_wire_endpoint`), from header pins with two names (`multiple_net_names`), and from the template header symbols without a library nickname (`footprint_link_issues`).
  - The `PWR_FLAG`s for `+3v3`, `+5v0`, `GND`, `5v-9v-IN` and `VDDA` sit in the root schematic next to the sheet symbol.
  - The `pin_to_pin` warning U2 QOD ↔ VOUT is excluded in the project file (intended per the TPS22917 datasheet). The exclusion is bound to the position of U2: if U2 is moved or replaced, exclude it again.
- **DRC:** no errors, 0 unconnected pads. The 130 warnings are:
  - 124 × `padstack` on the header THT pads (negative paste margin), harmless.
  - 6 × `lib_footprint_issues`: the libraries `FRDM-MCXN947__Template__A.PcbLib` and `Wavenumber` of the template headers are not in `fp-lib-table`.
- **Ignored checks** in the project: `missing_courtyard` (only the template headers and the logo have none), `pth_inside_courtyard`, `npth_inside_courtyard`, `track_not_centered_on_via`, `footprint_type_mismatch`, `footprint_filters_mismatch`. Enabling them on a copy shows nothing beyond the missing courtyards.
- **Schematic parity:** no net or footprint mismatches. Remaining differences:
  - field mismatches (`MPN`, `Description`, `Sim.Pins`, `Height`, …);
  - JP1–JP3 values (`JP1` on the PCB vs. `0` in the schematic);
  - the headers are *Do not populate* on the PCB only;
  - the header footprint names have a library nickname on the PCB only.
- **Update PCB from Schematic:** untick *Delete footprints with no symbols* (otherwise the logo is deleted) and *Replace footprints* (the header symbols have no library nickname).
- **Plane splits on In2:** DIO1, DIO2/WS, DIO3 and NSS (SX1255 side) on B.Cu cross gaps between the In2 areas. This is uncritical at their speeds.

## Layout details

### Net classes and rules

| Class | Nets | Track | Clearance | Via (Ø / drill) |
|---|---|---|---|---|
| Default | everything else | 0.2 mm | 0.2 mm | 0.6 / 0.3 mm |
| RF | `RF_*` and the nets between SX1255, matching, filters and SMA | 0.3 mm | 0.3 mm | – (no vias allowed) |
| PWR_5V | `+5v0`, `5v-9v-IN` | 0.5 mm | 0.2 mm | 0.8 / 0.4 mm |
| PWR_3V3 | `+3v3`, `+3.3V_LDO`, `VBAT3`, `VDDA` | 0.4 mm | 0.2 mm | 0.8 / 0.4 mm |
| GND | `GND` | 0.4 mm | 0.2 mm | 0.6 / 0.3 mm |

- The vias actually placed on the power nets are mostly 0.6 / 0.3 mm (`+3.3V_LDO` 17×, `+5v0` 2×, `+3v3` 2×; three `+3v3` vias are 0.8 / 0.4 mm). This is sufficient for the currents involved.
- Board minimums: 0.15 mm track, clearance and annular ring; 0.5 mm via diameter; 0.3 mm drill; 0.5 mm copper to edge; 0.25 mm hole to hole. Silkscreen text is at least 1.0 mm high and 0.15 mm thick.

`phenix-1255-shield.kicad_dru` adds rules that the net classes cannot express. KiCad 10 needs a unit on every value, otherwise the whole file is rejected.

- **RF:** no vias, and no tracks on the inner layers or B.Cu (the reference there would be the power plane).
- **SX1255 fine pitch:** inside the IC1 courtyard the RF clearance drops to 0.2 mm, pad-to-pad within IC1 to 0.15 mm (the corner pads are 0.177 mm apart). Non-RF tracks may neck down to 0.15 mm (opt. 0.25 mm) there.
- **Solid GND at RF parts:** the GND pads of IC1, FL*, J5/J6, D1/D4/D8 connect without thermal reliefs.
  - Exception J5/J6: a local pad override takes precedence over the rule, so an edge-mount jack can be hand-soldered.
  - F.Cu: thermal relief with 1.0 mm spokes and a 0.3 mm gap. The spokes are placed by templates in the footprint: one towards the RF line, three outwards into the via fence, none towards the centre pin or the board edge.
  - B.Cu: 0.8 mm spokes, 0.3 mm gap.
  - The anchor of the CONSMA GND pads is 2 × 2 mm, because KiCad limits the spoke width to the smallest anchor size.
- **Stitching vias:** at least 0.25 mm between drill holes (JLCPCB minimum 0.2 mm).

### Ground and stitching

The GND fills on all four layers are tied together with 323 GND vias (0.6 / 0.3 mm):

- **Via fences** along both RF lines (0.8 mm from the line, 0.765 mm pitch, radially paired in the bends), between J5 and J6, and around the J5/J6 ground pads.
- **Pad vias:** each ground pad of the decoupling capacitors, the TCXO, the LDO, the load switch, the TVS diodes and the TX filter has its own via.
- **Stitching grid:** 7.62 mm grid centred on the board centre (148.50 / 105.00 mm).
  - Grid points that would hit pads, tracks, courtyards, header rows, silkscreen, the framed function blocks or the B.Cu logo are left out.
  - Four formally free points stay empty: 148.50 / 97.38 and 171.36 / 97.38 (too close to the C10 and FL1 labels), and 110.40 / 89.76 and 118.02 / 89.76 (too close to the DS1 outline and the SDA track).
  - One extra via at 186.60 / 94.51 mm ties the fill between the `HW_ID_1` and `HW_ID_2` tracks to GND.
- **No islands:** each fill area large enough for a via is tied to GND. The zones use *Remove islands: Always*, so no floating copper is left.

### SX1255 footprint

`ext_parts/SX1255IWLTRT.pretty` follows the recommended land pattern of the SX1255 datasheet Rev. 3.1, figure 7-2: pads 0.30 × 0.80 mm on a 4.90 mm row pitch, exposed pad 3.30 × 3.30 mm (the package pad is 3.10 mm nominal). It has thermal vias in the exposed pad. The paste on the exposed pad is split into 8 openings (4 windows between the vias, 4 border strips), about 50 % coverage, kept 0.25 mm from the via centres.

### Silkscreen

- **Reference designators:** 1.0 mm high, 0.17 mm thick (JLCPCB: at least 1.0 mm / 0.153 mm).
  - They run parallel to the part, centred on its axis, 0.4 mm from pads and part silkscreen, preferably in line with the part.
  - Rows of equal parts are labelled on the same side. Labels may lie on tented vias.
  - Distances refer to the visible text outline, stroke included.
  - J1–J4 and J9 labels sit vertically centred beside their header, J8 below it.
- **Exceptions:**
  - C2 and C3: 0.3 mm from their pads, because the row above (D2, R1) leaves no more room. Both labels are at the same height.
  - R1: at the same height as D2 (LED and series resistor of the PWR LED), therefore 0.6 mm from its own silkscreen.
  - IC1: left of the part near its upper end, in the resistor column above R3, centred between R3 and the pads of C10/C11 (0.61 mm on both sides). This puts it 1.0 mm from the IC1 pads and 3.0 mm above the IC1 axis. R3 and R6 sit at the height of the IC1 pins they connect to (pins 10 and 15), so there is no room for the label between them.
  - D4: left of the part and below its axis, because the courtyard and pads of IC1 are above it.
  - S1–S3: vertical (90°) on the left side of the switch, between pads 3 and 4, footprint-relative at x = 4.3, about 0.35 mm from the body outline.
  - S1–S3 pin-1 dot: below pad 1, centred between the end of the body outline and the end of the pad (footprint-relative −4.125 / −3.0), 0.26 mm from the pad. The same position is in the library footprint `EVQQ2`. The earlier position sat almost on pad 4 of the neighbouring switch.
  - DS1: outside the display outline at its top left, in line with the pin row (footprint-relative −15.81 / 0), 0.41 mm left of the outline, like the J2 label above it. Anything inside the outline is covered by the fitted module.
  - J5/J6: above the jack but 2.6 mm left of its axis, at the height of D1/D8, because L1/D1 and L5/D8 sit on the RF line above the jack centre.
  - R4 and R14: the "R" is flush with the neighbouring label (R5 beside R4, R13 below R14). Because the "4" is wider, both labels are 0.35 mm from their pads.
- **Hidden references:** JP1–JP3 (their labels are `0`–`2`) and the logo `G***`.
- **Display pin labels** (`GND`, `VDD`, `SCL`, `SDA`) run vertically below the pins. The display outline is interrupted there, in the library footprint as well.
- **Edge labels:** `MCU-Link`, `Ethernet` and `HS-USB` on the left edge mark the FRDM connectors below. They are 1.5 mm from the board edge or cutout and centred in their section.
- **Button and LED labels:** button labels (`<--`, `OK`, `-->`) and LED labels (`OK`, `INFO`, `ERR`) are centred above their parts at the same height. The LEDs and their resistors sit on a 6.35 mm grid.
- **Function blocks:** `LDO`, `PA Enable` and `HW ID` are framed. `PA Enable` and `HW ID` share the top edge, and their labels sit at the same distance above it. The `+3v3` vias of the HW ID jumpers sit exactly halfway between the jumpers.
- **SMA labels:** `RX (430MHz)` and `TX (440MHz)`.

### SMA land pattern (J5/J6)

`CONSMA001-SMD-G_EdgeHybrid` combines the CONSMA001-SMD-G pads with the pads of the Samtec SMA-J-P-H-ST-EM1 edge mount (from the KiCad footprint `SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount`, 1.57 mm board).

- **Placement:** the footprint origin is 4.4 mm from the board edge, so the edge-mount centre pad (1.27 × 3.2 mm, y = 0.7 … 3.9 mm) runs straight into the round CONSMA centre pad (Ø2.05 mm). The RF track ends at the centre of the round pad.
- **GND pads:**
  - The CONSMA GND pads follow the TE drawing (Rev. F): Ø4.56 mm clearance cut-out, pad 1 = centre, pad 2 = GND.
  - On F.Cu, the edge-mount GND legs sit on the CONSMA GND pads. The separate F.Cu edge-mount GND tabs were removed because they cut into the clearance around the centre pin.
  - The B.Cu tabs stay.
- **Paste:** the edge-mount pads have no paste.
- **3D models:**
  - The CONSMA model is generated by `scripts/make_3d_models.py` from the TE drawing (7 mm body on four 1.5 mm legs, barrel 5.38 mm, thread rings 6.35 mm, 10.4 mm high). Its origin is at the mounting plane. It has a PTFE insulator recessed 2.54 mm and a slotted centre socket flush with the mounting plane.
  - The Samtec model (`ext_parts/3d/SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount.step`) is the KiCad library model with an added insulator and socket. The insulator is flush with the front face (0.05 mm back), because a deeper recess renders as a dark slot.
  - The Samtec model is included but hidden on the board.

## RF calculation details

`scripts/rf_calc.py` reproduces all numbers below.

### CPWG impedance

- **Model:** CPWG on F.Cu over In1 at 0.2104 mm (prepreg 7628, εr 4.4), copper 35 µm. In1 has no cut-outs under the RF section. The coplanar ground is the F.Cu fill, tied to In1 by the via fences.
- **Closed form** (Wadell conformal mapping, Gupta thickness correction), gap 0.30 mm:

  | Track width | 0.25 mm | **0.30 mm** | 0.35 mm | 0.40 mm |
  |---|---|---|---|---|
  | Z0 | 54.7 Ω | **50.2 Ω** | 46.5 Ω | 43.3 Ω |

  The closed form gives εeff 3.19 for 0.30 / 0.30 mm, and 47.0 Ω at 0.30 / 0.20 mm (inside the IC1 courtyard).
- **Field solver:** 2D Laplace equation, finite differences, half cross-section with symmetry plane, 5 µm grid, 6 × 2.25 mm domain. Z0 = 1 / (c · √(C · C_air)). Halving the grid changes Z0 by less than 0.05 Ω.

  | Section | Bare copper | With 15 µm solder mask (εr 3.8) |
  |---|---|---|
  | 0.30 / 0.30 mm | 53.7 Ω, εeff 2.98 | **52.2 Ω**, εeff 3.15 |
  | 0.30 / 0.20 mm (IC1) | 51.6 Ω, εeff 2.88 | 49.9 Ω, εeff 3.07 |

- **Result:** about 52 Ω gives |Γ| ≈ 0.02, a return loss of about 33 dB and a mismatch loss below 0.01 dB.
  - The guided wavelength at 440 MHz is about 350 mm. The longest RF net (J5 to the TX filter) is 23 mm long.
  - An etching tolerance of ±0.03 mm shifts Z0 by ±2–3 Ω.
  - Not modelled: εr dispersion and tolerance, copper roughness.

### Open stub at the SMA jacks

With the CONSMA jack fitted, the part of the edge-mount centre pad beyond the round pad is an open stub: 1.27 mm wide, 2.9 mm long (3.9 mm from the pad centre as the worst case), 0.8 mm gap to the GND pads, In1 0.21 mm below.

- **Line parameters** (field solver, w = 1.27 mm, s = 0.805 mm): Z_S = 21.6 Ω, εeff = 3.58, C' = 293 pF/m. The open end adds 0.09 mm (Hammerstad/Kirschning).
- **Model:** Y = j · tan(βl) / Z_S, i.e. C ≈ C' · l.

| 440 MHz | 2.9 mm | 3.9 mm (worst case) |
|---|---|---|
| Electrical length | 3.0° | 4.0° |
| Shunt capacitance | 0.87 pF | 1.17 pF |
| Return loss (VSWR) on its own | 24.4 dB (1.13) | 21.9 dB (1.18) |
| Mismatch loss | 0.016 dB | 0.028 dB |
| λ/4 resonance | 13.3 GHz | 9.9 GHz |

- **Jack body:** the body sits 1.0 mm above the board on four 1.5 × 1.5 mm legs. The stub runs between them and sees about 0.01 pF more.
- **Partial cancellation:** the stub partly cancels the 100 nH DC shunt (+j 276 Ω at 440 MHz, about 7 mm from the jack, i.e. at the same electrical point).

### Shunt elements at the ports

TVS D1/D8 (PESD5V0F1BL, 0.4 pF) + 100 nH (L1/L5) + stub, on the 50 Ω line (negative = inductive):

| Port | Edge-mount jack (no stub) | SMD jack, stub 2.9 mm | SMD jack, stub 3.9 mm |
|---|---|---|---|
| TX, 440 MHz | −2.51 mS → RL 24 dB | −0.04 mS → RL 61 dB | +0.82 mS → RL 34 dB |
| RX, 430 MHz | −2.62 mS → RL 24 dB | −0.20 mS → RL 46 dB | +0.64 mS → RL 36 dB |

### Matching networks (supplement to the README)

- **TX** (R_H = 100 Ω, R_L = 50 Ω, 440 MHz, Q = √(R_H/R_L − 1) = 1.00). C14 is 3.6 Ω at 440 MHz.

  | Frequency | Z at RF_OP | RL vs. 100 Ω |
  |---|---|---|
  | 400 MHz | 90.3 + j3.4 Ω | 25.4 dB |
  | 420 MHz | 94.9 + j0.6 Ω | 31.6 dB |
  | 440 MHz | 99.5 − j3.1 Ω | 35.9 dB |
  | 460 MHz | 103.9 − j7.9 Ω | 27.3 dB |
  | 480 MHz | 107.9 − j13.8 Ω | 22.3 dB |

- **RX** (Q = 1.73 at 430 MHz). With C21 and L4 in series, RF_IN must show Y = 5.10 mS + j8.72 mS (196 Ω in parallel with a capacitance). The required 5.24 pF are made up as follows:
  - 3.21 pF for the L-network;
  - 2.01 pF compensated by L3;
  - 0.02 pF because L4/C21 differ slightly from the ideal series reactance.

## External components

Parts that are not in the KiCad standard libraries or the template live in `ext_parts/` and are registered in `sym-lib-table` / `fp-lib-table`.

| Part | Symbol / footprint | 3D model |
|---|---|---|
| SX1255 | own; land pattern per datasheet Rev. 3.1 figure 7-2, thermal vias and split paste added | KiCad library `QFN-32-1EP_5x5mm_P0.5mm_EP3.3x3.3mm` (referenced) |
| LFCN-490+ | own; pads from the suggested layout PL-137 in the datasheet | `scripts/make_3d_models.py` |
| EVQ-Q2Y03W | own; land pattern checked against the Panasonic catalog ANCTB12E (pads 3.2 × 1.0 mm, 3.6 mm gap, 4.0 mm row pitch; pads in one row connected internally) | `scripts/make_3d_models.py` |
| CONSMA001-SMD-G_EdgeHybrid | own; CONSMA pads from the TE drawing (Rev. F), edge-mount pads from the KiCad footprint `SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount` (CC-BY-SA 4.0) | CONSMA: `scripts/make_3d_models.py`; Samtec: KiCad library model with additions (CC-BY-SA 4.0) |
| TA0655A | own, drawn from the datasheet | own (`TA0655A.stp`, also contributed to Phenix-1255-HW) |
| Logo (`G***`) | Phenix-1255 project logo (own, also used in Phenix-1255-HW and phenix-1255-sw) | – |
| TG2520SMN | KiCad library footprint | own (`TG2520SMN.step`) |
| Display_128x64_096_I2C | footprint by TG9541 (github.com/TG9541/kicad-footprints, CC0), own symbol | own (`Display_128x64_096_I2C.stp`, also contributed to Phenix-1255-HW) |

- The project is licensed under CERN-OHL-P-2.0 (`LICENSE`); third-party content is listed in the README.
- Phenix-1255-HW (Copyright © Z32IT 2026) is also CERN-OHL-P-2.0. The licence requires keeping its notice and marking changes with a date: keep the README sections *Changes from Phenix-1255-HW* and *License* up to date when the design departs further from the original.
- License notices in the files: the title blocks of both schematic sheets and of the PCB (Z32IT, w4tchd0g, CERN-OHL-P-2.0, source URL), and an SPDX header (`SPDX-FileCopyrightText` / `SPDX-License-Identifier: CERN-OHL-P-2.0`) after the shebang of every script. Give new scripts the same header.
- The SX1255 and EVQ-Q2Y03W symbols use the pin names `VBATI`, `VR_ANAI` and `GND_n`. All pins are `passive`.
- The filter symbols (LFCN-490+, TA0655A) are compact 10.16 × 7.62 mm boxes with the IEC 60617 filter glyph (three waves, low frequency at the bottom; low-pass: upper two crossed out, band-pass: upper and lower crossed out). Pin names and numbers are hidden. The GND pins are stacked at the bottom centre (one visible, the others hidden at the same position). FL1 and FL2 are placed mirrored (`mirror y`) so that the signal runs from right to left.
- `scripts/make_3d_models.py` needs build123d (`pip install build123d`, Python ≤ 3.13). It writes `LFCN-490+.step`, `EVQ-Q2Y03W.step` and `CONSMA001-SMD-G.step`.

To add a part:

1. Put the symbol in `ext_parts/<Part>.kicad_sym` and the footprint in `ext_parts/<Part>.pretty/`.
2. Put the 3D model in `ext_parts/3d/` and link it as `${KIPRJMOD}/ext_parts/3d/<file>`. Prefer referencing KiCad library models via `${KICAD10_3DMODEL_DIR}` over copying them.
3. Register the libraries in `sym-lib-table` / `fp-lib-table`.
4. Keep manufacturer downloads and datasheets in `ext_parts/source/`. That folder is ignored by git: datasheets and vendor libraries (SamacSys, Ultra Librarian, SnapEDA, …) are usually not redistributable. Link the datasheet in the `Datasheet` field instead.
5. Do not commit vendor library files. Draw symbols and footprints from the datasheet, or use libraries with an open license (KiCad library: CC-BY-SA 4.0, attribute in the README).

## Repository housekeeping

- `.history/` is KiCad's local history and is ignored.
