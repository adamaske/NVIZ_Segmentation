# BrainSegmentation — FastSurfer Pipeline for NIRSViz

Generate high-quality cortex meshes from T1-weighted MRI scans using FastSurfer,
for import into NIRSViz.

## What This Does

```
T1w MRI (.nii.gz)  →  FastSurfer (Docker)  →  Cortex mesh (.obj)  →  NIRSViz
```

FastSurfer performs:
1. **Brain segmentation** — 95 anatomical classes in ~1 min (GPU)
2. **Surface reconstruction** — pial + white matter surfaces in ~45-60 min
3. **Surface conversion** — FreeSurfer format → OBJ for NIRSViz

---

## Prerequisites

### 1. Docker Desktop

- Download from: https://www.docker.com/products/docker-desktop/
- During install, ensure **WSL2 backend** is selected
- After install, open Docker Desktop and verify it's running

### 2. NVIDIA Container Toolkit (for GPU acceleration)

In a PowerShell terminal:
```powershell
# Verify your GPU is visible to Docker
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

If this fails, install the NVIDIA Container Toolkit:
- Guide: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
- You need: NVIDIA driver (Game Ready or Studio) + Docker Desktop with WSL2

Without GPU, FastSurfer still works but segmentation takes ~15 min instead of ~1 min.

### 3. FreeSurfer License (free)

FastSurfer requires a FreeSurfer license file even though it's separate software.

1. Register at: https://surfer.nmr.mgh.harvard.edu/registration.html
2. You'll receive `license.txt` via email
3. Place it in this folder as `license.txt`

---

## Usage

### Quick Start

```
1. Place your T1w scan in input/
2. Place license.txt in this folder
3. Run:   run_fastsurfer.bat sub-116_T1w.nii.gz
4. Wait ~1 hour
5. Find cortex.obj in output/<subject>/surf/
```

### Full Command

```batch
run_fastsurfer.bat <filename.nii.gz> [subject_id]
```

**Examples:**
```batch
:: Auto-generates subject ID from filename
run_fastsurfer.bat sub-116_ses-BL_T1w.nii.gz

:: Explicit subject ID  
run_fastsurfer.bat sub-116_ses-BL_T1w.nii.gz sub-116
```

### Convert Only (if you already ran FastSurfer)

```batch
convert_surfaces.bat sub-116
```

This converts FreeSurfer surfaces to OBJ and merges left+right hemispheres
into a single `cortex.obj`.

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
│   ├── cortex.obj            ← Merged lh+rh pial  ← OR THIS
│   └── ...
├── label/                     ← Cortical parcellation labels
├── stats/                     ← Thickness, volume statistics
└── scripts/                   ← Processing logs
```

### Files for NIRSViz

| File | What it is | Use in NIRSViz |
|------|-----------|----------------|
| `surf/cortex.obj` | Merged pial surface (both hemispheres) | Load as cortex mesh |
| `surf/lh.white.obj` + `rh.white.obj` | White matter surface | Load as WM mesh |
| `mri/aseg.mgz` | 95-class segmentation volume | Slice viewer overlay (future) |

---

## Surface Types Explained

**Pial surface** — the outer boundary of the cortex (grey matter / CSF boundary).
This is what you want for NIRS channel projection since optodes sit on the scalp
and project inward to the cortical surface.

**White surface** — the inner boundary of the cortex (grey matter / white matter boundary).
Useful for visualization and cortical thickness analysis.

**Inflated surface** — the pial surface "inflated" like a balloon, making sulci visible.
Useful for visualization but not for spatial analysis.

---

## Troubleshooting

**"Docker is not running"**
→ Open Docker Desktop and wait for it to start. The whale icon in the system tray
  should stop animating.

**"GPU not available via Docker"**
→ Make sure you have:
  - An NVIDIA GPU with recent drivers (check with `nvidia-smi` in PowerShell)
  - Docker Desktop using the WSL2 backend (Settings → General → Use WSL2)
  - NVIDIA Container Toolkit installed in WSL2

**FastSurfer fails with memory errors**
→ Docker Desktop defaults to limited RAM. Go to Settings → Resources and increase
  memory to at least 8 GB (16 GB recommended).

**Surfaces look wrong / have holes**
→ Input image quality matters. FastSurfer expects:
  - 3T scanner preferred (1.5T works but lower quality)
  - 1mm isotropic resolution (0.7-1.5mm acceptable)
  - MPRAGE or similar T1-weighted sequence
  - No excessive motion artifacts

**"FreeSurfer license not found"**
→ Register at https://surfer.nmr.mgh.harvard.edu/registration.html
  Place the received license.txt in this BrainSegmentation/ folder.

---

## For NIRSViz Integration (Developer Notes)

The OBJ files produced here are standard Wavefront OBJ with vertices and triangular
faces. They load directly with your existing OBJ loader (`cortex_model.obj` path).

Coordinate system: FreeSurfer surfaces are in **scanner RAS** coordinates (Right,
Anterior, Superior) in millimeters, matching the T1w image. If your MRI is loaded
via ITK in NIRSViz, the coordinates should align — both use the same physical
coordinate system from the NIfTI header.

Typical mesh stats for an adult brain:
- Pial surface: ~130,000-160,000 vertices per hemisphere
- `cortex.obj` (merged): ~260,000-320,000 vertices total
- If this is too heavy, decimate in MeshLab or use FreeSurfer's `mris_decimate`
