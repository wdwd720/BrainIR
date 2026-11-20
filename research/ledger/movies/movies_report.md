# Cande et al. 2018 (eLife 7:e34275) – behaviour movies: availability and file properties

## Hosting and access
- Dryad, doi:10.5061/dryad.fr89c0c: https://datadryad.org/dataset/doi:10.5061/dryad.fr89c0c (API: https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.fr89c0c, file list: https://datadryad.org/api/v2/versions/16720/files). One version, published 2019-06-18.
- It's a public Dryad record with a direct download link. I didn't test the download, so I haven't confirmed that it works without logging in.

## Files and size
- Dryad lists one file, `opto_movies.zip`: 2,206,557,352 bytes (about 2.2 GB, application/zip, MD5 b8f3181ed02a4fc409302919da088a29). That is the whole deposit.
- **Unknown:** how many movies are in the zip and how big each one is. Dryad doesn't show zip contents, and I didn't download it. The paper says the collection is "~5GB" and organised by driver line, but the actual zip is 2.2 GB.

## Recording and file properties
Taken from the paper's Methods (https://pmc.ncbi.nlm.nih.gov/articles/PMC6031430/):
- **Cameras:** 12 Point Grey FL3-U3-13Y3M-C monochrome cameras, one per fly. Each had a 35 mm lens and an 800 nm long-pass filter and was mounted above the arena, so there is a single top-down view per fly.
- **Raw acquisition:** 1024×1024 px over a 3 cm arena (about 34 px/mm) at 100 fps, saved as uncompressed AVI. Only a 150×150 px crop centred on the fly was kept.
- **Lighting:** backlit through a diffuser by 850 nm infrared LEDs, plus 627 nm red LEDs for stimulation. Recording was near-infrared and greyscale.
- **Arena:** one fly per 3 cm siliconised "fly bubble", so one fly per frame.
- **Deposited clips:** 2 s each (1 s before to 1 s after light onset), covering all flies and trials. Clips are slowed 4× (8 s of playback), which suggests a 25 fps playback rate.
- **Not stated anywhere I could find:** container and codec of the deposited clips, and their resolution. They are presumably the 150×150 crops, possibly rescaled and rotation-aligned as in the analysis pipeline.

## Licence
CC0 1.0, according to the Dryad API and the paper.

## Feasibility of markerless leg tracking (DeepLabCut, SLEAP, Anipose)
Marginal. Rough body-axis pose is possible; reliable leg-segment tracking is unlikely.
- **Pixels per fly:** about 34 px/mm gives a fly roughly 80–100 px long. Legs are only a few pixels wide, and the tibia and tarsus are near the resolution limit.
- **View:** a single top-down view. Legs sit partly under the body and wings, so joints are often hidden. With one camera, Anipose-style 3D triangulation is impossible.
- **Lighting:** silhouette backlighting gives good contrast for leg outlines but no surface detail. That helps find leg tips but makes left/right and joint identity ambiguous.
- **Frame rate:** 100 fps against walking step rates of about 10–20 Hz gives roughly 5–10 frames per step. That's enough for tip trajectories but coarse for swing phase, and exposure time isn't reported, so motion blur during swing is likely.
- **One fly per frame:** no identity swaps.
- **Overall:** 2D tracking of leg tips and body points with DeepLabCut or SLEAP is plausible. Check a sample first; lossy re-encoding would make it worse.
