"""
Merge left and right FreeSurfer hemisphere surfaces into a single triangulated OBJ mesh.

Reads FreeSurfer binary surface files (e.g. lh.pial, rh.pial) directly using nibabel,
merges them with correct vertex index offsetting, and writes a standard Wavefront OBJ
with triangular faces.

Requires: pip install nibabel numpy

Usage:
  python merge_to_obj.py <left_surface> <right_surface> <output.obj>

Examples:
  python merge_to_obj.py output/sub-116/surf/lh.pial output/sub-116/surf/rh.pial output/sub-116/surf/cortex.obj
  python merge_to_obj.py output/sub-116/surf/lh.white output/sub-116/surf/rh.white output/sub-116/surf/white.obj
"""
import os
import sys

import nibabel.freesurfer.io as fsio
import numpy as np


def read_freesurfer_surface(path):
    """Read a FreeSurfer binary surface file and return vertices and faces."""
    if not os.path.exists(path):
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)

    vertices, faces = fsio.read_geometry(path)
    print(f"  [OK] {os.path.basename(path)}: {len(vertices)} vertices, {len(faces)} faces")
    return vertices, faces


def merge_and_write_obj(lh_path, rh_path, output_path):
    """
    Read two FreeSurfer surfaces, merge them into a single mesh,
    and write as a triangulated Wavefront OBJ file.
    """
    print("--- Reading surfaces ---")
    lh_verts, lh_faces = read_freesurfer_surface(lh_path)
    rh_verts, rh_faces = read_freesurfer_surface(rh_path)

    # Offset right-hemisphere face indices by the number of left-hemisphere vertices
    rh_faces_offset = rh_faces + len(lh_verts)

    # Concatenate
    all_verts = np.concatenate([lh_verts, rh_verts], axis=0)
    all_faces = np.concatenate([lh_faces, rh_faces_offset], axis=0)

    print(f"\n--- Merged mesh ---")
    print(f"  Vertices: {len(all_verts)}")
    print(f"  Faces:    {len(all_faces)} (all triangles)")

    # Write OBJ
    print(f"\n--- Writing OBJ ---")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w") as f:
        f.write(f"# Merged FreeSurfer surface\n")
        f.write(f"# Left:  {os.path.basename(lh_path)} ({len(lh_verts)} verts)\n")
        f.write(f"# Right: {os.path.basename(rh_path)} ({len(rh_verts)} verts)\n")
        f.write(f"# Total: {len(all_verts)} vertices, {len(all_faces)} triangles\n\n")

        # Vertices
        for v in all_verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        f.write(f"\n# Left hemisphere faces\n")
        f.write(f"g left_hemisphere\n")
        for face in lh_faces:
            # OBJ faces are 1-indexed
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

        f.write(f"\n# Right hemisphere faces\n")
        f.write(f"g right_hemisphere\n")
        for face in rh_faces_offset:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

    print(f"  [OK] Written to: {output_path}")
    print(f"  File size: {os.path.getsize(output_path) / (1024*1024):.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <left_surface> <right_surface> <output.obj>")
        print()
        print("Examples:")
        print(f"  {sys.argv[0]} output/sub-116/surf/lh.pial output/sub-116/surf/rh.pial output/sub-116/surf/cortex.obj")
        print(f"  {sys.argv[0]} output/sub-116/surf/lh.white output/sub-116/surf/rh.white output/sub-116/surf/white.obj")
        sys.exit(1)

    merge_and_write_obj(sys.argv[1], sys.argv[2], sys.argv[3])
