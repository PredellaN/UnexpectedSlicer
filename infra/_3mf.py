from __future__ import annotations

from pathlib import Path

import numpy as np
import os, shutil, tempfile
import xml.etree.ElementTree as ET
from datetime import date

from ..infra.blender_mesh_capture import SlicingGroup, SlicingCollection

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

        sorted_data = sorted(
            zip(collection.mesh_start_ids, collection.mesh_end_ids, collection.objects),
            key=lambda x: (
                0 if x[2].name == collection.name else 1,
                object_type_order.get(x[2].object_type, 5),
                x[2].name,
            ),
        )

        object_elem = ET.SubElement(xml_content, "object", id=str(j+1), instances_count="1")
        ET.SubElement(object_elem, "metadata", type="object", key="name", value=collection.name)
        
        for i, (start, end, metadata) in enumerate(sorted_data):

            if metadata.object_type == "ModelPart":
                ET.SubElement(object_elem, "metadata", type="object", key="extruder", value=str(metadata.extruder))
                for mod in metadata.modifiers:
                    if not mod: continue
                    ET.SubElement(object_elem, "metadata", type="object", key=mod['param_id'], value=mod['param_value'])

            volume_elem = ET.SubElement(object_elem, "volume", firstid=str(start), lastid=str(end))
            
            ET.SubElement(volume_elem, "metadata", type="volume", key="name", value=metadata.name)
            if metadata.object_type == "ParameterModifier":
                ET.SubElement(volume_elem, "metadata", type="volume", key="modifier", value="1")
                for mod in metadata.modifiers:
                    if not mod: continue
                    ET.SubElement(volume_elem, "metadata", type="volume", key=mod['param_id'], value=mod['param_value'])

            ET.SubElement(volume_elem, "metadata", type="volume", key="volume_type", value=metadata.object_type)
            ET.SubElement(volume_elem, "metadata", type="volume", key="extruder", value=str(metadata.extruder))
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
        file.writelines([f'  <metadata name="{name}">{value}</metadata>\n' for name, value in metadata_entries])

        # Write resources element and object using list comprehension
        file.write(f'  <resources>\n')

        verts_template = np.vectorize(lambda x, y, z: '<vertex x="%.6f" y="%.6f" z="%.6f" />\n' % (x, y, z))
        idx_template = np.vectorize(lambda a, b, c: '<triangle v1="%d" v2="%d" v3="%d" />\n' % (a, b, c))

        valid_collections: dict[str, SlicingCollection] = {k: c for k, c in group.collections.items() if c.meshes}

        for i, (k, collection) in enumerate[tuple[str, SlicingCollection]](valid_collections.items()):
            if not collection.meshes: continue

            uv, t_idx = collection.unique_verts

            if uv.size and t_idx.size: 
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
        for i, k in enumerate(valid_collections):
            if not valid_collections[k].unique_verts[0].size: continue
            file.writelines([f'    <item objectid="{str(i+1)}" transform="1 0 0 0 1 0 0 0 1 0 0 0" printable="1" />\n' ])
        file.write(f'  </build>\n')

        # Close the model tag
        file.write(f'</model>\n')


def to_3mf(folder_path, output_base_path):
    zip_file_path = shutil.make_archive(os.path.splitext(output_base_path)[0], 'zip', folder_path)
    new_file_path = os.path.splitext(zip_file_path)[0] + '.3mf'
    os.replace(zip_file_path, new_file_path)

def write_z_gcodes(z_gcodes, filename: str):
    root = ET.Element("custom_gcodes_per_print_z", bed_idx="0")

    for c in z_gcodes:
        ET.SubElement(root, "code", {
            "print_z": str(c.z),
            "type": str(c.type),
            "extruder": str(c.extruder),
            "color": c.color,
            "extra": c.extra,
            "gcode": c.gcode,
        })

    ET.SubElement(root, "mode", {"value": "SingleExtruder"})

    ET.ElementTree(root).write(filename, encoding="utf-8", xml_declaration=True)

