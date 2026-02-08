# BrainSegmentation — FastSurfer Pipeline for NIRSViz

Generates cortex meshes (pial + white matter surfaces) from T1-weighted MRI scans
using FastSurfer via Docker. Output is loaded directly into NIRSViz.

---

## One-Time Setup

### 1. Prerequisites

- **Docker Desktop for Windows** with GPU support enabled
  - Settings > Resources > WSL Integration: enable your distro
  - Ensure NVIDIA GPU passthrough works

- **NVIDIA GPU drivers** — up to date

- **NVIDIA Container Toolkit** — Docker Desktop usually handles this.
  If you get `could not select device driver "" with capabilities: [[gpu]]`,
  see: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html

### 2. Pull the FastSurfer image

```
docker pull deepmi/fastsurfer:latest
```

Downloads ~8 GB. Only needed once.

### 3. Get a FreeSurfer license (free)

1. Register at: https://surfer.nmr.mgh.harvard.edu/registration.html
2. You'll receive `license.txt` by email
3. Place it in: `BrainSegmentation/license/license.txt`

---

## Usage

### Option A: Run script (easy)

1. Place your T1w `.nii.gz` in the `input/` folder
2. Open a terminal in this folder
3. Run: `run_fastsurfer.bat <filename> <subject_id>`

Example:
```
run_fastsurfer.bat sub-116_ses-BL_T1w.nii.gz sub-116
```

4. Wait ~45-75 minutes
5. Results appear in `output/sub-116/`

### Option B: Manual docker command

```powershell
docker run --gpus all ^
    -v %cd%\input:/data ^
    -v %cd%\output:/output ^
    -v %cd%\license:/fs_license ^
    --rm deepmi/fastsurfer:latest ^
    --fs_license /fs_license/license.txt ^
    --t1 /data/sub-116_ses-BL_T1w.nii.gz ^
    --sid sub-116 ^
    --sd /output ^
    --3T ^
    --threads max
```

### Convert surfaces to OBJ for NIRSViz

After FastSurfer completes:
```
convert_surfaces.bat sub-116
```

Produces:
```
output/sub-116/surf/lh.pial.obj
output/sub-116/surf/rh.pial.obj
output/sub-116/surf/lh.white.obj
output/sub-116/surf/rh.white.obj
```

---

## Output Structure

```
output/sub-116/
├── mri/
│   ├── orig.mgz                     # Original T1w (FreeSurfer format)
│   ├── aparc.DKTatlas+aseg.mgz      # 95-class segmentation volume
│   ├── aseg.mgz                     # Subcortical segmentation
│   └── brain.mgz                    # Skull-stripped brain
├── surf/
│   ├── lh.pial / rh.pial            # Pial surfaces (FreeSurfer binary)
│   ├── lh.white / rh.white          # White matter surfaces
│   ├── lh.pial.obj / rh.pial.obj    # Converted OBJ (after convert script)
│   └── lh.white.obj / rh.white.obj  # Converted OBJ
├── stats/
│   ├── aseg.stats                   # Volumetric statistics
│   └── lh.aparc.stats               # Cortical parcellation stats
└── label/
    └── lh.aparc.DKTatlas.annot      # Cortical parcellation labels
```

### What to load in NIRSViz

| File | Purpose |
|------|---------|
| `surf/lh.pial.obj` + `rh.pial.obj` | Cortex surface (grey matter outer boundary) |
| `surf/lh.white.obj` + `rh.white.obj` | White matter surface (grey matter inner boundary) |
| `mri/aparc.DKTatlas+aseg.mgz` | Segmentation volume (slice viewer overlay) |

---

## Tips

- **Segmentation only (~5 min):** Add `--seg_only` to skip surface reconstruction.
- **Skip registration (~30 min faster):** Add `--no_surfreg` if you don't need
  cross-subject correspondence.
- **Lower memory:** Reduce `--batch` from 16 to 8 if you hit GPU OOM.
- **Verify GPU:** `docker run --gpus all --rm deepmi/fastsurfer:latest --version`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| GPU driver error | Install NVIDIA Container Toolkit, restart Docker |
| CUDA out of memory | Use `--batch 8` or `--batch 4` |
| No license.txt | Register free at FreeSurfer link above |
| Bad surfaces | Ensure input is 1mm isotropic T1w MPRAGE |

---

## References

- FastSurfer: https://github.com/Deep-MI/FastSurfer
- FreeSurfer: https://surfer.nmr.mgh.harvard.edu/
