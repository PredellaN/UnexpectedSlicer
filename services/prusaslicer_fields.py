from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Any

import os
from functools import lru_cache

from ..infra.json import dict_from_json
from ..infra.csv import parse_csv_to_dict
from .. import ADDON_FOLDER

search_db_path: str = os.path.join(ADDON_FOLDER, 'services', 'prusaslicer_fields', 'prusaslicer_fields.json')
search_db: dict[str, dict[str, Any]] = dict_from_json(search_db_path)

search_db_mod_path: str = os.path.join(ADDON_FOLDER, 'services', 'prusaslicer_fields', 'prusaslicer_modifier_fields.csv')
search_db_mod: dict[str, list[str]] = parse_csv_to_dict(search_db_mod_path)

@lru_cache(maxsize=128)
def search_in_db(term: str) -> dict[str, dict[str, Any]]:
    if not term:
        return search_db
    words = term.lower().split()
    return {
        k: v for k, v in search_db.items()
        if all(word in f"{k} {v.get('label') or ''} {v.get('tooltip') or ''} {v.get('category') or ''}".lower() for word in words)
    }

@lru_cache(maxsize=128)
def search_in_mod_db(term: str) -> dict[str, dict[str, Any]]:
    filtered = {k: v for k, v in search_db.items() if k in search_db_mod}
    if not term:
        return filtered
    words = term.lower().split()
    return {
        k: v for k, v in filtered.items()
        if all(word in f"{k} {v.get('label') or ''} {v.get('tooltip') or ''} {v.get('category') or ''}".lower() for word in words)
    }

pass