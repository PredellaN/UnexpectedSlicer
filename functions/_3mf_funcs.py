from numpy import dtype, ndarray
from typing import Any

import numpy as np
import os, shutil, tempfile, hashlib
import xml.etree.ElementTree as ET
from datetime import date

from ..classes.slicing_classes import SlicingGroup

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
    ends: ndarray = starts + lengths - 1

    all_tris: ndarray = np.vstack(meshes)[:, :3, :]
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

def write_metadata_xml(group: SlicingGroup, filepath):
    # Custom sorting order for object types
    object_type_order = {
        'ModelPart': 0,
        'NegativeVolume': 1,
        'ParameterModifier': 2,
        'SupportBlocker': 3,
        'SupportEnforcer': 4
    }

    # Sort obj_metadatas and tris_data by metadata['object_type']


    xml_content = ET.Element("config")

    for j, (k, collection) in enumerate(group.collections.items()):

        sorted_data = sorted(zip(collection.mesh_start_ids, collection.mesh_end_ids, collection.objects), key=lambda x: object_type_order.get(x[2].object_type, 5))

        object_elem = ET.SubElement(xml_content, "object", id=str(j+1), instances_count="1")
        ET.SubElement(object_elem, "metadata", type="object", key="name", value=collection.name)
        
        for i, (start, end, metadata) in enumerate(sorted_data):
            volume_elem = ET.SubElement(object_elem, "volume", firstid=str(start), lastid=str(end))
            
            ET.SubElement(volume_elem, "metadata", type="volume", key="name", value=metadata.name)
            if metadata.object_type == "ParameterModifier":
                ET.SubElement(volume_elem, "metadata", type="volume", key="modifier", value="1")
                for mod in metadata.modifiers:
                    ET.SubElement(volume_elem, "metadata", type="volume", key=mod['param_id'], value=mod['param_value'])
            ET.SubElement(volume_elem, "metadata", type="volume", key="volume_type", value=metadata.object_type)
            ET.SubElement(volume_elem, "metadata", type="volume", key="extruder", value=metadata.extruder)
            ET.SubElement(volume_elem, "metadata", type="volume", key="source_object_id", value="0")
            ET.SubElement(volume_elem, "metadata", type="volume", key="source_volume_id", value=str(i))
            ET.SubElement(volume_elem, "metadata", type="volume", key="matrix", value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1")
            ET.SubElement(volume_elem, "mesh", edges_fixed="0", degenerate_facets="0", facets_removed="0", facets_reversed="0", backwards_edges="0")

    indent(xml_content)
    xml_tree = ET.ElementTree(xml_content)
    xml_tree.write(filepath, encoding="UTF-8", xml_declaration=True)


from datetime import date

def write_model_xml(group: SlicingGroup, filename: str):
    now = date.today().isoformat()
    
    # Open file for writing
    with open(filename, 'w', encoding="UTF-8") as file:
        # Write the XML declaration and opening model tag
        file.write(f'<?xml version="1.0" encoding="UTF-8"?>\n')
        file.write(f'<model xmlns="" unit="millimeter" xml:lang="en-US" xmlns:slic3rpe="">\n')
        
        # Write metadata entries using list comprehension
        metadata_entries = [
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
        file.writelines([f'  <metadata name="{name}">{value}</metadata>\n' for name, value in metadata_entries])

        # Write resources element and object using list comprehension
        file.write(f'  <resources>\n')

        for i, (k, collection) in enumerate(group.collections.items()):

            file.write(f'    <object id="{str(i+1)}" type="model">\n')
            file.write(f'      <mesh>\n')

            # Write vertices using list comprehension
            file.write(f'        <vertices>\n')
            file.writelines([f'          <vertex x="{x}" y="{y}" z="{z}" />\n' for x, y, z in collection.unique_verts])
            file.write(f'        </vertices>\n')

            # Write triangles using list comprehension
            file.write(f'        <triangles>\n')
            file.writelines([f'          <triangle v1="{v1}" v2="{v2}" v3="{v3}" />\n' for v1, v2, v3 in collection.tris_idx])
            file.write(f'        </triangles>\n')

            file.write(f'      </mesh>\n')
            file.write(f'    </object>\n')

        file.write(f'  </resources>\n')

        # Write build element
        file.write(f'  <build>\n')
        for i, k in enumerate(group.collections):
            file.write(f'    <item objectid="{str(i+1)}" transform="1 0 0 0 1 0 0 0 1 0 0 0" printable="1" />\n')
        file.write(f'  </build>\n')

        # Close the model tag
        file.write(f'</model>\n')


def to_3mf(folder_path, output_base_path):
    zip_file_path = shutil.make_archive(os.path.splitext(output_base_path)[0], 'zip', folder_path)
    new_file_path = os.path.splitext(zip_file_path)[0] + '.3mf'
    os.replace(zip_file_path, new_file_path)

def folder_checksum(directory):
    h = hashlib.sha256()
    for root, _, files in os.walk(directory):
        for fname in sorted(files):
            with open(os.path.join(root, fname), 'rb') as f:
                while (chunk := f.read(8192)):
                    h.update(chunk)
    return h.hexdigest()

def prepare_3mf(filepath: str, geoms: SlicingGroup, conf):

    source_folder = os.path.join(script_dir, 'prusaslicer_3mf')
    temp_dir = tempfile.mkdtemp()
    shutil.copytree(source_folder, temp_dir, dirs_exist_ok=True)
    
    os.makedirs(os.path.join(temp_dir, '3D'), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'Metadata'), exist_ok=True)

    write_model_xml(geoms, os.path.join(temp_dir, '3D', '3dmodel.model'))

    write_metadata_xml(geoms, os.path.join(temp_dir, 'Metadata', 'Slic3r_PE_model.config'))
    conf.write_ini_3mf(os.path.join(temp_dir, 'Metadata', 'Slic3r_PE.config'))

    checksum = folder_checksum(temp_dir)

    to_3mf(temp_dir, filepath)

    return checksum