# -*- coding: utf-8 -*-
"""
tasks/prestige_box.py — مهمة استلام صناديق النشاط اليومي لمهام الهيبة (Daily Prestige / Merit Chests)
══════════════════════════════════════════════════════════════════════════════════════════════════════
تقوم هذه المهمة باستلام صناديق النشاط اليومي الستة الناتجة عن نقاط مهام الهيبة والمجد اليومية:
  1. الاستعلام المسبق من السيرفر (CMD 1013 / SUB 1) لتحديث نقاط النشاط (dailyPoint) والصناديق المستلمة (dailyBoxRwd).
  2. فحص الصناديق الستة ومطابقتها مع النقاط المحققة:
     - صندوق 1: 40 نقطة
     - صندوق 2: 110 نقطة
     - صندوق 3: 180 نقطة
     - صندوق 4: 250 نقطة
     - صندوق 5: 340 نقطة
     - صندوق 6: 450 نقطة
  3. إذا لم تكن هناك أي صناديق جاهزة للاستلام، يتم إنهاء المهمة فوراً دون إرسال طلبات زائدة.
  4. إذا وُجدت صناديق جاهزة، يتم إرسال أمر الاستلام لكل صندوق (CMD 3105 / SUB 2 / data: {"boxId": box_id}).
"""

from __future__ import annotations

import sys
import os
import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

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

# ── أهداف ونقاط صناديق النشاط اليومي الستة ─────────────────────────
DAILY_MERIT_BOX_GOALS: List[Tuple[int, int]] = [
    (1, 40),
    (2, 110),
    (3, 180),
    (4, 250),
    (5, 340),
    (6, 450),
]


