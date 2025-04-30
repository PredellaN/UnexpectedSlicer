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
from . import property_groups as pg

from .preferences import ExportConfigOperator, ImportConfigOperator, PRUSASLICER_UL_ConfListBase, ConfListItem, SlicerPreferences
from .operators import UnmountUsbOperator, RunSlicerOperator
from .panels.object_panel import SlicerObjectPanel
from .panels.slicer_panel import SlicerPanel
from .panels.overrides_panel import SlicerPanel_0_Overrides
from .panels.pauses_panel import SlicerPanel_1_Pauses
from .panels.gcode_preview_panel import PreviewGcodeOperator, SlicerPanel_2_Gcode_Preview
from .property_groups import ParamsListItem, PauseListItem, SlicerObjectPropertyGroup, SlicerPropertyGroup
from .functions.bpy_classes import BasePanel, BaseOperator, ParamAddOperator, ParamRemoveOperator, ParamTransferOperator, RemoveObjectItemOperator, AddObjectItemOperator, RemoveItemOperator, AddItemOperator, TransferModItemOperator, TransferItemOperator

modules = [
    ExportConfigOperator, 
    ImportConfigOperator, 
    PRUSASLICER_UL_ConfListBase, 
    ConfListItem,
    SlicerPreferences,
    
    UnmountUsbOperator, 
    RunSlicerOperator,

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

    ParamsListItem, 
    PauseListItem, 
    SlicerObjectPropertyGroup, 
    SlicerPropertyGroup,

    BasePanel,
    BaseOperator,
    ParamAddOperator,
    ParamRemoveOperator,
    ParamTransferOperator,
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

    bpy.types.Collection.blendertoprusaslicer = bpy.props.PointerProperty(type=pg.SlicerPropertyGroup, name="blendertoprusaslicer") #type: ignore
    bpy.types.Object.blendertoprusaslicer = bpy.props.PointerProperty(type=pg.SlicerObjectPropertyGroup, name="blendertoprusaslicer") #type: ignore

def unregister():   
    for module in modules:
        bpy.utils.unregister_class(module)

    for pcoll in icons_pcoll.values():
        bpy.utils.previews.remove(pcoll)
    icons_pcoll.clear()

    del bpy.types.Collection.blendertoprusaslicer #type: ignore
    del bpy.types.Object.blendertoprusaslicer #type: ignore

if __name__ == "__main__":
    register()
