"""Core science helpers for the SPHEREx Sky Time Machine (numpy + Pillow only).

Everything produced by `simulate_*` functions is a SIMULATED DEMONSTRATION and must
be labelled as such in the UI. Real observations only enter through user-supplied
image pairs (see `build_pair`).
"""
from __future__ import annotations

import base64
import datetime as dt
import io
import math
import re

import numpy as np
from PIL import Image

PIX_ARCSEC = 6.2         
FIELD_PX = 128          
OUT_PX = 512             
PSF_SIGMA = 0.85      

MISSION_START = dt.date(2025, 5, 1)
MISSION_MID = dt.date(2026, 5, 1)
MISSION_END = dt.date(2027, 5, 1)

DETECTORS = [(1, 0.75, 1.09), (2, 1.09, 1.62), (3, 1.62, 2.41),
             (4, 2.41, 3.82), (5, 3.82, 4.42), (6, 4.42, 5.00)]


def _band_table():
    rows, i = [], 1
    for det, lo, hi in DETECTORS:
        for k in range(17):
            rows.append((i, det, lo + (k + 0.5) / 17 * (hi - lo)))
            i += 1
    return rows


BANDS = _band_table()                         
WL = np.array([b[2] for b in BANDS])          


def band_info(band: int):
    """Return (detector, wavelength_um) for a 1-based band index."""
    _, det, wl = BANDS[band - 1]
    return det, wl


TARGETS = {
    "Barnard's Star": dict(
        ra=269.4521, dec=4.6934, pmra=-798.6, pmdec=10328.1, teff=3200, ref_um=2.0, flux=900,
        variable=None, kind="High proper-motion M dwarf",
        note="Fastest-moving star in the sky (about 10.3 arcsec per year)."),
    "Epsilon Indi B": dict(
        ra=331.0440, dec=-56.7830, pmra=3966.0, pmdec=-2539.0, teff=1250, ref_um=3.0, flux=60,
        variable=None, kind="Nearby brown-dwarf binary",
        note="Cool brown dwarfs are faint at short wavelengths and brighten toward 3-5 micron."),
    "WISE 0855-0714": dict(
        ra=133.7955, dec=-7.2451, pmra=-8118.0, pmdec=680.0, teff=285, ref_um=4.5, flux=40,
        variable=None, kind="Coldest known brown dwarf (~285 K)",
        note="Essentially invisible below ~3.5 micron; appears only in the longest SPHEREx bands."),
    "RW Aurigae": dict(
        ra=76.9564, dec=30.4014, pmra=0.0, pmdec=0.0, teff=4500, ref_um=2.0, flux=500,
        variable="dimming", kind="Young star with irregular dimmings",
        note="Illustrative dimming event; the real light curve is not reproduced here."),
    "R Draconis": dict(
        ra=248.1770, dec=66.7550, pmra=0.0, pmdec=0.0, teff=3000, ref_um=2.0, flux=700,
        variable="mira", kind="Mira variable (period ~245 d)",
        note="Illustrative sinusoidal Mira pulsation; amplitude is larger at shorter wavelengths."),
}


def planck(wl_um, temp):
    wl = np.asarray(wl_um, dtype=float)
    x = np.minimum(14388.0 / (wl * temp), 700.0)
    return 1.0 / (wl ** 5 * np.expm1(x))


def variability(kind, day, wl):
    """Multiplicative brightness factor. `day` = days since MISSION_START."""
    wl = np.asarray(wl, dtype=float)
    if kind == "mira":
        f = max(0.55 + 0.45 * math.sin(2 * math.pi * day / 245.6 + 1.0), 0.03)
        return f ** ((2.0 / wl) ** 0.5)
    if kind == "dimming":
        return np.ones_like(wl) * (1.0 - 0.65 * math.exp(-((day - 300.0) / 75.0) ** 2))
    return np.ones_like(wl)


def target_flux(target, wl, date, with_variability=True):
    f = target["flux"] * planck(wl, target["teff"]) / planck(target["ref_um"], target["teff"])
    if with_variability:
        f = f * variability(target.get("variable"), (date - MISSION_START).days, wl)
    return f


