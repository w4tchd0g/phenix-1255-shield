#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 w4tchd0g (DM5LF)
# SPDX-License-Identifier: CERN-OHL-P-2.0
"""RF line and SMA launch calculation for the phenix-1255-shield.

1. Impedance of the 50 ohm CPWG on F.Cu (JLC04161H-7628, reference In1):
   - closed-form model (conformal mapping after Wadell, thickness
     correction after Gupta), standard library only
   - 2D electrostatic field solver (finite differences), needs numpy and scipy
2. Effect of the open stub that the edge-mount centre pad (1.27 x 3.2 mm)
   leaves at J5/J6 when the vertical CONSMA001-SMD-G jack is populated.
3. Shunt elements at the SMA ports (TVS, 100 nH, stub).
4. Matching networks at the SX1255: TX 100 -> 50 ohm (C13/L2),
   RX 50 -> 200 ohm (L4/L3 plus the capacitance at RF_IN).

Run:  python3 scripts/rf_calc.py
      (field solver part is skipped if numpy/scipy are missing)
"""
import math

C0 = 299792458.0
E0 = 8.8541878128e-12

# Stackup (phenix-1255-shield.kicad_pcb, JLC04161H-7628), mm
H = 0.2104      # prepreg F.Cu -> In1
T = 0.035       # outer copper
ER = 4.4        # prepreg 7628
MASK = 0.015    # solder mask thickness used in the field solver
ER_MASK = 3.8

# Geometry, mm
LINE = (0.30, 0.30)          # track width, gap to GND fill
LINE_IC = (0.30, 0.20)       # inside the SX1255 courtyard
STUB_W = 1.27                # edge-mount centre pad width
STUB_GAP = 1.44 - STUB_W / 2  # to the inner edge of the CONSMA GND pads
STUB_L = 3.9 - 2.05 / 2      # part of the edge-mount pad beyond the round CONSMA pad
STUB_L_MAX = 3.9             # worst case: whole length from the pad centre
L_SHUNT = 100e-9             # DC shunt at each port (L1 / L5)
FREQS = (430e6, 440e6)
Z0 = 50.0


# --- closed-form CPWG ----------------------------------------------------
def ellip_k(k):
    a, b = 1.0, math.sqrt(1 - k * k)
    for _ in range(40):
        a, b = (a + b) / 2, math.sqrt(a * b)
    return math.pi / (2 * a)


def cpwg_closed(w, s, h, er, t=0.0):
    if t > 0:
        d = 1.25 * t / math.pi * (1 + math.log(4 * math.pi * w / t))
        w, s = w + d, s - d
    k = w / (w + 2 * s)
    k3 = math.tanh(math.pi * w / (4 * h)) / math.tanh(math.pi * (w + 2 * s) / (4 * h))
    r1 = ellip_k(k) / ellip_k(math.sqrt(1 - k * k))
    r3 = ellip_k(k3) / ellip_k(math.sqrt(1 - k3 * k3))
    q = r3 / r1
    eeff = (1 + er * q) / (1 + q)
    z = 60 * math.pi / math.sqrt(eeff) / (r1 + r3)
    return z, eeff


