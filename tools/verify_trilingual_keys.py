# -*- coding: utf-8 -*-
"""
tools/verify_trilingual_keys.py
Adversarial mathematical parity audit for ar.json, en.json, and tr.json
"""
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "src", "locales")

def flatten_keys(d, prefix=""):
    keys = set()
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(flatten_keys(v, full_key))
        else:
            keys.add(full_key)
    return keys

def verify():
    langs = ["ar", "en", "tr"]
    key_sets = {}
    raw_counts = {}

    for lang in langs:
        file_path = os.path.join(LOCALES_DIR, f"{lang}.json")
        if not os.path.exists(file_path):
            print(f"❌ Missing locale file: {file_path}")
            sys.exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        flattened = flatten_keys(data)
        key_sets[lang] = flattened
        raw_counts[lang] = len(flattened)

    print("=== Trilingual Key Counts ===")
    for lang in langs:
        print(f"  {lang}.json: {raw_counts[lang]} keys")

    # Symmetric differences
    diff_ar_en = key_sets["ar"] ^ key_sets["en"]
    diff_ar_tr = key_sets["ar"] ^ key_sets["tr"]
    diff_en_tr = key_sets["en"] ^ key_sets["tr"]

    has_error = False

    if diff_ar_en:
        has_error = True
        print(f"❌ Difference between AR and EN: {len(diff_ar_en)} keys")
        print(f"   In AR not EN: {key_sets['ar'] - key_sets['en']}")
        print(f"   In EN not AR: {key_sets['en'] - key_sets['ar']}")

    if diff_ar_tr:
        has_error = True
        print(f"❌ Difference between AR and TR: {len(diff_ar_tr)} keys")
        print(f"   In AR not TR: {key_sets['ar'] - key_sets['tr']}")
        print(f"   In TR not AR: {key_sets['tr'] - key_sets['ar']}")

    if diff_en_tr:
        has_error = True
        print(f"❌ Difference between EN and TR: {len(diff_en_tr)} keys")
        print(f"   In EN not TR: {key_sets['en'] - key_sets['tr']}")
        print(f"   In TR not EN: {key_sets['tr'] - key_sets['en']}")

    if not has_error:
        print(f"✅ CLEAN: Exactly 100% symmetric parity across all 3 languages ({raw_counts['ar']} keys in each)!")
        if raw_counts["ar"] == 788:
            print("✅ Verified target: Exactly 788 keys present in ar, en, tr!")
        else:
            print(f"ℹ️ Note: Count is {raw_counts['ar']} (expected 788)")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    verify()
