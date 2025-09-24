from pathlib import Path
import os

def get_bed_size(bed_shape: str) -> tuple:
    try:
        coordinates: list[str] = bed_shape.split(',')
        
        x_values: list[int] = [int(coord.split('x')[0]) for coord in coordinates]
        y_values: list[int] = [int(coord.split('x')[1]) for coord in coordinates]
        
        bed_width: int = max(x_values)
        bed_height: int = max(y_values)
        
        return bed_width, bed_height
    
    except:
        return 0, 0

def get_print_stats(gcode: Path) -> tuple:
    from ..infra.gcode import parse_gcode_value
    if os.path.exists(gcode):
        print_time: str = parse_gcode_value(gcode, 'estimated printing time \\(normal mode\\)') or ''
        print_weight: str = parse_gcode_value(gcode, 'filament used \\[g\\]') or ''
        return print_time, print_weight
    return '', ''

from typing import Any
def filter_prusaslicer_dict_by_section(dict, section) -> dict[str, Any]:
    return {k.split(":")[1]: v for k, v in dict.items() if k.split(":")[0] == section}