# registry.py
_registry: list[type] = []

def register(cls: type) -> type:
    """Class decorator: adds the class to the global _registry."""
    _registry.append(cls)
    return cls

def get() -> list[type]:
    """Return a list of all registered classes."""
    return list(_registry)