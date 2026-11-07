# -*- coding: utf-8 -*-
"""
tasks/auction.py — مهمة المزايدة التلقائية على الحمام الزاجل في سوق المملكة (Auction Task)
═════════════════════════════════════════════════════════════════════════════════════

الوظيفة:
  1. الاستعلام عن سلع المزاد الجارية في سوق المملكة (cmd: "2031", subcmd: "1").
  2. البحث عن سلعة الحمام الزاجل (#501901) أو شظايا الحمام الزاجل (#503001).
  3. في حال عدم توفر السلعة، يتم الخروج فوراً دون أي استعلامات إضافية.
  4. التحقق مما إذا كان البوت هو صاحب أعلى عرض حالي (ownUid == my_uid):
     - إذا كان أعلى عرض، يتم التخطي فوراً لتفادي الخطأ #480006 وتوفير الذهب.
  5. مقارنة السعر الأدنى للمزايدة (currSaleGold + plus) مع الحد الأقصى المحدد (max_gold):
     - إذا كان السعر ضمن الحد المسموح: إرسال أمر المزايدة (cmd: "2031", subcmd: "2").
     - إذا تجاوز السعر الحد المسموح:
       * التحقق مما إذا كان للبوت ذهب مسترد في المزاد (notReceiveGold > 0).
       * إذا وجد ذهب مسترد، إرسال أمر سحبه فوراً (cmd: "2031", subcmd: "5").
       * إذا لم يوجد ذهب، التخطي بأمان دون استعلامات غير ضرورية.

بروتوكول اللعبة المعتمد:
  - وحدة المزاد:           CMD_SALES_ROOM_MODULE = "2031"
  - الاستعلام الأولي:      REQ_SALES_ROOM_INIT = "1"
  - إرسال المزايدة:        REQ_SALES_ROOM_ADD_PLUS = "2" -> {"shopID": shopID, "gold": price}
  - سحب كامل الذهب:        REQ_SALES_ROOM_RECEIVE_GOLD = "5"
  - معرف فعالية المزاد:    SALESROOM_ACTIVITY = 9001034
  - معرفات السلع المستهدفة: 501901 (الحمام الزاجل), 503001 (شظايا الحمام الزاجل)
"""

from __future__ import annotations

import sys
import os
import json
import time
import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from tasks.base_task import BaseTask, TaskResult

if TYPE_CHECKING:
    from game_client import GameConnection

# معرفات السلع المستهدفة حصراً (الحمام الزاجل وشظاياه)
TARGET_ITEM_IDS = {501901, 503001}
ITEM_NAMES = {
    501901: "الحمام الزاجل",
    503001: "شظايا الحمام الزاجل",
}

# أكواد أخطاء المزاد الرسمية في كود اللعبة (errDef.lua)
ERR_SALES_ROOM_GOLD_NOT_ENOUGH = "480003"   # الذهب غير كافٍ
ERR_SALES_ROOM_PLUS_NOT_ENOUGH = "480005"   # المبلغ أقل من الحد الأدنى للمزايدة
ERR_SALES_ROOM_SELF_OFFER      = "480006"   # اللاعب هو صاحب أعلى عرض بالفعل
ERR_SALES_ROOM_NOT_OPEN        = "480001"   # المزاد غير مفتوح


