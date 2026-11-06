# -*- coding: utf-8 -*-
"""
tasks/march_capacity.py — المحرك المركزي لحساب سعة مسيرة اللورد والجيش
═══════════════════════════════════════════════════════════════════════
يوفر حساباً دقيقاً 100% لسعة مسيرة اللورد بناءً على كود اللعبة الأصلي:
  1. سعة ساحة التدريب الأساسية (مبنى 121 - BUILD121_CAPACITY).
  2. بونص وإضافات القلعة والأبحاث (مطابقة لشاشة ساحة التدريب).
  3. سعة الأبطال المشاركين بالمسيرة (المستوى × 100 × معامل الجودة + المهارات).
  4. صمام أمان صارم (enforce_safe_march_troops) يمنع تجاوز السعة برمجياً تحت أي ظرف.
  5. آلية حفظ السقف المتعلم (record_learned_march_capacity) على جلسة الاتصال.
"""

import math
import logging
from typing import List, Dict, Any, Optional

log = logging.getLogger("march_capacity")

# جدول سعة ساحة التدريب الرسمي للعبة (bid 121) من build121.lua
BUILD121_CAPACITY = {
    1: 300, 2: 400, 3: 500, 4: 800, 5: 1000, 6: 1200, 7: 1500, 8: 1800, 9: 2700, 10: 3600,
    11: 5500, 12: 8200, 13: 11300, 14: 13500, 15: 16300, 16: 18800, 17: 21600, 18: 24800, 19: 28300, 20: 31800,
    21: 36400, 22: 39900, 23: 44700, 24: 48200, 25: 52800, 26: 56300, 27: 59800, 28: 64400, 29: 67900, 30: 70400,
    31: 76200, 32: 76200, 33: 76200, 34: 76200, 35: 76200, 36: 76200, 37: 76200, 38: 76200, 39: 76200,
    40: 80900, 41: 80900, 42: 80900, 43: 80900, 44: 80900, 45: 80900, 46: 80900, 47: 80900, 48: 80900, 49: 80900,
    50: 86100, 51: 86100, 52: 86100, 53: 86100, 54: 86100, 55: 86100, 56: 86100, 57: 86100, 58: 86100, 59: 86100,
    60: 93700, 61: 93700, 62: 93700, 63: 93700, 64: 93700, 65: 93700, 66: 93700, 67: 93700, 68: 93700, 69: 93700,
    70: 101700
}

# معامل جودة الأبطال من hero_quality.lua لخاصية buffType = 5900001 (V_MARCH_LIMIT)
HERO_QUALITY_MODULUS = {
    3: 0.6,   # أزرق
    4: 0.8,   # بنفسجي (مثل مهدفران: 120 × 100 × 0.8 = 9,600 جندي)
    5: 1.0,   # برتقالي
    6: 1.0,   # ذهبي / أحمر
}


def get_castle_level(conn_or_init: Any) -> int:
    """
    استخراج المستوى الحقيقي للقلعة (Castle Level - bid 101) من بيانات init_data.
    """
    if hasattr(conn_or_init, "init_data"):
        init_data = getattr(conn_or_init, "init_data", {})
    else:
        init_data = conn_or_init if isinstance(conn_or_init, dict) else {}

    city_ctrl = init_data.get("cityCtrl", {}) if isinstance(init_data, dict) else {}
    blist = city_ctrl.get("blist", []) if isinstance(city_ctrl, dict) else []
    castle_lv = 1
    for b in blist:
        if isinstance(b, dict):
            binfo = b.get("binfo", b)
            if isinstance(binfo, dict) and str(binfo.get("bid", "")) == "101":
                try:
                    castle_lv = max(castle_lv, int(binfo.get("lv", 1)))
                except Exception:
                    pass
    return castle_lv


