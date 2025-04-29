from ...functions.bpy_classes import ParamRemoveOperator

def create_operator_row(row, operator_id: str, list_id: str = '', idx: int | None = None, icon: str = 'NONE', text = None) -> ParamRemoveOperator:
    op: ParamRemoveOperator = row.operator(operator_id, text=text, icon=icon)  # type: ignore
    if list_id:
        op.list_id = list_id
    if idx:
        op.item_idx = idx
    return op