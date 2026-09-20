# -*- coding: utf-8 -*-
"""
tasks/transport.py — مهمة نقل وإمداد الموارد (Resource Transport / Aid)
════════════════════════════════════════════════════════════════════════

تُرسل فيالق نقل موارد إلى قلعة محددة بالإحداثيات (x, y) حتى امتلاء الطوابير.

معرفات الموارد (Resource IDs):
    1002 : 🌾 قمح (Food)
    1003 : 🪵 خشب (Wood)
    1004 : ⛏️ حديد / حجر (Iron / Stone)
    1005 : 💎 ألماس / ذهب (Diamond / Gold)

الإعدادات (config / Firebase):
    target_x          : إحداثي X للقلعة الهدف [افتراضي: 487]
    target_y          : إحداثي Y للقلعة الهدف [افتراضي: 290]
    resource_ids      : قائمة الموارد للتبرع بها، مثل [1002] أو [1002, 1003] [افتراضي: [1002]]
    max_capacity      : سعة الحمولة الكلية (يتم اكتشافها تلقائياً من لفل السوق إذا تُركت فارغة)
    tax_rate          : نسبة ضريبة السوق (تُكتشف تلقائياً)
    max_marches       : الحد الأقصى للمسيرات المتتالية [افتراضي: 6]
"""

from __future__ import annotations

import sys
import os

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  إعدادات افتراضية في رأس الملف (قابلة للتعديل والربط بـ Firebase)
# ════════════════════════════════════════════════════════════════════

DEFAULT_TARGET_X           = 344              # إحداثي X للهدف
DEFAULT_TARGET_Y           = 447              # إحداثي Y للهدف
DEFAULT_RESOURCE_IDS       = [1002 , 1003 , 1004 , 1005]           # [1002=قمح, 1003=خشب, 1004=حديد, 1005=ألماس/ذهب]


DEFAULT_MAX_CAPACITY       = 759000           # سعة الحمولة الكلية للقلعة (المستوى 40)
DEFAULT_TAX_RATE           = 0.10             # نسبة ضريبة السوق (10%)
DEFAULT_MAX_MARCHES        = 18                # الحد الأقصى للفيالق المتتالية

# أوزان الموارد في نظام اللعبة (Resource Weights)
# 1 قمح = 1 خشب | 1 حديد = 6 قمح | 1 ألماس = 24 قمح
RESOURCE_WEIGHTS = {
    1002: 1,   # 🌾 قمح (Food)
    1003: 1,   # 🪵 خشب (Wood)
    1004: 6,   # ⛏️ حديد / حجر (Iron / Stone)
    1005: 24,  # 💎 ألماس / ذهب (Diamond / Gold)
}

RESOURCE_NAMES = {
    1002: "🌾 قمح",
    1003: "🪵 خشب",
    1004: "⛏️ حديد/حجر",
    1005: "💎 ألماس/ذهب",
}


def get_market_capacity_for_level(level: int) -> Tuple[int, float]:
    """
    حساب سعة الحمولة الكلية ونسبة الضريبة بدقة لأي مستوى من مستويات مبنى السوق (1 إلى 100).
    المستوى 1: 10,000 (ضريبة 40%)
    المستوى 40: 759,000 (ضريبة 10%)
    """
    lv = max(1, min(100, int(level)))
    if lv <= 40:
        cap = int(10000 + (lv - 1) * (759000 - 10000) / 39)
        tax = max(0.10, 0.40 - (lv - 1) * (0.40 - 0.10) / 39)
    else:
        cap = int(759000 + (lv - 40) * 30000)
        tax = max(0.02, 0.10 - (lv - 40) * 0.0015)
    return cap, round(tax, 4)


def get_market_capacity_from_conn(conn: GameConnection) -> Tuple[int, float]:
    """
    استخراج مستوى مبنى السوق (bid=113) تلقائياً من بيانات القلعة واستنتاج السعة ونسبة الضريبة.
    """
    try:
        blist = conn.init_data.get('cityCtrl', {}).get('blist', [])
        market_lv = None
        for b in blist:
            binfo = b.get('binfo', {})
            if str(binfo.get('bid', '')) == '113':
                market_lv = int(binfo.get('lv', 40))
                break

        if market_lv is not None:
            cap, tax = get_market_capacity_for_level(market_lv)
            return cap, tax
    except Exception:
        pass

    return DEFAULT_MAX_CAPACITY, DEFAULT_TAX_RATE