# --- 2D field solver -----------------------------------------------------
def cpwg_field(w, s, h, t, er, mask=0.0, d=0.005, x_max=3.0, y_air=2.0):
    """Half cross-section (symmetry plane at x = 0), grid step d (mm).
    Returns Z0 (ohm), eps_eff and C' (F/m)."""
    import numpy as np
    import scipy.sparse as sp
    import scipy.sparse.linalg as spl

    nh, nt, nm = round(h / d), round(t / d), round(mask / d)
    nx, ny = round(x_max / d) + 1, nh + nt + round(y_air / d) + 1
    iw, ig = round(w / 2 / d), round((w / 2 + s) / d)

    sig = np.zeros((nx, ny), bool)
    gnd = np.zeros((nx, ny), bool)
    sig[: iw + 1, nh: nh + nt + 1] = True
    gnd[ig:, nh: nh + nt + 1] = True             # coplanar ground
    gnd[:, 0] = gnd[:, -1] = gnd[-1, :] = True   # In1 and outer box

    def permittivity(er_sub, er_mask):
        e = np.ones((nx - 1, ny - 1))
        e[:, :nh] = er_sub
        if nm:
            for i in range(nx - 1):
                top = nh + nt if (i < iw or i >= ig) else nh
                e[i, top: top + nm] = er_mask
            e[iw: iw + nm, nh: nh + nt] = er_mask
            e[ig - nm: ig, nh: nh + nt] = er_mask
        return e

    def capacitance(e):
        ep = np.pad(e, 1)
        cv = (ep[0:nx, 1:ny] + ep[1:nx + 1, 1:ny]) / 2   # edges (i,j)-(i,j+1)
        ch = (ep[1:nx, 0:ny] + ep[1:nx, 1:ny + 1]) / 2   # edges (i,j)-(i+1,j)
        fixed = sig | gnd
        v = np.where(sig, 1.0, 0.0)
        idx = -np.ones((nx, ny), int)
        idx[~fixed] = np.arange((~fixed).sum())
        n = (~fixed).sum()
        rows, cols, vals = [], [], []
        b, diag = np.zeros(n), np.zeros(n)

        def add(ai, aj, bi, bj, c):
            a, bb = idx[ai, aj], idx[bi, bj]
            for p, q, qi, qj in ((a, bb, bi, bj), (bb, a, ai, aj)):
                m = p >= 0
                np.add.at(diag, p[m], c[m])
                mq = m & (q >= 0)
                rows.append(p[mq]); cols.append(q[mq]); vals.append(-c[mq])
                mf = m & (q < 0)
                np.add.at(b, p[mf], c[mf] * v[qi[mf], qj[mf]])

        i, j = np.meshgrid(np.arange(nx), np.arange(ny - 1), indexing="ij")
        add(i.ravel(), j.ravel(), i.ravel(), j.ravel() + 1, cv.ravel())
        i, j = np.meshgrid(np.arange(nx - 1), np.arange(ny), indexing="ij")
        add(i.ravel(), j.ravel(), i.ravel() + 1, j.ravel(), ch.ravel())
        rows.append(np.arange(n)); cols.append(np.arange(n)); vals.append(diag)
        a = sp.csc_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
        v[~fixed] = spl.spsolve(a, b)
        energy = (cv * np.diff(v, axis=1) ** 2).sum() + (ch * np.diff(v, axis=0) ** 2).sum()
        return 2 * energy * E0   # both halves, V = 1

    c = capacitance(permittivity(er, ER_MASK))
    ca = capacitance(permittivity(1.0, 1.0))
    return 1 / (C0 * math.sqrt(c * ca)), c / ca, c


# --- stub ------------------------------------------------------------------
def open_end_extension(w, h, eeff):
    """Hammerstad/Kirschning open-end extension (mm)."""
    u = w / h
    return 0.412 * h * (eeff + 0.3) / (eeff - 0.258) * (u + 0.264) / (u + 0.8)


def stub_report(zs, es, length, f):
    le = length + open_end_extension(STUB_W, H, es)
    lam = C0 / f / math.sqrt(es) * 1e3            # guided wavelength, mm
    bl = 2 * math.pi * le / lam
    y_stub = math.tan(bl) / zs                    # open stub: Y = j tan(bl) / Zs
    c = y_stub / (2 * math.pi * f)
    y = complex(1 / Z0, y_stub)                   # shunt on a matched 50 ohm line
    zl = 1 / y
    g = abs((zl - Z0) / (zl + Z0))
    f_qw = C0 / (4 * le * 1e-3 * math.sqrt(es))
    return (f"    L = {length:.2f} mm (+{le - length:.2f} open end): {math.degrees(bl):.1f} deg of "
            f"lambda_g = {lam:.0f} mm, C = {c * 1e12:.2f} pF, X_C = {1 / y_stub:.0f} ohm, "
            f"|Gamma| = {g:.3f}, RL = {-20 * math.log10(g):.1f} dB, VSWR = {(1 + g) / (1 - g):.2f}, "
            f"mismatch loss = {-10 * math.log10(1 - g * g):.3f} dB, lambda/4 resonance at {f_qw / 1e9:.1f} GHz"), y_stub