def target_position(target, date, n=FIELD_PX, pix=PIX_ARCSEC):
    t = (date - MISSION_MID).days / 365.25
    c = (n - 1) / 2
    return c - target["pmra"] / 1000 * t / pix, c - target["pmdec"] / 1000 * t / pix


def expected_shift_px(target, date_a, date_b, pix=PIX_ARCSEC):
    yrs = abs((date_b - date_a).days) / 365.25
    return math.hypot(target["pmra"], target["pmdec"]) / 1000 * yrs / pix


def pixel_to_radec(x, y, ra0, dec0, n=FIELD_PX, pix=PIX_ARCSEC):
    c = (n - 1) / 2
    dec = dec0 - (y - c) * pix / 3600
    ra = ra0 - (x - c) * pix / 3600 / math.cos(math.radians(dec0))
    return ra % 360, dec


def field_stars(ra, dec, n=FIELD_PX):
    seed = (int(round(ra * 1000)) * 7919 + int(round((dec + 90) * 1000)) * 104729) & 0x7FFFFFFF
    rng = np.random.default_rng(seed)
    k = int(n * n / 400)
    x, y = rng.uniform(5, n - 5, k), rng.uniform(5, n - 5, k)
    temp = rng.uniform(2800, 9000, k)
    f = 10 ** rng.uniform(0.5, 2.3, k)
    keep = np.hypot(x - n / 2, y - n / 2) > 14      
    return x[keep], y[keep], temp[keep], f[keep]


def render_epoch(ra, dec, target, band, date, n=FIELD_PX, mover=True, with_variability=True):
    """Simulated single-band cutout for one observation date. Returns float32 array."""
    wl = WL[band - 1]
    day = (date - MISSION_START).days
    x, y, temp, f = field_stars(ra, dec, n)
    sx, sy = list(x), list(y)
    sf = list(f * planck(wl, temp) / planck(2.0, temp))

    if target is not None:
        tx, ty = target_position(target, date, n)
        sx.append(tx)
        sy.append(ty)
        sf.append(float(target_flux(target, wl, date, with_variability)))

    if mover:
        dd = (date - MISSION_MID).days
        off = np.array([0.35, -0.17]) * dd
        norm = float(np.hypot(*off))
        if norm > 10:
            off *= 10 / norm
        sx.append(0.28 * n + off[0])
        sy.append(0.72 * n + off[1])
        sf.append(60.0 * float(planck(wl, 5500) / planck(2.0, 5500)))

    yy, xx = np.mgrid[0:n, 0:n]
    img = 1.0 + 0.8 * xx / n + 0.3 * yy / n
    img *= 1.0 + 0.1 * math.sin(2 * math.pi * day / 365.25)        
    img = img + np.random.default_rng(date.toordinal() * 131 + band).normal(0, 0.4, (n, n))

    r = 6
    for px, py, pf in zip(sx, sy, sf):
        x0, x1 = int(max(0, math.floor(px) - r)), int(min(n, math.floor(px) + r + 2))
        y0, y1 = int(max(0, math.floor(py) - r)), int(min(n, math.floor(py) + r + 2))
        if x0 >= x1 or y0 >= y1:
            continue
        gx = np.exp(-0.5 * ((np.arange(x0, x1) - px) / PSF_SIGMA) ** 2)
        gy = np.exp(-0.5 * ((np.arange(y0, y1) - py) / PSF_SIGMA) ** 2)
        img[y0:y1, x0:x1] += pf * np.outer(gy, gx)
    return img.astype(np.float32)


def target_spectrum(target, date, with_variability=True):
    return target_flux(target, WL, date, with_variability)


def _local_max(m, r=2):
    h, w = m.shape
    pad = np.pad(m, r, mode="constant", constant_values=-np.inf)
    mx = np.full(m.shape, -np.inf)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            mx = np.maximum(mx, pad[dy:dy + h, dx:dx + w])
    return m >= mx


