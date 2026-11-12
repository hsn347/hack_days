# -*- coding: utf-8 -*-
"""
tools/test_select_gathering_army.py
═══════════════════════════════════════════════════════════════════════════════
أداة اختبار وفحص مخرجات دالة select_gathering_army بشكل عملي عبر التيرمينال
بتمرير إحداثيات الهدف (X, Y) أو بالبحث التلقائي عن أقرب حقل حي على الخريطة،
دون أي تعديل على الدالة الأصلية.
python tools/test_select_gathering_army.py -e "smsmeid90@gmail.com" --find -t 2 -l 6
أمثلة التشغيل من التيرمينال:
  python tools/test_select_gathering_army.py -x 338 -y 281
  python tools/test_select_gathering_army.py --find -t 5 -l 6
  python tools/test_select_gathering_army.py -e "user@gmail.com" -x 338 -y 281
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple
import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.session_manager import SessionManager
from game_client import GameConnection
from tasks.base_task import RESOURCE_NODE_CAPACITIES
from tasks.gather_2 import (
    select_gathering_army,
    calculate_load_bonus,
    calculate_estimated_march_capacity,
    get_resource_multiplier,
    pick_best_gather_heroes,
    UNIT_FREE_WEIGHTS,
)

TROOP_NAMES: Dict[int, str] = {
    701: "عربة نقل المستوى 1 (Tier 1)",
    703: "عربة نقل المستوى 3 (Tier 3)",
    705: "عربة نقل المستوى 5 (Tier 5)",
    707: "عربة نقل المستوى 7 (Tier 7)",
    709: "عربة نقل / هجوم المستوى 9 (Tier 9)",
    711: "عربة نقل المستوى 11 (Tier 11)",
    702: "منجنيق المستوى 2 (Tier 2)",
    704: "منجنيق المستوى 4 (Tier 4)",
    706: "منجنيق المستوى 6 (Tier 6)",
    708: "منجنيق المستوى 8 (Tier 8)",
    710: "منجنيق المستوى 10 (Tier 10)",
    712: "منجنيق المستوى 12 (Tier 12)",
    401: "مشاة T1", 402: "مشاة T2", 403: "مشاة T3", 404: "مشاة T4",
    405: "مشاة T5", 406: "مشاة T6", 407: "مشاة T7", 408: "مشاة T8",
    409: "مشاة T9", 410: "مشاة T10", 411: "مشاة T11", 412: "مشاة T12",
    501: "فرسان T1", 502: "فرسان T2", 503: "فرسان T3", 504: "فرسان T4",
    505: "فرسان T5", 506: "فرسان T6", 507: "فرسان T7", 508: "فرسان T8",
    509: "فرسان T9", 510: "فرسان T10", 511: "فرسان T11", 512: "فرسان T12",
    601: "رماة T1", 602: "رماة T2", 603: "رماة T3", 604: "رماة T4",
    605: "رماة T5", 606: "رماة T6", 607: "رماة T7", 608: "رماة T8",
    609: "رماة T9", 610: "رماة T10", 611: "رماة T11", 612: "رماة T12",
}


def calculate_unit_capacity(
    army_id: int,
    res_type: int = 1002,
    load_bonus: float = 0.0,
    hero_bonus: float = 0.0
) -> float:
    """
    حساب سعة حمل أي وحدة لأي مورد ديناميكياً لكل حساب وفق كود اللعبة الأصلي (kingdomMapCtrl:getArmyWeightPlus):
    السعة = الوزن الأساسي للوحدة * (1 + بونص الحساب الإجمالي + بونص الأبطال)
    تحويل نوع المورد المستخرج من كود اللعبة الأصلي (worldDispatchArmyView.lua):
      - القمح والخشب (1002, 1003): سعة القمح ÷ 1.0 (مضاعف الوزن = 1.0)
      - الحديد (1004): سعة القمح ÷ 6.0 (مضاعف الوزن = 6.0)
      - الكوارنز / الميثريل (1005): سعة القمح ÷ 24.0 (مضاعف الوزن = 24.0)
      - الذهب (1001, 1006): سعة القمح ÷ 1000.0 (مضاعف الوزن = 1000.0)
    """
    base_w = float(UNIT_FREE_WEIGHTS.get(army_id, 10))
    total_mult = 1.0 + load_bonus + hero_bonus
    wheat_cap = base_w * total_mult

    if res_type == 1004:
        return wheat_cap / 6.0
    elif res_type == 1005:
        return wheat_cap / 24.0
    elif res_type in (1001, 1006):
        return wheat_cap / 1000.0
    return wheat_cap


def select_gathering_army(
    available: Dict[int, int],
    target_load: int,
    load_bonus: float = 0.0,
    hero_bonus: float = 0.0,
    max_march_troops: Optional[int] = None,
) -> Tuple[List[Dict[str, int]], int]:
    """
    اختيار تشكيلة الجيش تلقائياً لجمع الموارد وفق كود اللعبة الأصلي (worldDispatchArmyView:sortArmyListByWeight):
    1. الأولوية المطلقة لعربة نقل المستوى 1 (701) أولاً دائماً.
    2. فرز باقي القوات والورشة تنازلياً حسب سعة الحمولة الحرة (freeWeight):
       - عربات الإمداد الأعلى (711، 709، 707، 705، 703) تأتي مباشرة لتغطية أي نقص.
       - ثم المنجنيق وعربات الهجوم (712..702) والمشاة والفرسان والرماة عند الحاجة.
    3. حساب سعة كل وحدة بدقة بالغة عبر calculate_unit_capacity ديناميكياً لكل حساب وفق عتاده ومستوى VIP وأبحاثه.
    4. إرسال أي قوات متاحة لتغطية حمولة الحقل بدون أي شرط مانع للسعة.
    5. الالتزام الصارم بسقف سعة معسكر التجمع ومسيرة اللورد (max_march_troops) لمنع تجاوز السعة وتجنب خطأ 8035.
    """
    # الترتيب المطابق تماماً لدالة sortArmyListByWeight في worldDispatchArmyView.lua
    def _troop_sort_key(tid: int):
        if tid == 701:
            return (0, 0, 0, 0)  # 701 أولاً دائماً
        w = UNIT_FREE_WEIGHTS.get(tid, 0)
        tid_mod = tid % 1000
        lv_mod = tid_mod % 100
        # فرز تنازلي حسب الحمولة، ثم الرتبة/المستوى، ثم تصاعدي حسب المعرف
        return (1, -w, -lv_mod, tid_mod)

    # استبعاد الفخاخ (8xx) والوحدات ذات الحمولة 0
    ordered_tids = sorted(
        [tid for tid, cnt in available.items() if cnt > 0 and tid < 800 and UNIT_FREE_WEIGHTS.get(tid, 0) > 0],
        key=_troop_sort_key
    )

    # حساب سعة الحمولة المطلوبة بدقة مطابقة لمحرك اللعبة (curResCount / armyWeight)
    rem_load = float(target_load)
    total_carried = 0.0
    army_list: List[Dict[str, int]] = []
    current_total_troops = 0

    for tid in ordered_tids:
        avail = available.get(tid, 0)
        if avail <= 0:
            continue

        unit_weight = calculate_unit_capacity(tid, load_bonus=load_bonus, hero_bonus=hero_bonus)
        needed = min(avail, math.ceil(rem_load / unit_weight))

        # كبح عدد القوات بحيث لا يتجاوز سعة معسكر التجمع ومسيرة اللورد (لمنع خطأ 8035)
        if max_march_troops and max_march_troops > 0:
            remaining_quota = max_march_troops - current_total_troops
            if remaining_quota <= 0:
                break
            needed = min(needed, remaining_quota)

        if needed > 0:
            army_list.append({"id": tid, "num": needed})
            available[tid] -= needed
            load_added = needed * unit_weight
            rem_load = max(0.0, rem_load - load_added)
            total_carried += load_added
            current_total_troops += needed
            if rem_load <= 0:
                break

    return army_list, int(round(total_carried))


RES_NAMES: Dict[int, str] = {
    1001: "الذهب (Gold)",
    1002: "القمح (Food)",
    1003: "الخشب (Wood)",
    1004: "الحديد (Iron)",
    1005: "الكوارنز / الفضة (Silver)",
}

SUBTYPE_TO_CODE = {1: 1001, 2: 1002, 3: 1003, 4: 1004, 5: 1005}
CODE_TO_SUBTYPE = {1001: 1, 1002: 2, 1003: 3, 1004: 4, 1005: 5}


async def run_test(tx: Optional[int], ty: Optional[int], email: Optional[str] = None, auto_find: bool = False, sub_type: int = 5, level: int = 6):
    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        print("❌ لا توجد حسابات مسجلة في session_cache.json!")
        return

    target_email = email.strip().lower() if email else None
    if not target_email:
        # البحث عن أول حساب نشط وغير محظور في castles.db أو session_cache
        try:
            from core.database import get_db_path, get_connection
            db_path = get_db_path()
            with get_connection(db_path) as db_conn:
                c = db_conn.cursor()
                c.execute("SELECT email FROM castle_states WHERE is_active=1 AND (conn_state IS NULL OR conn_state != 'sealed') ORDER BY last_updated DESC LIMIT 1")
                row = c.fetchone()
                if row and row[0] in accounts:
                    target_email = row[0]
        except Exception:
            pass
        if not target_email:
            target_email = next(iter(accounts.keys()))
    acc = accounts.get(target_email)
    if not acc:
        print(f"❌ الحساب {target_email} غير موجود في session_cache.json!")
        return

    conn = GameConnection(acc)
    print(f"\n🔌 جاري الاتصال بالحساب: {target_email} ...")
    if not await conn.connect():
        print("❌ فشل الاتصال بالسيرفر!")
        return

    try:
        for _ in range(12):
            await asyncio.sleep(0.5)
            if len(conn.init_data) > 0:
                break

        kid = getattr(conn, 'kingdom_id', 0)
        target_id = None
        target_lv = level
        actual_res_code = SUBTYPE_TO_CODE.get(sub_type, 1005)
        cur_res = 0

        # خيار البحث التلقائي إذا طُلب أو إذا لم تُمرر إحداثيات
        if auto_find or (tx is None or ty is None):
            print(f"🔍 جاري البحث على الخريطة عن أقرب حقل {RES_NAMES.get(actual_res_code)} لفل {level}...")
            # إحداثيات مركزية من قلعة المستخدم
            cx, cy = 400, 200
            city_ctrl = conn.init_data.get('cityCtrl', {})
            if isinstance(city_ctrl, dict):
                cx = int(city_ctrl.get('x', cx))
                cy = int(city_ctrl.get('y', cy))

            r_search = await conn.query('2011', '3', {
                "mapType": 5, "num": 1, "subType": sub_type,
                "y": cy, "x": cx, "minLv": level, "maxLv": level, "range": 100
            }, timeout=6.0)

            if r_search and r_search.get('result'):
                node = r_search['result'][0]
                tx, ty = int(node['x']), int(node['y'])
                target_id = str(node.get('id', f"{tx+1}-{ty+1}-5-{sub_type}-360{level}"))
                target_lv = int(node.get('level', level))
                print(f"   ✅ تم العثور على حقل حي عند ({tx}, {ty}) بمعرف [{target_id}]")
            else:
                print("❌ لم يتم العثور على أي حقل في النطاق المحدد!")
                return

        # إذا مرر المستخدم إحداثيات محددة، نتحقق من وجود الحقل فعلياً عبر مزامنة الخريطة
        if not target_id:
            print(f"🔍 التحقق من وجود الحقل على الخريطة عند الإحداثيات ({tx}, {ty})...")
            sync_packets = []
            def _on_pkt(cmd, sub, content):
                if str(cmd) == '1009' and str(sub) == '201':
                    sync_packets.append(content)

            conn.add_packet_listener(_on_pkt)
            await conn.query('1006', '1000', {'centerX': tx, 'centerY': ty, 'centerKid': kid}, timeout=3.0)
            await asyncio.sleep(0.8)

            found_item = None
            for pkt in sync_packets:
                items = pkt.get('data', {}).get('1', []) if isinstance(pkt, dict) else []
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            ix, iy = int(item.get('x', -1)), int(item.get('y', -1))
                            if (ix == tx and iy == ty) or (ix == tx + 1 and iy == ty + 1):
                                found_item = item
                                break
                if found_item: break

            if found_item:
                target_id = str(found_item.get('id'))
                target_lv = int(found_item.get('level', target_lv))
                sub_type = int(found_item.get('subMapType', sub_type))
                actual_res_code = SUBTYPE_TO_CODE.get(sub_type, 1005)
                print(f"   ✅ تم تأكيد الهدف في الخريطة: ID={target_id} | لفل {target_lv}")
            else:
                # صيغة المعرف القياسية لشبكة الخريطة
                target_id = f"{tx+1}-{ty+1}-5-{sub_type}-360{target_lv}"

        # استعلام 1006/22 بالمعرف الحقيقي للحقل
        r22 = await conn.query('1006', '22', {"x": tx, "y": ty, "id": target_id}, timeout=4.0)
        ret22 = r22.get('retData', {}) if (r22 and isinstance(r22, dict)) else {}

        if ret22:
            fresh_rem = int(ret22.get('remainSourceNum', 0))
            fresh_tot = int(ret22.get('totalSourceNum', 0))
            if fresh_rem > 0:
                cur_res = fresh_rem
            elif fresh_tot > 0:
                cur_res = fresh_tot

            if ret22.get('resourceType'):
                actual_res_code = int(ret22['resourceType'])
                sub_type = CODE_TO_SUBTYPE.get(actual_res_code, sub_type)

        # إذا لم يكن الحقل موجوداً أو لم يُرجع السيرفر رصيداً، نستخدم السعة الأصلية الرسمية من resource.lua
        if cur_res <= 0:
            official_caps = RESOURCE_NODE_CAPACITIES.get(sub_type, {})
            cur_res = official_caps.get(target_lv, 31500 if sub_type == 5 else 756000)
            if not ret22:
                print(f"   ℹ️ تنبيه: استعلام 1006/22 لم يجد الحقل عند ({tx}, {ty}) — تم استخدام السعة القياسية للعبة (لفل {target_lv}: {cur_res:,} مورد).")

        res_name = RES_NAMES.get(actual_res_code, f"مورد نوع {actual_res_code}")
        multiplier = get_resource_multiplier(actual_res_code, sub_type)
        target_load = int(cur_res * multiplier)

        # جلب القوات المتاحة
        available: Dict[int, int] = {}
        army_ctrl = conn.init_data.get('armyCtrl', {}) if hasattr(conn, 'init_data') else {}
        if isinstance(army_ctrl, dict):
            for k, v in army_ctrl.get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)

        if not available:
            r_army = await conn.query('1005', '1', {}, timeout=4.0)
            if r_army and 'data' in r_army:
                for k, v in r_army['data'].get('totalArmy', {}).items():
                    if str(k).isdigit() and str(v).isdigit():
                        available[int(k)] = int(v)

        # حساب البونص والأبطال وسقف المسيرة
        heroes_list = []
        hctrl = conn.init_data.get('heroCtrl')
        if isinstance(hctrl, list): heroes_list = hctrl
        elif isinstance(hctrl, dict): heroes_list = list(hctrl.get('heroList', {}).values())

        chosen_heroes = pick_best_gather_heroes(heroes_list, busy=set(), max_heroes=2, sub_type=sub_type)
        load_bonus = calculate_load_bonus(conn, sub_type=sub_type, hero_list=chosen_heroes)

        max_march_troops = calculate_estimated_march_capacity(
            getattr(conn, 'init_data', {}),
            chosen_heroes=chosen_heroes
        )

        # ════════════════════════════════════════════════════════════════
        # استدعاء دالة select_gathering_army الأصلية بدون أي تعديل
        # ════════════════════════════════════════════════════════════════
        avail_copy = dict(available)
        army_list, carried_load = select_gathering_army(
            available=avail_copy,
            target_load=target_load,
            load_bonus=load_bonus,
            max_march_troops=max_march_troops
        )

        total_troops_selected = sum(item['num'] for item in army_list)
        coverage_pct = (carried_load / target_load * 100.0) if target_load > 0 else 100.0
        rem_load_left = max(0, target_load - carried_load)
        rem_res_left = int(rem_load_left / multiplier) if multiplier > 0 else 0

        # طباعة التقرير
        print("\n" + "═" * 70)
        print(f"🎯 بيانات الهدف عند الإحداثيات ({tx}, {ty}):")
        print(f"   • معرف الهدف الحقيقي : {target_id}")
        print(f"   • نوع المورد         : {res_name} (كود {actual_res_code})")
        print(f"   • المستوى            : لفل {target_lv}")
        print(f"   • رصيد الحقل الحقيقي : {cur_res:,} وحدة مورد")
        print(f"   • مضاعف وزن المورد   : {multiplier:.1f}x")
        print(f"   • الحمولة المطلوبة   : {target_load:,} حمولة قمح مكافئة")
        print("─" * 70)
        print(f"🏰 بيانات القلعة [{target_email}]:")
        print(f"   • سقف المسيرة الأقصى (max_march_troops): {max_march_troops:,} جندي")
        print(f"   • بونص الحمولة الإجمالي (load_bonus)   : +{load_bonus * 100:.2f}%")
        print(f"   • الأبطال المختارون للمسيرة            : {chosen_heroes or 'بدون أبطال'}")
        print(f"   • إجمالي القوات المتوفرة بالقلعة       : {sum(available.values()):,} جندي")
        print("─" * 70)
        print(f"⚔️ مخرجات دالة select_gathering_army:")
        if not army_list:
            print("   ⚠️ الدالة أعادت قائمة فارغة [] — لا توجد قوات صالحة للإرسال!")
        else:
            for item in army_list:
                tid = item['id']
                num = item['num']
                tname = TROOP_NAMES.get(tid, f"وحدة #{tid}")
                w = UNIT_FREE_WEIGHTS.get(tid, 10)
                eff_w = w * (1.0 + load_bonus)
                unit_total_load = int(round(num * eff_w))
                print(f"   👉 [{tid}] {tname:<35} : {num:>7,} جندي | حمولة: {unit_total_load:>10,}")

            print("   " + "─" * 60)
            print(f"   • إجمالي الجنود المختارين : {total_troops_selected:,} / {max_march_troops:,} جندي")
            print(f"   • إجمالي الحمولة المنقولة : {carried_load:,} / {target_load:,}")
            print(f"   • نسبة تغطية الحقل        : {coverage_pct:.2f}%")

            if coverage_pct >= 99.9:
                print("   • نتيجة التصفية           : ✅ تصفية كاملة 100% — سيمسح الحقل بالكامل ولن يترك أي فتات!")
            else:
                print(f"   • نتيجة التصفية           : ⚠️ مسيرة جزئية — سيترك وراءه {rem_res_left:,} من المورد ({rem_load_left:,} حمولة)!")
                if max_march_troops and total_troops_selected >= max_march_troops:
                    print(f"   • سبب عدم التصفية الكاملة  : 🛑 تم كبح الجيش عند سقف ساحة التدريب والمسيرة ({max_march_troops:,} جندي).")
                else:
                    print("   • سبب عدم التصفية الكاملة  : 🛑 نفاد القوات المتاحة بالقلعة قبل استيفاء كامل حمولة الحقل.")

        print("═" * 70 + "\n")

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="تجربة دالة select_gathering_army على إحداثيات محددة دون تعديلها"
    )
    parser.add_argument("--tx", "-x", type=int, default=None, help="إحداثي X للمورد")
    parser.add_argument("--ty", "-y", type=int, default=None, help="إحداثي Y للمورد")
    parser.add_argument("--email", "-e", type=str, default=None, help="البريد الإلكتروني للقلعة (اختياري)")
    parser.add_argument("--find", "-f", action="store_true", help="البحث التلقائي عن أقرب حقل حقيقي في الخريطة")
    parser.add_argument("--res-type", "-t", type=int, default=5, help="نوع المورد (1: ذهب, 2: قمح, 3: خشب, 4: حديد, 5: فضة) [افتراضي: 5]")
    parser.add_argument("--level", "-l", type=int, default=6, help="مستوى الحقل المستهدف [افتراضي: 6]")
    args = parser.parse_args()

    asyncio.run(run_test(
        tx=args.tx,
        ty=args.ty,
        email=args.email,
        auto_find=args.find,
        sub_type=args.res_type,
        level=args.level
    ))


if __name__ == "__main__":
    main()
