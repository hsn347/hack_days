# -*- coding: utf-8 -*-
"""
tasks/torch_chest.py — مهمة صندوق مشعل رويال (شراء الصندوق من المتجر وفتحه من الحقيبة)
═════════════════════════════════════════════════════════════════════════════════════

المهام المنفذة:
  1. الاستعلام عن وجود صناديق في المتجر (shopItemID: 1000182، اسم الصندوق: "صندوق الشعلة" / itemId: 811037).
     إذا لم يكن الصندوق موجوداً بالمتجر أو انتهت صلاحيته، يتم إنهاء المهمة وتخطيها فوراً.
  2. إذا كان خيار الشراء مفعلاً (torch_chest):
     يتم شراء جميع الصناديق المتاحة حتى الحد الأقصى للفعالية بالكامل عبر الأمر 1034/2.
  3. إذا كان خيار الفتح مفعلاً (open_torch_chest):
     يتم فحص الحقيبة وفتح جميع صناديق المشعل المتوفرة بالكامل عبر الأمر 1004/2.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from game_client import GameConnection
from tasks.base_task import BaseTask, TaskResult

# الثوابت الخاصة بصندوق مشعل رويال
SHOP_ITEM_ID = 1000182    # معرف الصندوق في المتجر (صندوق الشعلة)
ITEM_ID = 811037          # معرف العنصر داخل الحقيبة وعند الفتح
DEFAULT_PRICE = 40        # السعر الافتراضي بالذهب
DEFAULT_LIMIT = 15        # الحد الأقصى الافتراضي للشراء


class TorchChestTask(BaseTask):
    """
    مهمة فحص وشراء وفتح صندوق مشعل رويال في المتجر والحقيبة.
    """
    name = "torch_chest"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        cfg = self.config or {}
        # دعم تفعيل الشراء سواء من المفتاح buy_enabled أو enabled المباشر
        self.buy_enabled: bool = bool(cfg.get("buy_enabled", cfg.get("enabled", False)))
        # دعم تفعيل الفتح
        self.open_enabled: bool = bool(cfg.get("open_enabled", False))

    async def run(self) -> TaskResult:
        """
        تنفيذ دورة مهمة صندوق مشعل رويال:
        1. استعلام وفحص توفر الصندوق في المتجر.
        2. شراء الصناديق حتى الحد الأقصى إن كان الشراء مفعلاً.
        3. فتح جميع الصناديق المتوفرة في الحقيبة إن كان الفتح مفعلاً.
        """
        if not self.buy_enabled and not self.open_enabled:
            return TaskResult.ok("⏭️ تم تخطي مهمة صندوق مشعل رويال (الخيارات غير مفعّلة)")

        self.log.info("🔍 جاري فحص توفر صندوق الشعلة (مشعل رويال) في المتجر...")

        # 1. فحص توفر الصندوق في المتجر
        config_data = await self._get_shop_config()
        torch_item = self._find_torch_item(config_data)

        if not torch_item:
            msg = "⏭️ صندوق الشعلة (مشعل رويال) غير متوفر في المتجر حالياً — تم إنهاء المهمة."
            self.log.info(msg)
            return TaskResult.ok(msg, in_store=False)

        self.log.info(f"✨ تم العثور على صندوق الشعلة في المتجر (shopItemID: {SHOP_ITEM_ID}) 🎉")

        bought_count = 0
        opened_count = 0

        # 2. الشراء بالذهب إذا كان خيار الشراء مفعلاً
        if self.buy_enabled:
            bought_count = await self._buy_torch_chests(torch_item)
            if self.is_stopped():
                return TaskResult.ok("🛑 تم إيقاف المهمة أثناء الشراء")

        # 3. الفتح إذا كان خيار الفتح مفعلاً
        if self.open_enabled:
            opened_count = await self._open_torch_chests()

        summary_parts = []
        if self.buy_enabled:
            summary_parts.append(f"شراء: {bought_count}")
        if self.open_enabled:
            summary_parts.append(f"فتح: {opened_count}")

        status_str = " | ".join(summary_parts) if summary_parts else "تم بنجاح"
        return TaskResult.ok(
            f"✅ اكتملت مهمة صندوق مشعل رويال ({status_str})",
            bought=bought_count,
            opened=opened_count
        )

    # ──────────────────────────────────────────────────────────────────
    #  دوال مساعدة لفحص المتجر وشراء الصناديق
    # ──────────────────────────────────────────────────────────────────

    async def _get_shop_config(self) -> Dict[str, Any]:
        """قراءة وتحديث بيانات المتجر من init_data أو عبر طلب 1034/1 المباشر."""
        item_shop = getattr(self.conn, "init_data", {}).get("itemShop", {})
        config_data = item_shop.get("configData", {}) if isinstance(item_shop, dict) else {}

        # إذا لم تكن بيانات المتجر موجودة في init_data، نستعلم عنها عبر 1034/1
        if not config_data:
            try:
                r_shop = await self.conn.query("1034", "1", {}, timeout=8)
                if r_shop and isinstance(r_shop.get("data"), dict):
                    retdata = r_shop.get("data", {}).get("retdata", {}) or r_shop.get("data", {})
                    if "itemShop" in retdata and isinstance(retdata["itemShop"], dict):
                        config_data = retdata["itemShop"].get("configData", {})
            except Exception as e:
                self.log.debug(f"استعلام المتجر 1034/1: {e}")

        if not config_data:
            item_shop = getattr(self.conn, "init_data", {}).get("itemShop", {})
            if isinstance(item_shop, dict):
                config_data = item_shop.get("configData", {})

        return config_data if isinstance(config_data, dict) else {}

    def _find_torch_item(self, config_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """البحث عن عنصر صندوق الشعلة والتأكد من سريانه."""
        candidate = None
        if str(SHOP_ITEM_ID) in config_data:
            candidate = config_data[str(SHOP_ITEM_ID)]
        elif SHOP_ITEM_ID in config_data:
            candidate = config_data[SHOP_ITEM_ID]
        else:
            for item in config_data.values():
                if isinstance(item, dict):
                    if int(item.get("itemId", 0)) == ITEM_ID or int(item.get("id", 0)) == ITEM_ID:
                        candidate = item
                        break

        if not isinstance(candidate, dict):
            return None

        # فحص وقت انتهاء الفعالية إن وجد
        endtime = int(candidate.get("endtime", 0))
        now_ts = int(time.time())
        if endtime > 0 and now_ts > endtime:
            self.log.info(f"⏳ فعالية صندوق الشعلة في المتجر منتهية (الوقت الحالي تجاوز endtime: {endtime}).")
            return None

        return candidate

    async def _buy_torch_chests(self, torch_item: Dict[str, Any]) -> int:
        """شراء صناديق مشعل رويال حتى الحد الأقصى للفعالية بالذهب."""
        mgr = getattr(self.conn, "init_data", {}).get("shopItemBuyTimesMgr", {})
        buy_entry = mgr.get(str(SHOP_ITEM_ID), mgr.get(SHOP_ITEM_ID, {})) if isinstance(mgr, dict) else {}

        buy_num = int(buy_entry.get("buyNum", 0)) if isinstance(buy_entry, dict) else 0
        limit_num = int(torch_item.get("limitNum", DEFAULT_LIMIT))
        price = int(torch_item.get("discountPrice") or torch_item.get("price", DEFAULT_PRICE))
        remaining = max(0, limit_num - buy_num)

        if remaining <= 0:
            self.log.info(f"ℹ️ تم شراء جميع صناديق الشعلة المتاحة للفعالية مسبقاً ({buy_num}/{limit_num}).")
            return 0

        self.log.info(f"🪙 جاري شراء {remaining} صندوق شعلة بالذهب (سعر الحبة: {price} ذهب، المتبقي: {remaining}/{limit_num})...")

        # تجربة الشراء المجمع بالكمية كاملة دفعة واحدة
        payload = {
            "shopItemID": SHOP_ITEM_ID,
            "num": remaining,
            "discountFlag": False
        }

        r_buy = await self.conn.query("1034", "2", payload, timeout=10)
        if r_buy and str(r_buy.get("err", "0")) == "0":
            if isinstance(buy_entry, dict):
                buy_entry["buyNum"] = buy_num + remaining
            self.log.info(f"✅ تم شراء {remaining} من صندوق الشعلة بنجاح بالذهب (الإجمالي: {remaining * price} ذهب) 🎉")
            await asyncio.sleep(1.0)
            return remaining

        # في حال عدم دعم الشراء المجمع من قبل السيرفر، يتم الشراء بالتتابع (1 تلو الآخر)
        err_code = str(r_buy.get("err", "unknown")) if r_buy else "timeout"
        self.log.info(f"ℹ️ الشراء المجمع أعاد كود ({err_code}) — الانتقال للشراء الفردي بالتتابع...")

        bought = 0
        for i in range(remaining):
            if self.is_stopped():
                break
            p_single = {
                "shopItemID": SHOP_ITEM_ID,
                "num": 1,
                "discountFlag": False
            }
            r_single = await self.conn.query("1034", "2", p_single, timeout=8)
            if r_single and str(r_single.get("err", "0")) == "0":
                bought += 1
                if isinstance(buy_entry, dict):
                    buy_entry["buyNum"] = buy_num + bought
                self.log.info(f"✅ تم شراء صندوق الشعلة #{bought} بنجاح بالذهب ({price} ذهب)")
                await asyncio.sleep(0.8)
            else:
                s_err = str(r_single.get("err", "unknown")) if r_single else "timeout"
                self.log.warning(f"⚠️ توقف شراء صناديق الشعلة عند الصندوق #{bought + 1} (كود: {s_err})")
                break

        return bought

    # ──────────────────────────────────────────────────────────────────
    #  دوال مساعدة لفحص الحقيبة وفتح الصناديق
    # ──────────────────────────────────────────────────────────────────

    async def _get_backpack_torch_count(self) -> int:
        """معرفة عدد صناديق مشعل رويال (811037) المتوفرة في الحقيبة."""
        bp_ctrl = getattr(self.conn, "init_data", {}).get("backpackCtrl", {})
        count = 0
        if isinstance(bp_ctrl, dict):
            item_entry = bp_ctrl.get(str(ITEM_ID), bp_ctrl.get(ITEM_ID, {}))
            if isinstance(item_entry, dict):
                count = int(item_entry.get("count", 0))

        # في حال كانت القيمة 0، نتحقق عبر استعلام الحقيبة 1004/1 لضمان الدقة بعد الشراء
        try:
            r_bag = await self.conn.query("1004", "1", {}, timeout=8)
            if r_bag and isinstance(r_bag.get("data"), dict):
                raw = r_bag["data"]
                items = raw.get("itemList", raw)
                if isinstance(items, dict):
                    t_item = items.get(str(ITEM_ID), items.get(ITEM_ID, {}))
                    if isinstance(t_item, dict):
                        count = int(t_item.get("count", t_item.get("num", 0)))
                elif isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict) and int(it.get("id", it.get("itemID", 0))) == ITEM_ID:
                            count = int(it.get("count", it.get("num", 0)))
                            break
        except Exception as e:
            self.log.debug(f"استعلام الحقيبة 1004/1: {e}")

        return count

    async def _open_torch_chests(self) -> int:
        """فتح جميع صناديق مشعل رويال المتوفرة بالحقيبة بالكامل."""
        count = await self._get_backpack_torch_count()
        if count <= 0:
            self.log.info("ℹ️ لا توجد صناديق مشعل رويال في الحقيبة لفتحها.")
            return 0

        self.log.info(f"📦 جاري فتح {count} من صندوق مشعل رويال بالحقيبة دفعة واحدة عبر 1004/2...")

        payload = {
            "itemID": ITEM_ID,
            "count": count
        }

        r_open = await self.conn.query("1004", "2", payload, timeout=10)
        if r_open and str(r_open.get("err", "0")) == "0":
            self.log.info(f"🎉 تم فتح {count} من صندوق مشعل رويال بنجاح واستلام كافة جوائزها! ✅")
            # تحديث رصيد الحقيبة محلياً
            bp_ctrl = getattr(self.conn, "init_data", {}).get("backpackCtrl", {})
            if isinstance(bp_ctrl, dict) and str(ITEM_ID) in bp_ctrl:
                bp_ctrl[str(ITEM_ID)]["count"] = max(0, int(bp_ctrl[str(ITEM_ID)].get("count", count)) - count)
            return count
        else:
            err_code = str(r_open.get("err", "unknown")) if r_open else "timeout"
            self.log.warning(f"⚠️ فشل فتح صناديق مشعل رويال (كود السيرفر: {err_code})")
            return 0
