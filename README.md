# BrainSegmentation — FastSurfer Pipeline for NIRSViz

Generate high-quality cortex meshes from T1-weighted MRI scans using FastSurfer for import into NIRSViz.

## What This Does

```
T1w MRI (.nii.gz)  →  FastSurfer (Docker)  →  Cortex mesh (.obj)  →  NIRSViz
```

FastSurfer performs:

1. **Brain segmentation** — 95 anatomical classes in ~1 min (GPU) or ~15 min (CPU)
2. **Surface reconstruction** — pial + white matter surfaces in ~45-60 min
3. **Surface conversion** — FreeSurfer format → OBJ for NIRSViz

---

## Prerequisites

### 1. Docker Desktop

* Download from: https://www.docker.com/products/docker-desktop/
* During install, ensure **WSL2 backend** is selected
* After install, open Docker Desktop and verify it's running

### 2. NVIDIA Container Toolkit (for GPU acceleration)

In a PowerShell terminal:

```powershell
# Verify your GPU is visible to Docker
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

If this fails, install the NVIDIA Container Toolkit:

* Guide: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
* You need: NVIDIA driver (Game Ready or Studio) + Docker Desktop with WSL2

Without GPU, FastSurfer still works but segmentation takes ~15 min instead of ~1 min.

### 3. FreeSurfer License (free)

FastSurfer requires a FreeSurfer license file even though it's separate software.

1. Register at: https://surfer.nmr.mgh.harvard.edu/registration.html
2. You'll receive `license.txt` via email
3. Place it in this folder as `license.txt`

---

## Usage

### Quick Start

```batch
1. Place your T1w scan in input/
2. Place license.txt in this folder
3. Run:   run_fastsurfer.bat sub-116_T1w.nii.gz
4. Wait ~1 hour
5. Find cortex.obj in output/<subject>/surf/
```

### Commands

#### run_fastsurfer.bat

**Purpose:** Runs the complete FastSurfer pipeline including segmentation, surface reconstruction, and automatic conversion to OBJ format.

**Syntax:**
```batch
run_fastsurfer.bat <filename.nii.gz> [subject_id]
```

**Parameters:**
* `<filename.nii.gz>` - Required. The T1-weighted MRI scan in NIfTI format (must be in `input/` folder)
* `[subject_id]` - Optional. Custom subject identifier. If omitted, automatically extracted from filename

**What it does:**
1. Launches FastSurfer Docker container with GPU support (if available)
2. Runs deep learning segmentation (~1 min with GPU, ~15 min without)
3. Reconstructs cortical surfaces using topology-preserving algorithms (~45-60 min)
4. Automatically calls `convert_surfaces.bat` to generate OBJ files
5. Creates merged cortex mesh combining left and right hemispheres

**Examples:**

```batch
:: Auto-generates subject ID from filename (e.g., "sub-116")
run_fastsurfer.bat sub-116_ses-BL_T1w.nii.gz

:: Explicit subject ID (useful for custom naming)
run_fastsurfer.bat scan001.nii.gz patient-abc

:: With full session info (extracts "sub-116_ses-baseline")
run_fastsurfer.bat sub-116_ses-baseline_T1w.nii.gz
```

**Output location:** `output/<subject_id>/`

#### convert_surfaces.bat

**Purpose:** Converts FreeSurfer surface files to OBJ format and merges hemispheres. Use this if you already have FastSurfer output or need to regenerate OBJ files without re-running the full pipeline.

**Syntax:**
```batch
convert_surfaces.bat <subject_id>
```

**Parameters:**
* `<subject_id>` - Required. The subject identifier (must match a folder in `output/`)

**What it does:**
1. Uses FreeSurfer's `mris_convert` tool inside Docker to convert binary surface files
2. Converts left hemisphere surfaces: `lh.pial`, `lh.white` → `lh.pial.obj`, `lh.white.obj`
3. Converts right hemisphere surfaces: `rh.pial`, `rh.white` → `rh.pial.obj`, `rh.white.obj`
4. Runs Python script to merge left and right pial surfaces into single `cortex.obj`
5. Preserves vertex ordering and adjusts coordinates for combined mesh

**When to use:**
* FastSurfer completed but OBJ files are missing or corrupted
* You want to regenerate merged cortex.obj with different parameters
* You have FreeSurfer output from another source and need OBJ conversion
* You modified surface files and need fresh OBJ exports

**Examples:**

```batch
:: Convert surfaces for subject "sub-116"
convert_surfaces.bat sub-116