def _centroid(img, x, y, r=4):
    h, w = img.shape
    x0, x1 = int(max(0, round(x) - r)), int(min(w, round(x) + r + 1))
    y0, y1 = int(max(0, round(y) - r)), int(min(h, round(y) + r + 1))
    sub = np.clip(img[y0:y1, x0:x1] - np.median(img), 0, None)
    s = float(sub.sum())
    if s <= 0:
        return float(x), float(y)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    return float((sub * xx).sum() / s), float((sub * yy).sum() / s)


def _local_peak(img, x, y, r=2):
    h, w = img.shape
    x0, x1 = int(max(0, round(x) - r)), int(min(w, round(x) + r + 1))
    y0, y1 = int(max(0, round(y) - r)), int(min(h, round(y) + r + 1))
    return float(img[y0:y1, x0:x1].max() - np.median(img))


def detect(a, b, nsig=5.0, pix=PIX_ARCSEC, max_sep=25.0, max_peaks=60):
    """Find difference-image peaks and pair +/- lobes into moving-source candidates."""
    d = (b - a).astype(float)
    med = float(np.median(d))
    sig = max(1.4826 * float(np.median(np.abs(d - med))), 1e-6)
    d = d - med
    thr = nsig * sig

    def peaks(m):
        pts = np.argwhere((m > thr) & _local_max(m))
        vals = m[pts[:, 0], pts[:, 1]] if len(pts) else np.array([])
        order = np.argsort(-vals)[:max_peaks]
        return [(float(pts[i, 1]), float(pts[i, 0]), float(vals[i])) for i in order]

    pos, neg = peaks(d), peaks(-d)
    used, cands = set(), []

    for nx, ny, na in neg:
        best, bd = None, max_sep
        for j, (px, py, pa) in enumerate(pos):
            if j in used:
                continue
            dist = math.hypot(px - nx, py - ny)
            if not (0.5 < na / pa < 2.0 and dist < bd):
                continue
            if dist > 4.0:
                if (_local_peak(a, px, py) > 0.3 * _local_peak(a, nx, ny)
                        or _local_peak(b, nx, ny) > 0.3 * _local_peak(b, px, py)):
                    continue
            best, bd = j, dist
        if best is None:
            continue
        used.add(best)
        px, py, pa = pos[best]
        xa, ya = _centroid(a, nx, ny)
        xb, yb = _centroid(b, px, py)
        shift = math.hypot(xb - xa, yb - ya)
        cands.append(dict(kind="moving", x=xb, y=yb, xa=xa, ya=ya, xb=xb, yb=yb,
                          shift_px=shift, shift_arcsec=shift * pix, snr=min(na, pa) / sig,
                          symmetry=min(na, pa) / max(na, pa)))

    paired_neg = {(c["xa"], c["ya"]) for c in cands}
    for j, (px, py, pa) in enumerate(pos):
        if j not in used:
            cands.append(dict(kind="brightening", x=px, y=py, xa=px, ya=py, xb=px, yb=py,
                              shift_px=0.0, shift_arcsec=0.0, snr=pa / sig))
    for nx, ny, na in neg:
        if not any(math.hypot(nx - c["xa"], ny - c["ya"]) < max_sep for c in cands if c["kind"] == "moving"):
            cands.append(dict(kind="dimming", x=nx, y=ny, xa=nx, ya=ny, xb=nx, yb=ny,
                              shift_px=0.0, shift_arcsec=0.0, snr=na / sig))

    cands.sort(key=lambda c: -c["snr"])
    n_pix = a.shape[0] * a.shape[1]
    for i, c in enumerate(cands, 1):
        c["id"] = f"C{i}"
        c["symmetry"] = round(c.get("symmetry", 1.0), 2)
        c["fa"] = float(f"{fa_expected(c['snr'], n_pix):.3g}")
        src = max(_local_peak(a, c["xa"], c["ya"]), _local_peak(b, c["xb"], c["yb"]), 1e-9)
        c["frac"] = round(min(c["snr"] * sig / src, 99.0), 3)
        c["reliability"] = reliability_label(c)
        c["note"] = ("Change is under 10% of the source brightness: more likely a calibration or resampling "
                     "residual than a real change." if c["frac"] < 0.1 else "")
        for k in ("x", "y", "xa", "ya", "xb", "yb", "shift_px", "shift_arcsec", "snr"):
            c[k] = round(c[k], 2)
    return cands, sig


