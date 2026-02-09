"""
Decimate and smooth a 3D mesh to reduce triangle count while preserving shape.
Useful for creating lower-resolution versions of brain meshes for visualization.

Requires: pip install open3d

Usage: python process_mesh.py <input_mesh> <output_mesh> [reduction]
  reduction: fraction of triangles to remove (default: 0.90 = keep 10%)
"""
import os
import sys

import open3d as o3d


def decimate_and_smooth(input_path, output_path, target_reduction=0.90):
    """
    Decimates the mesh to reduce triangle count while preserving shape.
    """
    if not os.path.exists(input_path):
        print(f"[ERROR] Path not found: {input_path}")
        return

    mesh = o3d.io.read_triangle_mesh(input_path)

    original_tri_count = len(mesh.triangles)
    keep_ratio = 1.0 - target_reduction
    target_count = int(original_tri_count * keep_ratio)

    print("--- Decimating Mesh ---")
    print(f"Original Count: {original_tri_count} triangles")
    print(f"Targeting: {target_count} triangles (Keeping {keep_ratio*100}%)")

    mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_count)

    print("[INFO] Smoothing surface...")
    mesh = mesh.filter_smooth_laplacian(number_of_iterations=2)

    mesh.compute_vertex_normals()

    o3d.io.write_triangle_mesh(output_path, mesh)
    print(f"[SUCCESS] Saved simplified mesh to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input_mesh> <output_mesh> [reduction]")
        print("  reduction: fraction to remove, 0.0-0.99 (default: 0.90 = keep 10%)")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    reduction = float(sys.argv[3]) if len(sys.argv) > 3 else 0.90

    decimate_and_smooth(input_file, output_file, target_reduction=reduction)
