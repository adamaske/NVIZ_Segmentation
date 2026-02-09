"""
Merge two STL meshes (left + right hemisphere) into a single triangulated OBJ.

Loads the STL files produced by convert_surfaces.bat, merges them, and exports
a standard Wavefront OBJ with triangular faces.

Requires: pip install trimesh

Usage:
  python merge_to_obj.py <left.stl> <right.stl> <output.obj>

Examples:
  python merge_to_obj.py output/sub-116/surf/lh_pial.stl output/sub-116/surf/rh_pial.stl output/sub-116/surf/pial.obj
  python merge_to_obj.py output/sub-116/surf/lh_white.stl output/sub-116/surf/rh_white.stl output/sub-116/surf/white.obj
"""
import os
import sys

import trimesh


def merge_stl_to_obj(lh_path, rh_path, output_path):
    """Load two STL meshes, merge them, and write as a triangulated OBJ."""

    for path in [lh_path, rh_path]:
        if not os.path.exists(path):
            print(f"[ERROR] File not found: {path}")
            sys.exit(1)

    print("--- Loading meshes ---")
    lh = trimesh.load(lh_path)
    print(f"  [OK] {os.path.basename(lh_path)}: {len(lh.vertices)} vertices, {len(lh.faces)} faces")

    rh = trimesh.load(rh_path)
    print(f"  [OK] {os.path.basename(rh_path)}: {len(rh.vertices)} vertices, {len(rh.faces)} faces")

    print("\n--- Merging ---")
    merged = trimesh.util.concatenate([lh, rh])
    print(f"  Vertices: {len(merged.vertices)}")
    print(f"  Faces:    {len(merged.faces)} (all triangles)")

    print(f"\n--- Writing OBJ ---")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    merged.export(output_path, file_type="obj")

    print(f"  [OK] Written to: {output_path}")
    print(f"  File size: {os.path.getsize(output_path) / (1024*1024):.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <left.stl> <right.stl> <output.obj>")
        print()
        print("Examples:")
        print(f"  {sys.argv[0]} output/sub-116/surf/lh_pial.stl output/sub-116/surf/rh_pial.stl output/sub-116/surf/pial.obj")
        print(f"  {sys.argv[0]} output/sub-116/surf/lh_white.stl output/sub-116/surf/rh_white.stl output/sub-116/surf/white.obj")
        sys.exit(1)

    merge_stl_to_obj(sys.argv[1], sys.argv[2], sys.argv[3])
