# Sky Time Machine

A Streamlit app for comparing SPHEREx observations of the same patch of sky taken at different times. Made for NASA Space Apps Challenge 2026 (Planet X and SPHEREx) made by 01Eipstein.

You pick a target or enter RA/Dec, choose a band and two dates, and the app shows the two images side by side, as a blink, with a swipe slider, or as a difference image. It then lists candidate sources that moved, got brighter or got fainter.

The built-in demo images are simulated. Real SPHEREx data only enter through FITS files you load yourself. Candidates are automatic detections and have not been verified.

## Running it

    pip install -r requirements.txt
    streamlit run sky_time_machine.py

Run it from this folder so it can find `assets/`. The four Python files must stay together.

## Pages

- Home: overview and a short tour.
- Sky Viewer: zoom, pan, RA/Dec readout, click a marker for details.
- Time Machine: side by side, blink, swipe, difference, and a timeline.
- Candidate Explorer: positions in A and B, displacement, significance, expected false alarms, reliability.
- Spectral Explorer: the same field in six bands, and a model spectrum across all 102.
- About & Data: methods, data sources, validation, how to load real data, limitations.

## Real data

Get a cutout file from IRSA (the IRSA tutorial on downloading SPHEREx spectral image cutouts as a multi-extension FITS file shows how), pick "Real SPHEREx FITS files" in the sidebar and upload it. The app lists the observations, suggests two at the same wavelength, aligns them using their WCS, optionally subtracts the zodiacal light, and runs the comparison.

This part was written from the documented file layout. It has not been run on real SPHEREx files yet.

## How candidates are found

1. Subtract B - A. Noise is 1.4826 times the median absolute deviation of the difference.
2. Peaks above the threshold (5 sigma by default) are candidates. A bright and a dark peak of similar strength within 25 pixels are treated as one moving source, and its positions in A and B are re-measured by centroiding.
3. Each candidate gets a significance, the number of noise peaks that strong expected per image (pixels x erfc(sigma / sqrt 2)), and a High, Medium or Low label.
4. Changes smaller than 10% of a source's brightness are rated Low, since they are more likely calibration or resampling residuals.

The label is a rule of thumb. It is not the probability that a candidate is real.

## Testing

On simulated data the detector finds all five challenge targets (Barnard's Star, Epsilon Indi B, WISE 0855-0714, RW Aurigae, R Draconis), gives no candidates for identical epochs, and gives about 0.012 false candidates per noise-only image against 0.009 expected. The noise there is white Gaussian, which real data are not. Real-data tests are still to do.

## Limitations

- The simulated sky is not the real sky at the coordinates you type in.
- The simulated fast mover is exaggerated so it is visible.
- Compare observations at about the same wavelength only.
- No Gaia or WISE overlays.
- Target coordinates and proper motions are approximate; check them in SIMBAD.

## Deploying

Put the folder in a public GitHub repo, then on share.streamlit.io choose the repo, branch `main` and main file `sky_time_machine.py`.

## Credits

SPHEREx is operated by Caltech and JPL for NASA; data are archived at NASA/IPAC IRSA. Home page images are NASA/JPL-Caltech SPHEREx releases. Built with Streamlit, NumPy, pandas, Pillow and astropy.
