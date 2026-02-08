import open3d as o3d
import os

def decimate_and_smooth(input_path, output_path, target_reduction=0.90):
    """
    Decimates the mesh to reduce triangle count while preserving shape.
    """
    if not os.path.exists(input_path):
        print(f"[ERROR] Path not found: {input_path}")
        return

    # Load mesh
    mesh = o3d.io.read_triangle_mesh(input_path)
    
    # Calculate how many triangles to KEEP
    original_tri_count = len(mesh.triangles)
    # If you want to reduce BY 90%, you keep 10%
    keep_ratio = 1.0 - target_reduction
    target_count = int(original_tri_count * keep_ratio)

    print(f"--- Decimating Mesh ---")
    print(f"Original Count: {original_tri_count} triangles")
    print(f"Targeting: {target_count} triangles (Keeping {keep_ratio*100}%)")

    # The actual Decimation step
    # This collapses edges to simplify the mesh without 'cutting' it
    mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_count)

    # Clean up the mesh (remove any orphaned vertices created by decimation)
    #mesh.remove_unreferenced_vertices()

    # Smoothing the 'jaggies'
    print("[INFO] Smoothing surface...")
    mesh = mesh.filter_smooth_laplacian(number_of_iterations=2)
    
    # Recalculate normals for that 'smooth' look in 3D viewers
    mesh.compute_vertex_normals()

    # Save
    o3d.io.write_triangle_mesh(output_path, mesh)
    print(f"[SUCCESS] Saved simplified mesh to: {output_path}")
if __name__ == "__main__":
    # Update these paths with your double backslashes
    input_obj = "C:\\Users\\adama\\dev\\NIRSViz\\Assets\\MRI\\sub-116_anat.obj"
    output_obj = "C:\\Users\\adama\\dev\\NIRSViz\\Assets\\MRI\\sub-116_anat_lowres.obj"
    
    # reduction_percentage=0.90 means it will keep only 10% of the original triangles
    decimate_and_smooth(input_obj, output_obj, target_reduction=0.90)