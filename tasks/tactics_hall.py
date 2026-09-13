# -*- coding: utf-8 -*-
"""
tasks/tactics_hall.py — مهمة قاعة الاستراتيجيات وتطوير أبحاث التكتيكات تلقائياً
══════════════════════════════════════════════════════════════════════════════════════

بروتوكول قاعة الاستراتيجيات (Hero Tactical Hall / Tactics Hall):
  - بدء البحث:    cmd: "3137", subcmd: "1", data: {"mid": tactic_mid}
  - استلام البحث: cmd: "3137", subcmd: "2"
  - مسار البحث:   queueCtrl['1257']

قائمة الأبحاث الـ 17 المتاحة:
  ⚔️ الحرب (War):
    - القلعة الفارغة (91010000)
    - قمة الاتقان (91010015)
    - الرماية الفردية (91010012)
    - الضرر الجانبي (91010014)
    - الرمح الثاقب (91010013)
    - سرعة البرق (91010016)

  🏗️ التطوير (Development):
    - البحث الكامل (91010001)
    - التعزيز الكامل (91010002)
    - المساعي الاكاديمية (91010011)
    - السيل الدافق (91010003)

  🛡️ الدعم (Support):
    - جنود الحرب (91010004)
    - التدريب المكثف للفرسان (91010009)
    - التدريب الجدي للمشاة (91010006)
    - تدريب مكثف للرماة والنشاب (91010007)
    - القعر العميق (91010005)
    - القنبلة الدخانية (91010010)
    - التدريب المكثف للعربات (91010008)

الاستخدام كملف مستقل:
    python tasks/tactics_hall.py --email "samartilleli@yopmail.com" --tactic "القلعة الفارغة"
    python tasks/tactics_hall.py --email "your_email@gmail.com" -t "القنبلة الدخانية"
    python tasks/tactics_hall.py --email "x.abd3@gmail.com" --mid 91010015
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
from typing import Any, Dict, List, Optional, Union

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

QUEUE_TYPE_TACTICAL = "1257"

# ════════════════════════════════════════════════════════════════════
#  تعريف خيارات أبحاث قاعة الاستراتيجيات
# ════════════════════════════════════════════════════════════════════

TACTICS_MAP: Dict[int, Dict[str, Any]] = {
    # ⚔️ الحرب
    91010000: {"id": 91010000, "category": "الحرب", "name_ar": "القلعة الفارغة", "name_en": "Empty Castle", "icon": "🏰"},
    91010015: {"id": 91010015, "category": "الحرب", "name_ar": "قمة الاتقان", "name_en": "Peak of Perfection", "icon": "👑"},
    91010012: {"id": 91010012, "category": "الحرب", "name_ar": "الرماية الفردية", "name_en": "Solo Archery", "icon": "🎯"},
    91010014: {"id": 91010014, "category": "الحرب", "name_ar": "الضرر الجانبي", "name_en": "Collateral Damage", "icon": "💥"},
    91010013: {"id": 91010013, "category": "الحرب", "name_ar": "الرمح الثاقب", "name_en": "Piercing Spear", "icon": "🔱"},
    91010016: {"id": 91010016, "category": "الحرب", "name_ar": "سرعة البرق", "name_en": "Lightning Speed", "icon": "⚡"},

    # 🏗️ التطوير
    91010001: {"id": 91010001, "category": "التطوير", "name_ar": "البحث الكامل", "name_en": "Complete Research", "icon": "📜"},
    91010002: {"id": 91010002, "category": "التطوير", "name_ar": "التعزيز الكامل", "name_en": "Complete Reinforcement", "icon": "🛡️"},
    91010011: {"id": 91010011, "category": "التطوير", "name_ar": "المساعي الاكاديمية", "name_en": "Academic Pursuits", "icon": "🎓"},
    91010003: {"id": 91010003, "category": "التطوير", "name_ar": "السيل الدافق", "name_en": "Torrential Flood", "icon": "🌊"},

    # 🛡️ الدعم
    91010004: {"id": 91010004, "category": "الدعم", "name_ar": "جنود الحرب", "name_en": "War Soldiers", "icon": "⚔️"},
    91010009: {"id": 91010009, "category": "الدعم", "name_ar": "التدريب المكثف للفرسان", "name_en": "Cavalry Training", "icon": "🐎"},
    91010006: {"id": 91010006, "category": "الدعم", "name_ar": "التدريب الجدي للمشاة", "name_en": "Infantry Training", "icon": "🛡️"},
    91010007: {"id": 91010007, "category": "الدعم", "name_ar": "تدريب مكثف للرماة والنشاب", "name_en": "Archers Training", "icon": "🏹"},
    91010005: {"id": 91010005, "category": "الدعم", "name_ar": "القعر العميق", "name_en": "Deep Abyss", "icon": "🕳️"},
    91010010: {"id": 91010010, "category": "الدعم", "name_ar": "القنبلة الدخانية", "name_en": "Smoke Bomb", "icon": "💨"},
    91010008: {"id": 91010008, "category": "الدعم", "name_ar": "التدريب المكثف للعربات", "name_en": "Siege Training", "icon": "🚜"},
}

TACTICS_ALIASES: Dict[str, int] = {
    # ⚔️ الحرب (Battle)
    "القلعة الفارغة": 91010000, "قلعة فارغة": 91010000, "empty castle": 91010000, "castle": 91010000, "91010000": 91010000,
    "empty fort": 91010000, "empty_fort": 91010000,
    "قمة الاتقان": 91010015, "قمة الإتقان": 91010015, "اتقان": 91010015, "peak": 91010015, "perfection": 91010015, "91010015": 91010015,
    "mount mastery": 91010015, "mount_mastery": 91010015,
    "الرماية الفردية": 91010012, "رماية فردية": 91010012, "رماية": 91010012, "solo archery": 91010012, "odd archery": 91010012, "odd_archery": 91010012, "91010012": 91010012,
    "الضرر الجانبي": 91010014, "ضرر جانبي": 91010014, "ضرر": 91010014, "collateral damage": 91010014, "عين الإبرة": 91010014, "عين الابرة": 91010014, "eye of the needle": 91010014, "eye_of_the_needle": 91010014, "91010014": 91010014,
    "الرمح الثاقب": 91010013, "رمح ثاقب": 91010013, "رمح": 91010013, "spear": 91010013, "رمح المهارة": 91010013, "skilled spearplay": 91010013, "skilled_spearplay": 91010013, "91010013": 91010013,
    "سرعة البرق": 91010016, "برق": 91010016, "lightning": 91010016, "speed": 91010016, "lightning speed": 91010016, "lightning_speed": 91010016, "91010016": 91010016,

    # 🏗️ التطوير (Development)
    "البحث الكامل": 91010001, "بحث كامل": 91010001, "complete research": 91010001, "complete search": 91010001, "complete_search": 91010001, "91010001": 91010001,
    "التعزيز الكامل": 91010002, "تعزيز كامل": 91010002, "تعزيز": 91010002, "reinforce": 91010002, "الغرفة الكاملة": 91010002, "غرفة كاملة": 91010002, "full room": 91010002, "full_room": 91010002, "91010002": 91010002,
    "المساعي الاكاديمية": 91010011, "المساعي الأكاديمية": 91010011, "اكاديمية": 91010011, "academic": 91010011, "المساعي الأدبية": 91010011, "المساعي الادبية": 91010011, "literary pursuits": 91010011, "literary_pursuits": 91010011, "91010011": 91010011,
    "السيل الدافق": 91010003, "سيل دافق": 91010003, "سيل": 91010003, "flood": 91010003, "أمواج الغسيل": 91010003, "امواج الغسيل": 91010003, "washing waves": 91010003, "washing_waves": 91010003, "91010003": 91010003,

    # 🛡️ الدعم (Help / Support)
    "جنود الحرب": 91010004, "جنود": 91010004, "soldiers": 91010004, "وُلد للحرب": 91010004, "ولد للحرب": 91010004, "born for war": 91010004, "born_for_war": 91010004, "91010004": 91010004,
    "التدريب المكثف للفرسان": 91010009, "تدريب فرسان": 91010009, "فرسان": 91010009, "cavalry": 91010009, "cavalry practice": 91010009, "cavalry_practice": 91010009, "91010009": 91010009,
    "التدريب الجدي للمشاة": 91010006, "تدريب مشاة": 91010006, "مشاة": 91010006, "infantry": 91010006, "infantry practice": 91010006, "infantry_practice": 91010006, "91010006": 91010006,
    "تدريب مكثف للرماة والنشاب": 91010007, "تدريب رماة": 91010007, "رماة": 91010007, "نشاب": 91010007, "archers": 91010007, "archer practice": 91010007, "archer_practice": 91010007, "91010007": 91010007,
    "القعر العميق": 91010005, "قعر عميق": 91010005, "قعر": 91010005, "abyss": 91010005, "بلا قاع": 91010005, "bottomless": 91010005, "91010005": 91010005,
    "القنبلة الدخانية": 91010010, "قنبلة دخانية": 91010010, "دخان": 91010010, "smoke": 91010010, "smoke bomb": 91010010, "smoke_bomb": 91010010, "91010010": 91010010,
    "التدريب المكثف للعربات": 91010008, "تدريب عربات": 91010008, "عربات": 91010008, "siege": 91010008, "chariot": 91010008, "chariot practice": 91010008, "chariot_practice": 91010008, "91010008": 91010008,
}


def parse_tactic_choice(raw_input: Union[str, int, None]) -> int:
    """تحويل اختيار المستخدم إلى معرف البحث الدقيق (MID)."""
    if raw_input is None or str(raw_input).strip() == "":
        # الافتراضي: القلعة الفارغة
        return 91010000

    if isinstance(raw_input, int) and raw_input in TACTICS_MAP:
        return raw_input

    cleaned = str(raw_input).strip().lower()
    if cleaned in TACTICS_ALIASES:
        return TACTICS_ALIASES[cleaned]

    # بحث جزئي ذكي
    for alias, mid in TACTICS_ALIASES.items():
        if alias in cleaned or cleaned in alias:
            return mid

    return 91010000


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (TacticsHallTask)
# ════════════════════════════════════════════════════════════════════

class TacticsHallTask(BaseTask):
    """
    مهمة قاعة الاستراتيجيات: التحقق من الأبحاث الجارية، استلام المكتمل منها، وبدء البحث المختار.
    """
    name = "tactics_hall"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        raw_tactic = self.config.get("tactic") or self.config.get("mid")
        self.target_mid = parse_tactic_choice(raw_tactic)

    async def run(self) -> TaskResult:
        t_info = TACTICS_MAP.get(self.target_mid, {"name_ar": f"بحث #{self.target_mid}", "category": "", "icon": "📜"})
        self.log.info(f"🏛️ بدء مهمة قاعة الاستراتيجيات | البحث المستهدف: {t_info['icon']} [{t_info['name_ar']}] ({t_info['category']})...")

        now_ts = int(time.time())

        # 1. محاولة استلام أي بحث مكتمل جاهز أولاً (subcmd: 2)
        r_claim = await self.conn.query("3137", "2", {}, timeout=8)
        if r_claim and str(r_claim.get("err", "0")) == "0":
            self.log.info("🎁 تم استلام نتائج ومكافآت البحث التكتيكي السابق بنجاح!")
            await asyncio.sleep(1.0)

        # 2. فحص مسار البحث الحالي (queueCtrl -> 1257)
        queue_ctrl = self.conn.init_data.get("queueCtrl", {})
        active_queue = queue_ctrl.get(QUEUE_TYPE_TACTICAL) if isinstance(queue_ctrl, dict) else None

        has_active_research = False
        active_end_time = 0
        active_mid = 0

        if active_queue and isinstance(active_queue, dict):
            q_data = active_queue.get("data", {})
            active_end_time = int(q_data.get("endTime", 0))
            active_mid = int(q_data.get("mid", 0))
            if active_end_time > now_ts:
                has_active_research = True

        # إذا كان هناك بحث جاري لم ينته بعد
        if has_active_research:
            active_info = TACTICS_MAP.get(active_mid, {"name_ar": f"بحث #{active_mid}", "icon": "⏳"})
            remaining_s = active_end_time - now_ts
            remaining_m = max(1, remaining_s // 60)
            msg = f"يوجد بحث جاري حالياً: {active_info['icon']} [{active_info['name_ar']}]. متبقي: {remaining_m} دقيقة."
            self.log.info(f"ℹ️ {msg}")

            return TaskResult.ok(
                msg,
                status="research_in_progress",
                retry_after=remaining_s,
                data={
                    "active_mid": active_mid,
                    "active_name": active_info["name_ar"],
                    "active_end_time": active_end_time,
                    "remaining_seconds": remaining_s
                }
            )

        # 3. لا يوجد بحث جاري (المسار فارغ) — بدء البحث المطلوب من المستخدم
        self.log.info(f"🚀 مسار الأبحاث فارغ وجاهز! جاري بدء تطوير: {t_info['icon']} [{t_info['name_ar']}]...")

        payload = {"mid": self.target_mid}
        resp = await self.conn.query("3137", "1", payload, timeout=8)

        if resp and str(resp.get("err", "0")) == "0":
            resp_data = resp.get("data", {})
            msg = f"تم بدء بحث {t_info['icon']} [{t_info['name_ar']}] في قاعة الاستراتيجيات بنجاح!"
            self.log.info(f"✅ {msg}")

            # المدة الافتراضية للبحث التكتيكي هي 12 ساعة (43200 ثانية)
            retry_after = 43200
            return TaskResult.ok(
                msg,
                status="started",
                retry_after=retry_after,
                data={
                    "mid": self.target_mid,
                    "name": t_info["name_ar"],
                    "category": t_info["category"],
                    "response": resp_data
                }
            )
        elif resp and resp.get("err") == "Err_HERO_TACTICAL_NOT_COUNT":
            msg = f"تعذر بدء البحث: نفدت مرات البحث التكتيكي المتاحة اليوم أو نقص المخططات المطلوبة."
            self.log.warning(f"⚠️ {msg}")
            return TaskResult.ok(
                msg,
                status="no_attempts_left",
                retry_after=86400,
                data={"err": "Err_HERO_TACTICAL_NOT_COUNT"}
            )
        else:
            err_code = resp.get("err", "unknown") if resp else "timeout"
            msg = f"فشل بدء بحث {t_info['name_ar']} (كود الخطأ: {err_code})"
            self.log.error(f"❌ {msg}")
            return TaskResult.fail(msg, status="error", data={"err": err_code})


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Tactical Hall Task — مهمة قاعة الاستراتيجيات وتطوير أبحاث التكتيكات")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--tactic", "-t", help="اسم البحث المطلوب (مثال: 'القلعة الفارغة' أو 'القنبلة الدخانية' أو 'البحث الكامل')")
    parser.add_argument("--mid", "-m", type=int, help="معرف البحث المباشر (مثل 91010000)")
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

        cfg = {"tactic": args.tactic or args.mid}
        task = TacticsHallTask(conn, cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
