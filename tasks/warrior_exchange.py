# -*- coding: utf-8 -*-
"""
tasks/warrior_exchange.py — مهمة استبدال متجر المحارب في مركز المنافع (Warrior Exchange Task)
════════════════════════════════════════════════════════════════════════════════════════════
المسار داخل اللعبة:
  مركز المنافع (Benefit Center) ← متجر الاستبدال (Redemption Mall) ← متجر المحارب (Warrior Shop)

مواصفات العملية:
  - معرف المتجر: 1500003 (gRedemptionMallShopId.WARRIOR)
  - معرف المنتج المستهدف: 910018
  - الحد الأقصى للاستبدال: 15 مرة
  - الحد الأدنى للاستبدال: 1 مرة
  - مادة التكلفة لكل استبدال: 5 وحدات من المادة #812033
  - المادة الناتجة عن الاستبدال: 1 وحدة من المادة #812034

القواعد الإلزامية:
  1. قبل التنفيذ، يتم فحص المسموح للاستبدال في اللعبة (limitnum - buyNum):
     - إذا كان المتاح أقل من 15 (تم استبدال أي جزء منه سابقاً) ← يتم تجاهل وإنهاء المهمة كلياً.
     - إذا كان المتاح 15 كاملاً ← يتم الانتقال للخطوة التالية.
  2. استبدال العدد الذي حدده المستخدم (بين 1 و 15).
  3. في حال عدم كفاية المواد في الحقيبة، يتم الاستبدال بأقصى عدد ممكن متاح بالمواد للعدد المحدد.
  4. حزمة الإرسال:
     {
       "cmd": "2057",
       "subcmd": "1",
       "data": {
         "goodsId": 910018,
         "goodsNum": <actual_count>
       }
     }

الاستخدام كملف مستقل:
    python tasks/warrior_exchange.py --email "samartilleli@yopmail.com" --count 10
    python tasks/warrior_exchange.py --email "x.abd3@gmail.com" --count 2
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# ════════════════════════════════════════════════════════════════════
#  ثوابت متجر المحارب
# ════════════════════════════════════════════════════════════════════

WARRIOR_SHOP_ID = 1500003
TARGET_GOODS_ID = 910018
MAX_EXCHANGE_LIMIT = 15
MIN_EXCHANGE_LIMIT = 1
DEFAULT_EXCHANGE_COUNT = 15

# التكلفة الافتراضية لكل عملية استبدال واحدة (في حال تعذر استخراجها ديناميكياً)
DEFAULT_COST_ITEM_ID = 812033
DEFAULT_COST_PER_ONE = 5
DEFAULT_RESULT_ITEM_ID = 812034


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (WarriorExchangeTask)
# ════════════════════════════════════════════════════════════════════

class WarriorExchangeTask(BaseTask):
    """
    مهمة استبدال منتج متجر المحارب في مركز المنافع (CMD 2057 / SUB 1).
    """
    name = "warrior_exchange"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})

    def _get_shop_and_goods_data(self) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        استخراج بيانات متجر المحارب والمنتج 910018 من init_data['exchangeStoreAgCtrl'].
        """
        store_ctrl = self.conn.init_data.get("exchangeStoreAgCtrl", {})
        if not isinstance(store_ctrl, dict):
            return None, None

        warrior_shop = store_ctrl.get(str(WARRIOR_SHOP_ID)) or store_ctrl.get(WARRIOR_SHOP_ID)
        if not isinstance(warrior_shop, dict):
            return None, None

        goods_list = warrior_shop.get("goodsList", {})
        if not isinstance(goods_list, dict):
            return warrior_shop, None

        goods_data = goods_list.get(str(TARGET_GOODS_ID)) or goods_list.get(TARGET_GOODS_ID)
        return warrior_shop, goods_data if isinstance(goods_data, dict) else None

    def _get_backpack_item_count(self, item_id: int) -> int:
        """
        استخراج رصيد مادة معينة من حقيبة القلعة (backpackCtrl).
        """
        bp = self.conn.init_data.get("backpackCtrl", {})
        if not isinstance(bp, dict):
            return 0

        item_entry = bp.get(str(item_id)) or bp.get(item_id)
        if isinstance(item_entry, dict):
            try:
                return int(item_entry.get("count", 0))
            except (ValueError, TypeError):
                return 0
        elif isinstance(item_entry, (int, float)):
            return int(item_entry)

        return 0

    async def run(self) -> TaskResult:
        cfg = self.config or {}
        raw_count = cfg.get("count", cfg.get("exchange_count", DEFAULT_EXCHANGE_COUNT))
        try:
            requested_count = int(raw_count)
        except (ValueError, TypeError):
            requested_count = DEFAULT_EXCHANGE_COUNT

        # ضبط العدد المطلوب بين الحدود المسموحة (1 إلى 15)
        requested_count = max(MIN_EXCHANGE_LIMIT, min(MAX_EXCHANGE_LIMIT, requested_count))

        self.log.info(
            f"🛒 بدء فحص مهمة متجر المحارب (المنتج المستهدف: #{TARGET_GOODS_ID} | "
            f"المرات المطلوبة: {requested_count})..."
        )

        # 1. استخراج بيانات المتجر والمنتج
        warrior_shop, goods_data = self._get_shop_and_goods_data()
        if not warrior_shop or not goods_data:
            msg = "⚠️ لم يتم العثور على بيانات متجر المحارب أو المنتج 910018 في استجابة السيرفر."
            self.log.warning(msg)
            return TaskResult(success=False, message=msg)

        limit_num = int(goods_data.get("limitnum", MAX_EXCHANGE_LIMIT))
        buy_num = int(goods_data.get("buyNum", 0))
        remain_allowed = max(0, limit_num - buy_num)

        self.log.info(
            f"🔍 حالة الاستبدال الحالية في السيرفر: المتبقي {remain_allowed} من أصل {limit_num} "
            f"(المستبدل سابقاً: {buy_num})"
        )

        # 2. الشرط الإلزامي الصارم:
        # إذا كان المتاح أقل من 15، يتم تجاهل وإنهاء المهمة كلياً فوراً
        if remain_allowed < MAX_EXCHANGE_LIMIT:
            msg = (
                f"⏭️ المتاح للاستبدال حالياً هو {remain_allowed} من {limit_num} (أقل من 15) — "
                f"تم إنهاء وتخطي المهمة تلقائياً وفقاً للشرط الإلزامي."
            )
            self.log.info(msg)
            return TaskResult(
                success=True,
                message=msg,
                data={
                    "skipped": True,
                    "reason": "remain_less_than_15",
                    "remain_allowed": remain_allowed,
                    "limit_num": limit_num,
                    "buy_num": buy_num,
                }
            )

        # 3. استخراج تفاصيل تكلفة الاستبدال والمواد المطلوبة
        cost_item_id = DEFAULT_COST_ITEM_ID
        cost_per_one = DEFAULT_COST_PER_ONE

        ex_item = goods_data.get("exchangeitem")
        if isinstance(ex_item, (list, tuple)) and len(ex_item) >= 2:
            try:
                cost_item_id = int(ex_item[0])
                cost_per_one = int(ex_item[1])
            except (ValueError, TypeError):
                pass

        # 4. فحص رصيد المواد في حقيبة اللاعب
        owned_materials = self._get_backpack_item_count(cost_item_id)
        max_affordable = owned_materials // cost_per_one if cost_per_one > 0 else 0

        self.log.info(
            f"🎒 رصيد المواد في الحقيبة: {owned_materials:,} من المادة #{cost_item_id} "
            f"(تكلفة المرة الواحدة: {cost_per_one} | أقصى استبدال متاح بالمواد: {max_affordable})"
        )

        if max_affordable <= 0:
            msg = (
                f"⚠️ لا توجد مواد كافية للاستبدال (المتوفر: {owned_materials} من المادة #{cost_item_id}، "
                f"والمطلوب للمرة الواحدة: {cost_per_one}). تم إنهاء المهمة."
            )
            self.log.warning(msg)
            return TaskResult(
                success=True,
                message=msg,
                data={
                    "affordable": 0,
                    "owned_materials": owned_materials,
                    "cost_item_id": cost_item_id,
                    "cost_per_one": cost_per_one,
                }
            )

        # 5. تحديد العدد الفعلي للاستبدال (أكبر عدد ممكن لما حدده المستخدم وحسب المواد المتاحة)
        actual_count = min(requested_count, max_affordable, remain_allowed)

        if actual_count < requested_count:
            self.log.info(
                f"⚡ المواد المتوفرة تكفي لـ {actual_count} من أصل {requested_count} مطلوبة — "
                f"سيتم تنفيذ الاستبدال بالحد الأقصى المتاح ({actual_count} مرة)."
            )

        # 6. إرسال أمر الاستبدال للسيرفر (CMD 2057 / SUB 1)
        self.log.info(
            f"🚀 جاري إرسال طلب استبدال المنتج #{TARGET_GOODS_ID} بعدد {actual_count} مرة في متجر المحارب..."
        )

        payload = {
            "goodsId": TARGET_GOODS_ID,
            "goodsNum": actual_count,
        }

        try:
            resp = await self.conn.query("2057", "1", payload, timeout=12)
        except Exception as e:
            msg = f"❌ خطأ أثناء إرسال أمر الاستبدال عبر الشبكة: {e}"
            self.log.error(msg)
            return TaskResult(success=False, message=msg)

        if not resp or not isinstance(resp, dict):
            msg = "❌ لم يتم استلام استجابة صالحة من السيرفر عند استبدال متجر المحارب."
            self.log.warning(msg)
            return TaskResult(success=False, message=msg)

        err_code = resp.get("err")
        if err_code not in (0, "0", None):
            msg = f"❌ فشل استبدال منتج متجر المحارب من السيرفر (كود الخطأ: {err_code})."
            self.log.warning(msg)
            return TaskResult(success=False, message=msg, data=resp)

        # 7. تحديث الذاكرة المحلية للعبة بعد نجاح الاستبدال
        resp_data = resp.get("data", {})
        new_buy_num = resp_data.get("buyNum", buy_num + actual_count)
        goods_data["buyNum"] = new_buy_num

        consumed_materials = actual_count * cost_per_one
        bp = self.conn.init_data.get("backpackCtrl", {})
        if isinstance(bp, dict):
            item_entry = bp.get(str(cost_item_id)) or bp.get(cost_item_id)
            if isinstance(item_entry, dict) and "count" in item_entry:
                item_entry["count"] = max(0, int(item_entry.get("count", 0)) - consumed_materials)

        success_msg = (
            f"🎉 تم استبدال المنتج #{TARGET_GOODS_ID} بنجاح بعدد {actual_count} مرة في متجر المحارب "
            f"(المتبقي الآن: {max(0, limit_num - new_buy_num)} من {limit_num} | "
            f"المستهلك: {consumed_materials:,} من المادة #{cost_item_id})."
        )
        self.log.info(success_msg)

        return TaskResult(
            success=True,
            message=success_msg,
            data={
                "goodsId": TARGET_GOODS_ID,
                "exchanged_count": actual_count,
                "requested_count": requested_count,
                "new_buy_num": new_buy_num,
                "consumed_materials": consumed_materials,
            }
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Empire Warrior Exchange Task — مهمة استبدال متجر المحارب في مركز المنافع"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument(
        "--count", "-c", type=int, default=15,
        help="عدد مرات الاستبدال المطلوبة من 1 إلى 15 [افتراضي: 15]"
    )
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

        print("⏳ جاري انتظار تحميل بيانات اللعبة الأولية (init_data)...")
        for _ in range(12):
            await asyncio.sleep(1.0)
            if "exchangeStoreAgCtrl" in conn.init_data:
                break

        task_cfg = {
            "count": args.count,
        }

        task = WarriorExchangeTask(conn, task_cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