def fa_expected(sigma, n_pixels):
    """Expected number of pure-noise pixels at least `sigma` away from zero (either sign)
    in an image of `n_pixels`, assuming independent Gaussian noise."""
    return n_pixels * math.erfc(sigma / math.sqrt(2))


def reliability_label(c):
    """High: <0.01 expected false alarms per image (and a balanced +/- pair if moving).
    Medium: <0.5 expected false alarms. Low: otherwise, or if the change is under 10% of the
    source brightness (likely calibration/resampling residual). NOT a probability of being real."""
    if c.get("frac", 1.0) < 0.1:
        return "Low"
    balanced = c["kind"] != "moving" or c.get("symmetry", 1.0) >= 0.6
    if c["fa"] < 0.01 and balanced:
        return "High"
    return "Medium" if c["fa"] < 0.5 else "Low"


_STOPS = [(0.0, (5, 8, 20)), (0.25, (40, 20, 110)), (0.5, (170, 40, 120)),
          (0.75, (250, 140, 40)), (1.0, (255, 245, 200))]
_LUT = np.stack([np.interp(np.linspace(0, 1, 256), [s[0] for s in _STOPS], [s[1][c] for s in _STOPS])
                 for c in range(3)], axis=1).astype(np.uint8)


def _stretch_rgb(a, lo, hi):
    z = np.clip((a - lo) / (hi - lo), 0, 1)
    z = np.arcsinh(10 * z) / np.arcsinh(10)
    return _LUT[(z * 255).astype(np.uint8)]


