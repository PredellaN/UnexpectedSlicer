import json
import bpy

import time
import shutil
import multiprocessing
import platform
import csv
import os

import cProfile
import pstats
import io

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

class SearchList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        self.draw_properties(row, item)
    
    def draw_properties(self, row, item):
        pass

class BaseList(bpy.types.UIList):
    delete_operator = None

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()

        delete_op = row.operator(self.delete_operator, text="", icon='X')
        delete_op.item_index = index
        delete_op.target = self.list_id

        self.draw_properties(row, item)
    
    def draw_properties(self, row, item):
        pass

class ParamAddOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.generic_add_operator"
    bl_label = "Add Parameter"
    target: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        prop_group = self.get_pg()

        list = getattr(prop_group, f'{self.target}')
        list.add()
        self.triggers()
        return {'FINISHED'}
    
    def get_pg(self):
        pass

    def triggers(self):
        pass

class ParamRemoveOperator(bpy.types.Operator):
    bl_idname = f"{TYPES_NAME}.generic_remove_operator"
    bl_label = "Generic Remove Operator"
    target: bpy.props.StringProperty() # type: ignore
    item_index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        prop_group = self.get_pg()

        list = getattr(prop_group, f'{self.target}')
        list.remove(self.item_index)
        self.triggers()
        return {'FINISHED'}
    
    def get_pg(self):
        pass
    
    def triggers(self):
        pass

def parse_csv_to_tuples(filename):
    if not hasattr(parse_csv_to_tuples, 'cache'):
        parse_csv_to_tuples.cache = {}

    current_mtime = os.path.getmtime(filename)

    if filename in parse_csv_to_tuples.cache:
        cached_mtime, cached_data = parse_csv_to_tuples.cache[filename]
        if current_mtime == cached_mtime:
            return cached_data

    with open(filename, 'r', newline='') as f:
        reader = csv.reader(f)
        data = [tuple(row) for row in reader]

    parse_csv_to_tuples.cache[filename] = (current_mtime, data)

    return sorted(data, key=lambda x: x[1])

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

def time_task(function, text = "", *args):
    start_time = time.perf_counter()
    res = function(*args)
    end_time = time.perf_counter()
    if (end_time - start_time) < 0.1:
        print(f'{text} - {(end_time - start_time):.4f}s')
    else:
        print(f'{text} - {(end_time - start_time):.2f}s')
    return res

def profiler(function, *args):
    pr = cProfile.Profile()
    pr.enable()

    res = function(*args)

    pr.disable()
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)

    ps.print_stats(lambda x: ps.stats[x][3] >= 10)
    print(s.getvalue())

    return res

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