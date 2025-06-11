from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Any
    from re import Match, Pattern

import re

def parse_gcode(file_path, name) -> str | Any | None:
    pattern: Pattern[Any] = re.compile(rb'^;? ?' + name.encode('utf-8') + rb' ?= ?(.+)$')
    with open(file_path, 'rb') as file:  # Open in binary mode
        lines: list[bytes] = file.readlines()[::-1] # Read all lines and reverse the order
        for line in lines:
            try:
                val: Match[bytes] | None = pattern.search(line)
                if val:
                    return val.group(1).decode()
            except UnicodeDecodeError:
                continue
    return None

def get_bed_size(bed_shape: str) -> tuple:
    try:
        # Split the string by commas to get each coordinate
        coordinates: list[str] = bed_shape.split(',')
        
        # Extract x and y values as integers from each coordinate
        x_values: list[int] = [int(coord.split('x')[0]) for coord in coordinates]
        y_values: list[int] = [int(coord.split('x')[1]) for coord in coordinates]
        
        # Bed size is defined by the max x and y values
        bed_width: int = max(x_values)
        bed_height: int = max(y_values)
        
        return bed_width, bed_height
    
    except:
        return 0, 0