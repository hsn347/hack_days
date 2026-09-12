# -*- coding: utf-8 -*-
"""
tasks/merchant.py — مهمة الشراء والتحديث التلقائي من التاجر المتجول (Traveling Merchant)
══════════════════════════════════════════════════════════════════════════════════════

بروتوكول التاجر المتجول (Traveling Merchant Protocol - CMD 1024):
  - الاستعلام الأولي:  cmd: "1024", subcmd: "1", data: {} (REQ_INIT_STORESDATA)
  - تحديث المتجر:     cmd: "1024", subcmd: "2", data: {} (REQ_REFRESH_STORESDATA)
  - شراء سلعة:       cmd: "1024", subcmd: "3", data: {"shopItemID": shopItemID} (REQ_PURCHASE_GOODS)

الموارد المسموح الشراء بها (pricetype):
  - 1002: القمح / الطعام (Food)
  - 1003: الخشب (Wood)
  - 1004: الحديد (Iron)
  - 1005: الألماس / الفضة / البلور (Silver / Mithril)
  - ⛔ ممنوع منعاً باتاً الشراء بالذهب (1001 أو 1006) للحفاظ على رصيد الذهب.

ميزات الأمان والحماية المتقدمة (Anti-Ban & Resource Protection):
  1. 🛡️ نظام أمان ضد الحظر (Anti-Ban Human Delays & Jitter):
     - محاكاة دقيقة للسلوك البشري عبر فترات انتظار عشوائية (Randomized Jitter) بين كل عملية شراء وتحديث.
     - منع إرسال الطلبات المتتالية السريعة التي تثير اشتباه خوارزميات كشف البوتات.
  2. 🌾 فحص ذكي لتوفر الموارد وتجنب النقص (Resource Availability Check):
     - رصد دقيق للموارد غير المتوفرة (الرصيد = 0 أو أقل من سعر السلعة) واستبعادها فوراً دون محاولات خاطئة.
     - في حال نفاد كافة الموارد في القلعة، تتوقف المهمة فوراً دون حرق التحديثات أو استنزاف الذهب عبثاً.
  3. 🎯 التحديث التلقائي حتى إتمام 10 عمليات شراء صافية ناجحة.

الاستخدام كملف مستقل:
    python tasks/merchant.py --email "burcudemr@gmail.com"
    python tasks/merchant.py --email "user@gmail.com" --target 10 --max-gold 20
    python tasks/merchant.py --email "user@gmail.com" --min-res 50000
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
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# الموارد المسموح الشراء بها حصرياً وأيقوناتها
ALLOWED_RESOURCE_TYPES: Dict[int, Dict[str, str]] = {
    1002: {"name": "قمح", "icon": "🌾"},
    1003: {"name": "خشب", "icon": "🪵"},
    1004: {"name": "حديد", "icon": "⛏️"},
    1005: {"name": "ألماس/فضة", "icon": "💎"}
}

DISALLOWED_TYPES: set = {1001, 1006}  # الذهب والعملات الخاصة


class MerchantTask(BaseTask):
    """
    مهمة التاجر المتجول التلقائية مع محاكاة بشرية ضد الحظر وفحص ذكي لتوفر الموارد.
    """
    name = "merchant"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self.target_buys = int(self.config.get("target", self.config.get("count", 10)))
        self.max_gold_refresh = int(self.config.get("max_gold", self.config.get("max_gold_refresh", 20)))
        self.max_refreshes = int(self.config.get("max_refreshes", 60))
        self.min_resource_reserve = float(self.config.get("min_res", self.config.get("min_reserve", 0)))
        # وضع الأمان ومحاكاة السلوك البشري
        self.safe_mode = bool(self.config.get("safe", True))

    async def on_start(self):
        """انتظار وصول حزم البيانات الأساسية من السيرفر (cityCtrl ومخزون الموارد)."""
        for _ in range(15):
            has_city = "cityCtrl" in self.conn.init_data
            if has_city:
                break
            await asyncio.sleep(0.3)
        await asyncio.sleep(0.4)

    def _get_player_resources(self) -> Dict[int, float]:
        """استخراج رصيد الموارد الحالي للقلعة من cityCtrl مع التحقق من النوع."""
        city_ctrl = self.conn.init_data.get("cityCtrl", {})
        reslist = city_ctrl.get("reslist", {}) if isinstance(city_ctrl, dict) else {}
        resources = {}
        for resid in (1002, 1003, 1004, 1005):
            try:
                resources[resid] = float(reslist.get(str(resid), 0))
            except Exception:
                resources[resid] = 0.0
        return resources

    def _get_player_gold(self) -> int:
        """استخراج رصيد الذهب الحالي للاعب."""
        try:
            lord_info = self.conn.init_data.get("lordInfoCtrl", {})
            return int(lord_info.get("baseInfo", {}).get("gold", 0))
        except Exception:
            return 0

    async def _safe_delay(self, min_s: float, max_s: float, reason: str = ""):
        """تأخير بشري عشوائي ذكي (Jitter) للوقاية من الحظر."""
        if not self.safe_mode:
            await asyncio.sleep(0.5)
            return
        sleep_time = random.uniform(min_s, max_s)
        await asyncio.sleep(sleep_time)

    async def _query_initial_store(self) -> Optional[Dict[str, Any]]:
        """
        الاستعلام الأولي عن بضائع التاجر المتجول (cmd: 1024, subcmd: 1).
        """
        resp = await self.conn.query("1024", "1", {}, timeout=6)
        if not resp:
            await asyncio.sleep(0.8)
            resp = await self.conn.query("1024", "1", {}, timeout=6)

        if resp and str(resp.get("err", "0")) == "0":
            return resp.get("data", {})
        return None

    async def _refresh_store(self) -> Optional[Dict[str, Any]]:
        """
        طلب تحديث سلع المتجر (cmd: 1024, subcmd: 2).
        """
        resp = await self.conn.query("1024", "2", {}, timeout=6)
        if not resp:
            await asyncio.sleep(0.8)
            resp = await self.conn.query("1024", "2", {}, timeout=6)

        if resp and str(resp.get("err", "0")) == "0":
            return resp.get("data", {})
        return None

    async def _purchase_item(self, shop_item_id: int) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        إرسال طلب شراء سلعة محددة من المتجر (cmd: 1024, subcmd: 3).
        """
        payload = {"shopItemID": int(shop_item_id)}
        resp = await self.conn.query("1024", "3", payload, timeout=6)
        if not resp:
            await asyncio.sleep(0.5)
            resp = await self.conn.query("1024", "3", payload, timeout=6)

        err = str(resp.get("err", "0")) if resp else "timeout"
        if err == "0" and resp:
            data = resp.get("data", {})
            new_item = data.get("newShopItem")
            return True, new_item, "0"

        return False, None, err

    async def run(self) -> TaskResult:
        self.log.info(
            f"🛒 بدء مهمة التاجر المتجول | المستهدف: {self.target_buys} عملية شراء صافية بالموارد | "
            f"سقف الذهب للتحديث: {self.max_gold_refresh} | نظام الأمان ومكافحة الحظر: نشط 🛡️"
        )

        # ════════════════════════════════════════════════════════════════
        # المرحلة 1: الاستعلام الأولي وفحص المتجر والموارد
        # ════════════════════════════════════════════════════════════════
        store_data = await self._query_initial_store()
        if not store_data:
            msg = "⚠️ تعذر الاتصال بالتاجر المتجول أو استلام بيانات المتجر (cmd 1024 / 1)!"
            self.log.warning(msg)
            return TaskResult.fail(msg)

        is_open = store_data.get("isOpen", True)
        if not is_open:
            msg = "🚪 كشك التاجر المتجول مغلق حالياً أو غير موجود في القلعة."
            self.log.info(msg)
            return TaskResult.ok(msg, status="closed", retry_after=3600)

        shop_items: List[Dict[str, Any]] = list(store_data.get("shopItemArray", []))
        refresh_gold = int(store_data.get("refreshGold", 0))

        # فحص تفصيلي للموارد المتوفرة وغير المتوفرة في القلعة
        player_res = self._get_player_resources()
        available_res_names = []
        depleted_res_names = []

        res_status_lines = []
        for resid, meta in ALLOWED_RESOURCE_TYPES.items():
            bal = player_res.get(resid, 0)
            icon = meta["icon"]
            name = meta["name"]
            if bal > self.min_resource_reserve:
                available_res_names.append(name)
                res_status_lines.append(f"{icon} {name}: {int(bal):,} (متوفر)")
            else:
                depleted_res_names.append(name)
                res_status_lines.append(f"{icon} {name}: {int(bal):,} (غير متوفر ❌)")

        self.log.info("💰 حالة مخزون موارد القلعة:\n   • " + " | ".join(res_status_lines))

        if depleted_res_names:
            self.log.info(
                f"ℹ️ الموارد غير المتوفرة: [{', '.join(depleted_res_names)}] "
                f"— سيتم استبعاد أي سلع معروضة بهذه الموارد تلقائياً والتركيز فقط على الموارد المتوفرة."
            )

        # التحقق: هل يوجد أي مورد متاح أصلاً في القلعة؟
        if not available_res_names:
            msg = "🛑 كافة الموارد المسموحة للشراء (القمح، الخشب، الحديد، الألماس) غير متوفرة أو منعدمة في القلعة! تم إيقاف المهمة لتجنب التحديث العبثي."
            self.log.warning(msg)
            return TaskResult.ok(msg, status="no_resources", data={"resources": player_res})

        # محاكاة بشرية: توقف قصير كأن اللاعب يطالع المتجر قبل اتخاذ القرار
        await self._safe_delay(1.2, 2.0, "معاينة أولية للمتجر")

        successful_purchases: List[Dict[str, Any]] = []
        total_refreshes = 0
        consecutive_no_buy_refreshes = 0
        consecutive_errors = 0
        max_consecutive_errors = 3

        # ════════════════════════════════════════════════════════════════
        # المرحلة 2: حلقة الشراء والتحديث الذكية مع تدابير الأمان
        # ════════════════════════════════════════════════════════════════
        while len(successful_purchases) < self.target_buys:
            # التحقق من سلامة الاتصال بالسيرفر
            if not getattr(self.conn, "is_connected", True):
                self.log.warning("⚠️ انقطع الاتصال بالسيرفر أثناء عمل التاجر المتجول! إنهاء المهمة فوراً.")
                return TaskResult.fail("انقطع الاتصال بالسيرفر (Disconnected)")

            if consecutive_errors >= max_consecutive_errors:
                self.log.warning(
                    f"⚠️ تكرر فشل عمليات المتجر ({consecutive_errors}) مرات متتالية (timeout أو انقطاع اتصال)! إنهاء المهمة فوراً."
                )
                return TaskResult.fail("تكرر فشل عمليات الشراء أو التحديث من السيرفر")

            purchased_in_this_pass = False

            # فحص السلع المعروضة في المتجر حالياً
            for idx, item in enumerate(shop_items):
                if not isinstance(item, dict):
                    continue

                if not getattr(self.conn, "is_connected", True):
                    self.log.warning("⚠️ انقطع الاتصال بالسيرفر أثناء محاولة الشراء!")
                    return TaskResult.fail("انقطع الاتصال بالسيرفر")

                p_type = int(item.get("pricetype", 0))
                p_price = int(item.get("price", 0))
                shop_item_id = int(item.get("shopItemID", 0))
                item_id = int(item.get("itemId", 0))
                item_num = int(item.get("itemNum", 1))

                # 1. استبعاد السلع غير المسموحة (الذهب 1001/1006)
                if p_type not in ALLOWED_RESOURCE_TYPES:
                    continue

                res_meta = ALLOWED_RESOURCE_TYPES[p_type]
                res_name = res_meta["name"]
                res_icon = res_meta["icon"]
                cur_balance = player_res.get(p_type, 0)
                usable_balance = cur_balance - self.min_resource_reserve

                # 2. فحص كفاية رصيد المورد المحدد
                if cur_balance <= 0:
                    # المورد غير متوفر أصلاً في القلعة
                    continue

                if usable_balance < p_price:
                    # الرصيد أقل من السعر المطلوب أو يمس الاحتياطي
                    self.log.info(
                        f"⏭️ السلعة ({item_id}) بسعر {p_price:,} {res_name} تم تجاوزها (الرصيد المتاح: {int(cur_balance):,})."
                    )
                    continue

                # 3. محاكاة بشرية قبل النقر على زر الشراء (Anti-Ban Jitter)
                await self._safe_delay(1.2, 2.4, "تجهيز الشراء")

                self.log.info(
                    f"🛍️ جاري شراء سلعة {res_icon} (معرف: {item_id} × {item_num:,}) بسعر {p_price:,} {res_name} (رقم السلعة: {shop_item_id})..."
                )

                success, new_item, err_code = await self._purchase_item(shop_item_id)
                if success:
                    consecutive_errors = 0
                    player_res[p_type] = max(0, player_res[p_type] - p_price)
                    # تحديث الكاش المحلي في cityCtrl
                    city_ctrl = self.conn.init_data.get("cityCtrl", {})
                    if isinstance(city_ctrl, dict) and "reslist" in city_ctrl:
                        city_ctrl["reslist"][str(p_type)] = player_res[p_type]

                    successful_purchases.append({
                        "shopItemID": shop_item_id,
                        "itemId": item_id,
                        "itemNum": item_num,
                        "price": p_price,
                        "pricetype": p_type,
                        "resource": res_name
                    })

                    curr_count = len(successful_purchases)
                    self.log.info(
                        f"✅ [{curr_count}/{self.target_buys}] تم بنجاح شراء سلعة {res_icon} (معرف: {item_id} × {item_num:,}) "
                        f"مقابل {p_price:,} {res_name}! 🎉"
                    )

                    consecutive_no_buy_refreshes = 0
                    purchased_in_this_pass = True

                    # استبدال السلعة المشتراة بالسلعة البديلة الجديدة فوراً
                    if new_item and isinstance(new_item, dict):
                        shop_items[idx] = new_item
                    else:
                        shop_items[idx] = {}

                    # محاكاة بشرية بعد الشراء (Anti-Ban Jitter)
                    await self._safe_delay(1.3, 2.5, "انتظار بعد الشراء")

                    # إذا اكتمل الهدف المطلوب نتوقف فوراً
                    if len(successful_purchases) >= self.target_buys:
                        break
                else:
                    consecutive_errors += 1
                    self.log.warning(f"⚠️ فشل شراء السلعة {shop_item_id} (كود سيرفر: {err_code} | أخطاء متتالية: {consecutive_errors})")
                    if consecutive_errors >= max_consecutive_errors:
                        self.log.warning("⚠️ تكرر فشل الشراء من السيرفر! إيقاف المهمة فوراً لإعادة الاتصال.")
                        return TaskResult.fail("تكرر فشل الشراء (timeout)")
                    # في حال كان الخطأ متعلقاً بنقص المورد في السيرفر
                    if str(err_code) in ("1004", "1005", "1002", "1003"):
                        player_res[p_type] = 0

            # إذا قمنا بالشراء في هذه الدورة، نعيد الفحص فوراً (فقد تكون السلعة البديلة قابلة للشراء بالموارد أيضاً)
            if purchased_in_this_pass and len(successful_purchases) < self.target_buys:
                continue

            # 4. التحقق قبل طلب التحديث: هل ما زال هناك أي مورد متوفر للشراء أصلاً؟
            remaining_viable_resources = [
                meta["name"] for r_id, meta in ALLOWED_RESOURCE_TYPES.items()
                if (player_res.get(r_id, 0) - self.min_resource_reserve) >= 50
            ]
            if not remaining_viable_resources:
                self.log.warning(
                    "🛑 نفدت كافة الموارد الصالحة للشراء في القلعة! تم إيقاف التحديث حمايةً للمتجر ورصيد الذهب."
                )
                break

            # 5. لم يعد هناك أي سلعة تباع بالموارد المتاحة حالياً -> يلزم التحديث
            if len(successful_purchases) < self.target_buys:
                if total_refreshes >= self.max_refreshes:
                    self.log.warning(f"⚠️ تم بلوغ الحد الأقصى المسموح لعدد التحديثات ({self.max_refreshes})!")
                    break

                if refresh_gold > self.max_gold_refresh:
                    self.log.warning(
                        f"⚠️ تكلفة التحديث الحالية ({refresh_gold} ذهب) تتجاوز سقف الأمان المسموح به "
                        f"({self.max_gold_refresh} ذهب)! تم إيقاف التحديث حمايةً لرصيد الذهب."
                    )
                    break

                # فحص رصيد الذهب إذا كانت هناك تكلفة
                if refresh_gold > 0:
                    player_gold = self._get_player_gold()
                    if player_gold > 0 and player_gold < refresh_gold:
                        self.log.warning(f"⚠️ رصيد الذهب ({player_gold}) غير كافٍ لرسوم التحديث ({refresh_gold})!")
                        break

                cost_label = f"{refresh_gold} ذهب" if refresh_gold > 0 else "مجاناً"
                self.log.info(
                    f"🔄 لا توجد سلع أخرى بالموارد المتوفرة، جاري تحديث المتجر (التكلفة: {cost_label})..."
                )

                # محاكاة بشرية قبل النقر على زر التحديث
                await self._safe_delay(1.5, 3.0, "تفكير قبل التحديث")

                refreshed_data = await self._refresh_store()
                if refreshed_data:
                    consecutive_errors = 0
                    total_refreshes += 1
                    consecutive_no_buy_refreshes += 1
                    shop_items = list(refreshed_data.get("shopItemArray", []))
                    refresh_gold = int(refreshed_data.get("refreshGold", 0))
                    self.log.info(
                        f"✨ تم تحديث سلع المتجر بنجاح (تحديث رقم {total_refreshes} | تكلفة التحديث القادم: {refresh_gold} ذهب)"
                    )
                    # محاكاة انتظار تحميل المتجر الجديد
                    await self._safe_delay(1.2, 2.2, "معاينة العرض الجديد")
                else:
                    consecutive_errors += 1
                    self.log.warning(f"⚠️ تعذر تحديث سلع المتجر من السيرفر (أخطاء متتالية: {consecutive_errors})، إعادة محاولة بعد قليل...")
                    if consecutive_errors >= max_consecutive_errors:
                        self.log.warning("⚠️ تكرر تعذر تحديث المتجر! إيقاف المهمة فوراً لإعادة الاتصال.")
                        return TaskResult.fail("تكرر تعذر تحديث المتجر (timeout)")
                    await self._safe_delay(2.0, 4.0, "تراجع مؤقت")

        # ════════════════════════════════════════════════════════════════
        # المرحلة 3: ملخص التنفيذ والتقرير النهائي
        # ════════════════════════════════════════════════════════════════
        done_count = len(successful_purchases)
        if done_count >= self.target_buys:
            msg = f"🎉 اكتملت المهمة بنجاح! تم إتمام {done_count} عمليات شراء صافية بالموارد وتحديث المتجر {total_refreshes} مرات بأمان تام."
            status = "success"
        elif done_count > 0:
            msg = f"⚠️ تم إتمام {done_count}/{self.target_buys} عمليات شراء بالموارد وتحديث المتجر {total_refreshes} مرات (توقف بسبب سقف الموارد أو الذهب)."
            status = "partial"
        else:
            msg = f"🛑 لم تتم أي عمليات شراء (الموارد المتاحة غير كافية أو المتجر يعرض سلع الذهب فقط)."
            status = "no_action"

        self.log.info(f"🏁 {msg}")

        return TaskResult.ok(
            msg,
            status=status,
            retry_after=1800,
            data={
                "target_buys": self.target_buys,
                "completed_buys": done_count,
                "total_refreshes": total_refreshes,
                "purchases": successful_purchases
            }
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Traveling Merchant Task — مهمة الشراء والتحديث التلقائي للتاجر المتجول مع الأمان ضد الحظر")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--target", "-t", type=int, default=10, help="عدد عمليات الشراء الناجحة المطلوبة (افتراضياً: 10)")
    parser.add_argument("--max-gold", "-g", type=int, default=20, help="سقف الذهب المسموح به للتحديث الواحد (افتراضياً: 20)")
    parser.add_argument("--max-refreshes", "-r", type=int, default=60, help="الحد الأقصى لمرات التحديث (افتراضياً: 60)")
    parser.add_argument("--min-res", "-m", type=float, default=0, help="الحد الأدنى لاحتياطي الموارد الذي لا يُمس (افتراضياً: 0)")
    parser.add_argument("--fast", action="store_true", help="تعطيل فترات الأمان ضد الحظر والتنفيذ السريع")
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

        # انتظار وصول بيانات cityCtrl
        for _ in range(15):
            await asyncio.sleep(0.3)
            if "cityCtrl" in conn.init_data:
                break
        await asyncio.sleep(0.4)

        cfg = {
            "target": args.target,
            "max_gold": args.max_gold,
            "max_refreshes": args.max_refreshes,
            "min_res": args.min_res,
            "safe": not args.fast
        }
        task = MerchantTask(conn, cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
