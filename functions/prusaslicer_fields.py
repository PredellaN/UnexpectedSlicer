from typing import Any, LiteralString

import os
from functools import lru_cache

from .basic_functions import dict_from_json, parse_csv_to_dict

search_db_path: LiteralString = os.path.join('functions', 'prusaslicer_fields.json')
search_db: dict[str, dict[str, Any]] = dict_from_json(search_db_path)

search_db_mod_path: LiteralString = os.path.join('functions', 'prusaslicer_modifier_fields.csv')
search_db_mod: dict[str, list[str]] = parse_csv_to_dict(search_db_mod_path)

@lru_cache(maxsize=128)
def search_in_db(term) -> dict[str, dict[str, Any]]:
    words: Any = term.lower().split()
    return {k: v for k, v in search_db.items() if all([word in k+" "+v.get('label','') for word in words])}

@lru_cache(maxsize=128)
def search_in_mod_db(term) -> dict[str, dict[str, Any]]:
    words = term.lower().split()
    filtered_search_db = {k: v for k, v in search_db.items() if k in search_db_mod}
    return {k: v for k, v in filtered_search_db.items() if all([word in k+" "+v.get('label','') for word in words])}

pass