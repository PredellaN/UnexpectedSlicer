from numpy._typing._shape import _Shape
from numpy import dtype, float16, ndarray
from typing import Any

import numpy as np
import os, shutil, tempfile, hashlib
import xml.etree.ElementTree as ET
from datetime import date

script_dir = os.path.dirname(os.path.abspath(__file__))


def indent(elem, level=0):
    i = "\n" + level * " "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + " "
        for child in elem:
            indent(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def prepare_triangles_grouped(meshes, decimals=4) -> dict[str, ndarray]:
    lengths: ndarray = np.array([len(m) for m in meshes])
    starts: ndarray = np.insert(np.cumsum(lengths)[:-1], 0, 0)
    ends: ndarray[_Shape, dtype[Any]] = starts + lengths - 1

    all_tris: ndarray[_Shape, dtype[Any]] = np.vstack(meshes)[:, :3, :]
    all_verts: ndarray[tuple[int, int], dtype[Any]] = all_tris.reshape(-1, 3)

    unique_verts_list: list[ndarray] = []
    tris_idx_list: list[ndarray] = []
    offset = 0
    for mesh in meshes:
        tris: ndarray = mesh[:, :3, :]
        verts: ndarray = tris.reshape(-1, 3)
        if decimals is not None:
            verts = np.round(verts, decimals=decimals)
        uniq, inv = np.unique(verts, axis=0, return_inverse=True)
        unique_verts_list.append(uniq)
        tris_idx_list.append(inv.reshape(-1, 3) + offset)
        offset += uniq.shape[0]

    unique_verts: ndarray = np.vstack(unique_verts_list)
    tris_idx: ndarray = np.vstack(tris_idx_list)

    return {
        'all_verts': all_verts,
        'unique_verts': unique_verts,
        'tris_idx': tris_idx,
        'mesh_lengths_ids': lengths,
        'mesh_start_ids': starts,
        'mesh_end_ids': ends,
    }

def write_metadata_xml(tris_data, filepath, names):
    xml_content = ET.Element("config")
    
    object_elem = ET.SubElement(xml_content, "object", id='1', instances_count="1")
    
    ET.SubElement(object_elem, "metadata", 
                type="object", key="name", value='Merged')
    
    for start, end, name in zip(tris_data['mesh_start_ids'], tris_data['mesh_end_ids'], names):
        volume_elem = ET.SubElement(object_elem, "volume", 
                                    firstid=str(start), lastid=str(end))
        
        ET.SubElement(volume_elem, "metadata",
                    type="volume", key="name", value=name)
        ET.SubElement(volume_elem, "metadata",
                    type="volume", key="volume_type", value="ModelPart")
        ET.SubElement(volume_elem, "metadata",
                    type="volume", key="matrix", 
                    value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1")
        
        ET.SubElement(volume_elem, "mesh",
                    edges_fixed="0", degenerate_facets="0",
                    facets_removed="0", facets_reversed="0",
                    backwards_edges="0")

    indent(xml_content)
    xml_tree = ET.ElementTree(xml_content)
    xml_tree.write(filepath, encoding="UTF-8", xml_declaration=True)


def write_model_xml(triangle_data: dict, filename: str):
    ns_core = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    ET.register_namespace("", ns_core)

    model_attrib: dict[str, str] = {"unit": "millimeter", "xml:lang": "en-US", "xmlns:slic3rpe": "http://schemas.slic3r.org/3mf/2017/06"}
    xml_content = ET.Element(f"{{{ns_core}}}model", model_attrib)

    now = date.today().isoformat()
    metadata_entries: list[tuple[str, str]] = [
        ("slic3rpe:Version3mf", "1"),
        ("Title", "box"),
        ("Designer", ""),
        ("Description", "box"),
        ("Copyright", ""),
        ("LicenseTerms", ""),
        ("Rating", ""),
        ("CreationDate", now),
        ("ModificationDate", now),
        ("Application", "PrusaSlicer-2.9.0")
    ]
    for name, value in metadata_entries:
        meta = ET.SubElement(xml_content, "metadata", name=name)
        meta.text = value

    resources_elem = ET.SubElement(xml_content, "resources")

    object_elem = ET.SubElement(resources_elem, "object", id='1', type="model")
    mesh_elem = ET.SubElement(object_elem, "mesh")

    vertices_elem = ET.SubElement(mesh_elem, "vertices")
    for vertex in triangle_data['unique_verts']:
        x, y, z = vertex
        ET.SubElement(vertices_elem, "vertex",
                    x=str(x), y=str(y), z=str(z))

    triangles_elem = ET.SubElement(mesh_elem, "triangles")
    for tri in triangle_data['tris_idx']:
        v1, v2, v3 = tri
        ET.SubElement(triangles_elem, "triangle",
                    v1=str(v1), v2=str(v2), v3=str(v3))

    build_elem = ET.SubElement(xml_content, "build")

    ET.SubElement(build_elem, "item", objectid='1',
        transform="1 0 0 0 1 0 0 0 1 0 0 0",
        printable="1"
    )

    indent(xml_content)
    xml_tree = ET.ElementTree(xml_content)
    xml_tree.write(filename, encoding="UTF-8", xml_declaration=True)


def to_3mf(folder_path, output_base_path):
    zip_file_path = shutil.make_archive(os.path.splitext(output_base_path)[0], 'zip', folder_path)
    new_file_path = os.path.splitext(zip_file_path)[0] + '.3mf'
    os.rename(zip_file_path, new_file_path)

def folder_checksum(directory):
    h = hashlib.sha256()
    for root, _, files in os.walk(directory):
        for fname in sorted(files):
            with open(os.path.join(root, fname), 'rb') as f:
                while (chunk := f.read(8192)):
                    h.update(chunk)
    return h.hexdigest()

def prepare_3mf(filepath, geoms, conf, names):

    source_folder = os.path.join(script_dir, 'prusaslicer_3mf')
    temp_dir = tempfile.mkdtemp()
    shutil.copytree(source_folder, temp_dir, dirs_exist_ok=True)

    triangle_data = prepare_triangles_grouped(geoms)
    
    write_model_xml(triangle_data, os.path.join(temp_dir, '3D', '3dmodel.model'))
    write_metadata_xml(triangle_data, os.path.join(temp_dir, 'Metadata', 'Slic3r_PE_model.config'), names)

    conf.write_ini_3mf(os.path.join(temp_dir, 'Metadata', 'Slic3r_PE.config'))

    checksum = folder_checksum(temp_dir)

    to_3mf(temp_dir, filepath)

    return checksum