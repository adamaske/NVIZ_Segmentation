"""
Convert a FreeSurfer scalp STL (lh.seghead) to a reoriented Wavefront OBJ.

Loads the STL produced by mris_convert, applies the same axis reorientation
used by merge_to_obj.py, and writes a Wavefront OBJ file.

Requires: pip install trimesh

Usage:
  python extract_scalp.py <lh_seghead.stl> <scalp.obj>

Example:
  python extract_scalp.py output/sub-116/surf/lh_seghead.stl output/sub-116/surf/scalp.obj
"""
import os
import sys

import numpy as np
import trimesh


def stl_to_obj(stl_path, output_path):
    """Load scalp STL, reorient axes, and export as OBJ."""

    if not os.path.exists(stl_path):
        print(f"[ERROR] File not found: {stl_path}")
        sys.exit(1)

    print(f"--- Loading: {stl_path} ---")
    mesh = trimesh.load(stl_path)
    print(f"  Vertices: {len(mesh.vertices):,}")
    print(f"  Faces:    {len(mesh.faces):,}")

    # Reorient: frontal (old +Z) -> +X, inferior (old +Y) -> -Z
    mesh.vertices = mesh.vertices[:, [2, 0, 1]] * np.array([1, -1, -1])

    print(f"\n--- Writing OBJ ---")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    mesh.export(output_path, file_type="obj")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  [OK] Written to: {output_path}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <lh_seghead.stl> <scalp.obj>")
        print()
        print("Example:")
        print(f"  {sys.argv[0]} output/sub-116/surf/lh_seghead.stl output/sub-116/surf/scalp.obj")
        sys.exit(1)

    stl_to_obj(sys.argv[1], sys.argv[2])
