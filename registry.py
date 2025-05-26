# registry.py
from bpy.utils.previews import ImagePreviewCollection


from bpy.utils.previews import ImagePreviewCollection

import bpy
import os
from typing import Callable

_bpy_class_registry: list[type] = []
_timer_registry: list[Callable] = []
_icons_pcoll: dict[str, ImagePreviewCollection] = {}
icons = {'main': None}

_timer_handles: list = []

# BPY CLASSES
def register_class(cls: type) -> type:
    _bpy_class_registry.append(cls)
    return cls

def get() -> list[type]:
    return list(_bpy_class_registry)

def blender_register_classes():
    for module in get():
        bpy.utils.register_class(module)

def blender_unregister_classes():
    for module in get():
        bpy.utils.unregister_class(module)

# TIMERS
def register_timer(clb: Callable):
    _timer_registry.append(clb)
    return clb

def get_timers() -> list[Callable]:
    return list(_timer_registry)

def blender_register_timers():
    global _timer_handles
    for timer in _timer_registry:
        _timer_handles.append(bpy.app.timers.register(timer))

def blender_unregister_timers():
    global _timer_handles
    for timer in _timer_handles:
        try:
            bpy.app.timers.unregister(timer)
        except: pass
    _timer_handles = []

# ICONS
def blender_register_icons():
    pcoll: ImagePreviewCollection = bpy.utils.previews.new()

    my_icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    for filename in os.listdir(my_icons_dir):
        if filename.endswith(".svg") or filename.endswith(".png"):
            icon_name = os.path.splitext(filename)[0]
            pcoll.load(icon_name, os.path.join(my_icons_dir, filename), 'IMAGE')
    _icons_pcoll['main'] = pcoll

def blender_unregister_icons():
    for pcoll in _icons_pcoll.values():
        bpy.utils.previews.remove(pcoll)
    _icons_pcoll.clear()

def get_icon(icon_id):
    return _icons_pcoll["main"][icon_id].icon_id #type: ignore