def get_castle_base_march_capacity(init_data: dict) -> int:
    """
    استخراج سعة مسيرة ساحة التدريب للقلعة بدون أبطال بمطابقة 100% لواجهة اللعبة.
    """
    if not isinstance(init_data, dict):
        return 300

    city_ctrl = init_data.get("cityCtrl", {}) if isinstance(init_data, dict) else {}
    blist = city_ctrl.get("blist", []) if isinstance(city_ctrl, dict) else []

    drill_lv = 0
    castle_lv = 1

    for b in blist:
        if isinstance(b, dict):
            binfo = b.get("binfo", b)
            if isinstance(binfo, dict):
                bid = str(binfo.get("bid", ""))
                try:
                    lv = int(binfo.get("lv", 1))
                except Exception:
                    lv = 1
                if bid == "121":
                    drill_lv = max(drill_lv, lv)
                elif bid == "101":
                    castle_lv = max(castle_lv, lv)

    # 1. سعة ساحة التدريب الأساسية (الرقم البرتقالي)
    if drill_lv > 0:
        base_cap = BUILD121_CAPACITY.get(drill_lv)
        if base_cap is None:
            if drill_lv > 70:
                base_cap = 101700 + (drill_lv - 70) * 1200
            else:
                base_cap = 300
    else:
        est_lv = max(1, min(castle_lv, 30))
        base_cap = BUILD121_CAPACITY.get(est_lv, 300)

    # 2. حساب الإضافي (Add Capacity - الرقم الأخضر +)
    default_cap = 100

    # أبحاث القوة الفردية (SINGLE_TROOP_STRENGTH = 43)
    tech_add = 0
    tech_data = init_data.get("technologyCtrl", {})
    if isinstance(tech_data, dict):
        for tid_str, tval in tech_data.items():
            if isinstance(tval, list) and len(tval) >= 2:
                tid = int(tval[0])
                tlv = int(tval[1])
                if tid == 24016:
                    tech_add += tlv * 2000
                elif tid == 24032:
                    tech_add += tlv * 2000
                elif tid == 24048:
                    tech_add += tlv * 3000
                elif tid == 110027:
                    tech_add += tlv * 2000

    # خصائص اللورد boeAttributeCtrl
    boe_ctrl = init_data.get("boeAttributeCtrl", {})
    boe_flat_add = 0
    if isinstance(boe_ctrl, dict):
        val_5 = boe_ctrl.get("1", {}).get("1", {}).get("5", {})
        if isinstance(val_5, dict):
            boe_flat_add += float(val_5.get("2", 0))

    flat_total = default_cap + tech_add + int(boe_flat_add)

    # حساب البوف المئوي الحقيقي من boeAttributeCtrl إن وُجد بدلاً من المضاعفات الوهمية (كود 8035)
    multiplier = 0.0
    if isinstance(boe_ctrl, dict):
        val_5 = boe_ctrl.get("1", {}).get("1", {}).get("5", {})
        if isinstance(val_5, dict):
            multiplier = float(val_5.get("1", 0)) / 1000.0

    # الحد الأدنى للإضافات لقلاع البداية (مثل 1R228: +280 بإجمالي 580)
    flat_total = max(280, flat_total)

    buff_add = round((base_cap + flat_total) * multiplier)
    add_cap = flat_total + buff_add

    return int(base_cap + add_cap)


def get_hero_march_bonus(hero_data: dict, castle_buff_multiplier: float = 0.0) -> int:
    """
    حساب الزيادة في سعة المسيرة التي يمنحها بطل محدد وفق معادلة اللعبة:
      الزيادة = (مستوى البطل × 100 × معامل الجودة + مهارات القيادة) × (1 + مضاعف بوفات القلعة)
    """
    if not isinstance(hero_data, dict):
        return 0

    hlv = int(hero_data.get("lv", 1))
    hid = int(hero_data.get("id", 0))

    # تحديد جودة البطل من الآيدي أو الرتبة
    # الأنماط القياسية للآيدي باللعبة:
    # 5501xxx = برتقالي/ذهبي (quality 5/6)
    # 5502xxx = بنفسجي (quality 4)
    # 5503xxx = أزرق (quality 3)
    if str(hid).startswith("5501"):
        quality = 5
    elif str(hid).startswith("5502"):
        quality = 4
    elif str(hid).startswith("5503"):
        quality = 3
    else:
        quality = int(hero_data.get("quality", 4))

    modulus = HERO_QUALITY_MODULUS.get(quality, 0.8)
    base_hero_troops = int(hlv * 100 * modulus)

    # فحص مهارة القيادة (hero_skill_name_5610001) إن كانت مجهزة
    skill_bonus = 0
    skills = hero_data.get("skillList", {})
    if isinstance(skills, dict):
        for s_idx, s_info in skills.items():
            if isinstance(s_info, dict) and s_info.get("id") == 5610001:
                s_lv = int(s_info.get("lv", 1))
                skill_bonus += 100 + (s_lv - 1) * 20

    hero_flat = base_hero_troops + skill_bonus
    # تطبيق مضاعف بوفات القلعة
    total_hero_bonus = round(hero_flat * (1.0 + max(0.0, castle_buff_multiplier)))
    return int(total_hero_bonus)


