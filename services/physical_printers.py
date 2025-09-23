import bpy
from .printer_service import PrinterQuerier

from concurrent.futures import ThreadPoolExecutor
import threading

assert bpy.context.preferences

max_conn = getattr(bpy.context.preferences.system, 'network_connection_limit', 1)
timeout = bpy.context.preferences.system.network_timeout
executor = ThreadPoolExecutor(max_workers=max_conn)
lock = threading.Lock()

printers_querier = PrinterQuerier(
    timeout=timeout,
    executor=executor,
    lock=lock
    )

from ..registry import register_timer
from ..functions.blender_funcs import redraw

@register_timer
def querier_timer() -> int:
    if not bpy.app.online_access: return 0
    try: printers_querier.query()
    except: pass
    redraw()
    return 1