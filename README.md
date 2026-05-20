# Reality Labs Whole-Eye OCT Dataset

A publicly available dataset of raw and processed Optical Coherence Tomography (OCT) volumetric
scans of the human eye, capturing the retina (channel 0) and cornea / anterior
segment (channel 1) simultaneously with a dual-channel swept-source OCT system. 

Only scans that passed manual QA filtering (no motion, retina visible, no cornea/retina
mismatch) are included.

More information about this dataset is available at https://arxiv.org/abs/2605.19191

## Overview

The release contains three categories:

| Category         | Contents                                                                                |
|------------------|-----------------------------------------------------------------------------------------|
| `raw_data`       | Raw spectral TIF volumes (retina + anterior) and their acquisition waveform CSVs.       |
| `processed_data` | Segmented anterior B-scans (masks and mask boundaries) and  3D calibrated point clouds. |
| `annotations`    | Per-volume cornea/sclera/iris segmentation masks bundled with their B-scan inputs.      |

All participant identifiers are replaced with a 12-character SHA-256 hash
(`pid_hash`). Each chunk zip also includes a `demographics.csv` keyed by
`pid_hash` (IPD, age, visual aid, Rx OD/OS).

## File Naming on the Download List

The URL list you obtain from the landing page contains one zip file per category

```
rloct_<category>_<YYYYMMDD>_batch_<NNN>.zip       # data chunks (~10-20 GB each)
```