def calculate_resource_allocation(res_ids: List[int], total_capacity: int = DEFAULT_MAX_CAPACITY, tax_rate: float = DEFAULT_TAX_RATE) -> List[Dict[str, int]]:
    """
    حساب الكميات الصافية الدقيقة لكل مورد بناءً على أوزان الموارد وضريبة السوق.
    المعادلة: Net_Capacity = Total_Capacity * (1 - TaxRate)
    لكل مورد: Amount = Net_Capacity / (عدد_الموارد * وزن_المورد)
    """
    if not res_ids:
        return []

    net_capacity = total_capacity * (1.0 - tax_rate)
    n = len(res_ids)

    result = []
    for rid in res_ids:
        w = RESOURCE_WEIGHTS.get(int(rid), 1)
        amount = int(net_capacity / (n * w))
        result.append({
            "id": int(rid),
            "num": amount
        })

    return result


def calculate_dynamic_resource_allocation(
    available_dict: Dict[int, int],
    res_ids: List[int],
    total_capacity: int = DEFAULT_MAX_CAPACITY,
    tax_rate: float = DEFAULT_TAX_RATE
) -> List[Dict[str, int]]:
    """
    توزيع ديناميكي ذكي بنسبة 100% من سعة السوق على الموارد المتوفرة بالقلعة حصراً:
    - يستبعد الموارد ذات الرصيد الصفري أو المحمي.
    - يقسم السعة بالتساوي بين الموارد المتاحة مع مراعاة أوزان الموارد (Food=1, Wood=1, Iron=6, Diamond=24).
    - إذا كان أحد الموارد لا يكفي لحصته، يأخذ كامل رصيده المتاح ويُعاد توزيع السعة المتبقية فوراً على بقية الموارد.
    - يضمن استغلال 100% من سعة السوق في كل مسيرة دون ترك أي سعة فارغة.
    """
    net_capacity = float(total_capacity) * (1.0 - tax_rate)

    # 1. فلترة الموارد التي لها رصيد متاح > 0
    active_rids = [int(rid) for rid in res_ids if available_dict.get(int(rid), 0) > 0]
    if not active_rids:
        return []

    allocated: Dict[int, int] = {rid: 0 for rid in active_rids}
    remaining_net_capacity = net_capacity
    remaining_rids = list(active_rids)

    while remaining_rids and remaining_net_capacity > 1.0:
        n = len(remaining_rids)
        share_per_res = remaining_net_capacity / n
        newly_exhausted = []

        for rid in remaining_rids:
            w = float(RESOURCE_WEIGHTS.get(rid, 1))
            max_units_for_share = int(share_per_res / w)
            avail_units = available_dict.get(rid, 0) - allocated[rid]

            if avail_units <= max_units_for_share:
                allocated[rid] += avail_units
                remaining_net_capacity -= avail_units * w
                newly_exhausted.append(rid)
            else:
                allocated[rid] += max_units_for_share
                remaining_net_capacity -= max_units_for_share * w

        if not newly_exhausted or newly_exhausted == remaining_rids:
            break
        for rid in newly_exhausted:
            remaining_rids.remove(rid)

    return [{"id": rid, "num": int(allocated[rid])} for rid in active_rids if allocated[rid] > 0]


# ════════════════════════════════════════════════════════════════════
#  دالة جلب معرف القلعة الهدف (Castle ID Lookup)
# ════════════════════════════════════════════════════════════════════

async def get_target_castle_info(conn: GameConnection, tx: int, ty: int, search_range: int = 5) -> Optional[Dict[str, Any]]:
    """
    البحث على الخريطة عن القلعة الموجودة عند الإحداثي (tx, ty) لجلب الـ id والاسم
    """
    try:
        r = await conn.query('2011', '3', {
            "mapType": 4,     # 4 = قلاع اللاعبين (Player Castles)
            "num": 20,
            "x": tx,
            "y": ty,
            "range": search_range
        }, timeout=4)

        if r and 'result' in r:
            results = r['result']
            for obj in results:
                if obj.get('x') == tx and obj.get('y') == ty:
                    return obj

            if results:
                closest = min(results, key=lambda o: abs(o.get('x', 0) - tx) + abs(o.get('y', 0) - ty))
                return closest
    except Exception as e:
        conn.log.warning(f"خطأ في استعلام موقع القلعة ({tx}, {ty}): {e}")

    return None


