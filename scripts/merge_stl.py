"""
Merge two STL mesh files into a single STL.
Used to combine lh_pial.stl + rh_pial.stl into whole_brain_pial.stl.

Usage: python merge_stl.py <left.stl> <right.stl> <output.stl>
"""
import os
import sys


def merge_stl_files(output_file, input_files):
    """
    Merges multiple STL files into a single STL file using UTF-8 encoding.
    """
    print("--- Starting Merge ---")

    with open(output_file, "w", encoding="utf-8", errors="ignore") as outfile:
        outfile.write("solid whole_brain_pial\n")

        for file_path in input_files:
            if not os.path.exists(file_path):
                print(f"[ERROR] File not found: {file_path}")
                continue

            print(f"[READING] {os.path.basename(file_path)}")
            with open(file_path, "r", encoding="utf-8", errors="ignore") as infile:
                lines = infile.readlines()
                if len(lines) > 2:
                    facet_data = lines[1:-1]
                    outfile.writelines(facet_data)

        outfile.write("endsolid whole_brain_pial\n")

    print(f"\n[SUCCESS] Created: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <left.stl> <right.stl> <output.stl>")
        sys.exit(1)

    merge_stl_files(sys.argv[3], [sys.argv[1], sys.argv[2]])
