import os

def merge_stl_files(output_file, input_files):
    """
    Merges multiple STL files into a single STL file using UTF-8 encoding.
    """
    print("--- Starting Merge ---")
    
    # Open output with utf-8 and ignore errors to be safe on Windows
    with open(output_file, 'w', encoding="utf-8", errors="ignore") as outfile:
        outfile.write("solid whole_brain_pial\n")
        
        for file_path in input_files:
            if not os.path.exists(file_path):
                print(f"[ERROR] File not found: {file_path}")
                continue
            
            print(f"[READING] {os.path.basename(file_path)}")
            # Use encoding="utf-8" and errors="ignore" to bypass the UnicodeDecodeError
            with open(file_path, 'r', encoding="utf-8", errors="ignore") as infile:
                lines = infile.readlines()
                if len(lines) > 2:
                    # Strip the original header and footer
                    facet_data = lines[1:-1]
                    outfile.writelines(facet_data)
        
        outfile.write("endsolid whole_brain_pial\n")
    
    print(f"\n[SUCCESS] Created: {output_file}")

if __name__ == "__main__":
    pial_parts = [
        "C:\\Users\\adama\\dev\\NVIZ_Segmentation\\BrainSegmentation\\output\\sub-116\\surf\\lh_pial.stl",
        "C:\\Users\\adama\\dev\\NVIZ_Segmentation\\BrainSegmentation\\output\\sub-116\\surf\\rh_pial.stl"
    ]
    
    output_path = "C:\\Users\\adama\\dev\\NVIZ_Segmentation\\BrainSegmentation\\output\\sub-116\\surf\\whole_brain_pial.stl"
    
    merge_stl_files(output_path, pial_parts)