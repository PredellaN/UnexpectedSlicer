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
registered_classes = []

def register():
    from .functions import modules as mod

    from . import preferences as pref
    mod.reload_modules([pref])
    registered_classes.extend(mod.register_classes(mod.get_classes([pref])))
    prefs = bpy.context.preferences.addons[PACKAGE].preferences
    prefs.update_config_bundle_manifest()

    from . import operators as op
    from . import panels as pn
    from . import property_groups as pg
    mod.reload_modules([op, pn, pg])
    registered_classes.extend(mod.register_classes(mod.get_classes([op,pn,pg])))

    bpy.types.Collection.blendertoprusaslicer = bpy.props.PointerProperty(type=pg.PrusaSlicerPropertyGroup, name="blendertoprusaslicer")

def unregister():   
    from .functions import modules as mod

    mod.unregister_classes(registered_classes)
    del bpy.types.Collection.blendertoprusaslicer


if __name__ == "__main__":
    register()
