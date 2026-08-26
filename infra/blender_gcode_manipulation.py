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

    gcode_path = meta.gcode_path
    transform = Vector(meta.transform) if not isinstance(meta.transform, Vector) else meta.transform
    scale = float(meta.scene_scale)*0.001

    old_obj = bpy.data.objects.get(object_name)
    if old_obj:
        bpy.data.objects.remove(old_obj, do_unlink=True)
    old_mesh = bpy.data.meshes.get(mesh_name)
    if old_mesh:
        bpy.data.meshes.remove(old_mesh, do_unlink=True)

    # State
    pos = Vector((0.0, 0.0, 0.0))

    # Collected geometry
    verts: list[Vector] = []
    edges: list[tuple[int, int]] = []
    edge_lines: list[int] = []
    extrusion: list[float] = []

    def bake_point(p: Vector) -> Vector:
        return (p + transform) * scale

    in_external_perimeter: bool = False

    lines: list[str | list[str]] = []
    with open(gcode_path, "r", encoding="utf-8", errors="replace") as f:
        lines += f
        
    for line_no_1based, raw in enumerate(lines, start=1):
        
        assert isinstance(raw, str)

        # Detect TYPE changes
        if raw[:6] == ";TYPE:":
            in_external_perimeter = (raw == ";TYPE:External perimeter\n")
            continue

        line = _strip_comment(raw)
        if not line: continue

        parts = line.split()
        if not parts: continue

        cmd = parts[0].upper()
        if cmd not in ["G1", "G0"]: continue

        x = _get_word_value(line.upper(), "X")
        y = _get_word_value(line.upper(), "Y")
        z = _get_word_value(line.upper(), "Z")
        e = _get_word_value(line.upper(), "E")
            
        new_pos = Vector((
            pos.x if x is None else float(x),
            pos.y if y is None else float(y),
            pos.z if z is None else float(z),
        ))

        a = bake_point(pos)
        b = bake_point(new_pos)
        pos = new_pos

        if e is None: continue
        if e <= 0: continue
        if cmd in ["G0"]: continue

        # Additional cleanup
        if not in_external_perimeter: continue

        ia = len(verts)
        ib = ia + 1
        verts.append(a)
        verts.append(b)
        edges.append((ia, ib))
        edge_lines.append(line_no_1based)
        extrusion.append(e)

    # Build mesh
    mesh = bpy.data.meshes.new(mesh_name)
    mesh.from_pydata([v.to_tuple() for v in verts], edges, [])
    mesh.update()

    edge_attr_name: str = "gcode_line"
    if edge_attr_name in mesh.attributes:
        mesh.attributes.remove(mesh.attributes[edge_attr_name])

    attr = mesh.attributes.new(name=edge_attr_name, type="INT", domain="EDGE")
    for i, ln in enumerate(edge_lines):
        attr.data[i].value = int(ln)-1  # pyright: ignore[reportAttributeAccessIssue]

    attr = mesh.attributes.new(name='extrusion', type="FLOAT", domain="EDGE")
    for i, ln in enumerate(edge_lines):
        attr.data[i].value = extrusion[i] # pyright: ignore[reportAttributeAccessIssue]

    obj = bpy.data.objects.new(object_name, mesh)
    assert bpy.context.collection
    bpy.context.collection.objects.link(obj)

    obj.display_type = "WIRE"

    # Path to the assets blend
    import os
    assets_blend = os.path.abspath("./assets/assets.blend")

    # Append the object that already has the modifier (e.g. "Dummy")
    from typing import Any, cast
    with cast(Any, bpy.data.libraries.load(assets_blend, link=False)) as (data_from, data_to):
        if "Dummy" not in data_from.objects:
            raise RuntimeError("Object 'Dummy' not found in assets.blend")
        data_to.objects = ["Dummy"]

    dummy = data_to.objects[0]
    bpy.context.collection.objects.link(dummy)

    # Find the modifier on Dummy
    src_mod = dummy.modifiers.get("US_displacer")
    if src_mod is None:
        raise RuntimeError("Modifier 'US_displacer' not found on Dummy")

    # Create the same modifier on tmp_gcode
    dst_mod = obj.modifiers.new(
        name=src_mod.name,
        type=src_mod.type
    )

    # Copy all writable properties
    for prop in src_mod.bl_rna.properties:
        if not prop.is_readonly and prop.identifier != "name":
            try:
                setattr(dst_mod, prop.identifier, getattr(src_mod, prop.identifier))
            except Exception:
                pass

    # Optional: remove the appended helper object
    bpy.data.objects.remove(dummy, do_unlink=True)
    obj.modifiers["US_displacer"]["Socket_2"] = bpy.data.objects.get(meta.objs[0])

    import numpy as np
    eval_mesh = _get_evaluated_mesh(bpy.data.objects["tmp_gcode"])
    eval_verts = eval_mesh.vertices
    verts_new: NDArray = np.empty((len(eval_verts) * 3))
    eval_verts.foreach_get('co', verts_new)
    verts_new = verts_new.reshape((-1, 3))

    verts_new_gcode_idx: NDArray = np.empty((len(eval_verts))).astype(np.int32)
    eval_mesh.attributes["gcode_line"].data.foreach_get("value", verts_new_gcode_idx)

    verts_new_extrusion: NDArray = np.empty((len(eval_verts))).astype(np.float32)
    eval_mesh.attributes["extrusion"].data.foreach_get("value", verts_new_extrusion)

    for v, p, e in zip(verts_new, verts_new_gcode_idx, verts_new_extrusion):
        v_gcode = (v/scale)-transform
        if isinstance(lines[p], str): lines[p] = []
        lines[p] += [f'G1 X{v_gcode[0]:.6f} Y{v_gcode[1]:.6f} Z{v_gcode[2]:.6f} E{e:.6f}\n']

    expanded = [item for sub in lines for item in (sub if isinstance(sub, list) else [sub])]

    with open(gcode_path, "w", encoding="utf-8") as f:
        f.writelines(expanded)

    bpy.data.objects.remove(obj, do_unlink=True)
    tmp_mesh = bpy.data.meshes.get(mesh_name)
    assert tmp_mesh
    bpy.data.meshes.remove(tmp_mesh, do_unlink=True)

    return obj