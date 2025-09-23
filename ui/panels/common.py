def create_operator_row(row, operator_id: str = "none.generic_operator", list_id: str = '', idx: int | None = None, icon: str = 'NONE', text = None):
    op = row.operator(operator_id, text=text, icon=icon) 
    if list_id:
        op.list_id = list_id
    if idx:
        op.item_idx = idx
    return op