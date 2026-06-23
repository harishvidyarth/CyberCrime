"""Local IFSC lookup (bank / branch / state) — instant and offline.

Source priority: IFSC_CODES.pkl (a ready {IFSC: row} dict) -> .json cache -> .xlsx.
Loaded once and memoised, so per-lookup cost is a dict access.
"""

import os
import sys
import json
import pickle

import pandas as pd
from functools import lru_cache

# Candidate directories, then the dataset paths in each (pickle preferred).
_BASE = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
_DIRS = [_BASE, "", "uploads", "instance"]
PKL_PATHS = [os.path.join(d, "IFSC_CODES.pkl") for d in _DIRS]
POSSIBLE_PATHS = [os.path.join(d, "IFSC_CODES.xlsx") for d in _DIRS]


def _load_ifsc_from_pickle():
    """First valid {IFSC: row} pickle, else None."""
    for p in PKL_PATHS:
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    table = pickle.load(f)
                if isinstance(table, dict) and table:
                    return table
            except Exception as e:
                print(f"IFSC: could not load pickle {p}: {e}")
    return None


def _load_ifsc_from_json():
    """First JSON cache that loads, else None."""
    for p in POSSIBLE_PATHS:
        json_path = os.path.splitext(p)[0] + ".json"
        if os.path.exists(json_path):
            try:
                with open(json_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return None


def _detect_ifsc_columns(df, cols):
    """Resolve (ifsc, branch, phone) column names from a dataframe."""
    ifsc_col = next((cols[c] for c in ("IFSC", "Ifsc Code", "Ifsc", "IFSC Code") if c in cols), None) or next(
        (c for c in df.columns if "ifsc" in c.lower()), None
    )
    branch_col = next(
        (c for c in ("BRANCH", "Branch", "BRANCH_NAME", "Branch Name", "BranchName", "BRANCH NAME") if c in cols),
        None,
    ) or next((c for c in df.columns if "branch" in str(c).lower()), None)
    phone_col = next(
        (c for c in ("Phone", "PHONE", "Contact", "Telephone", "Contact Number", "Phone No", "PhoneNumber") if c in cols),
        None,
    ) or next((c for c in df.columns if any(t in str(c).lower() for t in ("phone", "contact", "tel"))), None)
    return ifsc_col, branch_col, phone_col


def _build_ifsc_mapping(df, ifsc_col, branch_col, phone_col):
    """Build {IFSC_UPPER: rowdict} from a parsed dataframe."""
    mapping = {}
    for row in df.to_dict("records"):
        ifsc_val = str(row.get(ifsc_col, "")).strip()
        if not ifsc_val:
            continue
        rowdict = {str(k).strip(): (v if v is not None else "") for k, v in row.items()}
        rowdict["BRANCH"] = str(row.get(branch_col, "")).strip() if branch_col else ""
        rowdict["PHONE"] = str(row.get(phone_col, "")).strip() if phone_col else ""
        mapping[ifsc_val.upper()] = rowdict
    return mapping


def _cache_ifsc_json(p, mapping):
    """Persist the parsed mapping next to the source for next time."""
    try:
        with open(os.path.splitext(p)[0] + ".json", "w") as f:
            json.dump(mapping, f)
    except Exception as e:
        print(f"IFSC: could not cache JSON: {e}")


def _load_ifsc_from_excel():
    """Parse the first available Excel source, cache to JSON, else None."""
    for p in POSSIBLE_PATHS:
        if not os.path.exists(p):
            continue
        try:
            df = pd.read_excel(p, dtype=str).fillna("")
            cols = {c.strip(): c for c in df.columns}
            ifsc_col, branch_col, phone_col = _detect_ifsc_columns(df, cols)
            if not ifsc_col:
                continue
            mapping = _build_ifsc_mapping(df, ifsc_col, branch_col, phone_col)
            _cache_ifsc_json(p, mapping)
            return mapping
        except Exception as e:
            print(f"IFSC: could not load Excel {p}: {e}")
    return None


@lru_cache(maxsize=1)
def load_ifsc_table():
    """Return {IFSC_UPPER: {BANK, BRANCH, STATE, PHONE, ...}} from the first source found
    (pickle -> JSON cache -> Excel)."""
    table = _load_ifsc_from_pickle()
    if table is not None:
        return table
    table = _load_ifsc_from_json()
    if table is not None:
        return table
    table = _load_ifsc_from_excel()
    if table is not None:
        return table
    return {}


def get_ifsc_info(ifsc):
    """Full row for an IFSC, or None."""
    if not ifsc:
        return None
    return load_ifsc_table().get(ifsc.upper())


def get_state(ifsc):
    """State name for an IFSC, or 'Unknown'."""
    info = get_ifsc_info(ifsc)
    if not info:
        return "Unknown"
    for key in ("STATE", "State", "STATE_NAME", "state"):
        if info.get(key):
            return str(info[key]).strip()
    return "Unknown"