def rgb_to_html_hex(rgb: tuple[float, float, float]) -> str:
    r: int = int(round(rgb[0] * 255))
    g: int = int(round(rgb[1] * 255))
    b: int = int(round(rgb[2] * 255))
    return "#{:02X}{:02X}{:02X}".format(r, g, b)

def generate_full_spectrum_data(pg) -> dict:
    physical_colors = [
        pg.filament_color,
        pg.filament_2_color,
        pg.filament_3_color,
        pg.filament_4_color,
        pg.filament_5_color,
    ]
    
    physical_extruders = [
        {
            "color": rgb_to_html_hex(color),
            "id": i + 1
        }
        for i, color in enumerate(physical_colors)
    ]
    
    virtual_extruders = []
    if hasattr(pg, "virtual_extruders"):
        for idx, item in enumerate(pg.virtual_extruders):
            raw_ratios = list(item.ratios)
            active = [(i + 1, r) for i, r in enumerate(raw_ratios) if r > 0.0]
            if len(active) > 3:
                active = sorted(active, key=lambda x: x[1], reverse=True)[:3]
                active.sort(key=lambda x: x[0])
            
            total_sum = sum(r for _, r in active)
            if total_sum > 1.0:
                normalized = [(ext, r / total_sum) for ext, r in active]
            else:
                normalized = active
                
            components = [
                {"extruder": ext, "ratio": round(r, 5)}
                for ext, r in normalized
            ]
            
            if total_sum > 0:
                calc_norm = total_sum if total_sum > 1.0 else total_sum
                r_mix = sum(r * physical_colors[ext - 1][0] for ext, r in normalized) / calc_norm
                g_mix = sum(r * physical_colors[ext - 1][1] for ext, r in normalized) / calc_norm
                b_mix = sum(r * physical_colors[ext - 1][2] for ext, r in normalized) / calc_norm
                virt_color = rgb_to_html_hex((r_mix, g_mix, b_mix)).lower()
            else:
                virt_color = "#000000"
                
            virtual_extruders.append({
                "color": virt_color,
                "components": components,
                "id": 6 + idx,
                "kind": "fullspectrum"
            })
            
    return {
        "physical_extruders": physical_extruders,
        "version": 1,
        "virtual_extruders": virtual_extruders
    }

def write_full_spectrum_json(pg, filepath: str):
    import json
    data = generate_full_spectrum_data(pg)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def prepare_3mf(filepath: Path, geoms: SlicingGroup, conf, z_gcodes, pg=None) -> None:

    source_folder = os.path.join(script_dir, 'prusaslicer_3mf')
    temp_dir = tempfile.mkdtemp()
    shutil.copytree(source_folder, temp_dir, dirs_exist_ok=True)
    
    os.makedirs(os.path.join(temp_dir, '3D'), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'Metadata'), exist_ok=True)

    write_model_xml(geoms, os.path.join(temp_dir, '3D', '3dmodel.model'))

    write_metadata_xml(geoms, os.path.join(temp_dir, 'Metadata', 'Slic3r_PE_model.config'))
    write_wipe_tower_xml(geoms, os.path.join(temp_dir, 'Metadata', 'Prusa_Slicer_wipe_tower_information.xml'))
    write_z_gcodes(z_gcodes, os.path.join(temp_dir, 'Metadata', 'Prusa_Slicer_custom_gcode_per_print_z.xml'))
    conf.write_ini_3mf(os.path.join(temp_dir, 'Metadata', 'Slic3r_PE.config'))

    if pg is not None and hasattr(pg, 'virtual_extruders') and len(pg.virtual_extruders) > 0:
        write_full_spectrum_json(pg, os.path.join(temp_dir, 'Metadata', 'Prusa_Slicer_full_spectrum.json'))

    to_3mf(temp_dir, filepath)

    return None