"""
Extract a scalp surface from a FreeSurfer/FastSurfer T1.mgz using pure Python.

Replaces the FreeSurfer `mkheadsurf` command, which is missing from the
stripped-down FreeSurfer distribution bundled with the FastSurfer Docker image.

Algorithm:
  1. Load T1.mgz with nibabel
  2. Threshold the volume to create a binary head mask
  3. Apply morphological closing to fill small gaps
  4. Fill interior holes so we get a solid head volume
  5. Optionally erode + dilate to smooth the boundary
  6. Extract the isosurface via marching cubes (skimage)
  7. Transform vertices from voxel coords to FreeSurfer surface-RAS (tkRAS)
  8. Apply the same axis reorientation used by the rest of the pipeline
  9. Decimate if the mesh is very dense
  10. Export as Wavefront OBJ

Requires:
  pip install nibabel numpy scipy scikit-image trimesh fast-simplification

Usage:
  python extract_scalp.py <T1.mgz> <output.obj> [--threshold 15] [--smooth 2] [--decimate 50000]

Example:
  python extract_scalp.py output/sub-116/mri/T1.mgz output/sub-116/surf/scalp.obj
"""

import argparse
import os
import sys

import fast_simplification
import nibabel as nib
import numpy as np
from scipy import ndimage
from skimage import measure
import trimesh


def create_head_mask(data, threshold=15, smooth_iterations=2):
    """
    Create a binary scalp mask from T1 intensity data.

    Parameters
    ----------
    data : ndarray
        3D T1 intensity volume.
    threshold : float
        Intensity threshold to separate head from background.
        Default 15 works well for FreeSurfer-conformed T1.mgz volumes
        (intensity range ~0-255). Adjust if your data differs.
    smooth_iterations : int
        Number of binary-closing iterations for smoothing the mask.

    Returns
    -------
    mask : ndarray (bool)
        Binary mask where True = inside the head.
    """
    print(f"  Thresholding at intensity >= {threshold} ...")
    mask = data > threshold

    # Morphological closing to bridge small gaps (e.g. in sinuses, ears)
    struct = ndimage.generate_binary_structure(3, 2)  # 3x3x3 connectivity
    if smooth_iterations > 0:
        print(f"  Morphological closing ({smooth_iterations} iterations) ...")
        mask = ndimage.binary_closing(mask, structure=struct,
                                      iterations=smooth_iterations)

    # Fill all interior holes so we get a single solid volume
    print("  Filling interior holes ...")
    mask = ndimage.binary_fill_holes(mask)

    # One round of erosion + dilation to smooth jagged edges
    print("  Smoothing boundary ...")
    mask = ndimage.binary_erosion(mask, structure=struct, iterations=1)
    mask = ndimage.binary_dilation(mask, structure=struct, iterations=1)

    return mask


