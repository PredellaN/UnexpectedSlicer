from __future__ import annotations

import re
import bpy
from mathutils import Vector
from numpy.typing import NDArray

_NUM = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_RE_FLOAT = re.compile(_NUM)


def _parse_float(s: str) -> float | None:
    m = _RE_FLOAT.search(s)
    return float(m.group(0)) if m else None


def _strip_comment(line: str) -> str:
    line = line.split(";", 1)[0]
    while True:
        a = line.find("(")
        if a == -1:
            break
        b = line.find(")", a + 1)
        if b == -1:
            line = line[:a]
            break
        line = line[:a] + line[b + 1 :]
    return line.strip()


def _get_word_value(code: str, letter: str) -> float | None:
    # Find e.g. X12.3, Y-4, Z0.2, E..., F...
    idx = code.find(letter)
    if idx == -1:
        return None
    return _parse_float(code[idx + 1 :])

def _get_evaluated_mesh(obj: bpy.types.Object) -> bpy.types.Mesh:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh_eval = obj_eval.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    return mesh_eval