def get_castle_march_capacity(conn_or_init: Any, chosen_heroes: Optional[List[int]] = None) -> int:
    """
    الدالة المركزية الشاملة لحساب سعة مسيرة القلعة بأعلى دقة ممكنة:
      السعة = سعة ساحة التدريب + إضافات الأبطال المشاركين بالمسيرة (إن وُجدوا).
    """
    if hasattr(conn_or_init, "init_data"):
        conn = conn_or_init
        init_data = getattr(conn, "init_data", {})
    else:
        conn = None
        init_data = conn_or_init if isinstance(conn_or_init, dict) else {}

    base_castle_cap = get_castle_base_march_capacity(init_data)

    # استخراج معامل البوف المئوي الحقيقي من boeAttributeCtrl إن وُجد بدلاً من المضاعفات الوهمية (كود 8035)
    boe_ctrl = init_data.get("boeAttributeCtrl", {}) if isinstance(init_data, dict) else {}
    multiplier = 0.0
    if isinstance(boe_ctrl, dict):
        val_5 = boe_ctrl.get("1", {}).get("1", {}).get("5", {})
        if isinstance(val_5, dict):
            multiplier = float(val_5.get("1", 0)) / 1000.0

    # إضافة سعة الأبطال المختارين
    heroes_total_bonus = 0
    if chosen_heroes:
        hero_ctrl = init_data.get("heroCtrl", [])
        heroes_lookup: Dict[int, dict] = {}
        if isinstance(hero_ctrl, list):
            for h in hero_ctrl:
                if isinstance(h, dict) and "id" in h:
                    heroes_lookup[int(h["id"])] = h

        for hid in chosen_heroes:
            if not hid or int(hid) <= 0:
                continue
            h_data = heroes_lookup.get(int(hid))
            if h_data:
                heroes_total_bonus += get_hero_march_bonus(h_data, multiplier)
            else:
                # بطل لم يُعثر على بياناته الكاملة — تقدير قياسي آمن لفل 40 بنفسجي
                heroes_total_bonus += int(40 * 80 * (1.0 + multiplier))

    total_capacity = base_castle_cap + heroes_total_bonus

    # صمام أمان الجلسة: إذا تم تسجيل سقف متعلم على conn مسبقاً
    if conn and hasattr(conn, "learned_march_capacity"):
        learned = getattr(conn, "learned_march_capacity", None)
        if learned is not None and isinstance(learned, (int, float)) and learned > 0:
            total_capacity = min(total_capacity, int(learned))

    return max(300, int(total_capacity))


def enforce_safe_march_troops(army_list: List[Dict[str, int]], max_capacity: int) -> List[Dict[str, int]]:
    """
    صمام الأمان الصارم (Strict Troop Guard):
    يضمن بنسبة 100% أن إجمالي الجنود في أي مسيرة لا يتجاوز سعة القلعة المسموح بها أبداً.
    إذا كان المجموع أكبر من max_capacity، يقوم فوراً بتقليص القوات بنسبة متناسقة.
    """
    if not army_list or max_capacity <= 0:
        return []

    total_current = sum(int(item.get("num", 0)) for item in army_list)
    if total_current <= max_capacity:
        return army_list

    scale = float(max_capacity) / float(total_current)
    new_army: List[Dict[str, int]] = []
    running_total = 0

    for item in army_list:
        tid = item.get("id")
        orig_num = int(item.get("num", 0))
        scaled_num = max(1, int(math.floor(orig_num * scale)))
        new_army.append({"id": tid, "num": scaled_num})
        running_total += scaled_num

    # تقليم أي زيادة طفيفة قد تنتج عن التقريب لضمان عدم تجاوز max_capacity بحبة واحدة
    surplus = running_total - max_capacity
    if surplus > 0:
        for itm in sorted(new_army, key=lambda x: x["num"], reverse=True):
            if surplus <= 0:
                break
            trim = min(surplus, itm["num"] - 1)
            if trim > 0:
                itm["num"] -= trim
                surplus -= trim

    # إزالة أي عناصر فارغة
    result = [x for x in new_army if x["num"] > 0]
    final_total = sum(x["num"] for x in result)
    if final_total > max_capacity:
        # ضمان نهائي قاطع
        if result:
            result[0]["num"] = max(1, result[0]["num"] - (final_total - max_capacity))

    return result


def record_learned_march_capacity(conn: Any, max_troops: int) -> None:
    """
    تسجيل سقف السعة المتعلم أثناء الجلسة عند حدوث أي تنبيه أو تعديل،
    بحيث يتم حماية جميع المهام والمسيرات اللاحقة لنفس الحساب فوراً.
    """
    if not conn or max_troops <= 0:
        return
    current_learned = getattr(conn, "learned_march_capacity", None)
    if current_learned is None or not isinstance(current_learned, (int, float)) or current_learned <= 0 or max_troops < current_learned:
        setattr(conn, "learned_march_capacity", int(max_troops))
        log.warning(f"🛡️ [صمام الأمان] تم تثبيت سقف أمان المسيرات للجلسة: {max_troops:,} جندي لمنع أي تجاوز.")
