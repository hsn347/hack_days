# -*- coding: utf-8 -*-
"""
tasks/watermill.py — مهمة الساقية وزيادة إنتاج موارد القلعة (City Resource Production Boost)
════════════════════════════════════════════════════════════════════════════════════════════
    python tasks/watermill.py --email "sumo-1234@hotmil.com" --type all --buy
تُفعّل الساقية ومضاعفة إنتاج المباني داخل القلعة (مزارع، مناشر، مناجم حديد، مناجم فضة):
  1. تفحص مباني الموارد من الذاكرة الحية (cityCtrl.blist - Zero-Request).
  2. تفحص التعزيزات النشطة (buffCtrl) وتتجاوز المباني المفعلة مسبقاً (صلاحية 24 ساعة).
  3. تفحص الحقيبة من الذاكرة الحية (backpackCtrl - Zero-Request) للتأكد من توفر أدوات التعزيز.
  4. تشتري تلقائياً من متجر التحالف (1010/40) بنقاط شرف التحالف إذا كانت الأدوات ناقصة والشراء مفعلاً.
  5. تُرسل أمر التفعيل الجماعي (1001/9) مع قاطع دارة ذكي.

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
import random
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
        "items": [501501],  # 501501 = تعزيز إنتاج القمح (24 ساعة)
    },
    "wood": {
        "bid": 202,
        "name": "🪵 مناشر الخشب",
        "buff_id": 5019,
        "items": [501401],  # 501401 = تعزيز إنتاج الخشب (24 ساعة)
    },
    "iron": {
        "bid": 203,
        "name": "⛏️ مناجم الحديد",
        "buff_id": 5021,
        "items": [501601],  # 501601 = تعزيز إنتاج الحديد (24 ساعة)
    },
    "silver": {
        "bid": 204,
        "name": "💎 مناجم الألماس",
        "buff_id": 5022,
        "items": [501701],  # 501701 = تعزيز إنتاج الألماس (24 ساعة)
    },
}

BOOST_DURATION_SEC = 86400    # مدة التعزيز 24 ساعة


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (WatermillTask)
# ════════════════════════════════════════════════════════════════════

class WatermillTask(BaseTask):
    """
    مهمة الساقية وزيادة إنتاج موارد القلعة (Watermill & Resource Production Boost).
    معمارية معيارية تعتمد بنسبة 100% على الذاكرة الحية (Zero-Request Architecture).
    """
    name = "watermill"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    def resolve_target_configs(self, raw_types: Any) -> Tuple[List[dict], str]:
        """
        استخراج إعدادات الموارد المستهدفة بناءً على مدخلات المستخدم.
        """
        TYPE_MAP = {
            "all": "all", "الكل": "all", "جميع": "all",
            "food": "food", "قمح": "food", "طعام": "food", "مزارع": "food",
            "wood": "wood", "خشب": "wood", "مناشر": "wood",
            "iron": "iron", "حديد": "iron", "مناجم حديد": "iron",
            "silver": "silver", "diamond": "silver", "فضة": "silver", "الماس": "silver", "ألماس": "silver",
            "مناجم فضة": "silver", "مناجم الماس": "silver", "مناجم ألماس": "silver"
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

        return target_bids, display_res

    def get_city_resource_buildings(self) -> Dict[int, List[int]]:
        """
        جلب وتصنيف مباني الموارد الجاهزة فقط (state == '0') من الذاكرة الحية (RAM / Zero-Request).
        ملاحظة صارمة: الاعتماد 100% على cityCtrl.blist في الذاكرة الحية بدون أي استعلام 1001/1 إطلاقاً.
        """
        blist = self.conn.init_data.get('cityCtrl', {}).get('blist', [])
        if not blist or not isinstance(blist, list):
            self.log.warning("⚠️ لا توجد بيانات مباني بالذاكرة الحية (cityCtrl.blist)")
            return {}

        valid_bids = {cfg['bid'] for cfg in BUILDING_CONFIG.values()}
        city_buildings: Dict[int, List[int]] = {}

        for b in blist:
            binfo = b.get('binfo', {}) if isinstance(b, dict) else {}
            try:
                bid = int(binfo.get('bid', 0))
                iid = int(binfo.get('iid', 0))
            except (ValueError, TypeError):
                continue

            state = str(binfo.get('state', '0'))
            # المبنى جاهز ومكتمل فقط بدون ترقية أو هدم (state == '0')
            if bid in valid_bids and state == '0':
                if bid not in city_buildings:
                    city_buildings[bid] = []
                city_buildings[bid].append(iid)

        return city_buildings

    def get_active_resource_buffs(self) -> Set[Tuple[int, int]]:
        """
        فحص التعزيزات النشطة السارية (< 24 ساعة) من الذاكرة الحية buffCtrl (RAM / Zero-Request).
        ترجع مجموعة من أزواج (bid, iid).
        """
        now_ts = int(time.time())
        active_buffs: Set[Tuple[int, int]] = set()

        buff_ctrl = self.conn.init_data.get('buffCtrl', [])
        if isinstance(buff_ctrl, list):
            for b in buff_ctrl:
                if not isinstance(b, dict):
                    continue
                extra = b.get('extra', {})
                try:
                    b_begin = int(b.get('beginTime', 0))
                except (ValueError, TypeError):
                    b_begin = 0

                if isinstance(extra, dict):
                    try:
                        e_bid = int(extra.get('bid', 0))
                        e_iid = int(extra.get('iid', 0))
                        if (now_ts - b_begin) < BOOST_DURATION_SEC:
                            active_buffs.add((e_bid, e_iid))
                    except (ValueError, TypeError):
                        pass

        return active_buffs

    def get_available_tools(self) -> Dict[int, int]:
        """
        استخراج رصيد أدوات تعزيز الموارد من الذاكرة الحية backpackCtrl حصراً (RAM / Zero-Request).
        ترجع خريطة {item_id: count}.
        """
        bag_counts: Dict[int, int] = {}
        bp_ctrl = self.conn.init_data.get('backpackCtrl', {})
        if isinstance(bp_ctrl, dict):
            for k, v in bp_ctrl.items():
                try:
                    item_id = int(k)
                    if isinstance(v, dict) and 'count' in v:
                        bag_counts[item_id] = int(v.get('count', 0))
                    elif str(v).isdigit():
                        bag_counts[item_id] = int(v)
                except (ValueError, TypeError):
                    continue
        return bag_counts

    def get_pending_activations(
        self,
        target_bids: List[dict],
        city_buildings: Dict[int, List[int]],
        active_buffs: Set[Tuple[int, int]]
    ) -> Dict[str, List[Dict[str, int]]]:
        """
        تحديد المباني التي تحتاج تفعيل لكل نوع مورد على حدة وتجاوز المعززة مسبقاً.
        ترجع قاموساً بمفتاح اسم المورد وقائمة المباني المطلوب تفعيلها.
        """
        pending: Dict[str, List[Dict[str, int]]] = {}

        for bcfg in target_bids:
            bid = bcfg['bid']
            bname = bcfg['name']
            iids = city_buildings.get(bid, [])

            to_activate = [
                {"bid": bid, "iid": iid, "mode": 1}
                for iid in iids
                if (bid, iid) not in active_buffs
            ]

            if to_activate:
                pending[bname] = to_activate
                self.log.debug(f"📌 {bname}: {len(to_activate)} مبنى بحاجة للتفعيل (من أصل {len(iids)})")
            else:
                self.log.debug(f"✓ {bname}: جميع المباني الـ {len(iids)} مفعلة ونشطة مسبقاً ✅")

        return pending

    async def get_alliance_shop_stock(self) -> Dict[int, int]:
        """
        جلب مخزون أدوات الموارد في متجر التحالف.
        يفحص الذاكرة المؤقتة (cached_packets) أولاً، وإذا لم تكن متوفرة يستعلم عبر 1010/39.
        """
        shop_stock: Dict[int, int] = {}

        # 1. فحص الحزمة المخزنة مسبقاً في cached_packets إن وجدت (Zero-Request)
        cached = self.conn.cached_packets.get(('1010', '39'))
        if cached and isinstance(cached, dict):
            c_data = cached.get('data', {})
            ret = c_data.get('retdata', {}) if isinstance(c_data, dict) else {}
            item_list = ret.get('itemlist', {})
            if isinstance(item_list, dict) and item_list:
                for k, v in item_list.items():
                    try:
                        shop_stock[int(k)] = int(v)
                    except (ValueError, TypeError):
                        pass
                if shop_stock:
                    self.log.debug(f"🏪 تم استخراج مخزون متجر التحالف من الذاكرة المؤقتة ({len(shop_stock)} صنف)")
                    return shop_stock

        # 2. استعلام السيرفر 1010/39 عند عدم التوفر بالذاكرة المؤقتة
        r_store = await self.conn.query('1010', '39', {}, timeout=8)
        if r_store and str(r_store.get('err', '0')) == '0' and isinstance(r_store.get('data'), dict):
            ret = r_store['data'].get('retdata', {})
            item_list = ret.get('itemlist', {})
            if isinstance(item_list, dict):
                for k, v in item_list.items():
                    try:
                        shop_stock[int(k)] = int(v)
                    except (ValueError, TypeError):
                        pass
            if shop_stock:
                self.log.info(f"🏪 تم جلب متجر التحالف بنجاح ({len(shop_stock)} نوع أداة متاحة للشراء)")
            else:
                self.log.info("ℹ️ متجر التحالف فارغ أو القلعة غير عضو في تحالف.")

        return shop_stock

    async def buy_missing_tools(
        self,
        item_id: int,
        missing_count: int,
        bname: str,
        shop_stock: Dict[int, int],
        bag_counts: Dict[int, int]
    ) -> int:
        """
        شراء أدوات التعزيز الناقصة من متجر التحالف بنقاط شرف التحالف (1010/40).
        ترجع عدد الأدوات التي تم شراؤها بنجاح.
        """
        in_store = shop_stock.get(item_id, 0)
        if in_store <= 0 or missing_count <= 0:
            return 0

        buy_qty = min(missing_count, in_store)
        self.log.info(f"🛒 جاري شراء {buy_qty} من أداة ({item_id}) لـ {bname} من متجر التحالف (المتوفر بالمتجر: {in_store})...")
        r_buy = await self.conn.query('1010', '40', {"itemid": item_id, "count": buy_qty}, timeout=8)
        if r_buy and str(r_buy.get('err', '0')) == '0':
            self.log.info(f"✅ تم شراء {buy_qty} أداة بنجاح من متجر التحالف!")
            bag_counts[item_id] = bag_counts.get(item_id, 0) + buy_qty
            shop_stock[item_id] -= buy_qty
            return buy_qty
        else:
            err_b = r_buy.get('err', 'unknown') if r_buy else 'timeout'
            self.log.warning(f"⚠️ تعذر شراء الأداة {item_id} (كود {err_b})")
            return 0

    async def activate_building_boost(
        self,
        can_activate: List[Dict[str, int]],
        bname: str
    ) -> Tuple[int, int]:
        """
        إرسال أمر التفعيل (1001/9) لمجموعة المباني المحددة.
        في حال تعذر قبول الدفعة بالكامل، يتم التراجع للتفعيل الفردي مع قاطع دارة ذكي عند الخطأ 1008.
        ترجع (عدد المباني الناجحة، عدد المباني الفاشلة).
        """
        if not can_activate:
            return 0, 0

        can_len = len(can_activate)
        r_batch = await self.conn.query('1001', '9', {"allData": can_activate}, timeout=8)
        if r_batch and str(r_batch.get('err', '0')) == '0':
            self.log.info(f"🎉 تم تفعيل {bname} بنجاح ({can_len} مبنى) دفعة واحدة! ✅")
            return can_len, 0

        err_b = str(r_batch.get('err', 'unknown')) if r_batch else 'timeout'
        self.log.warning(f"⚠️ دفعة {bname} لم تقبل بالكامل (كود {err_b}) — محاولة التفعيل الفردي...")

        success_s = 0
        failed_s = 0
        consecutive_fails = 0

        for item in can_activate:
            r_s = await self.conn.query('1001', '9', {"allData": [item]}, timeout=5)
            if r_s and str(r_s.get('err', '0')) == '0':
                success_s += 1
                consecutive_fails = 0
            else:
                failed_s += 1
                consecutive_fails += 1
                err_s = str(r_s.get('err', 'unknown')) if r_s else 'timeout'
                if err_s == '1008' or consecutive_fails >= 2:
                    self.log.warning(f"⚠️ توقف التفعيل الفردي لـ {bname} بعد فشلين متتاليين أو نفاد الأدوات (كود {err_s}).")
                    break
            await asyncio.sleep(random.uniform(0.9, 1.8))

        if success_s > 0:
            self.log.info(f"✅ تم تفعيل {success_s} من {bname} بنجاح عبر المحاولة الفردية.")

        return success_s, failed_s

    async def run(self) -> TaskResult:
        """
        تنفيذ مهمة الساقية بتناسق تام عبر الدوال المعيارية المستقلة.
        """
        cfg = self.config
        raw_types = cfg.get('types') or cfg.get('res_type', 'all')
        auto_buy  = bool(cfg.get('allow_shop_buy', cfg.get('auto_buy', cfg.get('allow_alliance_shop', False))))

        # 1. استخراج الموارد المستهدفة
        target_bids, display_res = self.resolve_target_configs(raw_types)
        if not target_bids:
            self.log.error(f"❌ لم يتم تحديد أي موارد صالحة للتعزيز: {raw_types}")
            return TaskResult.fail(f"نوع المورد غير معروف: {raw_types}")

        self.log.debug(f"💧 بدء مهمة الساقية لزيادة الإنتاج (الأنواع: {display_res} | شراء من متجر التحالف: {'مسموح' if auto_buy else 'معطل'})")

        # 2. مباني الموارد من الذاكرة الحية (cityCtrl.blist - Zero-Request)
        city_buildings = self.get_city_resource_buildings()
        if not city_buildings:
            self.log.info("ℹ️ لم يتم العثور على أي مباني موارد جاهزة بالذاكرة الحية.")
            return TaskResult.ok("لا توجد مباني موارد جاهزة بالذاكرة الحية", activated=0)

        # 3. التعزيزات النشطة (buffCtrl - Zero-Request)
        active_buffs = self.get_active_resource_buffs()

        # 4. تحديد المباني المطلوب تفعيلها وتجاوز النشطة
        pending_by_type = self.get_pending_activations(target_bids, city_buildings, active_buffs)
        if not pending_by_type:
            self.log.debug("🎉 جميع مباني الموارد المستهدفة مفعلة ونشطة حالياً — لا حاجة للتفعيل.")
            return TaskResult.ok("جميع مباني الموارد مفعلة ونشطة", activated=0)

        total_needed = sum(len(items) for items in pending_by_type.values())
        self.log.debug(f"⚡ إجمالي المباني المطلوب تفعيلها: {total_needed} مبنى")

        # 5. رصيد الأدوات من الذاكرة الحية (backpackCtrl - Zero-Request)
        bag_counts = self.get_available_tools()

        # 6. مخزون متجر التحالف (فقط إذا كان الشراء التلقائي مفعلاً)
        shop_stock: Dict[int, int] = {}
        if auto_buy:
            shop_stock = await self.get_alliance_shop_stock()

        # 7. معالجة وتفعيل كل نوع مورد بشكل مستقل
        success_count = 0
        failed_count = 0
        activated_details: Dict[str, int] = {}

        for bcfg in target_bids:
            bname = bcfg['name']
            type_needed = pending_by_type.get(bname, [])
            if not type_needed:
                continue

            needed_len = len(type_needed)
            item_candidates = bcfg['items']
            avail_in_bag = sum(bag_counts.get(it, 0) for it in item_candidates)

            self.log.info(f"🔍 {bname}: مطلوب تفعيل {needed_len} | الأدوات المتوفرة بالحقيبة: {avail_in_bag:,}")

            # محاولة الشراء إذا لم تكفِ الأدوات وكان الشراء مفعلاً
            if avail_in_bag < needed_len and auto_buy:
                missing = needed_len - avail_in_bag
                for item_id in item_candidates:
                    if missing <= 0:
                        break
                    bought = await self.buy_missing_tools(item_id, missing, bname, shop_stock, bag_counts)
                    missing -= bought

            # إعادة فحص المتوفر بعد الشراء
            avail_in_bag = sum(bag_counts.get(it, 0) for it in item_candidates)
            if avail_in_bag <= 0:
                self.log.info(f"⏭️ {bname}: تم تخطي التفعيل لعدم توفر أدوات تعزيز بالحقيبة أو متجر التحالف.")
                continue

            # تفعيل فقط المباني التي تكفيها الأدوات المتوفرة
            can_activate = type_needed[:avail_in_bag]
            can_len = len(can_activate)
            if can_len < needed_len:
                self.log.info(f"⚠️ {bname}: سيتم تفعيل {can_len} مبنى فقط بناءً على رصيد الأدوات المتوفر ({avail_in_bag}).")

            # إرسال أمر التفعيل
            s_ok, s_fail = await self.activate_building_boost(can_activate, bname)
            success_count += s_ok
            failed_count += s_fail

            if s_ok > 0:
                activated_details[bname] = s_ok
                # خصم الأدوات المستخدمة محلياً لمزامنة الرصيد
                used = s_ok
                for item_id in item_candidates:
                    c = bag_counts.get(item_id, 0)
                    sub = min(c, used)
                    bag_counts[item_id] = c - sub
                    used -= sub
                    if used <= 0:
                        break

            await asyncio.sleep(random.uniform(1.2, 2.4))

        self.log.info(f"🏁 النتيجة النهائية: تم تفعيل {success_count} مبنى | فشل/تجاوز: {failed_count}")

        if success_count > 0:
            return TaskResult.ok(
                f"✅ تم تفعيل الساقية لـ {success_count} مبنى بنجاح",
                activated=success_count,
                failed=failed_count,
                details=activated_details
            )
        else:
            return TaskResult.ok(
                "تم تخطي تفعيل الساقية (الأدوات غير متوفرة بالحقيبة أو متجر التحالف)",
                skipped=True,
                no_items=True,
                activated=0,
                retry_after=3600
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