def main():
    print("CPWG on F.Cu, h = %.4f mm, t = %.3f mm, er = %.1f" % (H, T, ER))
    print("\nClosed-form (Wadell, Gupta thickness correction):")
    for w, s in (LINE, LINE_IC):
        z, e = cpwg_closed(w, s, H, ER, T)
        print(f"  w = {w:.2f} / s = {s:.2f} mm: Z0 = {z:.1f} ohm, eps_eff = {e:.2f}")
    sweep = ", ".join(f"{w:.2f} mm: {cpwg_closed(w, LINE[1], H, ER, T)[0]:.1f} ohm" for w in (0.25, 0.30, 0.35, 0.40))
    print(f"  width sweep at s = {LINE[1]:.2f} mm: {sweep}")
    zs, es = cpwg_closed(STUB_W, STUB_GAP, H, ER, T)
    print(f"  stub w = {STUB_W:.2f} / s = {STUB_GAP:.3f} mm: Z0 = {zs:.1f} ohm, eps_eff = {es:.2f}")

    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401
        have_fd = True
    except ImportError:
        have_fd = False
        print("\n(numpy/scipy not found, field solver skipped, stub uses closed-form values)")

    if have_fd:
        print("\n2D field solver (5 um grid):")
        for w, s in (LINE, LINE_IC):
            for m in (0.0, MASK):
                z, e, _ = cpwg_field(w, s, H, T, ER, m)
                tag = f"with {MASK * 1e3:.0f} um mask" if m else "bare copper"
                g = abs(z - Z0) / (z + Z0)
                print(f"  w = {w:.2f} / s = {s:.2f} mm, {tag:>16}: Z0 = {z:.1f} ohm, eps_eff = {e:.2f}, "
                      f"RL vs 50 ohm = {-20 * math.log10(g):.0f} dB")
        zs, es, cs = cpwg_field(STUB_W, STUB_GAP, H, T, ER)
        print(f"  stub w = {STUB_W:.2f} / s = {STUB_GAP:.3f} mm: Z0 = {zs:.1f} ohm, eps_eff = {es:.2f}, "
              f"C' = {cs * 1e12:.0f} pF/m")

    print("\nOpen stub at J5/J6 with the CONSMA001-SMD-G jack (shunt on a matched 50 ohm line):")
    for f in FREQS:
        print(f"  f = {f / 1e6:.0f} MHz")
        for length in (STUB_L, STUB_L_MAX):
            line, y_stub = stub_report(zs, es, length, f)
            print(line)
        y_l = 1 / (2 * math.pi * f * L_SHUNT)
        print(f"    for comparison, 100 nH DC shunt at the port: X_L = {1 / y_l:.0f} ohm "
              f"({y_l * 1e3:.2f} mS inductive vs. {y_stub * 1e3:.2f} mS capacitive for the full stub)")

    body = E0 * STUB_W * 0.8 / 1.0 * 1e-3   # 1.27 x 0.8 mm under the body, 1.0 mm air
    print(f"\nCoupling of the stub to the jack body (1.0 mm stand-off): about {body * 1e12:.3f} pF")

    print_port(zs, es)
    print_matching()


# --- ports: TVS + 100 nH + stub ---------------------------------------------
C_TVS = 0.4e-12   # PESD5V0F1BL


def print_port(zs, es):
    print("\nShunt elements at the SMA ports (TVS 0.4 pF, 100 nH, stub), on a matched 50 ohm line:")
    for f, port in ((440e6, "TX"), (430e6, "RX")):
        b_l = -1 / (2 * math.pi * f * L_SHUNT)
        b_tvs = 2 * math.pi * f * C_TVS
        parts = []
        for label, length in (("edge mount (no stub)", None), ("SMD, stub 2.9 mm", STUB_L), ("SMD, stub 3.9 mm", STUB_L_MAX)):
            b = b_l + b_tvs
            if length is not None:
                b += stub_report(zs, es, length, f)[1]
            parts.append(f"{label}: B = {b * 1e3:+.2f} mS, RL = {rl_shunt(b):.0f} dB")
        print(f"  {port} {f / 1e6:.0f} MHz: " + "; ".join(parts))


def rl_shunt(b):
    y = complex(1 / Z0, b)
    g = abs((1 / y - Z0) / (1 / y + Z0))
    return -20 * math.log10(g)


# --- matching networks at the SX1255 ----------------------------------------
def zc(c, f):
    return 1 / (2j * math.pi * f * c)


def zl(l, f):
    return 2j * math.pi * f * l


def par(a, b):
    return a * b / (a + b)


def rl(z, z0):
    return -20 * math.log10(abs((z - z0) / (z + z0)))


def lnet(r_high, r_low, f):
    """Low-pass L-network: shunt C at the high side, series L at the low side."""
    q = math.sqrt(r_high / r_low - 1)
    return q, 1 / (2 * math.pi * f * r_high / q), q * r_low / (2 * math.pi * f)


def tx_zin(f, c13=3.6e-12, l2=18e-9, c14=100e-12):
    """Impedance seen by RF_OP: C14 series, C13 shunt, L2 series, LFCN-490+ as 50 ohm."""
    return zc(c14, f) + par(zc(c13, f), zl(l2, f) + Z0)