def _diff_rgb(d, sig):
    s = np.clip(d / (10 * sig), -1, 1)
    pos, neg = np.clip(s, 0, 1), np.clip(-s, 0, 1)
    rgb = np.stack([8 + 240 * pos + 30 * neg, 10 + 100 * pos + 150 * neg, 18 + 50 * pos + 240 * neg], axis=-1)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def _png_url(rgb, smooth):
    im = Image.fromarray(rgb, "RGB").resize((OUT_PX, OUT_PX), Image.BICUBIC if smooth else Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def build_pair(a, b, smooth=True, nsig=5.0, pix=PIX_ARCSEC):
    """Turn two aligned arrays into display images, a difference image and candidates."""
    both = np.concatenate([a.ravel(), b.ravel()])
    lo, hi = float(np.percentile(both, 5)), float(np.percentile(both, 99.7))
    hi = max(hi, lo + 1e-6)
    cands, sig = detect(a, b, nsig=nsig, pix=pix)
    return dict(a=_png_url(_stretch_rgb(a, lo, hi), smooth), b=_png_url(_stretch_rgb(b, lo, hi), smooth),
                d=_png_url(_diff_rgb(b - a, sig), smooth), cands=cands, sigma=sig, n=int(a.shape[0]),
                arr_a=a, arr_b=b, lo=lo, hi=hi)


def thumbnail(arr, scale=8, lo=None, hi=None):
    """Small PIL image of an array using the same stretch as the main viewer."""
    lo = float(np.percentile(arr, 5)) if lo is None else lo
    hi = float(np.percentile(arr, 99.7)) if hi is None else hi
    im = Image.fromarray(_stretch_rgb(arr, lo, max(hi, lo + 1e-6)), "RGB")
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def candidate_crops(pair, c, half=12, scale=8):
    """A, B and difference thumbnails centred on a candidate (A/B share one stretch)."""
    a, b = pair["arr_a"], pair["arr_b"]
    x, y = int(round(c["x"])), int(round(c["y"]))
    h, w = a.shape
    x0, y0 = int(np.clip(x - half, 0, max(w - 2 * half, 0))), int(np.clip(y - half, 0, max(h - 2 * half, 0)))
    sl = (slice(y0, y0 + 2 * half), slice(x0, x0 + 2 * half))
    d = (b - a)[sl]
    drgb = Image.fromarray(_diff_rgb(d, pair["sigma"]), "RGB")
    return (thumbnail(a[sl], scale, pair["lo"], pair["hi"]), thumbnail(b[sl], scale, pair["lo"], pair["hi"]),
            drgb.resize((drgb.width * scale, drgb.height * scale), Image.NEAREST))


def validate(nsig=5.0, trials=100):
    """Run the whole pipeline on simulated data with known truth. Returns (rows, controls)."""
    d = dt.date
    cases = [
        ("Barnard's Star", 60, d(2025, 6, 1), d(2026, 11, 1), "motion"),
        ("Epsilon Indi B", 100, d(2025, 6, 1), d(2026, 11, 1), "motion"),
        ("WISE 0855-0714", 100, d(2025, 6, 1), d(2026, 11, 1), "motion"),
        ("RW Aurigae", 40, d(2025, 6, 1), d(2026, 2, 25), "change"),
        ("R Draconis", 40, d(2025, 6, 1), d(2025, 11, 1), "change"),
    ]
    rows = []
    for name, band, da, db, mode in cases:
        t = TARGETS[name]
        a = render_epoch(t["ra"], t["dec"], t, band, da)
        b = render_epoch(t["ra"], t["dec"], t, band, db)
        cands, _ = detect(a, b, nsig)
        tx, ty = target_position(t, db)
        near = [c for c in cands if math.hypot(c["x"] - tx, c["y"] - ty) < 3.0]
        row = dict(target=name, band=band, wavelength=round(float(WL[band - 1]), 2),
                   epochs=f"{da} → {db}", mode=mode)
        if mode == "motion":
            exp = expected_shift_px(t, da, db)
            mv = [c for c in near if c["kind"] == "moving"]
            meas = mv[0]["shift_px"] if mv else None
            row.update(expected=f"{exp:.2f} px shift", measured="not detected" if meas is None else f"{meas:.2f} px shift",
                       passed=bool(mv) and abs(meas - exp) <= 0.25 * exp,
                       reliability=mv[0]["reliability"] if mv else "-")
        else:
            ch = [c for c in near if c["kind"] in ("brightening", "dimming")]
            fa, fb = (float(target_flux(t, WL[band - 1], x)) for x in (da, db))
            truth = "brightening" if fb > fa else "dimming"
            row.update(expected=f"{truth} ({fa:.0f} → {fb:.0f})",
                       measured="not detected" if not ch else ch[0]["kind"],
                       passed=bool(ch) and ch[0]["kind"] == truth,
                       reliability=ch[0]["reliability"] if ch else "-")
        rows.append(row)

    same = render_epoch(180.0, 0.0, None, 60, d(2025, 6, 1), mover=False)
    rng = np.random.default_rng(7)
    false_counts = []
    for _ in range(trials):
        ra, dec = rng.uniform(0, 360), rng.uniform(-60, 60)
        band = int(rng.integers(1, 103))
        da = d(2025, 6, 1) + dt.timedelta(days=int(rng.integers(0, 300)))
        db = da + dt.timedelta(days=int(rng.integers(30, 400)))
        a = render_epoch(ra, dec, None, band, da, mover=False)
        b = render_epoch(ra, dec, None, band, db, mover=False)
        false_counts.append(len(detect(a, b, nsig)[0]))
    controls = dict(
        identical_epochs=len(detect(same, same, nsig)[0]),
        noise_trials=trials,
        false_per_image=float(np.mean(false_counts)),
        images_with_false=int(np.sum(np.array(false_counts) > 0)),
        expected_per_image=fa_expected(nsig, FIELD_PX * FIELD_PX),
    )
    return rows, controls


def tan_inverse(ra0, dec0, n, pix=PIX_ARCSEC):
    """RA/Dec (deg) of every pixel of an n x n tangent-plane grid (north up, east left)."""
    c = (n - 1) / 2
    yy, xx = np.mgrid[0:n, 0:n]
    xi = np.radians(-(xx - c) * pix / 3600.0)
    eta = np.radians(-(yy - c) * pix / 3600.0)
    d0 = math.radians(dec0)
    rho = np.hypot(xi, eta)
    cc = np.arctan(rho)
    with np.errstate(invalid="ignore", divide="ignore"):
        sin_c, cos_c = np.sin(cc), np.cos(cc)
        dec = np.arcsin(cos_c * math.sin(d0) + np.where(rho > 0, eta * sin_c * math.cos(d0) / rho, 0.0))
    ra = math.radians(ra0) + np.arctan2(xi * sin_c, rho * math.cos(d0) * cos_c - eta * math.sin(d0) * sin_c)
    return np.degrees(ra) % 360.0, np.degrees(dec)


def resample(img, world_to_pix, ra, dec):
    """Bilinear-resample `img` onto the sky grid (ra, dec). `world_to_pix(ra, dec)` must return
    0-based (x, y) pixel coordinates in `img`. Returns (resampled, valid_mask)."""
    h, w = img.shape
    x, y = world_to_pix(ra, dec)
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y) & (x >= 0) & (y >= 0) & (x <= w - 1) & (y <= h - 1)
    x0 = np.clip(np.floor(np.nan_to_num(x)).astype(int), 0, w - 2)
    y0 = np.clip(np.floor(np.nan_to_num(y)).astype(int), 0, h - 2)
    fx, fy = np.clip(np.nan_to_num(x) - x0, 0, 1), np.clip(np.nan_to_num(y) - y0, 0, 1)
    out = ((1 - fx) * (1 - fy) * img[y0, x0] + fx * (1 - fy) * img[y0, x0 + 1]
           + (1 - fx) * fy * img[y0 + 1, x0] + fx * fy * img[y0 + 1, x0 + 1])
    ok &= np.isfinite(out)
    return np.where(ok, out, np.nan), ok