:: Convert for custom subject ID
convert_surfaces.bat patient-abc
```

**Requirements:**
* `output/<subject_id>/surf/` must contain FreeSurfer surface files:
  * `lh.pial` and `rh.pial` (required for cortex.obj)
  * `lh.white` and `rh.white` (optional, for white matter)
* Docker must be running
* FastSurfer Docker image must be available

**Output files in** `output/<subject_id>/surf/`:
* `lh.pial.obj` - Left hemisphere cortical surface
* `rh.pial.obj` - Right hemisphere cortical surface  
* `lh.white.obj` - Left hemisphere white matter surface
* `rh.white.obj` - Right hemisphere white matter surface
* `cortex.obj` - **Merged bilateral pial surface (use this in NIRSViz)**

---

## Output Structure

After a successful run, `output/<subject_id>/` contains:

```
output/sub-116/
├── mri/
│   ├── aseg.mgz              ← Volumetric segmentation (95 classes)
│   ├── brain.mgz             ← Skull-stripped brain
│   ├── orig.mgz              ← Original T1w in FreeSurfer space
│   └── ...
├── surf/
│   ├── lh.pial               ← Left hemisphere pial surface (FreeSurfer format)
│   ├── rh.pial               ← Right hemisphere pial surface
│   ├── lh.white              ← Left hemisphere white matter surface
│   ├── rh.white              ← Right hemisphere white matter surface
│   ├── lh.pial.obj           ← Left pial as OBJ  ← USE THESE
│   ├── rh.pial.obj           ← Right pial as OBJ
│   ├── lh.white.obj          ← Left white as OBJ
│   ├── rh.white.obj          ← Right white as OBJ
│   ├── cortex.obj            ← Merged lh+rh pial  ← OR THIS (RECOMMENDED)
│   └── ...
├── label/                     ← Cortical parcellation labels
├── stats/                     ← Thickness, volume statistics
└── scripts/                   ← Processing logs
```

### Files for NIRSViz

| File | What it is | Use in NIRSViz |
| --- | --- | --- |
| `surf/cortex.obj` | Merged pial surface (both hemispheres) | **Primary cortex mesh for NIRS channel projection** |
| `surf/lh.pial.obj` + `rh.pial.obj` | Individual hemisphere pial surfaces | Load separately if hemisphere-specific analysis needed |
| `surf/lh.white.obj` + `rh.white.obj` | White matter surface | Visualization of GM/WM boundary |
| `mri/aseg.mgz` | 95-class segmentation volume | Slice viewer overlay (future feature) |

---

## Surface Types Explained

**Pial surface** — The outer boundary of the cortex (grey matter/CSF boundary). This is the primary surface for NIRS applications since optodes sit on the scalp and project inward to the cortical surface. The pial surface represents where light actually interacts with cortical tissue.

**White surface** — The inner boundary of the cortex (grey matter/white matter boundary). Useful for visualization, cortical thickness analysis, and understanding the full extent of grey matter.

**Inflated surface** — The pial surface "inflated" like a balloon, making sulci visible. Purely for visualization purposes, not geometrically accurate for spatial analysis.

**Cortex.obj (merged)** — A single unified mesh combining left and right pial surfaces. This is the most convenient format for NIRSViz as it allows bilateral channel mapping on one mesh rather than managing two separate hemisphere files.

---

## Troubleshooting

**"Docker is not running"**
→ Open Docker Desktop and wait for it to start. The whale icon in the system tray should stop animating. If Docker fails to start, check Windows Services for "Docker Desktop Service" and ensure virtualization is enabled in BIOS.

**"GPU not available via Docker"**
→ Make sure you have:
* An NVIDIA GPU with recent drivers (check with `nvidia-smi` in PowerShell)
* Docker Desktop using the WSL2 backend (Settings → General → Use WSL2)
* NVIDIA Container Toolkit installed in WSL2
* GPU support enabled in Docker Desktop (Settings → Resources → WSL Integration)

**FastSurfer fails with memory errors**
→ Docker Desktop defaults to limited RAM. Go to Settings → Resources → WSL Integration and increase memory to at least 8 GB (16 GB recommended for complex cases).

**Surfaces look wrong / have holes**
→ Input image quality matters. FastSurfer expects:
* 3T scanner preferred (1.5T works but lower quality)
* 1mm isotropic resolution (0.7-1.5mm acceptable)
* MPRAGE or similar T1-weighted sequence
* No excessive motion artifacts
* Proper brain coverage (full brain from skull base to vertex)

**"FreeSurfer license not found"**
→ Register at https://surfer.nmr.mgh.harvard.edu/registration.html  
Place the received license.txt in this BrainSegmentation/ folder (not in subdirectories).

**convert_surfaces.bat fails with "subject not found"**
→ Verify:
* The subject folder exists in `output/<subject_id>/`
* The folder contains `surf/lh.pial` and `surf/rh.pial`
* You're using the exact subject_id that matches the folder name

**OBJ files are empty or corrupted**
→ Check the processing logs in `output/<subject_id>/scripts/`. If surfaces were generated but conversion failed, try running `convert_surfaces.bat <subject_id>` again. Ensure Docker has sufficient disk space.

**"Cannot find merge_obj.py"**
→ Ensure `merge_obj.py` is in the same directory as `convert_surfaces.bat`. This script is required to merge left and right hemisphere surfaces into cortex.obj.

---

## Performance Notes

**GPU vs CPU:**
* Segmentation: ~1 min (GPU) vs ~15 min (CPU)
* Surface reconstruction: ~45-60 min (both, CPU-bound)
* Total time: ~50-70 min with GPU, ~60-75 min without

**Docker resource recommendations:**
* RAM: 8 GB minimum, 16 GB recommended
* Disk: 10 GB free space minimum (for output + temporary files)
* CPU: 4+ cores recommended (surface reconstruction can use multiple cores)

---

## About FastSurfer

FastSurfer is a neuroimaging pipeline based on deep learning that provides fast and accurate whole brain segmentation. It replicates FreeSurfer's anatomical preprocessing in a fraction of the time using convolutional neural networks.

**Key advantages over FreeSurfer:**
* 100x faster segmentation (~1 min vs ~1.5 hours)
* Comparable or better accuracy on modern 3T data
* GPU acceleration support
* Fully open source (Apache 2.0 license)

**Citation:**
If you use this pipeline, please cite:  
Henschel L, Conjeti S, Estrada S, Diers K, Fischl B, Reuter M. FastSurfer - A fast and accurate deep learning based neuroimaging pipeline. NeuroImage 2020. https://doi.org/10.1016/j.neuroimage.2020.117012

---

## File Formats

**NIfTI (.nii.gz)** — Compressed volumetric MRI data format, standard in neuroimaging  
**FreeSurfer binary** — Proprietary surface format (e.g., lh.pial, rh.white)  
**OBJ (.obj)** — Standard 3D mesh format, widely compatible and human-readable  
**MGZ (.mgz)** — Compressed FreeSurfer volume format

---

## Advanced Usage

### Processing multiple subjects

Create a batch script to process multiple subjects:

```batch
@echo off
for %%f in (input\*.nii.gz) do (
    echo Processing %%f
    call run_fastsurfer.bat %%~nxf
)
```

### Custom output directory

Modify `run_fastsurfer.bat` to specify a different output location by changing the Docker volume mount.

### Using custom segmentation settings

Advanced users can modify the FastSurfer Docker command in `run_fastsurfer.bat` to add flags like:
* `--no_surf` - Skip surface reconstruction (segmentation only)
* `--seg_only` - Run only the segmentation network
* `--parallel` - Enable parallel processing of left/right hemispheres

---

## Additional Resources

* FastSurfer GitHub: https://github.com/Deep-MI/FastSurfer
* FastSurfer documentation: https://deep-mi.org/research/fastsurfer/
* FreeSurfer wiki: https://surfer.nmr.mgh.harvard.edu/
* NIRSViz documentation: [link to NIRSViz docs]

---

## License

This pipeline uses:
* FastSurfer - Apache 2.0 License
* FreeSurfer - FreeSurfer License (registration required)
* Docker - Apache 2.0 License
