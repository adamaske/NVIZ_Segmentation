# NVIZ Segmentation

Generate cortex and white matter meshes from T1-weighted MRI scans using [FastSurfer](https://github.com/Deep-MI/FastSurfer) via Docker. Designed for import into [NIRSViz](https://github.com/adamaske/NIRSViz).

```
T1w MRI (.nii.gz)  →  FastSurfer (Docker + GPU)  →  STL surfaces  →  NIRSViz
```

---

## Prerequisites

You need three things installed before you start:

### 1. Docker Desktop

Download and install from [docker.com](https://www.docker.com/products/docker-desktop/). During installation make sure **WSL2 backend** is selected (Windows). After installing, open Docker Desktop and wait for it to fully start (the whale icon in the system tray stops animating).

### 2. NVIDIA GPU Support in Docker

This is needed for fast processing (~1 min instead of ~15 min for segmentation). Open PowerShell and run:

```powershell
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

If this prints your GPU info, you're good. If it fails, install the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). You need up-to-date NVIDIA drivers and Docker Desktop using the WSL2 backend (Settings → General → Use WSL2).

> **No NVIDIA GPU?** FastSurfer still works on CPU, it's just slower. Segmentation takes ~15 min instead of ~1 min. Surface reconstruction (~45-60 min) is CPU-bound either way.

### 3. FreeSurfer License (free)

FastSurfer requires a FreeSurfer license file.

1. Register at: https://surfer.nmr.mgh.harvard.edu/registration.html
2. You'll receive `license.txt` by email
3. Place it in the `license/` folder so the path is `license/license.txt`

---

## Quick Start

```
1.  Place your T1w scan (.nii.gz) in the input/ folder
2.  Place your FreeSurfer license.txt in the license/ folder
3.  Open a terminal in this folder
4.  Run:  run_fastsurfer.bat sub-116_ses-BL_T1w.nii.gz sub-116
5.  Wait ~45-75 minutes
6.  Run:  convert_surfaces.bat sub-116
7.  Run:  merge_surfaces.bat sub-116
8.  Find your merged OBJ in output/sub-116/surf/pial.obj
```

---

## Step-by-Step Guide

### Step 0: Verify Your Setup

Run the setup checker to make sure everything is working:

```batch
verify_setup.bat
```

This checks that Docker is running, your GPU is accessible, the FastSurfer image is downloaded, and your license file is in place. If the FastSurfer image isn't downloaded yet, run:

```batch
docker pull deepmi/fastsurfer:latest
```

This downloads ~8 GB and only needs to be done once.

### Step 1: Run FastSurfer

```batch
run_fastsurfer.bat <filename.nii.gz> <subject_id>
```

**Example:**
```batch
run_fastsurfer.bat sub-116_ses-BL_T1w.nii.gz sub-116
```

This runs brain segmentation and surface reconstruction. It takes roughly 45-75 minutes total. The script will show progress as it runs.

**What happens under the hood:**
- Deep learning segmentation labels 95 brain regions (~1 min GPU / ~15 min CPU)
- Surface reconstruction builds pial and white matter surfaces (~45-60 min)
- Results are written to `output/<subject_id>/`

### Step 2: Convert Surfaces to STL

After FastSurfer completes, convert the FreeSurfer surface files to STL format:

```batch
convert_surfaces.bat <subject_id>
```

**Example:**
```batch
convert_surfaces.bat sub-116
```

This produces four STL files in `output/<subject_id>/surf/`:

| File | Description |
|------|-------------|
| `lh_pial.stl` | Left hemisphere cortical surface (grey matter outer boundary) |
| `rh_pial.stl` | Right hemisphere cortical surface |
| `lh_white.stl` | Left hemisphere white matter surface (grey matter inner boundary) |
| `rh_white.stl` | Right hemisphere white matter surface |

### Step 3: Merge Hemispheres to OBJ

Merge the left and right hemispheres into a single triangulated OBJ mesh:

```batch
pip install -r requirements.txt
merge_surfaces.bat <subject_id> [surface_type]
```

**Examples:**
```batch
:: Merge pial surfaces (default) → pial.obj
merge_surfaces.bat sub-116

:: Merge white matter surfaces → white.obj
merge_surfaces.bat sub-116 white
```

This reads the FreeSurfer binary surfaces directly, merges them with correct vertex indexing, and writes a standard Wavefront OBJ with triangular faces. The hemispheres are preserved as separate groups (`left_hemisphere` / `right_hemisphere`) inside the OBJ, so you can still distinguish them in your 3D viewer if needed.

**Output:** `output/<subject_id>/surf/pial.obj` (or `white.obj`)

### Step 4: Load in NIRSViz

Load the OBJ file from `output/<subject_id>/surf/` into NIRSViz. The individual STL files from Step 2 are also available if you need per-hemisphere meshes.

---

## Optional: Merge & Simplify Meshes

Two Python utility scripts are included in the `scripts/` folder. These require Python 3.11+ and the dependencies listed in `requirements.txt`:

```batch
pip install -r requirements.txt
```

**Merge left + right hemispheres into a single mesh:**
```batch
python scripts/merge_stl.py output/sub-116/surf/lh_pial.stl output/sub-116/surf/rh_pial.stl output/sub-116/surf/whole_brain_pial.stl
```

**Reduce mesh complexity for faster rendering** (keeps 10% of triangles by default):
```batch
python scripts/process_mesh.py output/sub-116/surf/whole_brain_pial.stl output/sub-116/surf/whole_brain_pial_lowres.stl 0.90
```

---

## Output Structure

```
output/sub-116/
├── mri/
│   ├── orig.mgz                     # Original T1w in FreeSurfer space
│   ├── aparc.DKTatlas+aseg.mgz      # 95-class segmentation volume
│   ├── aseg.mgz                     # Subcortical segmentation
│   └── brain.mgz                    # Skull-stripped brain
├── surf/
│   ├── lh.pial / rh.pial            # Pial surfaces (FreeSurfer binary format)
│   ├── lh.white / rh.white          # White matter surfaces (FreeSurfer binary)
│   ├── lh_pial.stl / rh_pial.stl    # Per-hemisphere STL files
│   ├── lh_white.stl / rh_white.stl  # Per-hemisphere STL files
│   ├── pial.obj                     # ← Merged pial OBJ (use this in NIRSViz)
│   └── white.obj                    # ← Merged white matter OBJ
├── stats/                            # Volumetric and parcellation statistics
└── label/                            # Cortical parcellation labels
```

---

## Surface Types Explained

**Pial surface** — The outer boundary of the cortex (grey matter / CSF boundary). This is the primary surface for NIRS applications since optodes sit on the scalp and project inward to the cortical surface.

**White surface** — The inner boundary of the cortex (grey matter / white matter boundary). Useful for cortical thickness analysis and understanding the full extent of grey matter.

---

## Processing Multiple Subjects

Create a batch file to process several scans:

```batch
@echo off
call run_fastsurfer.bat sub-001_T1w.nii.gz sub-001
call convert_surfaces.bat sub-001

call run_fastsurfer.bat sub-002_T1w.nii.gz sub-002
call convert_surfaces.bat sub-002
```

---

## Troubleshooting

**"Docker is not running"** — Open Docker Desktop and wait for it to fully start. Check that the Docker Desktop Service is running in Windows Services. Ensure virtualization is enabled in your BIOS.

**"GPU not available"** — Make sure you have an NVIDIA GPU with recent drivers (`nvidia-smi` in PowerShell should show your GPU). Docker Desktop must use the WSL2 backend (Settings → General). Install the NVIDIA Container Toolkit if you haven't. Enable GPU support in Docker Desktop (Settings → Resources → WSL Integration).

**FastSurfer fails with memory errors** — Docker Desktop defaults to limited RAM. Go to Settings → Resources and increase memory to at least 8 GB (16 GB recommended).

**Surfaces look wrong or have holes** — Input image quality matters. FastSurfer expects a T1-weighted scan (MPRAGE or similar) at ~1mm isotropic resolution from a 3T scanner (1.5T works but lower quality). Make sure there are no excessive motion artifacts and full brain coverage.

**"FreeSurfer license not found"** — Make sure `license.txt` is placed in the `license/` folder, not in the root directory.

**convert_surfaces.bat fails** — Verify that `output/<subject_id>/surf/lh.pial` exists. If it doesn't, FastSurfer may not have completed successfully. Check the logs in `output/<subject_id>/scripts/`.

---

## Performance

| Stage | GPU | CPU |
|-------|-----|-----|
| Segmentation | ~1 min | ~15 min |
| Surface reconstruction | ~45-60 min | ~45-60 min |
| **Total** | **~50-70 min** | **~60-75 min** |

**Recommended Docker resources:** 8 GB RAM minimum (16 GB recommended), 10 GB free disk space, 4+ CPU cores.

---

## Project Structure

```
NVIZ_Segmentation/
├── run_fastsurfer.bat       # Step 1: Runs FastSurfer segmentation + surfaces
├── convert_surfaces.bat     # Step 2: Converts FreeSurfer surfaces to STL
├── merge_surfaces.bat       # Step 3: Merges hemispheres into a triangulated OBJ
├── verify_setup.bat         # Checks Docker, GPU, image, and license
├── scripts/
│   ├── merge_to_obj.py      # Reads FreeSurfer surfaces → merged OBJ
│   ├── merge_stl.py         # Merge two STL files (legacy/optional)
│   └── process_mesh.py      # Decimate and smooth meshes for visualization
├── input/                   # Place your T1w .nii.gz files here
├── license/                 # Place your FreeSurfer license.txt here
├── output/                  # Created automatically, contains results
├── requirements.txt         # Python dependencies (nibabel, numpy, open3d)
└── README.md
```

---

## References

- **FastSurfer:** Henschel L, Conjeti S, Estrada S, Diers K, Fischl B, Reuter M. *FastSurfer — A fast and accurate deep learning based neuroimaging pipeline.* NeuroImage 2020. [DOI: 10.1016/j.neuroimage.2020.117012](https://doi.org/10.1016/j.neuroimage.2020.117012)
- FastSurfer GitHub: https://github.com/Deep-MI/FastSurfer
- FreeSurfer: https://surfer.nmr.mgh.harvard.edu/

## License

This pipeline uses FastSurfer (Apache 2.0), FreeSurfer tools (FreeSurfer License, free registration required), and Docker (Apache 2.0).
