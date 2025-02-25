from functools import lru_cache

import json
import bpy

import shutil
import multiprocessing
import platform
import csv
import os

from .. import TYPES_NAME

class BasePanel(bpy.types.Panel):
    bl_label = "Default Panel"
    bl_idname = "COLLECTION_PT_BasePanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"
    def populate_ui(self, layout, property_group, item_rows):
            for item_row in item_rows:
                row = layout.row()
                if type(item_row) == list:
                    for item in item_row:
                        row.prop(property_group, item)
                elif type(item_row) == str:
                    if ';' in item_row:
                        text, icon = item_row.split(';')
                    else:
                        text, icon = item_row, '',
                    row.label(text=text, icon=icon)

    def draw(self, context):
        pass

class ParamAddOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.generic_add_operator"
    bl_label = "Add Parameter"
    list_id: bpy.props.StringProperty()

    def execute(self, context): #type: ignore
        prop_group = self.get_pg()

        list = getattr(prop_group, f'{self.list_id}')
        list.add()
        return {'FINISHED'}
    
    def get_pg(self):
        pass

    def trigger(self):
        pass

class ParamRemoveOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.generic_remove_operator"
    bl_label = "Generic Remove Operator"

    item_idx: bpy.props.IntProperty()
    list_id: bpy.props.StringProperty()

    def execute(self, context): #type: ignore
        prop_group = self.get_pg()

        list = getattr(prop_group, f'{self.list_id}')
        list.remove(self.item_idx)
        return {'FINISHED'}

    def get_pg(self):
        pass

    def trigger(self):
        pass

class ParamTransferOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.generic_transfer_operator"
    bl_label = "Transfer Parameter"

    item_idx: bpy.props.IntProperty()
    list_id: bpy.props.StringProperty()
    target_list: bpy.props.StringProperty()

    def execute(self, context): #type: ignore
        prop_group = self.get_pg()

        source_list = getattr(prop_group, f'{self.list_id}')
        source_item = source_list[self.item_idx]

        target_list = getattr(prop_group, f'{self.target_list}')
        item = target_list.add()
        item.param_id = source_item.param_id
        self.trigger()
        return {'FINISHED'}
    
    def get_pg(self):
        pass

    def trigger(self):
        pass

@lru_cache(maxsize=128)
def _load_csv(filename: str, mtime: float, encoding: str | None = None) -> tuple[tuple[str, ...], ...]:
    with open(filename, 'r', newline='', encoding=encoding) as f:
        reader = csv.reader(f)
        return tuple(tuple(row) for row in reader)

def parse_csv_to_tuples(filename: str) -> list[tuple[str, ...]]:
    current_mtime = os.path.getmtime(filename)
    data: tuple[tuple[str, ...], ...] = _load_csv(filename, current_mtime)
    return sorted(data, key=lambda x: x[1])

def parse_csv_to_dict(filename: str) -> dict[str, list[str]]:
    current_mtime = os.path.getmtime(filename)
    data: tuple[tuple[str, ...], ...] = _load_csv(filename, current_mtime, encoding='utf-8-sig')
    result = {}
    for row in data:
        if row:
            result[row[0]] = list(row[1:])
    return result

def is_usb_device(partition):
    if platform.system() == "Windows":
        return 'removable' in partition.opts.lower()
    else:
        return 'usb' in partition.opts or "/media" in partition.mountpoint

def threaded_copy(from_file, to_file):
    process = multiprocessing.Process(target=shutil.copy, args=(from_file, to_file))
    process.start()

def show_progress(ref, progress, progress_text = ""):
    setattr(ref, 'progress', progress)
    setattr(ref, 'progress_text', progress_text)
    for workspace in bpy.data.workspaces:
        for screen in workspace.screens:
            for area in screen.areas:
                area.tag_redraw()
    return None

def redraw():
    for workspace in bpy.data.workspaces:
        for screen in workspace.screens:
            for area in screen.areas:
                area.tag_redraw()
    return None

def totuple(a):
    return tuple(map(tuple, a))

def reset_selection(object, field):
    if getattr(object, field) > -1:
        setattr(object, field, -1)

def dict_from_json(path):
    with open(path, 'r') as file:
        return json.load(file)

def dump_dict_to_json(dictionary, path):
    # Ensure the directory exists
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    
    # Write the dictionary to the file as JSON
    with open(path, 'w') as file:
        json.dump(dictionary, file, indent=2)