def tx_gain(f, c13=3.6e-12, l2=18e-9, c14=100e-12, rs=100.0):
    """Transducer gain from a 100 ohm source at RF_OP into 50 ohm (dB)."""
    zn = par(zc(c13, f), zl(l2, f) + Z0)
    zin = zc(c14, f) + zn
    v_load = zin / (rs + zin) * zn / zin * Z0 / (zl(l2, f) + Z0)
    return 10 * math.log10(abs(v_load) ** 2 / Z0 / (1 / (4 * rs)))


def rx_zin(f, c_tot, r_lna=200.0, l3=68e-9, l4=33e-9, c21=100e-12):
    """Impedance seen by the SAW output: C21 series, L4 series, then L3 shunt,
    total shunt capacitance at RF_IN (pin, BAV99, pad) and the 200 ohm LNA."""
    zp = 1 / (1 / r_lna + 2j * math.pi * f * c_tot + 1 / zl(l3, f))
    return zc(c21, f) + zl(l4, f) + zp


def print_matching():
    f = 440e6
    q, c, l = lnet(100, 50, f)
    print(f"\nTX matching at {f / 1e6:.0f} MHz, 100 ohm (RF_OP, RF_ON AC-grounded) -> 50 ohm (LFCN-490+):")
    print(f"  ideal L-network: Q = {q:.2f}, shunt C = {c * 1e12:.2f} pF, series L = {l * 1e9:.2f} nH"
          f"  -> used: 3.6 pF (C13), 18 nH (L2)")
    print(f"  C14 / C15 (100 pF): X = {abs(zc(100e-12, f)).real:.1f} ohm")
    for ff in (400e6, 420e6, 440e6, 460e6, 480e6):
        z = tx_zin(ff)
        print(f"  {ff / 1e6:.0f} MHz: Z at RF_OP = {z.real:.1f} {z.imag:+.1f}j ohm, RL vs 100 ohm = {rl(z, 100):.1f} dB")
    worst = min(rl(tx_zin(f, c13, l2), 100) for c13 in (3.5e-12, 3.7e-12) for l2 in (18e-9 * 0.98, 18e-9 * 1.02))
    print(f"  tolerances (C13 +-0.1 pF, L2 +-2 %): RL >= {worst:.1f} dB")
    print("  extra low-pass effect of the L-network: " + ", ".join(
        f"{n}f0 {tx_gain(n * f):.1f} dB" for n in (1, 2, 3)))

    f = 430e6
    q, c, l = lnet(200, 50, f)
    print(f"\nRX matching at {f / 1e6:.0f} MHz, 50 ohm (TA0655A) -> 200 ohm (LNA, LnaZin = 1):")
    print(f"  ideal L-network: Q = {q:.2f}, series L = {l * 1e9:.2f} nH, shunt C = {c * 1e12:.2f} pF")
    z_series = zc(100e-12, f) + zl(33e-9, f)
    y_pin = 1 / (Z0 - z_series)
    c_tot = (y_pin.imag + 1 / (2 * math.pi * f * 68e-9)) / (2 * math.pi * f)
    print(f"  with C21 = 100 pF and L4 = 33 nH the RF_IN node must show Y = {y_pin.real * 1e3:.2f} mS "
          f"(R = {1 / y_pin.real:.0f} ohm) {y_pin.imag * 1e3:+.2f}j mS")
    print(f"  L3 = 68 nH cancels {1 / ((2 * math.pi * f) ** 2 * 68e-9) * 1e12:.2f} pF, so the total capacitance "
          f"at RF_IN must be {c_tot * 1e12:.2f} pF")
    for ct in (4.0e-12, 4.5e-12, 5.0e-12, c_tot, 5.5e-12, 6.0e-12):
        best = max(range(380, 501), key=lambda m: rl(rx_zin(m * 1e6, ct), Z0))
        print(f"    C_tot = {ct * 1e12:.2f} pF: RL at 430 MHz = {rl(rx_zin(f, ct), Z0):.1f} dB, best match at {best} MHz")
    print("  L3 for a match at 430 MHz if C_tot differs: " + ", ".join(
        f"{ct * 1e12:.0f} pF -> {1 / (2 * math.pi * f * (2 * math.pi * f * ct - y_pin.imag)) * 1e9:.0f} nH"
        for ct in (4e-12, 5e-12, 6e-12, 7e-12)))
    band = [ff for ff in range(400, 461) if rl(rx_zin(ff * 1e6, c_tot), Z0) >= 20]
    print(f"  RL >= 20 dB from {band[0]} to {band[-1]} MHz (C_tot = {c_tot * 1e12:.2f} pF)")


if __name__ == "__main__":
    main()
