# -*- coding: utf-8 -*-
"""
tasks/territory_expansion.py — مهمة جمع مكافآت التوسع الإقليمي في الأحداث (Territorial Expansion)
═══════════════════════════════════════════════════════════════════════════════════════════════════

بروتوكول استلام مكافآت المهام (CMD 1028 - Quest / Universal Task Module):
  - استعلام المهام وحالاتها: من واقع بيانات السيرفر (generalAtyMgr[9001373].data.quests).
  - إرسال طلب استلام المكافأة:
    cmd: "1028", subcmd: "5", data: {"dynamicId": dynamicId}
  - الرد الناجح:
    cmd: "1028", subcmd: "5", err: "0", data: {"dynamicId": dynamicId}

أقسام مهام التوسع الإقليمي الأربعة (النشاط ID 9001373):
  1. 📅 إجمالي تسجيل الدخول (Total Login Days): المهام 4110482 إلى 4110486.
  2. ⚔️ تقوية القوة العسكرية (Military Power): المهام 4110487 إلى 4110493 و 4118587.
  3. 🗺️ استكشاف الكنوز (Treasure Exploration): المهام 4110494 إلى 4110499.
  4. 🌾 نهب الموارد (Resource Plundering): المهام 4110500 إلى 4110505 و 4118588 و 4118589.

الاستخدام كملف مستقل:
    python tasks/territory_expansion.py --email "king7moe1990@gmail.com" --check-only
    python tasks/territory_expansion.py --email "king7moe1990@gmail.com"
    python tasks/territory_expansion.py --email "meik.gaertner2306.MGr@gmail.com" --all-events
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
import argparse
from typing import Any, Dict, List, Optional, Tuple, Set

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection
from core.session_manager import SessionManager


# ════════════════════════════════════════════════════════════════════
#  تكوين وتصنيف مهام التوسع الإقليمي (TERRITORY EXPANSION)
# ════════════════════════════════════════════════════════════════════

EXPANSION_ACTIVITY_ID = 9001373

EXPANSION_CATEGORIES: Dict[int, Dict[str, Any]] = {
    1: {
        "name": "إجمالي تسجيل الدخول",
        "icon": "📅",
        "task_ids": [4110482, 4110483, 4110484, 4110485, 4110486],
        "descriptions": {
            4110482: "تسجيل الدخول لمدة 1 يوم",
            4110483: "تسجيل الدخول لمدة 2 يوم",
            4110484: "تسجيل الدخول لمدة 3 أيام",
            4110485: "تسجيل الدخول لمدة 4 أيام",
            4110486: "تسجيل الدخول لمدة 5 أيام",
        }
    },
    2: {
        "name": "تقوية القوة العسكرية",
        "icon": "⚔️",
        "task_ids": [4110487, 4110488, 4110489, 4110490, 4110491, 4110492, 4110493, 4118587],
        "descriptions": {
            4110487: "رفع القوة العسكرية إلى 4,000",
            4110488: "رفع القوة العسكرية إلى 8,000",
            4110489: "رفع القوة العسكرية إلى 12,000",
            4110490: "رفع القوة العسكرية إلى 16,000",
            4110491: "رفع القوة العسكرية إلى 24,000",
            4110492: "رفع القوة العسكرية إلى 40,000",
            4110493: "رفع القوة العسكرية إلى 64,000",
            4118587: "رفع القوة العسكرية إلى 100,000",
        }
    },
    3: {
        "name": "استكشاف الكنوز",
        "icon": "🗺️",
        "task_ids": [4110494, 4110495, 4110496, 4110497, 4110498, 4110499],
        "descriptions": {
            4110494: "استكشاف الكنوز والآثار 30 مرة",
            4110495: "استكشاف الكنوز والآثار 60 مرة",
            4110496: "استكشاف الكنوز والآثار 90 مرة",
            4110497: "استكشاف الكنوز والآثار 120 مرة",
            4110498: "استكشاف الكنوز والآثار 150 مرة",
            4110499: "استكشاف الكنوز والآثار 180 مرة",
        }
    },
    4: {
        "name": "نهب الموارد",
        "icon": "🌾",
        "task_ids": [4110500, 4110501, 4110502, 4118588, 4110503, 4110504, 4110505, 4118589],
        "descriptions": {
            4110500: "نهب الموارد 30 مرة",
            4110501: "نهب الموارد 60 مرة",
            4110502: "نهب الموارد 120 مرة",
            4118588: "نهب الموارد 200 مرة",
            4110503: "نهب 3,000,000 من الموارد",
            4110504: "نهب 6,000,000 من الموارد",
            4110505: "نهب 12,000,000 من الموارد",
            4118589: "نهب 20,000,000 من الموارد",
        }
    }
}


class TerritoryExpansionTask(BaseTask):
    """
    مهمة فحص واستلام مكافآت حدث التوسع الإقليمي في الأحداث (CMD 1028).
    """
    name = "territory_expansion"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.check_only: bool = self.config.get("check_only", False)
        self.all_events: bool = self.config.get("all_events", False)

    # ──────────────────────────────────────────────────────────────────
    #  استخراج بيانات مهام التوسع الإقليمي
    # ──────────────────────────────────────────────────────────────────

    def get_expansion_quests(self) -> Dict[str, Any]:
        """
        قراءة وتصنيف مهام حدث التوسع الإقليمي من بيانات السيرفر (generalAtyMgr).
        """
        mgr = self.conn.init_data.get("generalAtyMgr", {})
        aty_data = mgr.get(str(EXPANSION_ACTIVITY_ID)) or mgr.get(EXPANSION_ACTIVITY_ID, {})
        data_block = aty_data.get("data", {})
        server_quests = data_block.get("quests", {})

        categories_data = []
        all_ready_quests = []
        all_claimed_count = 0
        all_in_prog_count = 0

        server_map = {}
        for qk, qv in server_quests.items():
            qid = int(qv.get("id", qk))
            server_map[qid] = qv

        for cat_id, cat_info in EXPANSION_CATEGORIES.items():
            cat_quests = []
            cat_ready = 0
            cat_claimed = 0

            for tid in cat_info["task_ids"]:
                s_q = server_map.get(tid)
                desc = cat_info["descriptions"].get(tid, f"مهمة {tid}")

                if s_q:
                    status_val = int(s_q.get("status", 2))
                    c_num = int(s_q.get("cNum", 0))
                    l_num = int(s_q.get("lNum", 1))
                    dynamic_id = int(s_q.get("dynamicId", 0))

                    if status_val == 3:
                        status_code = "ready"
                        status_desc = "🎁 جاهزة للاستلام"
                        cat_ready += 1
                        all_ready_quests.append({
                            "activity_id": EXPANSION_ACTIVITY_ID,
                            "category_name": cat_info["name"],
                            "task_id": tid,
                            "dynamic_id": dynamic_id,
                            "desc": desc,
                            "progress": f"{c_num:,}/{l_num:,}"
                        })
                    elif status_val == 4:
                        status_code = "claimed"
                        status_desc = "✅ تم الاستلام"
                        cat_claimed += 1
                        all_claimed_count += 1
                    else:
                        status_code = "in_progress"
                        status_desc = "⏳ قيد التقدم"
                        all_in_prog_count += 1
                else:
                    status_code = "locked"
                    status_desc = "🔒 غير مبدوءة"
                    c_num = 0
                    l_num = 1
                    dynamic_id = 0

                cat_quests.append({
                    "id": tid,
                    "desc": desc,
                    "dynamic_id": dynamic_id,
                    "status_code": status_code,
                    "status_desc": status_desc,
                    "c_num": c_num,
                    "l_num": l_num,
                    "progress_str": f"{c_num:,} / {l_num:,}"
                })

            categories_data.append({
                "id": cat_id,
                "name": cat_info["name"],
                "icon": cat_info["icon"],
                "quests": cat_quests,
                "ready_count": cat_ready,
                "claimed_count": cat_claimed,
                "total_count": len(cat_quests)
            })

        return {
            "activity_id": EXPANSION_ACTIVITY_ID,
            "exists": bool(server_quests),
            "categories": categories_data,
            "ready_quests": all_ready_quests,
            "claimed_count": all_claimed_count,
            "in_progress_count": all_in_prog_count,
            "total_quests": len(server_map)
        }

    def get_other_ready_quests(self) -> List[Dict[str, Any]]:
        """
        فحص باقي الأحداث في generalAtyMgr للبحث عن أي مكافآت جاهزة أخرى.
        """
        mgr = self.conn.init_data.get("generalAtyMgr", {})
        other_ready = []

        for aty_id_str, aty in mgr.items():
            if str(aty_id_str) == str(EXPANSION_ACTIVITY_ID):
                continue
            if not isinstance(aty, dict):
                continue
            data = aty.get("data", {})
            quests = data.get("quests", {})
            for qk, q in quests.items():
                if int(q.get("status", 0)) == 3:
                    other_ready.append({
                        "activity_id": aty_id_str,
                        "task_id": int(q.get("id", qk)),
                        "dynamic_id": int(q.get("dynamicId", 0)),
                        "progress": f"{q.get('cNum', 0):,}/{q.get('lNum', 1):,}"
                    })
        return other_ready

    # ──────────────────────────────────────────────────────────────────
    #  استلام المكافأة (Claim Reward)
    # ──────────────────────────────────────────────────────────────────

    async def _claim_task_reward(self, dynamic_id: int, activity_id: int = EXPANSION_ACTIVITY_ID, task_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        إرسال حزمة استلام مكافأة المهمة (cmd: 1028, subcmd: 5).
        """
        payload = {
            "dynamicId": dynamic_id
        }
        try:
            rsp = await self.conn.query("1028", "5", payload)
            if not rsp:
                return False, "لم يتم استلام رد من السيرفر"

            err = str(rsp.get("err", ""))
            if err == "0":
                # تحديث حالة المهمة محلياً في generalAtyMgr
                mgr = self.conn.init_data.setdefault("generalAtyMgr", {})
                aty = mgr.setdefault(str(activity_id), {})
                data = aty.setdefault("data", {})
                quests = data.setdefault("quests", {})
                if task_id and str(task_id) in quests:
                    quests[str(task_id)]["status"] = 4
                else:
                    for qk, qv in quests.items():
                        if int(qv.get("dynamicId", 0)) == dynamic_id:
                            qv["status"] = 4
                            break
                return True, "تم استلام المكافأة بنجاح"
            elif err == "1002":
                return False, "المهمة غير مكتملة أو تم استلامها مسبقاً"
            else:
                return False, f"فشل الاستلام (كود الخطأ: {err})"
        except Exception as e:
            return False, f"استثناء أثناء استلام المكافأة: {e}"

    # ──────────────────────────────────────────────────────────────────
    #  عرض تقرير الطرفية
    # ──────────────────────────────────────────────────────────────────

    def _print_status_report(self, info: Dict[str, Any], other_ready: List[Dict[str, Any]]):
        """تقرير الطرفية — معطّل في Thread Pool mode (المعلومات تمر عبر Firebase)."""
        pass

    # ──────────────────────────────────────────────────────────────────
    #  تنفيذ المهمة (Main Execution Flow)
    # ──────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """
        تنفيذ استعلام مهام التوسع الإقليمي وجمع كافة المكافآت الجاهزة.
        """
        # انتظار وصول بيانات generalAtyMgr
        for _ in range(20):
            if "generalAtyMgr" in self.conn.init_data and len(self.conn.init_data["generalAtyMgr"]) > 5:
                break
            await asyncio.sleep(0.3)

        info = self.get_expansion_quests()
        other_ready = self.get_other_ready_quests()

        self._print_status_report(info, other_ready)

        if self.check_only:
            ready_count = len(info["ready_quests"])
            msg = f"🔍 تم فحص التوسع الإقليمي: جاهزة: {ready_count} | مستلمة: {info['claimed_count']} | قيد التقدم: {info['in_progress_count']}"
            if other_ready:
                msg += f" | أحداث أخرى جاهزة: {len(other_ready)}"
            return TaskResult.ok(msg, ready_count=ready_count, claimed_count=info["claimed_count"], other_ready=len(other_ready))

        # ── جمع مكافآت التوسع الإقليمي الجاهزة ──
        targets = list(info["ready_quests"])

        # إذا طلب المستخدم جمع مكافآت كافة الأحداث العامة
        if self.all_events and other_ready:
            for oq in other_ready:
                targets.append({
                    "activity_id": oq["activity_id"],
                    "category_name": f"حدث عام ({oq['activity_id']})",
                    "task_id": oq["task_id"],
                    "dynamic_id": oq["dynamic_id"],
                    "desc": f"مهمة {oq['task_id']}",
                    "progress": oq["progress"]
                })

        if not targets:
            self.log.info("ℹ️ لا توجد أي مكافآت جاهزة للاستلام حالياً في التوسع الإقليمي.")
            return TaskResult.ok("ℹ️ لا توجد مكافآت جاهزة للاستلام حالياً في التوسع الإقليمي.", claimed=0)

        claimed_count = 0
        failed_count = 0

        for i, q in enumerate(targets):
            if i > 0:
                jitter = round(random.uniform(1.6, 2.8), 2)
                await asyncio.sleep(jitter)

            did = q["dynamic_id"]
            aid = q["activity_id"]
            tid = q["task_id"]

            ok, msg = await self._claim_task_reward(did, activity_id=aid, task_id=tid)
            if ok:
                claimed_count += 1
                self.log.debug(f"  ✅ [{q['category_name']}]: {q['desc']} -> تم استلام المكافأة بنجاح!")
            else:
                failed_count += 1
                self.log.debug(f"  ❌ [{q['category_name']}]: {q['desc']} -> {msg}")

        summary = f"🎯 اكتملت العملية: تم استلام {claimed_count} مكافأة بنجاح"
        if failed_count > 0:
            summary += f" | فشل {failed_count}"
        return TaskResult.ok(summary, claimed=claimed_count, failed=failed_count)


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول كملف مستقل (CLI Runner)
# ════════════════════════════════════════════════════════════════════

async def _cli_main():
    parser = argparse.ArgumentParser(description="مهمة جمع مكافآت التوسع الإقليمي في الأحداث")
    parser.add_argument("--email", type=str, help="البريد الإلكتروني للحساب")
    parser.add_argument("--check-only", action="store_true", help="استعلام فقط وعرض حالة المهام والتقدم دون استلام")
    parser.add_argument("--all-events", action="store_true", help="جمع المكافآت الجاهزة في جميع الأحداث العامة الأخرى أيضاً")
    args = parser.parse_args()

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

    print(f"📡 جارٍ الاتصال بالحساب: {target_email}...")
    conn = GameConnection(acc)
    if not await conn.connect():
        print("❌ فشل الاتصال بالسيرفر!")
        return

    # انتظار استقرار بيانات الدخول
    for _ in range(20):
        await asyncio.sleep(0.3)
        if "generalAtyMgr" in conn.init_data and len(conn.init_data["generalAtyMgr"]) > 5:
            break

    config = {
        "check_only": args.check_only,
        "all_events": args.all_events
    }

    task = TerritoryExpansionTask(conn, config)
    res = await task.run()

    print(f"\n📊 النتيجة النهائية:\n  {res.message}\n")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(_cli_main())
