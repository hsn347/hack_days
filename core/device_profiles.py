# -*- coding: utf-8 -*-
"""
core/device_profiles.py — إدارة وتوليد بصمات الأجهزة الحقيقية (Device Fingerprints)
══════════════════════════════════════════════════════════════════════════════════════
يوفر هذا الملف تشكيلة واسعة من بصمات هواتف حقيقية (Samsung, Xiaomi, Huawei, Pixel)
مع ربط كل قلعة ببصمة ثابتة وفريدة (Deterministic Fingerprint) مبنية على معرف الحساب،
مما يمنع كشف البوت ويلغي بصمة المحاكي الافتراضية المكشوفة (sdk_gphone64_x86_64).
"""

import hashlib
from typing import Dict, Any, List

# قائمة هواتف حقيقية منتشرة وشائعة الاستخدام في ألعاب الهواتف (65+ هاتف ذكي حقيقي)
REAL_DEVICE_PROFILES: List[Dict[str, str]] = [
    # ── Samsung Galaxy Flagships & S-Series ──
    {"model": "SM-S928B", "brand": "samsung", "android_ver": "14", "carrier": "STC"},         # S24 Ultra
    {"model": "SM-S926B", "brand": "samsung", "android_ver": "14", "carrier": "Mobily"},      # S24+
    {"model": "SM-S921B", "brand": "samsung", "android_ver": "14", "carrier": "Zain"},        # S24
    {"model": "SM-S918B", "brand": "samsung", "android_ver": "14", "carrier": "STC"},         # S23 Ultra
    {"model": "SM-S916B", "brand": "samsung", "android_ver": "13", "carrier": "Mobily"},      # S23+
    {"model": "SM-S911B", "brand": "samsung", "android_ver": "13", "carrier": "Zain"},        # S23
    {"model": "SM-S908B", "brand": "samsung", "android_ver": "13", "carrier": "STC"},         # S22 Ultra
    {"model": "SM-S906B", "brand": "samsung", "android_ver": "13", "carrier": "Vodafone"},    # S22+
    {"model": "SM-S901B", "brand": "samsung", "android_ver": "12", "carrier": "Turkcell"},    # S22
    {"model": "SM-G998B", "brand": "samsung", "android_ver": "12", "carrier": "Mobily"},      # S21 Ultra
    {"model": "SM-G991B", "brand": "samsung", "android_ver": "12", "carrier": "STC"},         # S21
    {"model": "SM-G990B", "brand": "samsung", "android_ver": "13", "carrier": "Zain"},        # S21 FE 5G
    {"model": "SM-G781B", "brand": "samsung", "android_ver": "12", "carrier": "Turkcell"},    # S20 FE 5G
    {"model": "SM-N986B", "brand": "samsung", "android_ver": "12", "carrier": "STC"},         # Note 20 Ultra
    {"model": "SM-F946B", "brand": "samsung", "android_ver": "14", "carrier": "Mobily"},      # Z Fold 5
    {"model": "SM-F731B", "brand": "samsung", "android_ver": "14", "carrier": "Zain"},        # Z Flip 5

    # ── Samsung Galaxy A-Series (Mid-range Popular) ──
    {"model": "SM-A556B", "brand": "samsung", "android_ver": "14", "carrier": "STC"},         # A55 5G
    {"model": "SM-A546B", "brand": "samsung", "android_ver": "14", "carrier": "Turkcell"},    # A54 5G
    {"model": "SM-A536B", "brand": "samsung", "android_ver": "13", "carrier": "Vodafone"},    # A53 5G
    {"model": "SM-A528B", "brand": "samsung", "android_ver": "13", "carrier": "Mobily"},      # A52s 5G
    {"model": "SM-A356B", "brand": "samsung", "android_ver": "14", "carrier": "Zain"},        # A35 5G
    {"model": "SM-A346B", "brand": "samsung", "android_ver": "13", "carrier": "STC"},         # A34 5G
    {"model": "SM-A256B", "brand": "samsung", "android_ver": "14", "carrier": "Vodafone"},    # A25 5G
    {"model": "SM-A156B", "brand": "samsung", "android_ver": "14", "carrier": "Mobily"},      # A15 5G
    {"model": "SM-A736B", "brand": "samsung", "android_ver": "13", "carrier": "STC"},         # A73 5G

    # ── Xiaomi Flagships & Mid-range ──
    {"model": "23116PN5BC", "brand": "Xiaomi", "android_ver": "14", "carrier": "STC"},        # Xiaomi 14 Pro
    {"model": "23127PN0CG", "brand": "Xiaomi", "android_ver": "14", "carrier": "Mobily"},     # Xiaomi 14
    {"model": "23078PND5G", "brand": "Xiaomi", "android_ver": "13", "carrier": "Zain"},       # Xiaomi 13T Pro
    {"model": "2210132C",  "brand": "Xiaomi", "android_ver": "13", "carrier": "Vodafone"},    # Xiaomi 13 Pro
    {"model": "2211133G",  "brand": "Xiaomi", "android_ver": "13", "carrier": "Turkcell"},    # Xiaomi 13
    {"model": "2112123AG", "brand": "Xiaomi", "android_ver": "12", "carrier": "STC"},         # Xiaomi 12
    {"model": "2203121C",  "brand": "Xiaomi", "android_ver": "12", "carrier": "Mobily"},      # Xiaomi 12 Pro

    # ── Redmi Series ──
    {"model": "23090RA98G", "brand": "Redmi",  "android_ver": "14", "carrier": "STC"},        # Redmi Note 13 Pro+
    {"model": "2312DRA50G", "brand": "Redmi",  "android_ver": "13", "carrier": "Mobily"},     # Redmi Note 13 Pro
    {"model": "2312DRAABG", "brand": "Redmi",  "android_ver": "13", "carrier": "Zain"},       # Redmi Note 13
    {"model": "22101316G",  "brand": "Redmi",  "android_ver": "13", "carrier": "Turkcell"},   # Redmi Note 12 Pro+
    {"model": "22111317G",  "brand": "Redmi",  "android_ver": "13", "carrier": "Vodafone"},   # Redmi Note 12
    {"model": "21091116UG", "brand": "Redmi",  "android_ver": "12", "carrier": "STC"},        # Redmi Note 11 Pro 5G

    # ── POCO Series (Gaming Phones) ──
    {"model": "2311DRK48G", "brand": "POCO",   "android_ver": "14", "carrier": "Mobily"},     # POCO X6 Pro
    {"model": "24069PC21G", "brand": "POCO",   "android_ver": "14", "carrier": "Zain"},       # POCO F6
    {"model": "23049PCD8G", "brand": "POCO",   "android_ver": "13", "carrier": "STC"},        # POCO F5
    {"model": "23013PC75G", "brand": "POCO",   "android_ver": "13", "carrier": "Turkcell"},   # POCO F5 Pro
    {"model": "2201117PG",  "brand": "POCO",   "android_ver": "12", "carrier": "Vodafone"},   # POCO X4 Pro 5G
    {"model": "22041216G",  "brand": "POCO",   "android_ver": "12", "carrier": "STC"},        # POCO F4

    # ── OnePlus ──
    {"model": "CPH2581",   "brand": "OnePlus", "android_ver": "14", "carrier": "STC"},         # OnePlus 12
    {"model": "CPH2449",   "brand": "OnePlus", "android_ver": "13", "carrier": "Mobily"},      # OnePlus 11
    {"model": "CPH2551",   "brand": "OnePlus", "android_ver": "14", "carrier": "Zain"},        # OnePlus Open
    {"model": "CPH2493",   "brand": "OnePlus", "android_ver": "13", "carrier": "Vodafone"},    # OnePlus Nord 3
    {"model": "CPH2413",   "brand": "OnePlus", "android_ver": "13", "carrier": "STC"},         # OnePlus 10T

    # ── Oppo & Realme ──
    {"model": "PGEM10",    "brand": "OPPO",    "android_ver": "13", "carrier": "Mobily"},      # Find X6 Pro
    {"model": "CPH2521",   "brand": "OPPO",    "android_ver": "13", "carrier": "STC"},         # Reno 10 Pro+
    {"model": "CPH2607",   "brand": "OPPO",    "android_ver": "14", "carrier": "Turkcell"},    # Reno 11 Pro
    {"model": "CPH2565",   "brand": "OPPO",    "android_ver": "13", "carrier": "Zain"},        # A78 5G
    {"model": "RMX3888",   "brand": "realme",  "android_ver": "14", "carrier": "STC"},         # GT 5 Pro
    {"model": "RMX3840",   "brand": "realme",  "android_ver": "14", "carrier": "Mobily"},      # 12 Pro+ 5G
    {"model": "RMX3741",   "brand": "realme",  "android_ver": "13", "carrier": "Vodafone"},    # 11 Pro+ 5G
    {"model": "RMX3710",   "brand": "realme",  "android_ver": "13", "carrier": "Zain"},        # C55

    # ── Vivo ──
    {"model": "V2324A",    "brand": "vivo",    "android_ver": "14", "carrier": "STC"},         # X100 Pro
    {"model": "V2219",     "brand": "vivo",    "android_ver": "13", "carrier": "Mobily"},      # X90 Pro
    {"model": "V2318",     "brand": "vivo",    "android_ver": "14", "carrier": "Zain"},        # V30 5G
    {"model": "V2250",     "brand": "vivo",    "android_ver": "13", "carrier": "Turkcell"},    # V29 5G

    # ── Huawei & Honor ──
    {"model": "ALN-AL00",  "brand": "HUAWEI",  "android_ver": "13", "carrier": "STC"},         # Mate 60 Pro
    {"model": "MNA-AL00",  "brand": "HUAWEI",  "android_ver": "12", "carrier": "Mobily"},      # P60 Pro
    {"model": "JAD-AL50",  "brand": "HUAWEI",  "android_ver": "12", "carrier": "Zain"},        # P50 Pro
    {"model": "NOH-NX9",   "brand": "HUAWEI",  "android_ver": "12", "carrier": "Turkcell"},    # Mate 40 Pro
    {"model": "BVL-N49",   "brand": "HONOR",   "android_ver": "14", "carrier": "STC"},         # Magic 6 Pro
    {"model": "PGT-N19",   "brand": "HONOR",   "android_ver": "13", "carrier": "Vodafone"},    # Magic 5 Pro
    {"model": "REA-NX9",   "brand": "HONOR",   "android_ver": "13", "carrier": "Mobily"},      # Honor 90
    {"model": "FNE-AN00",  "brand": "HONOR",   "android_ver": "12", "carrier": "Zain"},        # Honor 70
    {"model": "ALI-NX1",   "brand": "HONOR",   "android_ver": "13", "carrier": "STC"},         # Honor X9b

    # ── Google Pixel ──
    {"model": "Pixel 8 Pro", "brand": "Google", "android_ver": "14", "carrier": "STC"},
    {"model": "Pixel 8",     "brand": "Google", "android_ver": "14", "carrier": "Mobily"},
    {"model": "Pixel 7 Pro", "brand": "Google", "android_ver": "14", "carrier": "Zain"},
    {"model": "Pixel 7",     "brand": "Google", "android_ver": "13", "carrier": "STC"},
    {"model": "Pixel 7a",    "brand": "Google", "android_ver": "14", "carrier": "Vodafone"},
    {"model": "Pixel 6 Pro", "brand": "Google", "android_ver": "13", "carrier": "Mobily"},
    {"model": "Pixel 6a",    "brand": "Google", "android_ver": "13", "carrier": "Zain"},
]



def get_device_profile(identifier: str) -> Dict[str, str]:
    """
    استخراج بصمة جهاز حقيقية ثابتة لكل حساب بناءً على هاش المعرف (الإيميل أو معرف القلعة).
    
    يضمن هذا المنطق:
      1. عدم استخدام بصمة المحاكي المكشوفة sdk_gphone64_x86_64.
      2. ثبات بصمة نفس القلعة دائماً لتبدو اللعبة وكأنها تُلعب من نفس الهاتف الشخصي للاعب.
      3. تنوع البصمات بين القلاع المختلفة تلقائياً.
    """
    clean_id = (identifier or "default").strip().lower()
    # توليد رقم ثابت وموحد لكل حساب
    h = hashlib.md5(clean_id.encode("utf-8")).hexdigest()
    idx = int(h, 16) % len(REAL_DEVICE_PROFILES)
    
    profile = dict(REAL_DEVICE_PROFILES[idx])
    
    # بناء حقل platform المطابق لبروتوكول اللعبة:
    # Android {android_ver} {model} {brand} and.onemt.boe.tr ar
    platform_str = f"Android {profile['android_ver']} {profile['model']} Google and.onemt.boe.tr ar"
    profile["platform"] = platform_str
    return profile
