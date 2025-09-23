import os, json

def dict_from_json(path):
    with open(path, 'r') as file:
        return json.load(file)

def dump_dict_to_json(dictionary, path):
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    
    with open(path, 'w') as file:
        json.dump(dictionary, file, indent=2)