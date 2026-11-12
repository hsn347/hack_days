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

# جدول الجودة الرسمي للأبطال من heroinfodes.lua
HERO_QUALITY_MAP = {
    5501001: 5, 5501002: 5, 5501003: 5, 5501004: 5, 5501005: 5, 5501006: 4, 5501007: 4, 5501008: 4, 5501009: 5, 5501010: 4,
    5501011: 4, 5501012: 5, 5501013: 5, 5501014: 5, 5501015: 5, 5501016: 5, 5501017: 5, 5501018: 5, 5501019: 5, 5501020: 5,
    5501021: 5, 5501022: 4, 5501023: 4, 5501024: 5, 5501025: 4, 5501026: 5, 5501027: 5, 5501028: 5, 5501029: 5, 5501030: 5,
    5501031: 5, 5501032: 5, 5501033: 6, 5501034: 4, 5501035: 5, 5501036: 6, 5501037: 6, 5501038: 6, 5501039: 6, 5501040: 6,
    5501041: 6, 5501042: 6, 5501043: 6,
    5502001: 5, 5502002: 4, 5502003: 4, 5502004: 4, 5502005: 4, 5502006: 3, 5502007: 4, 5502008: 3, 5502009: 3, 5502010: 3,
    5502011: 5, 5502012: 5, 5502013: 5,
    5503001: 5, 5503002: 4, 5503003: 4, 5503004: 4, 5503005: 4, 5503006: 4, 5503007: 4, 5503008: 3, 5503009: 3, 5503010: 3,
    5503011: 3, 5503012: 5, 5503013: 5, 5503014: 5, 5503015: 5, 5503016: 5, 5503017: 5, 5503018: 5, 5503019: 5, 5503020: 6,
    5503021: 6, 5503022: 6, 5503023: 5, 5503024: 6, 5503025: 6, 5503026: 6, 5503027: 6
}

# جدول عناصر وبوفات زيادة المسيرة النشطة (effectType 19 - MARCH_LIMIT_BOOST) من buff.lua
ACTIVE_MARCH_BUFF_PERCENT = {
    4006: 0.10,
    4506: 0.10,
    4569: 0.10,
    4570: 0.15,
    5010: 0.25,
    5044: 0.35,
    5055: 0.50,
    5091: 0.20,
    5120: 0.25,
    5302: 0.20,
    5305: 0.15,
    5347: 0.50,
    5348: 0.70,
    5349: 0.90,
}


def get_weapon_strengthen_base(slv: int) -> int:
    """إرجاع الزيادة الأساسية لتقوية السلاح من equipment_strengthen.lua"""
    if slv <= 0:
        return 0
    if slv <= 10:
        return slv * 10
    if slv <= 30:
        return 100 + (slv - 10) * 20
    if slv <= 50:
        return 500 + (slv - 30) * 40
    if slv <= 70:
        return 1300 + (slv - 50) * 60
    if slv <= 90:
        return 2500 + (slv - 70) * 80
    if slv <= 100:
        return 4100 + (slv - 90) * 90
    return 5000 + (slv - 100) * 100


def get_weapon_refine_values(rlv: int) -> tuple:
    """إرجاع (refineAddBaseValue, refineAddSkillValue) لصقل السلاح من equipment_refine.lua"""
    if rlv <= 0:
        return 0, 0
    base = rlv * 200 - 100
    if rlv <= 20:
        skill = rlv * 9
    else:
        skill = 180 + (rlv - 20) * 18
    return base, skill


def get_lord_weapon_march_bonus(init_data: dict) -> int:
    """
    حساب الزيادة في سعة المسيرة من سلاح اللورد (EID 6110000) خاصية 41 (MARCH_VALUE_LIMIT_BOOST).
    وفق دالة equipmentCell:getCurEquipRefineSkillResult في كود اللعبة الأصلي.
    """
    if not isinstance(init_data, dict):
        return 0
    equip_ctrl = init_data.get("equipmentCtrl", {})
    if not isinstance(equip_ctrl, dict):
        return 0
    eq_list = equip_ctrl.get("equipment_array", [])
    if not isinstance(eq_list, list):
        return 0

    for eq in eq_list:
        if isinstance(eq, dict) and eq.get("eid") == 6110000:
            slv = int(eq.get("slv", 0))
            rlv = int(eq.get("rlv", 0))
            # Base value from equipment_info (100) + strengthen + refine
            base_val = 100 + get_weapon_strengthen_base(slv) + get_weapon_refine_values(rlv)[0]
            # Skill value from equipment_info (180) + refine skill addition
            skill_val = 180 + get_weapon_refine_values(rlv)[1]
            # Result: math.floor(baseValue / 100 * skillValue)
            return math.floor(base_val / 100.0 * skill_val)
    return 0


def get_vip_march_bonus(init_data: dict) -> int:
    """
    حساب امتيازات سعة المسيرة من VIP للخاصية 96 (MARCH_VALUE_LIMIT_BOOST) من جدول vip.lua:
      - VIP 13: +10,000 جندي
      - VIP 14: +20,000 جندي
      - VIP 15+: +30,000 جندي
    """
    if not isinstance(init_data, dict):
        return 0
    vip_ctrl = init_data.get("vipCtrl", {})
    if not isinstance(vip_ctrl, dict):
        return 0
    vlv = int(vip_ctrl.get("vipLv", 0))
    if vlv >= 15:
        return 30000
    elif vlv == 14:
        return 20000
    elif vlv == 13:
        return 10000
    return 0


