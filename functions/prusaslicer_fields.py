import os
from .. import ADDON_FOLDER
from .basic_functions import parse_csv_to_dict

search_db_path = os.path.join(ADDON_FOLDER, 'functions', 'prusaslicer_fields.csv')
search_db: dict[str, list[str]] = parse_csv_to_dict(search_db_path)

search_db_mod_path = os.path.join(ADDON_FOLDER, 'functions', 'prusaslicer_modifier_fields.csv')
search_db_mod: dict[str, list[str]] = parse_csv_to_dict(search_db_mod_path)

def search_in_db(term):
    words = term.lower().split()
    return {k: v for k, v in search_db.items() if all([word in k+" "+v[0]+" "+v[1] for word in words])}

def search_in_mod_db(term):
    words = term.lower().split()
    return {k: v for k, v in search_db_mod.items() if all([word in k+" "+v[0]+" "+v[1] for word in words])}