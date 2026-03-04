"""
Generate one OBJ mesh per tissue label from head_labels.nii.gz.

Reads:
  head_labels.nii.gz — output of voxelize_labels.py
    0 = background, 1 = skull, 2 = CSF, 3 = grey matter, 4 = white matter

Writes (to output_dir/):
  skull.obj
  csf.obj
  grey_matter.obj
  white_matter.obj

Each mesh is extracted with marching cubes (level=0.5 on a binary mask),
decimated to a target face count, and exported as Wavefront OBJ so it can
be opened in Blender, MeshLab, 3D Slicer, etc.

Usage:
  python meshify_labels.py head_labels.nii.gz output_dir/

Requires:
  pip install nibabel numpy scikit-image trimesh fast-simplification
"""

import argparse
import os
import sys

import nibabel as nib
import numpy as np
from skimage import measure
import trimesh
import fast_simplification


TISSUES = [
    (1, "skull",       200_000),  # (label_value, filename, target_faces)
    (2, "csf",         150_000),
    (3, "grey_matter", 200_000),
    (4, "white_matter", 150_000),
]


def extract_mesh(binary_mask, affine, target_faces):
    """
    Run marching cubes on a binary mask, transform to world coordinates,
    decimate if needed, and return a trimesh.Trimesh.
    """
    verts, faces, normals, _ = measure.marching_cubes(
        binary_mask.astype(np.float32),
        level=0.5,
        step_size=2,       # step_size=2 keeps initial mesh size manageable
    )

    # Transform voxel indices → NIfTI world space (RAS mm)
    ones = np.ones((len(verts), 1))
    verts_world = (affine @ np.hstack([verts, ones]).T).T[:, :3]

    mesh = trimesh.Trimesh(vertices=verts_world, faces=faces,
                           vertex_normals=normals, process=False)

    if target_faces and len(mesh.faces) > target_faces:
        reduction = 1.0 - target_faces / len(mesh.faces)
        pts_out, faces_out = fast_simplification.simplify(
            mesh.vertices.astype(np.float32),
            mesh.faces,
            target_reduction=float(reduction),
        )
        mesh = trimesh.Trimesh(vertices=pts_out, faces=faces_out, process=False)

    return mesh


def main():
    parser = argparse.ArgumentParser(
        description="Meshify a 4-label head volume into per-tissue OBJ files.")
    parser.add_argument("labels_vol", help="Path to head_labels.nii.gz")
    parser.add_argument("output_dir", help="Directory to write OBJ files")
    parser.add_argument("--step-size", type=int, default=2,
                        help="Marching-cubes step size (default: 2)")
    args = parser.parse_args()

    if not os.path.isfile(args.labels_vol):
        print(f"[ERROR] File not found: {args.labels_vol}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Loading: {args.labels_vol}")
    img = nib.load(args.labels_vol)
    data = np.asarray(img.dataobj, dtype=np.int8)
    affine = img.affine
    print(f"  Shape: {data.shape}")

    for label_val, name, target_faces in TISSUES:
        out_path = os.path.join(args.output_dir, f"{name}.obj")

        mask = data == label_val
        count = int(mask.sum())
        if count == 0:
            print(f"  [{name}] label {label_val} has no voxels — skipping.")
            continue

        print(f"\n  [{name}] label={label_val}  voxels={count:,}")
        print(f"    Running marching cubes ...")
        mesh = extract_mesh(mask, affine, target_faces)
        print(f"    Mesh: {len(mesh.vertices):,} vertices, {len(mesh.faces):,} faces")

        mesh.export(out_path, file_type="obj")
        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        print(f"    [OK] {out_path}  ({size_mb:.1f} MB)")

    print("\nDone. Open the OBJ files in a 3D viewer to inspect the segmentation.")


if __name__ == "__main__":
    main()
