import bpy  # type: ignore
import json
import tempfile
import re
import hashlib
import numpy as np
import struct
import math

from collections import Counter

def names_array_from_objects(obj_names):
    summarized_names = [re.sub(r'\.\d{0,3}$', '', name) for name in obj_names]
    name_counter = Counter(summarized_names)
    final_names = [f"{count}x_{name}" if count > 1 else name for name, count in name_counter.items()]
    final_names.sort()
    return final_names

def generate_config(id, profiles):
    conf_current = profiles[id]['conf_dict']  # Copy to avoid modifying the original config
    if conf_current.get('inherits', False):
        curr_category = id.split(":")[0]
        inherited_ids = [curr_category + ":" + inherit_id.strip() for inherit_id in conf_current['inherits'].split(';')]  # Split on semicolon for multiple inheritance
        merged_conf = {}
        for inherit_id in inherited_ids:
            if inherit_id in profiles:
                inherited_conf = generate_config(inherit_id, profiles)  # Recursive call for each inherited config
                merged_conf.update(inherited_conf)  # Merge each inherited config
        merged_conf.update(conf_current)  # Update with current config values (overriding inherited)
        conf_current = merged_conf
    conf_current.pop('inherits', None)
    conf_current.pop('compatible_printers_condition', None)
    return conf_current

class ConfigLoader:
    def __init__(self):
        self.config_dict = {}
        self.overrides_dict = {}
        self.original_file_path = None
        
        self.temp_dir = tempfile.gettempdir()

    @property
    def config_with_overrides(self):
        if self.config_dict is None:
            return None

        config = self.config_dict.copy()
        
        if self.overrides_dict:
            config.update(self.overrides_dict)
        return config
    
    def load_config(self, key, profiles, append = False):
        if not key:
            return False

        if not append:
            self.config_dict = {}
        config = generate_config(key, profiles)
        self.config_dict.update(config)

        return True

    def write_ini(self, config_local_path, use_overrides=True):
        config = self.config_with_overrides if use_overrides else self.config_dict
        with open(config_local_path, 'w') as file:
            for key in sorted(config.keys()):
                file.write(f"{key} = {config[key]}\n")
        return config_local_path
    
    def write_ini_3mf(self, config_local_path, use_overrides=True):
        config = self.config_with_overrides if use_overrides else self.config_dict
        with open(config_local_path, 'w') as file:
            for key in sorted(config.keys()):
                file.write(f"; {key} = {config[key]}\n")
        return config_local_path

    def load_ini(self, config_local_path, append = False):
        if not append:
            self.config_dict = {}
        with open(config_local_path, 'r') as file:
            lines = file.readlines()

        for line in lines:
            line = line.strip()
            if line.startswith('#') or not line:
                continue

            key, value = line.split('=', 1)
            self.config_dict[key.strip()] = value.strip()

    def _write_text_block(self, text_block_id):
        if self.config_dict:
            json_content = json.dumps(self.config_dict, indent=4)
            
            if text_block_id in bpy.data.texts:
                text_block = bpy.data.texts[text_block_id]
                text_block.clear()
            else:
                text_block = bpy.data.texts.new(name=text_block_id)

            text_block.from_string(json_content)
            self.text_block_id = text_block_id

    def _read_text_block(self, text_block_id):
        text_block_id = self.text_block_id
        
        if text_block_id:
            if text_block_id in bpy.data.texts:
                text_block = bpy.data.texts[text_block_id]
                json_content = text_block.as_string()
                self.config_dict = json.loads(json_content)

    def load_list_to_overrides(self, list):
        for item in list:
            self.overrides_dict[item.param_id] = item.param_value
        self.overrides_dict.pop("", None)
    
    def add_pauses_and_changes(self, list):
        colors = [
            "#79C543", "#E01A4F", "#FFB000", "#8BC34A", "#808080",
            "#ED1C24", "#A349A4", "#B5E61D", "#26A69A", "#BE1E2D",
            "#39B54A", "#CCCCCC", "#5A4CA2", "#D90F5A", "#A4E100",
            "#B97A57", "#3F48CC", "#F9E300", "#FFFFFF", "#00A2E8"
        ]
        combined_layer_gcode = self.config_dict['layer_gcode']
        pause_gcode = "\\n;PAUSE_PRINT\\n" + (self.config_dict.get('pause_print_gcode') or 'M0')
    
        for item in list:
            try:
                if item.param_value_type == "layer":
                    layer_num = int(item.param_value) - 1
                else:
                    layer_num = int(math.ceil(float(item.param_value) / float(self.config_dict['layer_height'])) - 1)
            except:
                continue

            if item.param_type == 'pause':
                item_gcode = pause_gcode
            elif item.param_type == 'color_change':
                color_change_gcode = f"\\n;COLOR_CHANGE,T0,{colors[0]}\\n" + (self.config_dict.get('color_change_gcode') or 'M600')
                item_gcode = color_change_gcode
                colors.append(colors.pop(0))
            elif item.param_type == 'custom_gcode' and item.param_cmd:
                custom_gcode = f"\\n;CUSTOM GCODE\\n{item.param_cmd}"
                item_gcode = custom_gcode
            else:
                continue
        
            combined_layer_gcode += f"{{if layer_num=={layer_num}}}{item_gcode}{{endif}}"

        self.overrides_dict['layer_gcode'] = combined_layer_gcode 

def calculate_md5(file_paths):
    md5_hash = hashlib.md5()
    for file_path in file_paths:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def coll_from_selection():
    for obj in bpy.context.selected_objects:
        return obj.users_collection[0]
    active_layer_collection = bpy.context.view_layer.active_layer_collection.collection
    return active_layer_collection
        