class PrestigeBoxTask(BaseTask):
    """
    مهمة استلام صناديق النشاط اليومي لمهام الهيبة والمجد (CMD 3105 / SUB 2):
    تفحص الصناديق المستحقة وتستلمها تباعاً، وتنهي المهمة فوراً إذا لم توجد صناديق جاهزة.
    """
    name = "prestige_box"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config or {})

    async def _refresh_merit_data(self) -> Dict[str, Any]:
        """تجديد بيانات مهام الهيبة ونقاط النشاط اليومي من السيرفر مباشرة."""
        try:
            r = await self.conn.query("1013", "1", {}, timeout=6)
            if r and isinstance(r, dict) and "data" in r:
                merit_data = r["data"].get("meritoriousTaskCtrl")
                if merit_data and isinstance(merit_data, dict):
                    self.conn.init_data["meritoriousTaskCtrl"] = merit_data
                    return merit_data
        except Exception as e:
            self.log.debug(f"استعلام 1013/1 لم يكتمل: {e}")

        # استخدام الكاش المتوفر كبديل احتياطي
        return self.conn.init_data.get("meritoriousTaskCtrl", {})

    def get_ready_boxes(self, merit_data: Dict[str, Any]) -> Tuple[int, List[int], List[int]]:
        """
        فحص نقاط النشاط والصناديق المستلمة لتحديد الصناديق الجاهزة للاستلام حالياً.
        ترجع: (daily_points, ready_box_ids, claimed_box_ids)
        """
        daily_points = int(merit_data.get("dailyPoint", 0))
        claimed_raw = merit_data.get("dailyBoxRwd", {})
        claimed_ids: Set[int] = set()

        if isinstance(claimed_raw, dict):
            for k in claimed_raw.keys():
                if str(k).isdigit():
                    claimed_ids.add(int(k))
        elif isinstance(claimed_raw, list):
            for item in claimed_raw:
                if str(item).isdigit():
                    claimed_ids.add(int(item))

        ready_boxes: List[int] = []
        for box_id, req_points in DAILY_MERIT_BOX_GOALS:
            if box_id in claimed_ids:
                continue
            if daily_points >= req_points:
                ready_boxes.append(box_id)

        return daily_points, ready_boxes, sorted(list(claimed_ids))

    async def claim_box(self, box_id: int) -> Dict[str, Any]:
        """
        إرسال أمر استلام صندوق محدد عبر CMD 3105 / SUB 2.
        Payload: {"boxId": box_id}
        """
        payload = {"boxId": int(box_id)}
        resp = await self.conn.query("3105", "2", payload, timeout=6)
        if not resp:
            return {"success": False, "error": "timeout", "boxId": box_id}

        err_code = str(resp.get("err", "-1"))
        if err_code == "0":
            data = resp.get("data", {})
            ret_data = data.get("retData", {})
            rwd_list = ret_data.get("getRwdList", [])

            # تحديث كاش الصناديق المستلمة محلياً في init_data
            server_box_rwd = ret_data.get("dailyBoxRwd", {})
            if isinstance(server_box_rwd, dict):
                merit_ctrl = self.conn.init_data.setdefault("meritoriousTaskCtrl", {})
                current_claimed = merit_ctrl.setdefault("dailyBoxRwd", {})
                if isinstance(current_claimed, dict):
                    current_claimed.update(server_box_rwd)
                merit_ctrl.setdefault("dailyBoxRwd", {})[str(box_id)] = int(time.time())

            return {
                "success": True,
                "boxId": box_id,
                "rewards_count": len(rwd_list),
                "rewards": rwd_list,
            }
        else:
            return {
                "success": False,
                "boxId": box_id,
                "err": err_code,
            }

    async def run(self) -> TaskResult:
        """تنفيذ فحص واستلام صناديق مهام الهيبة اليومية."""
        self.log.info("🎁 ───【 بدء مهمة استلام صناديق مهام الهيبة والنشاط اليومي 】───")

        # 1. استعلام مسبق عن أحدث حالة للصناديق ونقاط النشاط
        merit_data = await self._refresh_merit_data()
        daily_points, ready_boxes, claimed_boxes = self.get_ready_boxes(merit_data)

        self.log.info(f"📊 [استعلام مسبق] نقاط النشاط الحالية: {daily_points} نقطة | الصناديق المستلمة سابقاً: {claimed_boxes}")

        # 2. فحص: إذا لم تكن هناك أي صناديق جاهزة للاستلام، يتم إنهاء المهمة فوراً
        if not ready_boxes:
            msg = f"ℹ️ لا توجد صناديق هيبة جاهزة للاستلام حالياً (النقاط: {daily_points} — المستلم: {len(claimed_boxes)}/6)."
            self.log.info(msg)
            return TaskResult.ok(
                msg,
                daily_points=daily_points,
                claimed_boxes=claimed_boxes,
                claimed_now=[],
            )

        self.log.info(f"✨ تم العثور على {len(ready_boxes)} صندوق جاهز للاستلام: {ready_boxes}")

        claimed_now: List[int] = []
        failed_boxes: List[int] = []

        # 3. استلام الصناديق الجاهزة واحداً تلو الآخر
        for box_id in ready_boxes:
            req_pts = next((goal for bid, goal in DAILY_MERIT_BOX_GOALS if bid == box_id), 0)
            self.log.info(f"🎁 جاري استلام الصندوق رقم #{box_id} (المتطلب: {req_pts} نقطة)...")

            res = await self.claim_box(box_id)
            if res.get("success"):
                claimed_now.append(box_id)
                self.log.info(f"✅ تم استلام الصندوق #{box_id} بنجاح! (عدد الجوائز المستلمة: {res.get('rewards_count', 0)})")
            else:
                failed_boxes.append(box_id)
                self.log.warning(f"⚠️ تعذر استلام الصندوق #{box_id} (كود الخطأ: {res.get('err')})")

            # تأخير زمني محاكي للبشر
            await asyncio.sleep(round(random.uniform(1.2, 2.0), 2))

        # ملخص النتيجة
        total_claimed_today = len(claimed_boxes) + len(claimed_now)
        if claimed_now:
            msg = f"🎉 تم استلام {len(claimed_now)} صندوق هيبة بنجاح: {claimed_now} (إجمالي اليوم: {total_claimed_today}/6)"
        else:
            msg = f"⚠️ لم يتم استلام أي صناديق جديدة (الصناديق التي تعذرت: {failed_boxes})"

        self.log.info(msg)
        return TaskResult.ok(
            msg,
            daily_points=daily_points,
            claimed_now=claimed_now,
            total_claimed_today=total_claimed_today,
            failed_boxes=failed_boxes,
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر لسطر الأوامر (Standalone CLI)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(description="Prestige Box Task — مهمة استلام صناديق مهام الهيبة اليومية")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")

    args = parser.parse_args()

    async def _main():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة في session_cache.json")
            return

        target_email = args.email.strip() if args.email else next(iter(accounts.keys()))
        account = accounts.get(target_email)
        if not account:
            for em, acc in accounts.items():
                if em.lower() == target_email.lower():
                    account = acc
                    break

        if not account:
            print(f"❌ لم يتم العثور على الحساب: {target_email}")
            return

        conn = GameConnection(account)
        print(f"🔌 جاري الاتصال بحساب {target_email}...")
        if not await conn.connect():
            print("❌ فشل الاتصال بالسيرفر!")
            return

        for _ in range(30):
            await asyncio.sleep(0.5)
            if "cityCtrl" in conn.init_data and "meritoriousTaskCtrl" in conn.init_data:
                break

        task = PrestigeBoxTask(conn)
        await task.on_start()
        result = await task.run()

        print("\n" + "═" * 60)
        print(f"📊 النتيجة: {'✅ نجاح' if result.success else '❌ فشل'}")
        print(f"💬 الرسالة: {result.message}")
        print("═" * 60)

        await conn.close()

    asyncio.run(_main())
