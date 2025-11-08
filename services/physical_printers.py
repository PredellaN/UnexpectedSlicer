import bpy
from .printer_service import PrinterController

from concurrent.futures import ThreadPoolExecutor
import threading

assert bpy.context.preferences

max_conn = getattr(bpy.context.preferences.system, 'network_connection_limit', 1)
timeout = bpy.context.preferences.system.network_timeout
executor = ThreadPoolExecutor(max_workers=max_conn)
lock = threading.Lock()

printers_querier = PrinterController(poll_interval=5)

from ..registry import register_timer
from ..infra.blender_bridge import redraw

@register_timer
def querier_timer() -> int:
    if not bpy.app.online_access: return 0
    try: printers_querier.poll()
    except: pass
    redraw()
    return 1