import bpy, os

### Constants
ADDON_FOLDER = os.path.dirname(os.path.abspath(__file__))
PG_NAME = "UnexpectedSlicer"
TYPES_NAME = "blendertoprusaslicer"
PACKAGE: str = __package__ or "unexpectedslicer"

### Blender Addon Initialization
bl_info = {
    "name" : "UnexpectedSlicer",
    "author" : "Nicolas Predella",
    "description" : "PrusaSlicer integration into Blender",
    "blender" : (4, 2, 0),
    "version" : (1, 0, 0),  
    "location" : "",
    "warning" : "",
}

icons_pcoll = {}

### Initialization
from .preferences import physical_printers
from .preferences import config_selection
from .preferences import preferences

from . import property_groups
from . import operators

from .panels import object_panel
from .panels import slicer_panel
from .panels import overrides_panel
from .panels import pauses_panel
from .panels import gcode_preview_panel
from .panels import stdout_panel
from .panels import physical_printers_panel

from .classes import bpy_classes

### Load collected modules
from . import registry
modules = registry.get()

def register():
    import bpy.utils.previews
    pcoll = bpy.utils.previews.new()

    my_icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    for filename in os.listdir(my_icons_dir):
        if filename.endswith(".svg") or filename.endswith(".png"):
            icon_name = os.path.splitext(filename)[0]
            pcoll.load(icon_name, os.path.join(my_icons_dir, filename), 'IMAGE')
    icons_pcoll["main"] = pcoll

    for module in modules:
        bpy.utils.register_class(module)

    bpy.types.WorkSpace.blendertoprusaslicer = bpy.props.PointerProperty(type=property_groups.SlicerWorkspacePropertyGroup, name="blendertoprusaslicer") #type: ignore
    bpy.types.Collection.blendertoprusaslicer = bpy.props.PointerProperty(type=property_groups.SlicerPropertyGroup, name="blendertoprusaslicer") #type: ignore
    bpy.types.Object.blendertoprusaslicer = bpy.props.PointerProperty(type=property_groups.SlicerObjectPropertyGroup, name="blendertoprusaslicer") #type: ignore

    if __debug__:
        from . import dev

def unregister():   
    from .panels.gcode_preview_panel import drawer
    drawer.stop()

    for module in modules:
        bpy.utils.unregister_class(module)

    for pcoll in icons_pcoll.values():
        bpy.utils.previews.remove(pcoll)
    icons_pcoll.clear()

    del bpy.types.WorkSpace.blendertoprusaslicer #type: ignore
    del bpy.types.Collection.blendertoprusaslicer #type: ignore
    del bpy.types.Object.blendertoprusaslicer #type: ignore

if __name__ == "__main__":
    register()
