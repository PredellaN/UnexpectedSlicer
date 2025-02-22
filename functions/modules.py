from typing import Any
import bpy
import importlib
import inspect

def reload_modules(modules) -> None:
    for module in modules:
        importlib.reload(module)

def get_classes(modules) -> list[type]:
    classes: list[type] = []
    for module in modules:
        classes_in_module: list[type] = [cls for name, cls in inspect.getmembers(module, inspect.isclass) if cls.__module__ == module.__name__ ]
        classes.extend(classes_in_module)
    return classes

def register_classes(classes) -> list[str]:
    for class_to_register in classes:
        bpy.utils.register_class(class_to_register)
    return classes

def unregister_classes(classes) -> list[str]:
    for class_to_register in classes:
        try:
            bpy.utils.unregister_class(class_to_register)
        except:
            continue
    return []