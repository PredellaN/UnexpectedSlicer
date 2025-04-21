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

### Initialization
from . import property_groups as pg

from .preferences import ExportConfigOperator, ImportConfigOperator, PRUSASLICER_UL_ConfListBase, ConfListItem, SlicerPreferences
from .operators import UnmountUsbOperator, RunSlicerOperator
from .panels import RemoveObjectItemOperator, AddObjectItemOperator, SlicerObjectPanel, SlicerPanel, RemoveItemOperator, AddItemOperator, TransferModItemOperator, TransferItemOperator, SlicerPanel_0_Overrides, SlicerPanel_1_Pauses
from .property_groups import ParamsListItem, PauseListItem, SlicerObjectPropertyGroup, SlicerPropertyGroup
from .functions.bpy_classes import BasePanel, BaseOperator, ParamAddOperator, ParamRemoveOperator, ParamTransferOperator

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
    for module in modules:
        bpy.utils.register_class(module)

    bpy.types.Collection.blendertoprusaslicer = bpy.props.PointerProperty(type=pg.SlicerPropertyGroup, name="blendertoprusaslicer") #type: ignore
    bpy.types.Object.blendertoprusaslicer = bpy.props.PointerProperty(type=pg.SlicerObjectPropertyGroup, name="blendertoprusaslicer") #type: ignore

def unregister():   
    for module in modules:
        bpy.utils.unregister_class(module)

    del bpy.types.Collection.blendertoprusaslicer #type: ignore
    del bpy.types.Object.blendertoprusaslicer #type: ignore

if __name__ == "__main__":
    register()
