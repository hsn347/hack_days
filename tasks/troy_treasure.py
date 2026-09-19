# -*- coding: utf-8 -*-
"""
tasks/troy_treasure.py — مهمة كنز طروادة (Troy Treasure Task)
═════════════════════════════════════════════════════════════
تتكون هذه المهمة من سلسلة مراحل خاصة بحدث كنز طروادة (Troy Treasure):
  المرحلة 1: استلام كافة جوائز إنجاز المهام الجاهزة (Quest Rewards Claim):
    - فحص مهام طروادة من بيانات السيرفر (troyTreasureAgCtrl.quests).
    - استعلام السيرفر لتحديث بيانات كنز طروادة (CMD 2059 / SUB 36).
    - إرسال طلب استلام المكافأة لكل مهمة مكتملة وجاهزة (status == 3 أو cNum >= lNum):
      cmd: "1028", subcmd: "5", data: {"dynamicId": dynamicId}
    - الرد الناجح: err: "0"، ويتم تحديث حالة المهمة محلياً إلى status = 4.
"""

from __future__ import annotations

import sys
import os
import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple

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
from game_client import GameConnection


class TroyTreasureTask(BaseTask):
    """
    مهمة كنز طروادة (CMD 1028 / SUB 5 - استلام جوائز إنجاز مهام طروادة):
    تفحص المهام المكتملة وتستلم جوائزها تباعاً، وتنهي المهمة فوراً إذا لم توجد جوائز جاهزة.
    """
    name = "troy_treasure"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})
        self.subtasks: Dict[str, Any] = self.config.get("subtasks", {
            "claim_quests": True,
        })

    # ──────────────────────────────────────────────────────────────────
    #  استعلام وتحديث بيانات كنز طروادة من السيرفر
    # ──────────────────────────────────────────────────────────────────

    async def _refresh_troy_data(self) -> Dict[str, Any]:
        """
        استعلام السيرفر لتحديث بيانات كنز طروادة (CMD 2059 / SUB 36).
        """
        try:
            rsp = await self.conn.query("2059", "36", {}, timeout=6)
            if rsp and isinstance(rsp, dict) and "data" in rsp:
                troy_data = rsp["data"].get("troyTreasureAgCtrl")
                if troy_data and isinstance(troy_data, dict):
                    self.conn.init_data["troyTreasureAgCtrl"] = troy_data
                    return troy_data
        except Exception as e:
            self.log.debug(f"تعذر استعلام كنز طروادة عبر 2059/36 (سيتم الاعتماد على بيانات الدخول): {e}")

        return self.conn.init_data.get("troyTreasureAgCtrl", {})

    # ──────────────────────────────────────────────────────────────────
    #  استخراج المهام الجاهزة للاستلام
    # ──────────────────────────────────────────────────────────────────

    def _get_ready_quests(self, troy_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        استخراج قائمة المهام المكتملة الجاهزة للاستلام من troyTreasureAgCtrl.quests.
        """
        quests = troy_data.get("quests", {})
        if not isinstance(quests, dict):
            return []

        ready = []
        for qk, q in quests.items():
            if not isinstance(q, dict):
                continue

            dynamic_id = q.get("dynamicId")
            if dynamic_id is None:
                continue

            try:
                dynamic_id = int(dynamic_id)
            except Exception:
                continue

            status = int(q.get("status", 2))
            c_num = int(q.get("cNum", 0))
            l_num = int(q.get("lNum", 1))

            # status == 3: جاهزة للاستلام
            # c_num >= l_num و status != 4: مكتملة أيضاً
            if status == 3 or (c_num >= l_num and status != 4):
                ready.append({
                    "id": q.get("id", qk),
                    "dynamicId": dynamic_id,
                    "status": status,
                    "cNum": c_num,
                    "lNum": l_num,
                    "ref": q,
                })

        return ready

    # ──────────────────────────────────────────────────────────────────
    #  استلام جائزة مهمة (CMD 1028 / SUB 5)
    # ──────────────────────────────────────────────────────────────────

    async def _claim_quest(self, dynamic_id: int, quest_ref: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        إرسال حزمة استلام جائزة مهمة طروادة (cmd: 1028, subcmd: 5).
        """
        payload = {"dynamicId": dynamic_id}
        try:
            rsp = await self.conn.query("1028", "5", payload, timeout=6)
            if not rsp:
                return False, "لم يتم استلام رد من السيرفر"

            err = str(rsp.get("err", ""))
            if err == "0":
                if quest_ref is not None and isinstance(quest_ref, dict):
                    quest_ref["status"] = 4
                return True, "تم استلام المكافأة بنجاح"
            elif err == "1002":
                if quest_ref is not None and isinstance(quest_ref, dict):
                    quest_ref["status"] = 4
                return False, "المهمة مستلمة مسبقاً أو غير مكتملة"
            else:
                return False, f"خطأ السيرفر: err={err}"
        except Exception as e:
            return False, f"استثناء أثناء إرسال الطلب: {e}"

    # ──────────────────────────────────────────────────────────────────
    #  التنفيذ الرئيسي للمهمة
    # ──────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """
        تنفيذ مراحل مهمة كنز طروادة.
        """
        if not self.config.get("enabled", True):
            return TaskResult(
                success=True,
                message="تم تخطي مهمة كنز طروادة (معطلة في الإعدادات)",
                data={"skipped": True}
            )

        self.log.info("🏛️ بدء تنفيذ مهمة كنز طروادة...")

        # 1. تحديث بيانات طروادة من السيرفر
        troy_data = await self._refresh_troy_data()
        if not troy_data:
            return TaskResult(
                success=True,
                message="لا توجد بيانات فعالية كنز طروادة حالياً (الفعالية غير نشطة)",
                data={"active": False}
            )

        claimed_count = 0
        failed_count = 0
        details_log: List[str] = []

        # 2. المرحلة 1: استلام كافة جوائز إنجاز المهام
        if self.subtasks.get("claim_quests", True):
            ready_quests = self._get_ready_quests(troy_data)

            if not ready_quests:
                msg = "لا توجد أي جوائز مهام جاهزة للاستلام في كنز طروادة حالياً"
                self.log.info(f"ℹ️ {msg}")
                return TaskResult(
                    success=True,
                    message=msg,
                    data={"claimed_count": 0, "ready_count": 0}
                )

            self.log.info(f"🎁 تم العثور على {len(ready_quests)} جوائز مهام جاهزة للاستلام في كنز طروادة.")

            for q in ready_quests:
                dynamic_id = q["dynamicId"]
                qid = q["id"]
                self.log.info(f"  ⬆️ جاري استلام جائزة المهمة (ID: {qid}, dynamicId: {dynamic_id})...")

                success, note = await self._claim_quest(dynamic_id, q.get("ref"))
                if success:
                    claimed_count += 1
                    details_log.append(f"مهمة {qid} (dynamicId: {dynamic_id}): تم الاستلام بنجاح")
                    self.log.info(f"  ✅ تم استلام جائزة المهمة {qid} بنجاح.")
                else:
                    failed_count += 1
                    details_log.append(f"مهمة {qid} (dynamicId: {dynamic_id}): فشل ({note})")
                    self.log.warning(f"  ⚠️ تعذر استلام جائزة المهمة {qid}: {note}")

                # فاصل زمني طبيعي بين الاستلامات
                await asyncio.sleep(random.uniform(0.6, 1.2))

        final_msg = f"تم استلام {claimed_count} من جوائز مهام كنز طروادة بنجاح"
        if failed_count > 0:
            final_msg += f" (تعذر {failed_count})"

        self.log.info(f"🎉 {final_msg}")

        return TaskResult(
            success=True,
            message=final_msg,
            data={
                "claimed_count": claimed_count,
                "failed_count": failed_count,
                "log": details_log,
            }
        )


if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(description="اختبار مهمة كنز طروادة المستقلة")
    parser.add_argument("--email", required=True, help="البريد الإلكتروني للقلعة")
    args = parser.parse_args()

    async def main_test():
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
        sm = SessionManager()
        castle_data = sm.get_castle_by_email(args.email)
        if not castle_data:
            print(f"القلعة غير موجودة: {args.email}")
            return

        conn = GameConnection()
        auth = sm.get_auth_token(args.email)
        if not auth or not await conn.connect_with_token(auth):
            print("فشل الاتصال باللعبة")
            return

        task = TroyTreasureTask(conn, {"enabled": True, "subtasks": {"claim_quests": True}})
        res = await task.run()
        print("نتيجة المهمة:", res.message, res.details)
        await conn.close()

    asyncio.run(main_test())