class AuctionTask(BaseTask):
    """مهمة المزايدة التلقائية على الحمام الزاجل وشظاياه في سوق المملكة."""

    name = "auction"
    description = "🕊️ المزايدة على الحمام الزاجل في المزاد"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})

    def _get_my_uid(self) -> int:
        """جلب معرف اللاعب (UID) مباشرة من الذاكرة الحية دون أي استعلام شبكي."""
        lord_ctrl = self.conn.init_data.get("lordInfoCtrl", {})
        base = lord_ctrl.get("base", {}) if isinstance(lord_ctrl, dict) else {}
        return int(base.get("uid", 0))

    async def _fetch_auction_data(self) -> Tuple[bool, List[Dict[str, Any]], int, str]:
        """
        الاستعلام الموحد الأولي لجلب بيانات سلع المزاد والذهب غير المستلم (2031/1).
        يعيد: (نجح_الطلب, قائمة_السلع, رصيد_الذهب_المسترد, رسالة_الخطأ)
        """
        try:
            resp = await self.conn.query("2031", "1", {}, timeout=10)
        except Exception as e:
            return False, [], 0, f"خطأ اتصال أثناء الاستعلام عن المزاد: {e}"

        if not resp:
            return False, [], 0, "لم تصل استجابة من السيرفر لطلب المزاد"

        err = str(resp.get("err", "-1"))
        if err != "0":
            return False, [], 0, f"السيرفر أعاد خطأ برقم {err}"

        data = resp.get("data", {})
        raw_items = data.get("itemsInfo", [])

        # استيعاب هيكل itemsInfo سواء جاء كـ dict أو list
        items_list: List[Dict[str, Any]] = []
        if isinstance(raw_items, dict):
            items_list = [v for v in raw_items.values() if isinstance(v, dict)]
        elif isinstance(raw_items, list):
            items_list = [v for v in raw_items if isinstance(v, dict)]

        not_receive_gold = int(data.get("notReceiveGold", 0))

        # تحديث الذاكرة الحية للجلسة لتبادل البيانات
        if "salesRoomAgCtrl" in self.conn.init_data and isinstance(self.conn.init_data["salesRoomAgCtrl"], dict):
            self.conn.init_data["salesRoomAgCtrl"]["itemsInfo"] = raw_items
            self.conn.init_data["salesRoomAgCtrl"]["notReceiveGold"] = not_receive_gold
            if "timeAndStatus" in data:
                self.conn.init_data["salesRoomAgCtrl"]["timeAndStatus"] = data["timeAndStatus"]

        return True, items_list, not_receive_gold, ""

    def _find_target_item(self, items_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """البحث عن سلعة الحمام الزاجل (501901) أو شظايا الحمام (503001) في سلع المزاد."""
        for it in items_list:
            item_id = int(it.get("item", it.get("goodId", 0)))
            if item_id in TARGET_ITEM_IDS:
                return it
        return None

    async def _send_bid(self, shop_id: int, bid_amount: int) -> Tuple[bool, str]:
        """إرسال أمر المزايدة على السلعة عبر (2031/2)."""
        payload = {
            "shopID": shop_id,
            "gold": bid_amount,
        }
        try:
            resp = await self.conn.query("2031", "2", payload, timeout=10)
        except Exception as e:
            return False, f"خطأ اتصال أثناء إرسال المزايدة: {e}"

        if not resp:
            return False, "لم يتم استلام استجابة لأمر المزايدة"

        err = str(resp.get("err", "-1"))
        if err == "0":
            return True, f"تمت المزايدة بنجاح بمبلغ {bid_amount:,} ذهب"
        elif err == ERR_SALES_ROOM_SELF_OFFER:
            return True, "القلعة هي صاحبة أعلى مزايدة حالياً"
        elif err == ERR_SALES_ROOM_GOLD_NOT_ENOUGH:
            return False, f"رصيد الذهب الحالي غير كافٍ للمزايدة بـ {bid_amount:,} ذهب"
        elif err == ERR_SALES_ROOM_PLUS_NOT_ENOUGH:
            return False, f"مبلغ المزايدة {bid_amount:,} أقل من الحد الأدنى المقبول بالسيرفر"
        else:
            return False, f"تعذرت المزايدة (كود خطأ: {err})"

    async def _reclaim_gold(self) -> Tuple[bool, str]:
        """سحب واسترداد كامل الذهب المسترد في المزاد عبر (2031/5)."""
        try:
            resp = await self.conn.query("2031", "5", {}, timeout=10)
        except Exception as e:
            return False, f"خطأ اتصال أثناء سحب الذهب: {e}"

        if not resp:
            return False, "لم يتم استلام استجابة لطلب استرداد الذهب"

        err = str(resp.get("err", "-1"))
        if err == "0":
            rec_gold = resp.get("data", {}).get("receiveGold", 0)
            if "salesRoomAgCtrl" in self.conn.init_data and isinstance(self.conn.init_data["salesRoomAgCtrl"], dict):
                self.conn.init_data["salesRoomAgCtrl"]["notReceiveGold"] = 0
            return True, f"تم سحب واسترداد {rec_gold:,} ذهب بنجاح من المزاد"
        return False, f"فشل استرداد الذهب من المزاد (كود خطأ: {err})"

    async def run(self) -> TaskResult:
        """
        تنفيذ مهمة المزاد وفق التسلسل المحكم:
          1. فحص توافر الحمام في سلع المزاد.
          2. التحقق من أعلى مزايد.
          3. المزايدة إذا كان السعر ضمن السقف.
          4. سحب الذهب إذا تجاوز السعر السقف ووجد رصيد مسترد.
        """
        max_gold = int(self.config.get("max_gold", 2000))
        my_uid = self._get_my_uid()

        self.log.info(f"🕊️ [مهمة المزاد] بدء فحص سوق المزاد للحمام الزاجل (الحد الأقصى: {max_gold:,} ذهب)...")

        # 1. جلب بيانات المزاد الحالية من السيرفر
        ok, items_list, not_receive_gold, err_msg = await self._fetch_auction_data()
        if not ok:
            self.log.warning(f"⚠️ {err_msg}")
            return TaskResult.fail(err_msg)

        # 2. البحث عن سلعة الحمام الزاجل
        target_item = self._find_target_item(items_list)
        if not target_item:
            msg = "🕊️ سلعة الحمام الزاجل غير معروضة في دورة المزاد الحالية."
            self.log.info(f"⏭️ {msg}")
            return TaskResult.ok(msg, skipped=True, reason="ITEM_NOT_IN_AUCTION")

        item_id = int(target_item.get("item", target_item.get("goodId", 0)))
        item_name = ITEM_NAMES.get(item_id, f"سلعة #{item_id}")
        shop_id = int(target_item.get("shopID", 0))
        curr_price = int(target_item.get("currSaleGold", 0))
        plus = int(target_item.get("plus", 0))
        min_bid = curr_price + plus
        own_uid = int(target_item.get("ownUid", 0))
        item_count = int(target_item.get("num", 1))

        self.log.info(
            f"🔍 تم العثور على: {item_name} (عدد: {item_count}) | السعر الحالي: {curr_price:,} | "
            f"الزيادة: {plus:,} | أقل مزايدة ممكنة: {min_bid:,} ذهب"
        )

        # 3. التحقق مما إذا كان البوت هو صاحب العرض الأعلى بالفعل
        if my_uid > 0 and own_uid == my_uid:
            msg = f"✨ القلعة هي صاحبة أعلى مزايدة حالياً على {item_name} ({curr_price:,} ذهب) — لا حاجة للمزايدة."
            self.log.info(f"✅ {msg}")
            return TaskResult.ok(msg, skipped=True, reason="ALREADY_HIGHEST_BIDDER", current_price=curr_price)

        # 4. مقارنة السعر بالحد الأقصى المسموح به
        if min_bid <= max_gold:
            self.log.info(f"🚀 أقل مزايدة ({min_bid:,}) <= الحد الأقصى ({max_gold:,}) — إرسال المزايدة...")
            bid_ok, bid_msg = await self._send_bid(shop_id, min_bid)
            if bid_ok:
                full_msg = f"✅ {item_name}: {bid_msg}"
                self.log.info(full_msg)
                return TaskResult.ok(full_msg, bid_gold=min_bid, shop_id=shop_id)
            else:
                full_err = f"❌ فشلت المزايدة على {item_name}: {bid_msg}"
                self.log.warning(full_err)
                return TaskResult.fail(full_err)

        # 5. السعر أعلى من الحد المسموح: فحص استرداد الذهب السابق
        self.log.info(
            f"⚠️ سعر المزايدة المطلوب ({min_bid:,} ذهب) يتجاوز الحد الأقصى المسموح ({max_gold:,} ذهب)!"
        )

        if not_receive_gold > 0:
            self.log.info(f"💰 تم رصد {not_receive_gold:,} ذهب مسترد في المزاد بحاجة للسحب — جاري السحب...")
            rec_ok, rec_msg = await self._reclaim_gold()
            if rec_ok:
                full_msg = f"🛡️ تم تجاوز الحد الأقصى ({min_bid:,} > {max_gold:,}) و{rec_msg}"
                self.log.info(full_msg)
                return TaskResult.ok(full_msg, reclaimed_gold=not_receive_gold)
            else:
                full_err = f"⚠️ تجاوز السعر الحد مع تعذر سحب الذهب: {rec_msg}"
                self.log.warning(full_err)
                return TaskResult.fail(full_err)

        # تجاوز الحد ولا يوجد ذهب للسحب
        skip_msg = (
            f"⏭️ تخطي المزايدة: السعر المطلوب ({min_bid:,} ذهب) أعلى من الحد الأقصى ({max_gold:,} ذهب)، "
            f"ولا يوجد ذهب سابق لسحبه."
        )
        self.log.info(skip_msg)
        return TaskResult.ok(skip_msg, skipped=True, reason="PRICE_EXCEEDS_BUDGET_NO_GOLD")


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول للتشغيل المستقل (Standalone CLI)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager
    from game_client import GameConnection

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    parser = argparse.ArgumentParser(description="🕊️ مهمة المزايدة على الحمام الزاجل في المزاد")
    parser.add_argument("--email", required=True, help="البريد الإلكتروني للقلعة المستهدفة")
    parser.add_argument("--max-gold", type=int, default=2000, help="الحد الأقصى للذهب المسموح به")
    args = parser.parse_args()

    async def main():
        sm = SessionManager()
        acc = sm.get_or_login(email=args.email)
        if not acc:
            print(f"❌ تعذر العثور على بيانات الحساب: {args.email}")
            return

        conn = GameConnection(acc)
        if not await conn.connect():
            print("❌ فشل الاتصال باللعبة!")
            return

        for _ in range(12):
            await asyncio.sleep(0.3)
            if "lordInfoCtrl" in conn.init_data:
                break

        task = AuctionTask(conn, {"max_gold": args.max_gold})
        res = await task.run()
        print("\n🏁 نتيجة المهمة:", res)
        await conn.close()

    asyncio.run(main())