def parse_coord(text, is_ra):
    """Parse decimal degrees or sexagesimal (17h57m48.5s, 17:57:48.5, -56 47 10)."""
    s = text.strip().lower()
    if not s:
        raise ValueError("empty coordinate")
    sign = -1.0 if s.startswith("-") else 1.0
    tokens = [t for t in re.split(r"[:\s]+", re.sub(r"[hdms°'\"]", ":", s.lstrip("+-"))) if t]
    try:
        vals = [float(t) for t in tokens]
    except ValueError:
        raise ValueError(f"'{text.strip()}' is not a valid coordinate (try 269.45 or 17h57m48.5s)") from None
    if not vals:
        raise ValueError("empty coordinate")
    if len(vals) == 1:
        v = vals[0]
    else:
        v = sum(x / 60 ** i for i, x in enumerate(vals[:3]))
        if is_ra:
            v *= 15
    v *= sign
    if is_ra and not 0 <= v < 360:
        raise ValueError("RA must be between 0 and 360 degrees")
    if not is_ra and not -90 <= v <= 90:
        raise ValueError("Dec must be between -90 and +90 degrees")
    return v


def array_from_upload(data: bytes, name: str):
    """Read a FITS (needs astropy) or ordinary image upload into a 2-D float array."""
    lower = name.lower()
    if lower.endswith((".fits", ".fit", ".fts", ".fits.gz")):
        try:
            from astropy.io import fits
        except ImportError as exc:                       # pragma: no cover
            raise RuntimeError("Reading FITS files needs astropy (pip install astropy).") from exc
        with fits.open(io.BytesIO(data)) as hdul:
            pick = None
            for hdu in hdul:
                if hdu.data is not None and getattr(hdu.data, "ndim", 0) == 2:
                    if (hdu.name or "").upper() == "IMAGE":
                        pick = hdu
                        break
                    pick = pick or hdu
            if pick is None:
                raise ValueError("No 2-D image extension found in this FITS file.")
            return np.nan_to_num(np.asarray(pick.data, dtype=float))
    return np.asarray(Image.open(io.BytesIO(data)).convert("L"), dtype=float)


def cutout(arr, size, cx=None, cy=None):
    h, w = arr.shape
    size = int(min(size, h, w))
    cx = w // 2 if cx is None else int(cx)
    cy = h // 2 if cy is None else int(cy)
    x0 = int(np.clip(cx - size // 2, 0, w - size))
    y0 = int(np.clip(cy - size // 2, 0, h - size))
    return arr[y0:y0 + size, x0:x0 + size]
