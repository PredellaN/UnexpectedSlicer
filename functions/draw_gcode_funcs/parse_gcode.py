from numpy import ndarray

import mmap
import numpy as np
from pathlib import Path
import re

labels = [
    'Perimeter', #1
    'External perimeter', #2
    'Overhang perimeter', #3
    'Internal infill', #4
    'Solid infill', #5
    'Top solid infill', #6
    'Bridge infill', #7
    'Skirt/Brim', #8
    'Custom', #9
    'Support material', #10
    'Support material interface', #11
    'Gap fill', #12
]

class SegmentData():
    def __init__(self, n):
        self.length: int = n
        self.seg_count: int = 0
        self.pos = np.zeros((n, 3), dtype=np.float32)
        self.width = np.zeros((n), dtype=np.float16)
        self.height = np.zeros((n), dtype=np.float16)
        self.fan_speed = np.zeros((n), dtype=np.float16)
        self.temperature = np.zeros((n), dtype=np.float16)
        self.extrusion = np.zeros((n), dtype=np.float16)
        self.feature_type = np.empty((n), dtype=np.uint8)
        self.pt_id_of_seg = np.full((n, 2), -1, dtype=np.int64)

import mmap
def count_lines_mmap(path: str | Path, filter=b'\n'):
    with open(path, 'rb') as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        n = mm[:].count(filter)
        mm.close()
    return n

# def forward_fill_floats(arr, col, cmd=[b'G1']):
#     arr = np.array([m[col] if m[1] in cmd else b'' for m in arr], dtype='S')

#     valid = (arr != b'')

#     data = np.empty(arr.shape, dtype=np.float32)
#     data[valid] = arr[valid].astype(np.float32)

#     if not valid[0]:
#         first = np.argmax(valid)
#         data[:first] = data[first]

#     idx = np.where(valid, np.arange(arr.size), 0)
#     np.maximum.accumulate(idx, out=idx)

#     return data[idx]

# def zero_fill_floats(arr, col):
#     str_vals = np.array([m[col] for m in arr], dtype='S')
#     valid = (str_vals != b'')
    
#     data = np.zeros(str_vals.shape, dtype=np.float32)
#     data[valid] = str_vals[valid].astype(np.float32)
    
#     return data

def parse_gcode(path) -> SegmentData:
    with open(path, "r+b") as f:
        mm: mmap.mmap = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

    mesh = SegmentData(count_lines_mmap(path, b'\nG1'))
    labels_idx = labels.index

    x: float = .0
    y: float = .0
    z: float = .0
    width: float = .0
    height: float = .0
    temp: float = .0
    fan: float = .0
    feature_type: int = 0

    width_i: int = 0
    height_i: int = 0
    temp_i: int = 0
    fan_i: int = 0
    feature_type_i: int = 0

    i: int = 0

    pattern = re.compile(rb'((\w+) ?(X\S+)? ?(Y\S+)? ?(Z\S+)? ?(E\S+)? ?(F\S+)? ?(P\S+)? ?(S\S+)?|;.+)', flags=re.ASCII)
    # groups: 1:cmd/comment 2:x 3:y 4:z 5:e 6:f 7:p 8:s

    lst = pattern.findall(mm)

    # extr_data: list[tuple[int, str, str, str, str, str, str, str, str]] = [(i, m[1], m[2][1:], m[3][1:], m[4][1:], m[5][1:], m[6][1:], m[7][1:], m[8][1:]) for i, m in enumerate(lst)]

    # mask = np.array([e[1] == b'G1' for e in extr_data])

    # mesh.pos[:, 0] = forward_fill_floats(extr_data, 2)[mask]
    # mesh.pos[:, 1] = forward_fill_floats(extr_data, 3)[mask]
    # mesh.pos[:, 2] = forward_fill_floats(extr_data, 4)[mask]

    # mesh.extrusion[:] = zero_fill_floats(extr_data, 5)[mask]

    # mesh.fan_speed[:] = forward_fill_floats(extr_data, 8, [b'M106'])[mask]
    # mesh.temperature[:] = forward_fill_floats(extr_data, 8, [b'M104', b'M109'])[mask]

    for m in lst:
        if m[1] == b'G1':
            if v:=m[2]: x = float(v[1:])
            if v:=m[3]: y = float(v[1:])
            if v:=m[4]: z = float(v[1:])
            mesh.pos[i] = x, y, z

            if v:=m[5]: mesh.extrusion[i] = float(v[1:])

            mesh.pt_id_of_seg[i] = i - 1, i
            
            i += 1
            continue

        if m[0][:6] == b';TYPE:':
            mesh.feature_type[feature_type_i:i] = feature_type

            feature_type_i = i
            txt = m[0][6:].decode()
            feature_type = labels_idx(txt)
            continue
            
        if m[0][:7] == b';WIDTH:':
            mesh.width[width_i:i] = width
            
            width_i = i
            width = float(m[0][7:])
            continue

        if m[0][:8] == b';HEIGHT:':
            mesh.height[height_i:i] = height

            height_i = i
            height = float(m[0][8:])
            continue

        if m[1][:4] == b'M106':
            mesh.fan_speed[fan_i:i] = fan

            fan_i = i
            fan = float(m[8][1:])
            continue

        if m[1][:4] in [b'M104', b'M109']:
            mesh.temperature[temp_i:i] = temp

            temp_i = i
            temp = float(m[8][1:])
            continue

    mesh.pt_id_of_seg[0] = 0, 0
    mesh.feature_type[feature_type_i:i] = feature_type
    mesh.width[width_i:i] = width
    mesh.height[height_i:i] = height
    mesh.fan_speed[fan_i:i] = fan
    mesh.temperature[temp_i:i] = temp
    mesh.seg_count = i

    return mesh

if __name__ == '__main__':
    parse_gcode('functions/draw_gcode_funcs/test.gcode')