from __future__ import annotations

from pathlib import Path

import numpy as np
import os, shutil, tempfile
import xml.etree.ElementTree as ET
from datetime import date

from ..infra.mesh_capture import SlicingGroup

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

def write_metadata_xml(group: SlicingGroup, filepath):
    # Custom sorting order for object types
    object_type_order = {
        'ModelPart': 0,
        'NegativeVolume': 1,
        'ParameterModifier': 2,
        'SupportBlocker': 3,
        'SupportEnforcer': 4
    }

    xml_content = ET.Element("config")

    valid_collections = {k: c for k, c in group.collections.items() if c.meshes}

    for j, (k, collection) in enumerate(valid_collections.items()):

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

def write_wipe_tower_xml(group: SlicingGroup, filename):
    with open(filename, 'w', encoding="UTF-8") as file:
        file.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
        file.write(f'<wipe_tower_information bed_idx="0" position_x="{group.wipe_tower_xy[0]}" position_y="{group.wipe_tower_xy[1]}" rotation_deg="{group.wipe_tower_rotation_deg}"/>\n')

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

        verts_template = np.vectorize(lambda x, y, z: '<vertex x="%.6f" y="%.6f" z="%.6f" />\n' % (x, y, z))
        idx_template = np.vectorize(lambda a, b, c: '<triangle v1="%d" v2="%d" v3="%d" />\n' % (a, b, c))

        valid_collections = {k: c for k, c in group.collections.items() if c.meshes}

        for i, (k, collection) in enumerate(valid_collections.items()):
            if not collection.meshes: continue

            uv, t_idx = collection.unique_verts

            file.write(f'    <object id="{str(i+1)}" type="model">\n')
            file.write(f'      <mesh>\n')

            file.write(f'        <vertices>\n')
            file.writelines(verts_template(uv[:,0], uv[:,1], uv[:,2]))
            file.write(f'        </vertices>\n')

            file.write(f'        <triangles>\n')
            file.writelines(idx_template(t_idx[:,0], t_idx[:,1], t_idx[:,2]))
            file.write(f'        </triangles>\n')

            file.write(f'      </mesh>\n')
            file.write(f'    </object>\n')

        file.write(f'  </resources>\n')

        # Write build element
        file.write(f'  <build>\n')
        file.writelines([f'    <item objectid="{str(i+1)}" transform="1 0 0 0 1 0 0 0 1 0 0 0" printable="1" />\n' for i, k in enumerate(valid_collections)])
        file.write(f'  </build>\n')

        # Close the model tag
        file.write(f'</model>\n')


def to_3mf(folder_path, output_base_path):
    zip_file_path = shutil.make_archive(os.path.splitext(output_base_path)[0], 'zip', folder_path)
    new_file_path = os.path.splitext(zip_file_path)[0] + '.3mf'
    os.replace(zip_file_path, new_file_path)

def prepare_3mf(filepath: Path, geoms: SlicingGroup, conf) -> None:

    source_folder = os.path.join(script_dir, 'prusaslicer_3mf')
    temp_dir = tempfile.mkdtemp()
    shutil.copytree(source_folder, temp_dir, dirs_exist_ok=True)
    
    os.makedirs(os.path.join(temp_dir, '3D'), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'Metadata'), exist_ok=True)

    write_model_xml(geoms, os.path.join(temp_dir, '3D', '3dmodel.model'))

    write_metadata_xml(geoms, os.path.join(temp_dir, 'Metadata', 'Slic3r_PE_model.config'))
    write_wipe_tower_xml(geoms, os.path.join(temp_dir, 'Metadata', 'Prusa_Slicer_wipe_tower_information.xml'))
    conf.write_ini_3mf(os.path.join(temp_dir, 'Metadata', 'Slic3r_PE.config'))

    to_3mf(temp_dir, filepath)

    return None