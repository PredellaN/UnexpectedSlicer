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
from .preferences.physical_printers import AddPrefItemOperator, RemovePrefItemOperator, PrintersListItem
from .preferences.config_selection import ImportConfigOperator, ExportConfigOperator
from .preferences.preferences import PRUSASLICER_UL_ConfListBase, ConfListItem, SlicerPreferences

from .operators import UnmountUsbOperator, RunSlicerOperator
from .classes.bpy_classes import BaseOperator

from .panels.object_panel import SlicerObjectPanel
from .panels.slicer_panel import SlicerPanel
from .panels.overrides_panel import SlicerPanel_0_Overrides
from .panels.pauses_panel import SlicerPanel_1_Pauses
from .panels.gcode_preview_panel import PreviewGcodeOperator, SlicerPanel_2_Gcode_Preview
from .panels.stdout_panel import SlicerPanel_3_Stdout
from .panels.physical_printers_panel import SlicerPanel_4_Printers, PhysicalPrintersPollOperator, PausePrintOperator

from .property_groups import ParamsListItem, PauseListItem, SlicerObjectPropertyGroup, SlicerPropertyGroup, SlicerWorkspacePropertyGroup

from .classes.bpy_classes import RemoveObjectItemOperator, AddObjectItemOperator, RemoveItemOperator, AddItemOperator, TransferModItemOperator, TransferItemOperator

modules = [
    AddPrefItemOperator,
    RemovePrefItemOperator,
    PrintersListItem,
    ExportConfigOperator,
    ImportConfigOperator, 
    PRUSASLICER_UL_ConfListBase, 
    ConfListItem,
    SlicerPreferences,
    
    UnmountUsbOperator, 
    RunSlicerOperator,
    BaseOperator,

    RemoveObjectItemOperator, 
    AddObjectItemOperator, 
    SlicerObjectPanel, 
    SlicerPanel, 
    RemoveItemOperator, 
    AddItemOperator, 
    TransferModItemOperator, 
    TransferItemOperator, 
    SlicerPanel_0_Overrides, 
    SlicerPanel_1_Pauses,
    
    PreviewGcodeOperator,
    SlicerPanel_2_Gcode_Preview,

    SlicerPanel_3_Stdout,

    PhysicalPrintersPollOperator,
    PausePrintOperator,
    SlicerPanel_4_Printers,

    ParamsListItem, 
    PauseListItem, 
    SlicerObjectPropertyGroup, 
    SlicerPropertyGroup,
    SlicerWorkspacePropertyGroup,
]

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

    bpy.types.WorkSpace.blendertoprusaslicer = bpy.props.PointerProperty(type=SlicerWorkspacePropertyGroup, name="blendertoprusaslicer") #type: ignore
    bpy.types.Collection.blendertoprusaslicer = bpy.props.PointerProperty(type=SlicerPropertyGroup, name="blendertoprusaslicer") #type: ignore
    bpy.types.Object.blendertoprusaslicer = bpy.props.PointerProperty(type=SlicerObjectPropertyGroup, name="blendertoprusaslicer") #type: ignore

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