def get_active_march_buff_multiplier(init_data: dict) -> float:
    """
    فحص البوفات النشطة في buffCtrl وحساب المضاعف الإضافي لسعة المسيرة (effectType 19).
    """
    if not isinstance(init_data, dict):
        return 0.0
    buff_ctrl = init_data.get("buffCtrl", [])
    extra_mult = 0.0
    buff_items = []
    if isinstance(buff_ctrl, list):
        buff_items = buff_ctrl
    elif isinstance(buff_ctrl, dict):
        buff_items = list(buff_ctrl.values())

    for b in buff_items:
        if isinstance(b, dict):
            bid = b.get("id")
            try:
                bid_int = int(bid)
                if bid_int in ACTIVE_MARCH_BUFF_PERCENT:
                    extra_mult = max(extra_mult, ACTIVE_MARCH_BUFF_PERCENT[bid_int])
            except Exception:
                pass
    return extra_mult


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


def get_castle_base_march_capacity(conn_or_init: Any) -> int:
    """
    استخراج سعة مسيرة ساحة التدريب للقلعة بدون أبطال بمطابقة 100% لواجهة وكود اللعبة:
      Total = floor((Base + Default + Tech + BuffValueAdd + BoeCount) * (1 + Multiplier))
    """
    if hasattr(conn_or_init, "init_data"):
        init_data = getattr(conn_or_init, "init_data", {})
    else:
        init_data = conn_or_init if isinstance(conn_or_init, dict) else {}

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

    # بونص سلاح اللورد (EID 6110000 property 41 MARCH_VALUE_LIMIT_BOOST)
    weapon_bonus = get_lord_weapon_march_bonus(init_data)

    # بونص امتيازات الـ VIP (خاصية 96 MARCH_VALUE_LIMIT_BOOST)
    vip_bonus = get_vip_march_bonus(init_data)

    # خصائص اللورد boeAttributeCtrl
    boe_ctrl = init_data.get("boeAttributeCtrl", {})
    boe_flat_add = 0.0
    multiplier = 0.0
    if isinstance(boe_ctrl, dict):
        val_5 = boe_ctrl.get("1", {}).get("1", {}).get("5", {})
        if isinstance(val_5, dict):
            multiplier = float(val_5.get("1", 0)) / 1000.0
            boe_flat_add = float(val_5.get("2", 0))

    # بوفات زيادة المسيرة النشطة (effectType 19)
    active_buff_mult = get_active_march_buff_multiplier(init_data)
    total_multiplier = multiplier + active_buff_mult

    # إجمالي الإضافات الثابتة داخل القوس وفق كود buildLogic.getExpArmyCount:
    # total_add = math.floor(default + tech_add + pet_add + buff_value_add + boeBuffValueCount)
    buff_value_add = weapon_bonus + vip_bonus
    inner_total = math.floor(default_cap + tech_add + buff_value_add + boe_flat_add)

    # تطبيق المضاعف المئوي
    buff_add = math.floor((base_cap + inner_total) * total_multiplier)
    final_cap = base_cap + inner_total + buff_add

    return int(max(300, final_cap))


def get_hero_march_bonus(hero_data: dict, castle_buff_multiplier: float = 0.0) -> int:
    """
    حساب الزيادة في سعة المسيرة التي يمنحها بطل محدد وفق معادلة اللعبة:
      الزيادة = (مستوى البطل × 100 × معامل الجودة + مهارات القيادة) × (1 + مضاعف بوفات القلعة)
    """
    if not isinstance(hero_data, dict):
        return 0

    hlv = int(hero_data.get("lv", 1))
    hid = int(hero_data.get("id", 0))

    # جلب الجودة الحقيقية للبطل من جدول heroinfodes.lua الرسمي
    quality = hero_data.get("quality")
    if quality is None or int(quality) <= 0:
        quality = HERO_QUALITY_MAP.get(hid, 4)
    else:
        quality = int(quality)

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

    # استخراج معامل البوف المئوي الحقيقي من boeAttributeCtrl وبوفات العناصر النشطة
    boe_ctrl = init_data.get("boeAttributeCtrl", {}) if isinstance(init_data, dict) else {}
    multiplier = 0.0
    if isinstance(boe_ctrl, dict):
        val_5 = boe_ctrl.get("1", {}).get("1", {}).get("5", {})
        if isinstance(val_5, dict):
            multiplier = float(val_5.get("1", 0)) / 1000.0

    multiplier += get_active_march_buff_multiplier(init_data)

    # إضافة سعة الأبطال المختارين
    heroes_total_bonus = 0
    if chosen_heroes:
        hero_ctrl = init_data.get("heroCtrl", [])
        heroes_lookup: Dict[int, dict] = {}
        if isinstance(hero_ctrl, list):
            for h in hero_ctrl:
                if isinstance(h, dict) and "id" in h:
                    try:
                        heroes_lookup[int(h["id"])] = h
                    except Exception:
                        pass
        elif isinstance(hero_ctrl, dict):
            for k, h in hero_ctrl.items():
                if isinstance(h, dict):
                    hid = h.get("id", k)
                    try:
                        heroes_lookup[int(hid)] = h
                    except Exception:
                        pass

        for hid in chosen_heroes:
            if not hid or int(hid) <= 0:
                continue
            h_data = heroes_lookup.get(int(hid))
            if h_data:
                heroes_total_bonus += get_hero_march_bonus(h_data, multiplier)
            else:
                # بطل غير مسجل في heroCtrl للحساب — حساب دقيق بمستوى 1 وفق جودته الرسمية
                quality = HERO_QUALITY_MAP.get(int(hid), 4)
                modulus = HERO_QUALITY_MODULUS.get(quality, 0.8)
                base_hero_troops = int(1 * 100 * modulus)
                heroes_total_bonus += round(base_hero_troops * (1.0 + max(0.0, multiplier)))

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
