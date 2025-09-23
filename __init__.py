from typing import Any, Callable

import bpy, os

### Constants
ADDON_FOLDER = os.path.dirname(os.path.abspath(__file__))
PG_NAME = "UnexpectedSlicer"
TYPES_NAME = "blendertoprusaslicer"
PACKAGE: str = __package__ or "unexpectedslicer"

### Blender Addon Initialization
bl_info: dict[str, str | tuple[int, int, int]] = {
    "name" : "UnexpectedSlicer",
    "author" : "Nicolas Predella",
    "description" : "PrusaSlicer integration into Blender",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),  
    "location" : "",
    "warning" : "",
}

### Initialization
from .preferences import physical_printers
from .preferences import config_selection
from .preferences import preferences

from . import property_groups
from . import operators

from .ui.panels import object_panel
from .ui.panels import slicer_panel
from .ui.panels import overrides_panel
from .ui.panels import pauses_panel
from .ui.panels import gcode_preview_panel
from .ui.panels import stdout_panel
from .ui.panels import physical_printers_panel

### Load collected modules
from . import registry
modules = registry.get()
timers: list[Callable[str, int | None]] = registry.get_timers()  # pyright: ignore[reportInvalidTypeForm]

def register():

    registry.blender_register_classes()
    registry.blender_register_timers()
    registry.blender_register_icons()

    bpy.types.WorkSpace.blendertoprusaslicer = bpy.props.PointerProperty(type=property_groups.SlicerWorkspacePropertyGroup, name="blendertoprusaslicer") #type: ignore
    bpy.types.Collection.blendertoprusaslicer = bpy.props.PointerProperty(type=property_groups.SlicerPropertyGroup, name="blendertoprusaslicer") #type: ignore
    bpy.types.Object.blendertoprusaslicer = bpy.props.PointerProperty(type=property_groups.SlicerObjectPropertyGroup, name="blendertoprusaslicer") #type: ignore

    from .functions import bundler
    physical_printers.update_querier()

def unregister():   
    from .ui.panels.gcode_preview_panel import drawer
    drawer.stop()

    registry.blender_unregister_classes()
    registry.blender_unregister_timers()
    registry.blender_unregister_icons() 

    del bpy.types.WorkSpace.blendertoprusaslicer #type: ignore
    del bpy.types.Collection.blendertoprusaslicer #type: ignore
    del bpy.types.Object.blendertoprusaslicer #type: ignore

if __name__ == "__main__":
    register()