`<category>` is `raw_data` or `annotations`. You can decide what to download by filtering URLs on the 
`<category>` token — see the [Download](#download) section below.

## What's Inside Each Zip

All files are stored under a per-participant `pid_hash` directory using the
anonymized arcname pattern:

```
<pid_hash>/<pid_hash>_<scan_idx>_<type>.<ext>
```

- `pid_hash`: first 12 hex chars of `SHA256(participant_id)`.
- `scan_idx`: 3-digit zero-padded index of the scan within that participant.
  All files belonging to the same scan (retina TIF, anterior TIF, waveform CSVs)
  share the same `scan_idx` so they can be paired by name.
- `type`: see the table below.
- `ext`: `tif`, `csv`, or `npy`.

Each chunk zip also contains a top-level `demographics.csv` (one row per
`pid_hash` represented in that chunk).

### `raw_data` chunks

| Type token         | Extension | Contents                                                  |
|--------------------|-----------|-----------------------------------------------------------|
| `retina`           | `.tif`    | Raw spectral B-scan stack, retina channel (ch0). ~1.5 GB. |
| `anterior`         | `.tif`    | Raw spectral B-scan stack, anterior channel (ch1). ~1.5 GB. |
| `waveform_retina`  | `.csv`    | Galvanometer scan waveform for the retina TIF.            |
| `waveform_anterior`| `.csv`    | Galvanometer scan waveform for the anterior TIF.          |

A typical `raw_data` chunk layout:

```
<pid_hash>/<pid_hash>_000_retina.tif
<pid_hash>/<pid_hash>_000_anterior.tif
<pid_hash>/<pid_hash>_000_waveform_retina.csv
<pid_hash>/<pid_hash>_000_waveform_anterior.csv
<pid_hash>/<pid_hash>_001_retina.tif
...
demographics.csv
```
### `processed_data` chunks

| Type token           | Extension | Contents                                                                                          |
|----------------------|-----------|---------------------------------------------------------------------------------------------------|
| `bscans`             | `.tif`    | Processed anterior B-scan stack, for visualization. ~30MB.                                        |
| `depth_segmentation` | `.tif`    | B-scan segmentation model output, mask for cornea+sclera and iris. ~0.5MB                         |
| `depth_boundary`     | `.tif`    | Mask boundaries from segmentation model output: cornea front/back, sclera, iris front/back ~0.3MB |
| `point_cloud`        | `.npy`    | 3D calibrated, refraction-corrected point cloud of all surfaces from depth_boundary ~0.3MB        |

A typical `processed_data` chunk layout:

```
<pid_hash>/<pid_hash>_000_bscans.tif
<pid_hash>/<pid_hash>_000_depth_segmentation.tif
<pid_hash>/<pid_hash>_000_depth_boundary.tif
<pid_hash>/<pid_hash>_000_point_cloud.npy

```
### `annotations` chunks

Each annotation file is a **single bundled NumPy array** for one scan
attachment:

```
<pid_hash>/<pid_hash>_<scan_idx>_annotations.npy
```

- Shape: `(N_frames, 2, H, W)`, dtype `float64`.
- Channel 0: the processed B-scan that was annotated.
- Channel 1: the per-pixel cornea/sclera/iris segmentation mask.
- Mask classes: `0 = background`, `1 = cornea/sclera`, `3 = iris`.

## Download

### Step 1: Get Download URLs

Visit the dataset landing page to accept the license agreement and obtain
download URLs:

**[https://www.meta.com/emerging-tech/eye-tracking/](https://www.meta.com/emerging-tech/eye-tracking/)**

After accepting the terms, you will receive a list of CDN URLs covering all
files.

### Step 2: Download Files

Save the URLs into a text file (one URL per line, e.g. `urls.txt`), then run
the provided download script. The script extracts the filename from each URL
and skips files that are already present locally.

```bash
# Download everything (raw_data + annotations)
python download.py --url-file urls.txt --output-dir ./data

# Download only raw_data (TIF + waveform CSVs)
python download.py --url-file urls.txt --output-dir ./data --filter rloct_raw_data

# Download only annotations (bundled .npy)
python download.py --url-file urls.txt --output-dir ./data --filter rloct_annotations

# More parallel workers for fast networks
python download.py --url-file urls.txt --output-dir ./data --workers 8
```

`--filter` is a substring match against each URL. The release filename grammar
(`rloct_<category>_<YYYYMMDD>_...`) makes simple substrings sufficient for
category selection; you can also chain with shell tools, e.g.
`grep raw_data urls.txt | python download.py --output-dir ./data/raw_data`.

Or download individual files with curl/wget:

```bash
curl -L -o filename.zip "YOUR_CDN_URL_HERE"
wget -O filename.zip "YOUR_CDN_URL_HERE"
```

## Requirements

For the download script:

```bash
pip install requests tqdm
```

## File Formats

### TIFF Stacks (`*.tif`)

Raw spectral OCT B-scan stacks. Multi-page TIFF where each page is one
spectral B-scan. Load with PIL or `tifffile`:

```python
from PIL import Image
import numpy as np

img = Image.open("<pid_hash>_000_retina.tif")
frames = []
for i in range(img.n_frames):
    img.seek(i)
    frames.append(np.array(img))
volume = np.stack(frames)  # (n_bscans, height, width)
```

### Waveform CSVs (`*_waveform_retina.csv`, `*_waveform_anterior.csv`)

Per-acquisition galvanometer scan waveforms. Pair them with the matching
`_retina.tif` / `_anterior.tif` of the same `<pid_hash>_<scan_idx>` prefix.

### Annotations (`*_annotations.npy`)

Bundled per-scan tensor.

```python
import numpy as np

arr = np.load("<pid_hash>_000_annotations.npy")
print(arr.shape)   # (N_frames, 2, H, W)
bscans = arr[:, 0] # processed B-scans
masks  = arr[:, 1] # segmentation masks (0=bg, 1=cornea/sclera, 3=iris)
```

### Demographics (`demographics.csv`)

One row per `pid_hash` represented in the chunk:

| Column            | Description                                |
|-------------------|--------------------------------------------|
| `pid_hash`        | 12-hex-char anonymized participant ID.     |
| `ipd`             | Inter-pupillary distance.                  |
| `age`             | Participant age.                           |
| `visual_aid`      | Visual aid worn during acquisition.        |
| `prescription_od` | OD (right) prescription if applicable.     |
| `prescription_os` | OS (left) prescription if applicable.      |
* note that all volumes in this dataset are of participants' right eye (OS).

Additional demographic information in aggregate is described in https://arxiv.org/abs/2605.19191. Deaggregated demographic data not 
included in `demographics.csv` such as gender, self-reported ethnicity, and eye health conditions
may be provided upon reasonable request by email to the authors.  
## Citation

If you use this dataset in your research, please cite:

```bibtex
@misc{qian2026opensourcesegmentationbiometrydataset,
      title={Open-source segmentation and biometry dataset using spectrally-multiplexed whole-eye optical coherence tomography}, 
      author={Ruobing Qian and Catherine Fromm and Pushkar Anand and Kyle Johnson and Zach Willms and Yimin Ding and Weihan Zhang and Ali Behrooz and Mohamed El-Haddad},
      year={2026},
      eprint={2605.19191},
      archivePrefix={arXiv},
      primaryClass={physics.optics},
      url={https://arxiv.org/abs/2605.19191}, 
}
```

## License

This dataset is released under the [CC-BY-NC 4.0 License](LICENSE).

You are free to:
- **Share** — copy and redistribute the material in any medium or format
- **Adapt** — remix, transform, and build upon the material

Under the following terms:
- **Attribution** — You must give appropriate credit
- **NonCommercial** — You may not use the material for commercial purposes

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this project.

## Code of Conduct

This project adheres to the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Contact

For questions about the dataset, please open an issue on this repository.
