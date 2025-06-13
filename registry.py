# registry.py
import bpy
from typing import Any, Callable

_bpy_class_registry: list[type] = []
_timer_registry: list[Callable[Any, int | None]] = []

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
def register_timer(clb: Callable[Any, Any]):
    _timer_registry.append(clb)
    return clb

def get_timers() -> list[Callable[Any, int | None]]:
    return list(_timer_registry)

def blender_register_timers():
    for timer in _timer_registry:
        bpy.app.timers.register(timer, persistent=True)

def blender_unregister_timers():
    for timer in _timer_registry:
        bpy.app.timers.unregister(timer)

import os
from bpy.utils.previews import ImagePreviewCollection

_icons_pcoll: ImagePreviewCollection | None = None
icons = {'main': None}

def blender_register_icons():
    global _icons_pcoll
    _icons_pcoll = bpy.utils.previews.new()

    my_icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    for filename in os.listdir(my_icons_dir):
        if filename.endswith(".svg") or filename.endswith(".png"):
            icon_name = os.path.splitext(filename)[0]
            _icons_pcoll.load(icon_name, os.path.join(my_icons_dir, filename), 'IMAGE')

def blender_unregister_icons():
    global _icons_pcoll
    if not _icons_pcoll: return
    bpy.utils.previews.remove(_icons_pcoll)

def get_icon(icon_id: str) -> int:
    global _icons_pcoll
    return _icons_pcoll[icon_id].icon_id #type: ignore