def extract_surface(mask, t1_img, decimate_target=100_000):
    """
    Extract an isosurface mesh from the binary head mask.

    Parameters
    ----------
    mask : ndarray (bool)
        Binary head mask (True = inside).
    t1_img : nibabel image
        The original T1 image (used for the vox2ras-tkr transform).
    decimate_target : int or None
        If the mesh has more faces than this, decimate it.

    Returns
    -------
    mesh : trimesh.Trimesh
        The scalp surface mesh in FreeSurfer surface-RAS coordinates.
    """
    print("  Running marching cubes (step_size=2) ...")
    # step_size=2 gives ~4x fewer faces than step_size=1 with acceptable quality,
    # reducing both processing time and the burden on the decimation pass.
    verts, faces, normals, _ = measure.marching_cubes(
        mask.astype(np.float32),
        level=0.5,
        step_size=2,
    )
    print(f"    Raw mesh: {len(verts):,} vertices, {len(faces):,} faces")

    # Transform from voxel indices to FreeSurfer surface-RAS (tkRAS)
    # This is the coordinate system used by all FreeSurfer surfaces.
    vox2ras_tkr = t1_img.header.get_vox2ras_tkr()
    ones = np.ones((len(verts), 1))
    verts_hom = np.hstack([verts, ones])  # Nx4
    verts_tkr = (vox2ras_tkr @ verts_hom.T).T[:, :3]

    mesh = trimesh.Trimesh(vertices=verts_tkr, faces=faces,
                           vertex_normals=normals, process=False)

    # Decimate to target vertex range (~20-50k).
    # For a closed triangle mesh: vertices ≈ faces / 2, so face targets:
    #   20k verts → ~40k faces  |  35k verts → ~70k faces  |  50k verts → ~100k faces
    if decimate_target and len(mesh.faces) > decimate_target:
        target_reduction = 1.0 - (decimate_target / len(mesh.faces))
        est_verts = decimate_target // 2
        print(f"  Decimating to ~{decimate_target:,} faces (~{est_verts:,} vertices, "
              f"reduction={target_reduction:.1%}) ...")
        points_out, faces_out = fast_simplification.simplify(
            mesh.vertices.astype(np.float32),
            mesh.faces,
            target_reduction=target_reduction,
            volume_preservation=True,
        )
        mesh = trimesh.Trimesh(vertices=points_out, faces=faces_out, process=False)
        print(f"    Decimated: {len(mesh.vertices):,} vertices, {len(mesh.faces):,} faces")

    return mesh


def main():
    parser = argparse.ArgumentParser(
        description="Extract scalp surface from T1.mgz (pure Python, no mkheadsurf)")
    parser.add_argument("t1_path", help="Path to T1.mgz (FreeSurfer/FastSurfer output)")
    parser.add_argument("output_path", help="Output path for the OBJ file")
    parser.add_argument("--threshold", type=float, default=15,
                        help="Intensity threshold for head mask (default: 15)")
    parser.add_argument("--smooth", type=int, default=2,
                        help="Morphological closing iterations (default: 2)")
    parser.add_argument("--decimate", type=int, default=50_000,
                        help="Target face count for decimation (0=disable, default: 50000 → ~25k vertices)")
    parser.add_argument("--no-reorient", action="store_true",
                        help="Skip the axis reorientation step")
    args = parser.parse_args()

    if not os.path.isfile(args.t1_path):
        print(f"[ERROR] File not found: {args.t1_path}")
        sys.exit(1)

    # --- Load T1 ---
    print(f"\n--- Loading: {args.t1_path} ---")
    t1_img = nib.load(args.t1_path)
    data = t1_img.get_fdata()
    print(f"  Shape: {data.shape}")
    print(f"  Intensity range: {data.min():.1f} - {data.max():.1f}")

    # --- Create head mask ---
    print("\n--- Creating head mask ---")
    mask = create_head_mask(data, threshold=args.threshold,
                            smooth_iterations=args.smooth)
    voxel_count = mask.sum()
    print(f"  Mask voxels: {voxel_count:,}")

    if voxel_count < 1000:
        print("[ERROR] Mask is nearly empty — threshold may be too high.")
        print("  Try a lower value with --threshold (e.g. 5 or 10).")
        sys.exit(1)

    # --- Extract surface ---
    print("\n--- Extracting surface ---")
    decimate = args.decimate if args.decimate > 0 else None
    mesh = extract_surface(mask, t1_img, decimate_target=decimate)

    # --- Reorient axes to match the rest of the pipeline ---
    # Same convention as merge_to_obj.py: frontal (old +Z) -> +X,
    # inferior (old +Y) -> -Z
    if not args.no_reorient:
        print("\n--- Reorienting axes ---")
        mesh.vertices = mesh.vertices[:, [2, 0, 1]] * np.array([1, -1, -1])

    # --- Export ---
    print(f"\n--- Writing OBJ ---")
    os.makedirs(os.path.dirname(args.output_path) or ".", exist_ok=True)
    mesh.export(args.output_path, file_type="obj")
    size_mb = os.path.getsize(args.output_path) / (1024 * 1024)
    print(f"  [OK] {args.output_path}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()