# -*- coding: utf-8 -*-
"""
tasks/watermill.py — مهمة الساقية وزيادة إنتاج موارد القلعة (City Resource Production Boost)
════════════════════════════════════════════════════════════════════════════════════════════
    python tasks/watermill.py --email "sumo-1234@hotmil.com" --type all --buy
تُفعّل الساقية ومضاعفة إنتاج المباني داخل القلعة (مزارع، مناشر، مناجم حديد، مناجم فضة):
  1. تفحص المباني داخل القلعة (1001/1).
  2. تفحص التعزيزات النشطة (buffCtrl) وتتجاوز المباني المفعلة مسبقاً (صلاحية 24 ساعة).
  3. تفحص الحقيبة (1004/1) للتأكد من توفر أدوات التسريع الخاصة أو العامة (300201).
  4. تشتري تلقائياً من متجر التحالف (1010/40) بنقاط شرف التحالف إذا كانت الأدوات ناقصة.
  5. تُرسل أمر التفعيل الجماعي (1001/9).

الاستخدام كملف مستقل:
    python tasks/watermill.py --email "meik.gaertner2306.MGr@gmail.com" --type all --buy
    python tasks/watermill.py --email "sumo-1234@hotmil.com" --type wood
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  خريطة مباني الموارد وأدوات التعزيز
# ════════════════════════════════════════════════════════════════════

BUILDING_CONFIG = {
    "food": {
        "bid": 201,
        "name": "🌾 مزارع القمح",
        "buff_id": 5020,
        "items": [501501, 501201],  # 501501 = تعزيز إنتاج القمح (24 ساعة)
    },
    "wood": {
        "bid": 202,
        "name": "🪵 مناشر الخشب",
        "buff_id": 5019,
        "items": [501401, 501301],  # 501401 = تعزيز إنتاج الخشب (24 ساعة)
    },
    "iron": {
        "bid": 203,
        "name": "⛏️ مناجم الحديد",
        "buff_id": 5021,
        "items": [501601],          # 501601 = تعزيز إنتاج الحديد (24 ساعة)
    },
    "silver": {
        "bid": 204,
        "name": "🪙 مناجم الفضة/الألماس",
        "buff_id": 5022,
        "items": [501701],          # 501701 = تعزيز إنتاج الفضة/الألماس (24 ساعة)
    },
}

BOOST_DURATION_SEC = 86400    # مدة التعزيز 24 ساعة


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (WatermillTask)
# ════════════════════════════════════════════════════════════════════

class WatermillTask(BaseTask):
    """
    مهمة الساقية وزيادة إنتاج موارد القلعة.
    """
    name = "watermill"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    async def run(self) -> TaskResult:
        cfg = self.config
        raw_types = cfg.get('types') or cfg.get('res_type', 'all')
        auto_buy  = bool(cfg.get('allow_shop_buy', cfg.get('auto_buy', True)))

        TYPE_MAP = {
            "all": "all", "الكل": "all", "جميع": "all",
            "food": "food", "قمح": "food", "طعام": "food", "مزارع": "food",
            "wood": "wood", "خشب": "wood", "مناشر": "wood",
            "iron": "iron", "حديد": "iron", "مناجم حديد": "iron",
            "silver": "silver", "فضة": "silver", "الماس": "silver", "مناجم فضة": "silver"
        }

        resolved_types: Set[str] = set()
        if isinstance(raw_types, list):
            items = raw_types
        else:
            items = str(raw_types).replace("،", ",").split(",")

        for item in items:
            key = str(item).strip().lower()
            if key in TYPE_MAP:
                resolved_types.add(TYPE_MAP[key])

        if not resolved_types or "all" in resolved_types:
            target_bids = list(BUILDING_CONFIG.values())
            display_res = "الكل (جميع الموارد)"
        else:
            target_bids = [BUILDING_CONFIG[t] for t in resolved_types if t in BUILDING_CONFIG]
            display_res = "، ".join([BUILDING_CONFIG[t]['name'] for t in resolved_types if t in BUILDING_CONFIG])

        if not target_bids:
            self.log.error(f"❌ لم يتم تحديد أي موارد صالحة للتعزيز: {raw_types}")
            return TaskResult.fail(f"نوع المورد غير معروف: {raw_types}")

        self.log.info(f"💧 بدء مهمة الساقية لزيادة الإنتاج (الأنواع: {display_res} | شراء من متجر التحالف: {'مسموح' if auto_buy else 'معطل'})")

        # 2. جلب مباني القلعة (1001/1)
        r_city = await self.conn.query('1001', '1', {}, timeout=8)
        if not r_city or not isinstance(r_city.get('data'), dict):
            self.log.error("❌ فشل جلب بيانات مباني المدينة (1001/1)")
            return TaskResult.fail("فشل جلب مباني المدينة")

        blist = r_city['data'].get('blist', [])
        if not isinstance(blist, list):
            self.log.error("❌ مصفوفة المباني غير صالحة")
            return TaskResult.fail("بيانات المباني غير صالحة")

        # تصنيف المباني حسب bid
        city_buildings: Dict[int, List[int]] = {}
        for b in blist:
            binfo = b.get('binfo', {}) if isinstance(b, dict) else {}
            bid = int(binfo.get('bid', 0))
            iid = int(binfo.get('iid', 0))
            if bid > 0:
                if bid not in city_buildings:
                    city_buildings[bid] = []
                city_buildings[bid].append(iid)

        # 3. فحص التعزيزات النشطة (buffCtrl)
        now_ts = int(time.time())
        active_buffs: Set[Tuple[int, int]] = set()  # (bid, iid)

        buff_ctrl = self.conn.init_data.get('buffCtrl', [])
        if isinstance(buff_ctrl, list):
            for b in buff_ctrl:
                if not isinstance(b, dict): continue
                extra = b.get('extra', {})
                b_begin = int(b.get('beginTime', 0))
                if isinstance(extra, dict):
                    try:
                        e_bid = int(extra.get('bid', 0))
                        e_iid = int(extra.get('iid', 0))
                        # إذا لم تنتهِ الـ 24 ساعة
                        if (now_ts - b_begin) < BOOST_DURATION_SEC:
                            active_buffs.add((e_bid, e_iid))
                    except Exception:
                        pass

        # 4. تجميع المباني التي تحتاج تفعيل
        needed_activations: List[Dict[str, int]] = []
        total_needed_count = 0
        summary_by_type: Dict[str, int] = {}

        for bcfg in target_bids:
            bid = bcfg['bid']
            bname = bcfg['name']
            iids = city_buildings.get(bid, [])

            to_activate = []
            for iid in iids:
                if (bid, iid) not in active_buffs:
                    to_activate.append({"bid": bid, "iid": iid, "mode": 1})

            if to_activate:
                needed_activations.extend(to_activate)
                summary_by_type[bname] = len(to_activate)
                total_needed_count += len(to_activate)
                self.log.info(f"📌 {bname}: {len(to_activate)} مبنى بحاجة للتفعيل (من أصل {len(iids)})")
            else:
                self.log.info(f"✓ {bname}: جميع المباني الـ {len(iids)} مفعلة ونشطة مسبقاً ✅")

        if not needed_activations:
            self.log.info("🎉 جميع مباني الموارد المستهدفة مفعلة ونشطة حالياً — لا حاجة للتفعيل.")
            return TaskResult.ok("جميع مباني الموارد مفعلة ونشطة", activated=0)

        self.log.info(f"⚡ إجمالي المباني المطلوب تفعيلها: {total_needed_count} مبنى")

        # 5. فحص توفر الأدوات في الحقيبة (1004/1)
        r_bag = await self.conn.query('1004', '1', {}, timeout=8)
        bag_counts: Dict[int, int] = {}
        if r_bag and isinstance(r_bag.get('data'), dict):
            for k, v in r_bag['data'].items():
                if isinstance(v, dict) and 'count' in v:
                    try: bag_counts[int(k)] = int(v.get('count', 0))
                    except: pass
                elif str(v).isdigit():
                    try: bag_counts[int(k)] = int(v)
                    except: pass

        # 6. جلب متجر التحالف (1010/39) إذا كان الشراء التلقائي مفعّلاً
        #    ملاحظة: لا نشترط الكشف عن التحالف لأن الكشف قد يفشل أحياناً
        #    بينما القلعة فعلاً عضو — نحاول دائماً عند auto_buy=True
        shop_stock: Dict[int, int] = {}
        if auto_buy:
            r_store = await self.conn.query('1010', '39', {}, timeout=8)
            if r_store and str(r_store.get('err', '0')) == '0' and isinstance(r_store.get('data'), dict):
                ret = r_store['data'].get('retdata', {})
                item_list = ret.get('itemlist', {})
                if isinstance(item_list, dict):
                    for k, v in item_list.items():
                        try: shop_stock[int(k)] = int(v)
                        except: pass
                if shop_stock:
                    self.log.info(f"🏪 تم جلب متجر التحالف بنجاح ({len(shop_stock)} نوع أداة متاحة للشراء)")
                else:
                    self.log.info("ℹ️ متجر التحالف فارغ أو القلعة غير عضو في تحالف — سيتم الاعتماد على الحقيبة فقط.")

        # 7. معالجة وتفعيل كل نوع مبنى بشكل مستقل
        success_count = 0
        failed_count  = 0
        activated_details: Dict[str, int] = {}

        for bcfg in target_bids:
            bid = bcfg['bid']
            bname = bcfg['name']
            item_candidates = bcfg['items']
            iids = city_buildings.get(bid, [])

            # المباني التي تحتاج تفعيل لهذا النوع
            type_needed = [{"bid": bid, "iid": iid, "mode": 1} for iid in iids if (bid, iid) not in active_buffs]
            if not type_needed:
                continue

            needed_len = len(type_needed)
            
            # حساب الرصيد المتوفر في الحقيبة من أي أداة تدعم هذا المورد
            avail_in_bag = sum(bag_counts.get(iid, 0) for iid in item_candidates)
            self.log.info(f"🔍 {bname}: مطلوب تفعيل {needed_len} | الأدوات المتوفرة بالحقيبة: {avail_in_bag:,}")

            # محاولة الشراء التلقائي من متجر التحالف إذا لم تتوفر أدوات كافية
            if avail_in_bag < needed_len and auto_buy:
                missing = needed_len - avail_in_bag
                # البحث عن الأداة المتوفرة في مخزون المتجر
                bought = 0
                for item_id in item_candidates:
                    in_store = shop_stock.get(item_id, 0)
                    if in_store > 0 and missing > 0:
                        buy_qty = min(missing, in_store)
                        self.log.info(f"🛒 جاري شراء {buy_qty} من أداة ({item_id}) لـ {bname} من متجر التحالف (المتوفر بالمتجر: {in_store})...")
                        r_buy = await self.conn.query('1010', '40', {"itemid": item_id, "count": buy_qty}, timeout=8)
                        if r_buy and str(r_buy.get('err', '0')) == '0':
                            self.log.info(f"✅ تم شراء {buy_qty} أداة بنجاح من متجر التحالف!")
                            bag_counts[item_id] = bag_counts.get(item_id, 0) + buy_qty
                            shop_stock[item_id] -= buy_qty
                            missing -= buy_qty
                            bought += buy_qty
                        else:
                            err_b = r_buy.get('err', 'unknown') if r_buy else 'timeout'
                            self.log.warning(f"⚠️ تعذر شراء الأداة {item_id} (كود {err_b})")

            # إرسال دفعة التفعيل لهذا النوع
            r_batch = await self.conn.query('1001', '9', {"allData": type_needed}, timeout=8)
            if r_batch and str(r_batch.get('err', '0')) == '0':
                success_count += needed_len
                activated_details[bname] = needed_len
                self.log.info(f"🎉 تم تفعيل {bname} بنجاح ({needed_len} مبنى) دفعة واحدة! ✅")
            else:
                # إذا فشلت الدفعة الكاملة، نفعّل مبنى مبنى
                err_b = r_batch.get('err', 'unknown') if r_batch else 'timeout'
                self.log.warning(f"⚠️ دفعة {bname} لم تقبل بالكامل (كود {err_b}) — محاولة التفعيل الفردي...")
                type_ok = 0
                for item in type_needed:
                    r_s = await self.conn.query('1001', '9', {"allData": [item]}, timeout=5)
                    if r_s and str(r_s.get('err', '0')) == '0':
                        success_count += 1
                        type_ok += 1
                    else:
                        failed_count += 1
                    await asyncio.sleep(0.3)
                if type_ok > 0:
                    activated_details[bname] = type_ok
                    self.log.info(f"✅ تم تفعيل {type_ok} من {bname}")

            await asyncio.sleep(0.5)

        self.log.info(f"🏁 النتيجة النهائية: تم تفعيل {success_count} مبنى | فشل/تجاوز: {failed_count}")

        if success_count > 0:
            return TaskResult.ok(
                f"✅ تم تفعيل الساقية لـ {success_count} مبنى بنجاح",
                activated=success_count,
                failed=failed_count,
                details=activated_details
            )
        else:
            return TaskResult.fail(
                "لم يتم تفعيل أي مبنى (الأدوات غير كافية)",
                retry_after=1800
            )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Watermill / Resource Boost Task — مهمة الساقية وزيادة الإنتاج")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--type", "-t", default="all", choices=["all", "food", "wood", "iron", "silver"],
                        help="نوع المباني المراد تعزيزها: all, food, wood, iron, silver [افتراضي: all]")
    parser.add_argument("--buy", action="store_true", default=True,
                        help="شراء الأدوات الناقصة تلقائياً من متجر التحالف [افتراضي: True]")
    parser.add_argument("--no-buy", dest="buy", action="store_false",
                        help="تعطيل الشراء التلقائي من متجر التحالف")
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

        for _ in range(12):
            await asyncio.sleep(1.0)
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "res_type": args.type,
            "auto_buy": args.buy,
        }

        task = WatermillTask(conn, task_cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
