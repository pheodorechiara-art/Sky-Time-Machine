# Submission notes

Sky Time Machine is an interactive astronomy web application that allows users to explore how the sky changes over time. Inspired by NASA's SPHEREx mission, the project focuses on comparing astronomical observations taken at different times, especially images of the infrared sky. Through this application, users can view changes between observations, explore possible moving objects, and learn more about how astronomers study the universe. The idea behind this project is to make astronomical image comparison easier to understand and more accessible, even for people who do not have a background in astronomy.

One of the challenges in astronomy is that changes between observations are not always easy to notice. Images taken at different times may look almost identical, even when certain objects have moved or changed position. Finding these differences usually requires specific tools and image-processing techniques. Sky Time Machine was developed to make this process easier by bringing image comparison and basic analysis into one interactive platform.

The application includes a Dual Observation Viewer, where users can display two astronomical images side by side and compare them. Users can also select different observation times and switch between several viewing modes, such as Blink Mode, Swipe Comparison, and Difference-Image Mode. Zoom and pan controls are also available to help users examine specific areas more closely. These features make it easier to notice changes between observations and investigate objects that may have moved.

Another important part of the project is its Candidate Detection System. This feature uses image-processing techniques such as image subtraction, noise estimation, and local peak detection to find areas that may contain moving objects. It also uses positive and negative peak pairing to help identify possible changes in object positions between two observations. The results are displayed as potential candidates that users can examine further. However, these detections are only preliminary results and should not be treated as confirmed astronomical discoveries.

Sky Time Machine also includes a Spectral Exploration feature inspired by SPHEREx's 102 near-infrared spectral bands. This feature is intended to help users explore how astronomical observations can be studied across different wavelengths. In addition, the application provides educational explanations about its features, processing methods, and the science behind the project.

The application was built mainly with Python and Streamlit. NumPy and Pandas are used for numerical calculations and data organization, while Astropy supports astronomical FITS processing. Pillow is used for image handling, and HTML, CSS, and JavaScript help create the interactive viewing experience. Its image-processing workflow starts by loading two astronomical images and aligning them when necessary. The system then calculates the differences between the images, estimates background noise using the median absolute deviation, detects peaks above a selected threshold, and pairs positive and negative peaks within a certain distance. These results are then presented as possible candidates for further investigation.

The project also includes a FITS-processing module intended to support real astronomical observations. It is designed to handle image loading, coordinate alignment, observation pairing, and image comparison. However, the compatibility of this module with actual SPHEREx data still needs to be tested and verified using real mission files. For the current demonstration, simulated data are used to show how the application and its processing system work. This distinction is important because simulated results should not be confused with actual scientific observations. Similarly, the candidate scores are based on preliminary calculations and are not scientifically calibrated probabilities.

Although Sky Time Machine already provides several interactive features, there are still areas that need improvement. For example, the system may produce false-positive candidates, and image alignment errors or detector artefacts can affect the comparison results. FITS metadata extraction and wavelength information also need further testing to ensure compatibility with actual SPHEREx products. Moving forward, we hope to improve the image-processing system, test it with real SPHEREx observations, reduce false detections, and compare potential candidates with existing astronomical catalogues. We also plan to improve the spectral visualization and provide more detailed information about each observation.

Through Sky Time Machine, we hope to give more people the opportunity to explore astronomy in a simple and interactive way. More than just displaying astronomical images, the project encourages users to compare observations, notice small changes, and understand how scientists investigate objects in space. It is still a work in progress, but it represents our effort to connect technology, image processing, and astronomy in a way that makes exploring the universe more engaging and accessible.

## Summary

A web tool for comparing SPHEREx observations of the same sky region at different times, with blink and difference views and a list of candidate moving or changing sources.

## Data sources

- SPHEREx Level 2 spectral images from NASA/IPAC IRSA, including cutout files from the IRSA tutorial.
- Mission facts: 102 bands from 0.75 to 5.0 micron, six detectors, 6.2 arcsec pixels.
- Demo mode: simulated by the app. Not SPHEREx data.
- Target positions and proper motions: approximate catalogue values.

## Method

Resample both images onto one grid using their WCS, optionally subtract the modelled zodiacal light, subtract B - A, estimate the noise from the median absolute deviation, find peaks above the threshold, pair bright and dark peaks into moving sources, and score each candidate.

## Validation

Simulated data: all five challenge targets recovered, no candidates for identical epochs, 0.012 false candidates per noise-only image (0.009 expected). Real data: not yet tested.

## Limitations

See the README. The real-data path is written from the documented file layout and has not been run on real files.

## Demo video outline (about 3 minutes)

- 0:00 Home page. What SPHEREx is and the question the tool asks.
- 0:30 Time Machine with Barnard's Star. Blink, then difference, then click the marker.
- 1:30 Candidate Explorer. What each number means.
- 2:00 Spectral Explorer with WISE 0855-0714. Move the band slider.
- 2:30 About & Data, Validation. What was tested and what was not.
- 2:50 Real data upload, only if you have tested it.

## Checklist

- [ ] Run the app on a real IRSA cutout file and note what happens.
- [ ] Check the credit lines for the two Home page images.
- [ ] Check target coordinates in SIMBAD.
- [ ] Open the deployed URL in a private window and on another device.
- [ ] Repo is public with no keys or personal data.
- [ ] State AI use as the challenge rules require.
