#!/usr/bin/env python3

from __future__ import annotations
from configparser import ConfigParser
from typing import Any

import os
import re
import json

def ini_content_to_dict(path: str) -> dict[str, str]:
    with open(path, 'r') as file:
        content = file.read()

    config: ConfigParser = ConfigParser(interpolation=None)

    default_section = f"[default:default]\n" + content
    config.read_string(default_section)

    return dict(sorted(config.items(config.sections()[0])))

def dump_dict_to_json(dictionary, path):
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    
    with open(path, 'w') as file:
        json.dump(dictionary, file, indent=2)

import re
from typing import Any


def _strip_cpp_comments(t: str) -> str:
    out, i, n = [], 0, len(t)
    in_str = in_chr = esc = in_lc = in_bc = False
    while i < n:
        c, nxt = t[i], (t[i + 1] if i + 1 < n else "")
        if in_lc:
            if c == "\n": in_lc = False; out.append(c)
            i += 1; continue
        if in_bc:
            if c == "*" and nxt == "/": in_bc = False; i += 2
            else: i += 1
            continue
        if in_str:
            out.append(c)
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': in_str = False
            i += 1; continue
        if in_chr:
            out.append(c)
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == "'": in_chr = False
            i += 1; continue

        if c == "/" and nxt == "/": in_lc = True; i += 2; continue
        if c == "/" and nxt == "*": in_bc = True; i += 2; continue
        if c == '"': in_str = True; out.append(c); i += 1; continue
        if c == "'": in_chr = True; out.append(c); i += 1; continue
        out.append(c); i += 1
    return "".join(out)


def _split_statements(t: str) -> list[str]:
    stmts, buf = [], []
    in_str = in_chr = esc = False
    for c in t:
        buf.append(c)
        if in_str:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': in_str = False
            continue
        if in_chr:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == "'": in_chr = False
            continue
        if c == '"': in_str = True; continue
        if c == "'": in_chr = True; continue
        if c == ";":
            s = "".join(buf).strip()[:-1].strip()
            if s: stmts.append(s)
            buf = []
    tail = "".join(buf).strip()
    if tail: stmts.append(tail)
    return stmts


def _unesc(s: str) -> str:
    return (s.replace(r"\\", "\\").replace(r"\"", '"')
             .replace(r"\n", "\n").replace(r"\t", "\t").replace(r"\r", "\r"))


def _cat_string_literals(expr: str) -> str | None:
    lits = re.findall(r'"((?:\\.|[^"\\])*)"', expr)
    return None if not lits else "".join(_unesc(x) for x in lits).strip()


def _split_top_commas(s: str) -> list[str]:
    parts, buf = [], []
    dp = db = ds = 0
    in_str = in_chr = esc = False
    for c in s:
        buf.append(c)
        if in_str:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': in_str = False
            continue
        if in_chr:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == "'": in_chr = False
            continue
        if c == '"': in_str = True; continue
        if c == "'": in_chr = True; continue

        if c == "(": dp += 1
        elif c == ")": dp = max(0, dp - 1)
        elif c == "{": db += 1
        elif c == "}": db = max(0, db - 1)
        elif c == "[": ds += 1
        elif c == "]": ds = max(0, ds - 1)

        if c == "," and dp == db == ds == 0:
            buf.pop()
            p = "".join(buf).strip()
            if p: parts.append(p)
            buf = []
    tail = "".join(buf).strip()
    if tail: parts.append(tail)
    return parts


_num = re.compile(r"^[+-]?(?:(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)(?:[fF])?$")

def _val(expr: str) -> Any:
    e = expr.strip()
    s = _cat_string_literals(e)
    if s is not None: return s
    if e in {"true", "false"}: return e == "true"
    if e in {"nullptr", "NULL"}: return None

    ef = e[:-1] if e.endswith(("f", "F")) else e  # <-- NEW
    if _num.match(e):
        if any(ch in ef for ch in ".eE"):
            try: return float(ef)
            except ValueError: pass
        try: return int(ef)
        except ValueError: pass

    if e.startswith("{") and e.endswith("}"):
        inner = e[1:-1].strip()
        return [] if not inner else [_val(p) for p in _split_top_commas(inner)]
    return e

