from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bpy.types import UILayout

def draw_search_item(row, item, transfer_operator: str, target_list: str, key: str):
    op: ParamTransferOperator = row.operator(transfer_operator, text="", icon="ADD")  # type: ignore
    op.target_key = key
    op.target_list = target_list
    row.label(text=f"{item['label']} : {item['tooltip']}")

def draw_search_list(layout: UILayout, search_list_id: dict[str, dict], target_list: str, transfer_operator: str):
    box: UILayout = layout.box()

    for key, item in search_list_id.items():
        row = box.row()
        draw_search_item(row, item, transfer_operator, target_list, key)