"""
Merge two OBJ mesh files into a single OBJ.
Used to combine lh.pial.obj + rh.pial.obj into cortex.obj for NIRSViz.

Usage: python merge_obj.py lh.pial.obj rh.pial.obj cortex.obj
"""
import sys

def merge_obj(path_a, path_b, path_out):
    vertices = []
    faces = []
    vertex_offset = 0

    for path in [path_a, path_b]:
        local_verts = 0
        with open(path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                if parts[0] == 'v' and len(parts) >= 4:
                    vertices.append(line.strip())
                    local_verts += 1
                elif parts[0] == 'f':
                    # Offset face indices by current vertex count
                    new_indices = []
                    for idx_str in parts[1:]:
                        # Handle v, v/vt, v/vt/vn, v//vn formats
                        components = idx_str.split('/')
                        components[0] = str(int(components[0]) + vertex_offset)
                        new_indices.append('/'.join(components))
                    faces.append('f ' + ' '.join(new_indices))
        vertex_offset += local_verts

    with open(path_out, 'w') as f:
        f.write(f'# Merged from {path_a} and {path_b}\n')
        f.write(f'# Total vertices: {len(vertices)}, faces: {len(faces)}\n')
        for v in vertices:
            f.write(v + '\n')
        for face in faces:
            f.write(face + '\n')

    print(f'Merged: {len(vertices)} vertices, {len(faces)} faces -> {path_out}')

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(f'Usage: {sys.argv[0]} <input1.obj> <input2.obj> <output.obj>')
        sys.exit(1)
    merge_obj(sys.argv[1], sys.argv[2], sys.argv[3])