_ADD  = re.compile(r'^\s*(?:auto\s*\*?\s*)?def\s*=\s*(?:this->)?add\s*\(\s*"([^"]+)"\s*,\s*([A-Za-z_]\w*)(?:\s*,[\s\S]*?)?\)\s*$')
_ATTR = re.compile(r'^\s*def->([A-Za-z_]\w*)\s*=\s*([\s\S]+?)\s*$')
_ENUM = re.compile(r'^\s*def->set_enum\s*<\s*([A-Za-z_]\w*)\s*>\s*\(\s*([\s\S]+?)\s*\)\s*$')
_DEFT = re.compile(r'^\s*def->set_default_value\s*\(\s*new\s+([A-Za-z_]\w*)(?:\s*<\s*([^>]+?)\s*>)?\s*[\(\{]\s*([\s\S]*?)\s*[\)\}]\s*\)\s*')
_VEC2 = re.compile(r"^\s*(?:Vec2d|Point|Pointf)\s*\(\s*([\s\S]+?)\s*,\s*([\s\S]+?)\s*\)\s*$")

def _parse_vec2(expr: str) -> Any:
    m = _VEC2.match(expr)
    if not m: return _val(expr)
    x, y = m.groups()
    return [_val(x), _val(y)]

def _default(class_name: str, template: str | None, ctor_args: str) -> Any:
    cn, args = class_name.strip(), ctor_args.strip()
    parts = _split_top_commas(args) if args else []
    one  = lambda: _val(parts[0]) if parts else ""
    many = lambda: [_val(a) for a in parts]

    cn = cn.replace("Nullable", "")

    if cn in {"ConfigOptionPoints", "ConfigOptionPoint"}:
        return [_parse_vec2(p) for p in parts]
    if cn in {"ConfigOptionPointsGroups"}:
        return []
    if cn in {"ConfigOptionFloat", "ConfigOptionDouble", "ConfigOptionPercent", "ConfigOptionFloatOrPercent"}:
        v = one(); return float(v) if isinstance(v, (int, float)) else v
    if cn == "ConfigOptionInt":
        v = one(); return int(v) if isinstance(v, (int, float)) else v
    if cn == "ConfigOptionBool": return bool(one())
    if cn == "ConfigOptionString": return one()
    if cn in {"ConfigOptionFloats", "ConfigOptionDoubles", "ConfigOptionPercents"}:
        return [float(v) if isinstance(v, (int, float)) else v for v in many()]
    if cn == "ConfigOptionInts":
        return [int(v) if isinstance(v, (int, float)) else v for v in many()]
    if cn in {"ConfigOptionStrings"}:
        return many()
    if cn in {"ConfigOptionBools"}: return [bool(v) for v in many()]
    if cn in {"ConfigOptionEnum", "ConfigOptionEnumGeneric"}:
        return {"enum": template.strip() if template else "", "value": one()}
    if cn in {"ConfigOptionEnums", "ConfigOptionEnumsGeneric"}:
        return {"enum": template.strip() if template else "", "value": many()}

    raise Exception


def parse_orcaslicer_printconfig_cpp(path: str) -> dict[str, dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        stmts = _split_statements(_strip_cpp_comments(f.read()))

    configs: dict[str, dict[str, Any]] = {}
    cur_k: str = ""
    cur: dict[str, Any] = {}

    for s in (st.strip() for st in stmts):
        if (m := _ADD.match(s)):
            cur_k, typ = m.groups()
            cur = configs.setdefault(cur_k, {})
            cur["type"] = typ
            continue
        if not cur_k or cur is None: continue

        if (m := _ATTR.match(s)):
            a, rhs = m.groups()
            cur[a] = _val(rhs)
            continue

        if (m := _ENUM.match(s)):
            et, payload = m.groups()
            keys = [_unesc(k) for k in re.findall(r'"((?:\\.|[^"\\])*)"', payload)]
            cur["enum"] = {"type": et, "keys": keys, "raw": payload.strip()}
            continue

        if (m := _DEFT.match(s)):
            if "default" in cur: continue
            cn, tpl, args = m.groups()
            cur["default"] = _default(cn, tpl, args)
            continue

        if re.match(r"^\s*def\s*=\s*nullptr\s*$", s):
            cur_k = ""; cur = {}

    for k, cfg in configs.items():
        enum_key = cfg["default"]["value"]

    return configs


def parse(cpp_path, json_path):
    cfg = parse_orcaslicer_printconfig_cpp(cpp_path)
    dump_dict_to_json(cfg, json_path)

if __name__ == '__main__':
    # parse('experimental/PrintConfigClass_orca.cpp' , 'services/orcaslicer_fields/orcaslicer_fields.json')
    parse('experimental/PrintConfigClass.cpp' , 'services/prusaslicer_fields/prusaslicer_fields_experimental.json')