# ════════════════════════════════════════════════════════════════════
#  مهمة نقل الموارد (TransportTask)
# ════════════════════════════════════════════════════════════════════

class TransportTask(BaseTask):
    """
    مهمة إرسال فيالق نقل وتبرع بالموارد للقلعة المحددة.
    """
    name = "transport"

    async def run(self) -> TaskResult:
        cfg              = self.config
        target_x         = int(cfg.get('target_x', DEFAULT_TARGET_X))
        target_y         = int(cfg.get('target_y', DEFAULT_TARGET_Y))
        res_ids          = cfg.get('resource_ids', DEFAULT_RESOURCE_IDS)
        max_marches      = int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))

        if not isinstance(res_ids, list):
            res_ids = [res_ids]

        res_desc = ", ".join([RESOURCE_NAMES.get(rid, str(rid)) for rid in res_ids])
        self.log.info(f"🚚 بدء مهمة نقل الموارد إلى ({target_x}, {target_y}) | الموارد: [{res_desc}] | الحد الأقصى للمسيرات: {max_marches}")

        # 1. جلب معرف القلعة الهدف (Target Castle ID) أولاً لاستخراج البارتشن بدقة
        self.log.info(f"🔍 جلب بيانات ومعرف القلعة عند ({target_x}, {target_y})...")
        castle_info = await get_target_castle_info(self.conn, target_x, target_y)

        if castle_info and castle_info.get('id'):
            target_id = castle_info['id']
            actual_x  = castle_info.get('x', target_x)
            actual_y  = castle_info.get('y', target_y)
            c_lv      = castle_info.get('level', '?')
            self.log.info(f"🎯 تم العثور على القلعة: ID={target_id} عند ({actual_x}, {actual_y}) لفل={c_lv}")
        else:
            target_id = f"{target_x + 1}-{target_y + 1}-4-0-0"
            actual_x, actual_y = target_x, target_y
            self.log.warning(f"⚠️ لم يتم جلب الـ ID تلقائياً، سيتم استخدام المعرف القياسي: {target_id}")

        # 2. جلب معرف المملكة (kingdom_id / mapId)
        kingdom_id = 0
        if target_id and '-' in target_id:
            parts = target_id.split('-')
            if len(parts) >= 3 and parts[2].isdigit() and int(parts[2]) > 0:
                kingdom_id = int(parts[2])

        if not kingdom_id:
            uid_int = int(self.uid) if str(self.uid).isdigit() else 0
            if not uid_int:
                uid_int = int(getattr(self.conn, 'uid', 0) or 0)
            try:
                r_map = await self.conn.query('1002', '7', {"uid": uid_int}, timeout=4)
                if r_map and 'data' in r_map:
                    kingdom_id = int(r_map['data'].get('base', {}).get('partition', 0))
            except Exception:
                pass

        if not kingdom_id:
            kingdom_id = getattr(self.conn, 'server_id', 0) or getattr(self.conn, 'kingdom_id', 0)
        if not kingdom_id:
            kingdom_id = 4

        # 3. حساب سعة الحمولة والضريبة
        auto_cap, auto_tax = get_market_capacity_from_conn(self.conn)
        max_cap  = int(cfg.get('max_capacity') or auto_cap)
        tax_rate = float(cfg.get('tax_rate') or auto_tax)
        self.log.info(f"🏛️ سعة السوق المعتمدة: {max_cap:,} (ضريبة: {int(tax_rate*100)}%)")

        # 4. إرسال فيالق متتالية بتوزيع ديناميكي 100%
        sent_count = 0
        total_transported = 0

        city = self.conn.init_data.get('cityCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        reslist = city.get('reslist', {}) if isinstance(city, dict) else {}
        saferes = city.get('saferes', {}) if isinstance(city, dict) else {}

        for i in range(1, max_marches + 1):
            self.log.info(f"⚔️ محاولة إرسال فيلق النقل رقم ({i}/{max_marches})...")

            avail_dict = {}
            for rid in res_ids:
                rid_str = str(rid)
                tot = float(reslist.get(rid_str, 0))
                saf = float(saferes.get(rid_str, 0))
                avail_dict[int(rid)] = max(0, int(tot - saf))

            current_march_resources = calculate_dynamic_resource_allocation(
                available_dict=avail_dict,
                res_ids=res_ids,
                total_capacity=max_cap,
                tax_rate=tax_rate
            )

            if not current_march_resources:
                self.log.warning("⚠️ لا توجد موارد كافية قابلة للنقل لإرسال فيلق جديد.")
                break

            current_payload_units = sum(r['num'] for r in current_march_resources)

            march_payload = {
                "needSend": False,
                "runePages": [1],
                "heros": [],
                "pets": [],
                "matrixType": 4,      # 4 = نقل موارد
                "moveLineType": 5,    # 5 = مسار خط النقل
                "mapId": int(kingdom_id),
                "data": {
                    "to": {
                        "x": int(actual_x),
                        "y": int(actual_y),
                        "id": str(target_id)
                    },
                    "data": {
                        "resourceList": current_march_resources
                    },
                    "army": []
                }
            }

            r_send = await self.conn.query('1007', '2', march_payload)
            if not r_send:
                self.log.error("❌ لم يستجب السيرفر لأمر النقل!")
                break

            err = str(r_send.get('err', '0'))
            if err == '0':
                sent_count += 1
                total_transported += current_payload_units
                self.log.info(f"✅ تم إرسال فيلق النقل ({i}) بنجاح! 🚚 حمولة: {current_payload_units:,}")

                for itm in current_march_resources:
                    r_str = str(itm['id'])
                    if r_str in reslist:
                        try:
                            reslist[r_str] = max(0.0, float(reslist[r_str]) - float(itm['num']))
                        except Exception:
                            pass

                await asyncio.sleep(5.0)  # حماية من الحظر - تأخير بين المسيرات
            elif err in ('8004', '9007004'):
                self.log.info(f"🛑 اكتملت طوابير المسيرات للقلعة (الحد الأقصى - كود {err}).")
                if sent_count == 0:
                    return TaskResult.queue_full()
                break
            elif err == '8009':
                self.log.warning(f"⚠️ الموارد غير كافية بالقلعة لإرسال هذه الكمية (كود 8009).")
                break
            elif err in ('8062', '8063', '8060'):
                self.log.warning(f"⚠️ تعذر الإرسال للهدف (كود {err})")
                break
            else:
                self.log.error(f"❌ فشل إرسال فيلق النقل - كود الخطأ: {err}")
                break

        self.log.info(f"🏁 ملخص النقل: تم إرسال {sent_count} فيلق | إجمالي الموارد المنقولة: {total_transported:,}")
        if sent_count > 0:
            return TaskResult.ok(f"✅ تم إرسال {sent_count} فيلق نقل", sent=sent_count, total=total_transported)
        return TaskResult.fail("لم يتم إرسال أي فيلق نقل", retry_after=180)


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Transport Bot — نقل وإمداد الموارد")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--x", type=int, default=DEFAULT_TARGET_X, help=f"إحداثي X للقلعة الهدف [افتراضي: {DEFAULT_TARGET_X}]")
    parser.add_argument("--y", type=int, default=DEFAULT_TARGET_Y, help=f"إحداثي Y للقلعة الهدف [افتراضي: {DEFAULT_TARGET_Y}]")
    parser.add_argument("--res", type=int, nargs="+", default=DEFAULT_RESOURCE_IDS, help="معرفات الموارد: 1002=قمح 1003=خشب 1004=حديد 1005=ألماس [افتراضي: 1002]")
    parser.add_argument("--capacity", "-c", type=int, help="سعة الحمولة الكلية (اختياري، يكتشف تلقائياً)")
    parser.add_argument("--tax", "-t", type=float, help="نسبة ضريبة السوق (اختياري، يكتشف تلقائياً)")
    parser.add_argument("--marches", "-m", type=int, default=DEFAULT_MAX_MARCHES, help=f"عدد الفيالق [افتراضي: {DEFAULT_MAX_MARCHES}]")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    from core.session_manager import SessionManager

    async def _main():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة في session_cache.json!")
            return

        target_email = args.email or next(iter(accounts.keys()))
        acc = accounts.get(target_email)
        if not acc:
            print(f"❌ الحساب {target_email} غير موجود!")
            return

        conn = GameConnection(acc)
        if not await conn.connect():
            print("❌ فشل الاتصال بالسيرفر!")
            return

        for _ in range(10):
            await asyncio.sleep(2.0)  # حماية من الحظر
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "target_x": args.x,
            "target_y": args.y,
            "resource_ids": args.res,
            "max_capacity": args.capacity,
            "tax_rate": args.tax,
            "max_marches": args.marches
        }

        task = TransportTask(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
    