def get_collection_parents(target_collection, scene=None):
    if scene is None:
        scene = bpy.context.scene

    def recursive_find(coll, path):
        # If we found the target, return the full path (including the target)
        if coll == target_collection:
            return path + [coll]
        # Otherwise, search in each child
        for child in coll.children:
            result = recursive_find(child, path + [coll])
            if result is not None:
                return result
        return None

    return recursive_find(scene.collection, [])

def get_inherited_slicing_props(cx, pg_name):
    props = {'printer': None, 'filament': None, 'print': None}
    inherited = {'printer': None, 'filament': None, 'print': None}
    config_map = {
        'printer': 'printer_config_file',
        'filament': 'filament_config_file',
        'print':   'print_config_file'
    }

    coll_hierarchy = get_collection_parents(cx)

    for key, attr in config_map.items():
        is_set = False
        for coll in coll_hierarchy:
            pg = getattr(coll, pg_name)
            config = getattr(pg, attr, '')
            if config:
                is_set = True
                props[key] = config
        inherited[key] = is_set and not config

    return props, inherited

def objects_to_tris(selected_objects, scale):
    tris_count = sum(len(obj.data.loop_triangles) for obj in selected_objects)
    tris = np.empty(tris_count * 4 * 3, dtype=np.float64).reshape(-1, 4, 3)

    col_idx = 0
    for obj in selected_objects:
        mesh = obj.data
        curr_tris_count = len(mesh.loop_triangles)
        curr_vert_count = len(mesh.vertices)

        tris_v_i = np.empty(curr_tris_count * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices", tris_v_i)
        tris_v_i = tris_v_i.reshape((-1, 3))

        tris_v_n = np.empty(curr_tris_count * 3)
        mesh.loop_triangles.foreach_get("normal", tris_v_n)
        tris_v_n = tris_v_n.reshape((-1, 3))

        tris_verts = np.empty(curr_vert_count * 3)
        mesh.vertices.foreach_get("co", tris_verts)
        tris_verts = tris_verts.reshape((-1, 3))
        
        world_matrix = np.array(obj.matrix_world.transposed())

        homogeneous_verts = np.hstack((tris_verts, np.ones((tris_verts.shape[0], 1))))
        tx_verts = homogeneous_verts @ world_matrix
        tx_verts = (tx_verts[:, :3]) * scale

        homogeneous_norm = np.hstack((tris_v_n, np.ones((tris_v_n.shape[0], 1))))
        tx_norm = homogeneous_norm @ world_matrix.T
        tx_norm = tx_norm[:, :3]
        tx_norm = tx_norm / np.linalg.norm(tx_norm, axis=1, keepdims=True)
        tx_norm = tx_norm[:, np.newaxis, :]

        tx_tris = tx_verts[tris_v_i]
        
        tris_coords_and_norm = np.concatenate((tx_tris, tx_norm), axis=1)
        
        tris[col_idx:col_idx + curr_tris_count,:] = tris_coords_and_norm
        
        col_idx += curr_tris_count

    return tris

def transform_tris(tris, v=np.array([.0, .0, .0])):
    tris[:, :3] += v
    return tris

def scale_tris(tris, s=0):
    tris[:, :3] *= s
    return tris

def save_stl(tris, filename):
    header = b'\0' * 80 + struct.pack('<I', tris.shape[0])

    with open(filename, 'wb') as f:
        f.write(header)
        for tri in tris:
            v1, v2, v3, normal = tri
            data = struct.pack('<12fH', *normal, *v1, *v2, *v3, 0)
            f.write(data)

def prepare_mesh(context):
    depsgraph = bpy.context.evaluated_depsgraph_get()

    scene_scale = context.scene.unit_settings.scale_length

    selected_objects = [obj.evaluated_get(depsgraph) for obj in bpy.context.selected_objects if obj.type == 'MESH']
    tris_by_object = [objects_to_tris([obj], 1000 * scene_scale) for obj in selected_objects]

    global_tris = np.concatenate(tris_by_object)
    vertices = global_tris[:, :3, :]
    min_coords, max_coords = vertices.min(axis=(0, 1)), vertices.max(axis=(0, 1))
    transform = (min_coords*(-0.5, -0.5, 1) + max_coords*(-0.5, -0.5, 0))

    all_tris = []

    for i, tris in enumerate(tris_by_object):
        tris_transformed = transform_tris(tris, transform)
        all_tris.append(tris_transformed)

    # Combine all transformed triangles into a single numpy array
    all_tris_combined = np.concatenate(all_tris, axis=0)

    return all_tris_combined

def prepare_mesh_split(context):
    depsgraph = bpy.context.evaluated_depsgraph_get()

    scene_scale = context.scene.unit_settings.scale_length

    selected_objects = [obj.evaluated_get(depsgraph) for obj in bpy.context.selected_objects if obj.type == 'MESH']
    tris_by_object = [objects_to_tris([obj], 1000 * scene_scale) for obj in selected_objects]

    global_tris = np.concatenate(tris_by_object)
    vertices = global_tris[:, :3, :]
    min_coords, max_coords = vertices.min(axis=(0, 1)), vertices.max(axis=(0, 1))
    transform = (min_coords*(-0.5, -0.5, -1) + max_coords*(-0.5, -0.5, 0))

    all_tris = []

    for i, tris in enumerate(tris_by_object):
        tris_transformed = transform_tris(tris, transform)
        all_tris.append(tris_transformed)

    return tris_by_object