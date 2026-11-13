"""Reader for real SPHEREx spectral-image products (needs astropy).

Supported inputs (structure taken from the IRSA SPHEREx documentation):
  * a multi-extension "cutout" FITS made by the IRSA cutout tutorial: a CUTOUT_INFO table plus
    IMAGE<i>, FLAGS<i>, VARIANCE<i>, ZODI<i>, ... extensions for each cutout i;
  * a single Level-2 spectral image (IMAGE, FLAGS, VARIANCE, ZODI, PSF, WCS-WAVE).

NOTE: written against the documented structure but NOT yet tested on real SPHEREx files.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import re

import numpy as np

import sky_engine as eng

MJD0 = dt.date(1858, 11, 17)


def _need_astropy():
    try:
        from astropy.io import fits
        from astropy.wcs import WCS
    except ImportError as exc:
        raise RuntimeError("Reading real SPHEREx FITS files needs astropy (pip install astropy).") from exc
    return fits, WCS


def mjd_to_date(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return MJD0 + dt.timedelta(days=v) if 20000 < v < 100000 else None


def _celestial_wcs(WCS, header):
    w = WCS(header)
    return w.celestial if w.has_celestial else w


def _world_to_pix(wcs):
    return lambda ra, dec: wcs.all_world2pix(ra, dec, 0)


def _clean(arr):
    return None if arr is None else np.asarray(arr, dtype=np.float64)


def read_spherex(data: bytes, filename: str):
    """Return a list of observation dicts: index, date, wavelength, version, image, variance,
    flags, zodi, w2p (world->pixel callable), centre (ra, dec), meta."""
    fits, WCS = _need_astropy()
    sha = hashlib.sha256(data).hexdigest()[:12]
    obs = []
    with fits.open(io.BytesIO(data)) as hdul:
        names = {h.name.upper(): h for h in hdul}

        def grab(base, idx=None):
            h = names.get(f"{base}{idx}" if idx is not None else base)
            return None if h is None or h.data is None else h

        if "CUTOUT_INFO" in names:
            tbl = names["CUTOUT_INFO"].data
            cols = {c.lower(): c for c in tbl.columns.names}
            for row in tbl:
                idx = int(row[cols["cutout_index"]])
                him = grab("IMAGE", idx)
                if him is None:
                    continue
                w = _celestial_wcs(WCS, him.header)
                ny, nx = him.data.shape
                ra_c, dec_c = (float(v) for v in w.all_pix2world((nx - 1) / 2, (ny - 1) / 2, 0))
                date = mjd_to_date(row[cols["observation_date"]]) if "observation_date" in cols else None
                fl, zo, va = grab("FLAGS", idx), grab("ZODI", idx), grab("VARIANCE", idx)
                obs.append(dict(
                    index=idx, date=date, mjd=float(row[cols["observation_date"]]) if "observation_date" in cols else None,
                    wavelength=float(row[cols["central_wavelength"]]) if "central_wavelength" in cols else None,
                    version=str(row[cols["version"]]) if "version" in cols else "",
                    image=_clean(him.data), variance=_clean(va.data) if va else None,
                    flags=np.asarray(fl.data) if fl else None, zodi=_clean(zo.data) if zo else None,
                    w2p=_world_to_pix(w), centre=(ra_c, dec_c),
                    meta=dict(file=filename, sha=sha, source="IRSA SPHEREx cutout file", units="MJy/sr",
                              obs_id=f"cutout {idx}")))
        else:
            him = grab("IMAGE")
            if him is None:
                raise ValueError("No IMAGE extension found: this does not look like a SPHEREx spectral image.")
            w = _celestial_wcs(WCS, him.header)
            ny, nx = him.data.shape
            ra_c, dec_c = (float(v) for v in w.all_pix2world((nx - 1) / 2, (ny - 1) / 2, 0))
            hdr0 = hdul[0].header
            mjd = hdr0.get("MJD-OBS") or him.header.get("MJD-OBS")
            date = mjd_to_date(mjd)
            if date is None:
                for key in ("DATE-OBS", "DATE-BEG"):
                    val = hdr0.get(key) or him.header.get(key)
                    if val:
                        try:
                            date = dt.date.fromisoformat(str(val)[:10])
                        except ValueError:
                            pass
                        break
            m = re.search(r"level2_(?P<obs>.+?)D(?P<det>\d)_spx", filename)
            fl, zo, va = grab("FLAGS"), grab("ZODI"), grab("VARIANCE")
            obs.append(dict(
                index=0, date=date, mjd=mjd, wavelength=None, version=str(hdr0.get("VERSION", "")),
                image=_clean(him.data), variance=_clean(va.data) if va else None,
                flags=np.asarray(fl.data) if fl else None, zodi=_clean(zo.data) if zo else None,
                w2p=_world_to_pix(w), centre=(ra_c, dec_c),
                meta=dict(file=filename, sha=sha, source="IRSA SPHEREx Level-2 spectral image", units="MJy/sr",
                          obs_id=(m.group("obs") + f" detector D{m.group('det')}") if m else "unknown")))
    if not obs:
        raise ValueError("No usable image extensions were found in this file.")
    return obs


def suggest_pair(observations, tol=0.01, min_days=30):
    """Pick two observations at almost the same wavelength with the largest time separation.
    Returns (i, j, note) as positions in the list, or None."""
    best = None
    for i, a in enumerate(observations):
        for j in range(i + 1, len(observations)):
            b = observations[j]
            if None in (a["wavelength"], b["wavelength"], a["mjd"], b["mjd"]):
                continue
            dl = abs(a["wavelength"] - b["wavelength"]) / ((a["wavelength"] + b["wavelength"]) / 2)
            dd = abs(a["mjd"] - b["mjd"])
            if dl <= tol and dd >= min_days and (best is None or dd > best[0]):
                best = (dd, i, j, dl)
    if best is None:
        return None
    dd, i, j, dl = best
    return (i, j) if observations[i]["mjd"] <= observations[j]["mjd"] else (j, i)


def aligned_pair(obs_a, obs_b, ra0, dec0, n, pix=eng.PIX_ARCSEC, subtract_zodi=True, mask_flags=False):
    """Resample both observations onto one tangent-plane grid centred on (ra0, dec0).
    Returns (a, b, info) with info = coverage and flagged fractions."""
    ra, dec = eng.tan_inverse(ra0, dec0, n, pix)
    out, valid, flagged = [], [], []
    for o in (obs_a, obs_b):
        img = o["image"].copy()
        if subtract_zodi and o["zodi"] is not None:
            img = img - o["zodi"]
        bad = ~np.isfinite(img)
        if mask_flags and o["flags"] is not None:
            bad |= o["flags"] != 0
        img[bad] = np.nan
        res, ok = eng.resample(img, o["w2p"], ra, dec)
        out.append(res)
        valid.append(ok)
        flagged.append(float(bad.mean()))
    common = valid[0] & valid[1]
    if common.sum() < 0.1 * common.size:
        raise ValueError("The two observations barely overlap on the sky at this position. "
                         "Check the RA/Dec or choose observations of the same field.")
    arrays = []
    for res in out:
        fill = float(np.nanmedian(res[common]))
        arrays.append(np.where(common, res, fill).astype(np.float32))
    return arrays[0], arrays[1], dict(coverage=float(common.mean()), flagged_a=flagged[0], flagged_b=flagged[1])
