"""
Build a 1mm³ labeled head volume from FastSurfer outputs.

Reads:
  aseg.mgz      — FreeSurfer automated segmentation (grey, white, CSF labels)
  T1.mgz        — Intensity volume (used to derive the skull/scalp region)
  brainmask.mgz — Binary brain mask (used to separate skull from brain)

Writes:
  head_labels.nii.gz — NIfTI-1 int8 volume, same grid as T1.mgz
    0 = background
    1 = skull / scalp (inside head, outside brain)
    2 = CSF (ventricles + subarachnoid space)
    3 = grey matter (cortex + subcortical structures)
    4 = white matter

Priority (higher overwrites lower): WM > GM > CSF > skull > background

Usage:
  python voxelize_labels.py aseg.mgz T1.mgz brainmask.mgz head_labels.nii.gz

Requires:
  pip install nibabel numpy scipy
"""

import argparse
import sys
import os

import nibabel as nib
import numpy as np
from scipy import ndimage


# ---------------------------------------------------------------------------
# FreeSurfer aseg label sets
# ---------------------------------------------------------------------------

WM_LABELS = {
    2,    # Left-Cerebral-White-Matter
    41,   # Right-Cerebral-White-Matter
    7,    # Left-Cerebellum-White-Matter
    46,   # Right-Cerebellum-White-Matter
    77,   # WM-hypointensities
    78,   # Left-WM-hypointensities
    79,   # Right-WM-hypointensities
    192,  # Corpus-Callosum (some FastSurfer versions)
    251,  # CC_Posterior
    252,  # CC_Mid_Posterior
    253,  # CC_Central
    254,  # CC_Mid_Anterior
    255,  # CC_Anterior
}

GM_LABELS = {
    # Cortex
    3,    # Left-Cerebral-Cortex
    42,   # Right-Cerebral-Cortex
    8,    # Left-Cerebellum-Cortex
    47,   # Right-Cerebellum-Cortex
    # Subcortical grey
    10,   # Left-Thalamus
    11,   # Left-Caudate
    12,   # Left-Putamen
    13,   # Left-Pallidum
    17,   # Left-Hippocampus
    18,   # Left-Amygdala
    26,   # Left-Accumbens-area
    28,   # Left-VentralDC
    16,   # Brain-Stem
    49,   # Right-Thalamus
    50,   # Right-Caudate
    51,   # Right-Putamen
    52,   # Right-Pallidum
    53,   # Right-Hippocampus
    54,   # Right-Amygdala
    58,   # Right-Accumbens-area
    60,   # Right-VentralDC
}

CSF_LABELS = {
    4,    # Left-Lateral-Ventricle
    5,    # Left-Inf-Lat-Vent
    14,   # 3rd-Ventricle
    15,   # 4th-Ventricle
    24,   # CSF (subarachnoid)
    31,   # Left-Choroid-Plexus
    43,   # Right-Lateral-Ventricle
    44,   # Right-Inf-Lat-Vent
    63,   # Right-Choroid-Plexus
    72,   # 5th-Ventricle
}

LABEL_BG   = 0
LABEL_SKULL = 1
LABEL_CSF  = 2
LABEL_GM   = 3
LABEL_WM   = 4


def make_head_mask(t1_data, threshold=15, smooth_iter=2):
    """Threshold T1 intensity + morphological ops to get a binary head mask."""
    mask = t1_data > threshold
    struct = ndimage.generate_binary_structure(3, 2)
    if smooth_iter > 0:
        mask = ndimage.binary_closing(mask, structure=struct, iterations=smooth_iter)
    mask = ndimage.binary_fill_holes(mask)
    return mask


def map_aseg(aseg_data, label_set, out_volume, value):
    """Set all voxels whose aseg label is in `label_set` to `value`."""
    for lbl in label_set:
        out_volume[aseg_data == lbl] = value


def main():
    parser = argparse.ArgumentParser(
        description="Build a 4-label head volume from FastSurfer outputs.")
    parser.add_argument("aseg",       help="Path to aseg.mgz")
    parser.add_argument("t1",         help="Path to T1.mgz")
    parser.add_argument("brainmask",  help="Path to brainmask.mgz")
    parser.add_argument("output",     help="Output path (head_labels.nii.gz)")
    parser.add_argument("--threshold", type=float, default=15,
                        help="T1 intensity threshold for head mask (default: 15)")
    parser.add_argument("--smooth", type=int, default=2,
                        help="Morphological closing iterations (default: 2)")
    args = parser.parse_args()

    for path in (args.aseg, args.t1, args.brainmask):
        if not os.path.isfile(path):
            print(f"[ERROR] File not found: {path}", file=sys.stderr)
            sys.exit(1)

    # --- Load volumes ---
    print(f"Loading aseg.mgz      : {args.aseg}")
    aseg_img  = nib.load(args.aseg)
    aseg_data = np.asarray(aseg_img.dataobj, dtype=np.int32)

    print(f"Loading T1.mgz        : {args.t1}")
    t1_img  = nib.load(args.t1)
    t1_data = t1_img.get_fdata()

    print(f"Loading brainmask.mgz : {args.brainmask}")
    bm_img  = nib.load(args.brainmask)
    bm_data = np.asarray(bm_img.dataobj, dtype=np.float32) > 0

    shape = t1_data.shape
    print(f"Volume shape: {shape}  (should be ~256³ at 1mm isotropic)")

    # --- Build label volume (int8 is plenty: values 0-4) ---
    labels = np.zeros(shape, dtype=np.int8)

    # 1. Skull/scalp: voxels inside the head mask but outside the brain mask
    print("Computing skull/scalp region ...")
    head_mask = make_head_mask(t1_data, args.threshold, args.smooth)
    labels[head_mask & ~bm_data] = LABEL_SKULL

    # 2-4. Brain tissue from aseg (higher-priority labels overwrite lower ones)
    print("Mapping CSF labels ...")
    map_aseg(aseg_data, CSF_LABELS, labels, LABEL_CSF)

    print("Mapping grey matter labels ...")
    map_aseg(aseg_data, GM_LABELS, labels, LABEL_GM)

    print("Mapping white matter labels ...")
    map_aseg(aseg_data, WM_LABELS, labels, LABEL_WM)

    # Report voxel counts
    for val, name in [(0, "background"), (1, "skull"), (2, "CSF"),
                      (3, "grey matter"), (4, "white matter")]:
        count = int((labels == val).sum())
        pct = 100.0 * count / labels.size
        print(f"  {name:15s}: {count:>10,} voxels  ({pct:.1f}%)")

    # --- Save as NIfTI with the T1 affine ---
    print(f"\nWriting: {args.output}")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    out_img = nib.Nifti1Image(labels, t1_img.affine)
    out_img.header.set_data_dtype(np.int8)
    nib.save(out_img, args.output)
    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    print(f"[OK] {args.output}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
