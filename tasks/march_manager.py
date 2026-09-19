# -*- coding: utf-8 -*-
"""
tasks/march_manager.py — منسق الفيالق والمسيرات الخارجي الموحد (March Manager & Orchestrator)
════════════════════════════════════════════════════════════════════════════════════════════
يدير كافة مسيرات خريطة المملكة الخارجية للقلعة وفق مصفوفة أولويات ذكية ومضبوطة:

الأولويات التسلسلية المعتمدة:
  1. قتل غزاة الهيبة (Prestige Invaders): 5 هجمات مع فحص السيرفر المسبق لتوفير النشاط.
  2. الهجوم على معقل الهيبة (Prestige Stronghold): هجمتان مع فحص السيرفر المسبق.
  3. جمع موارد الهيبة (Prestige Gather): 4 مسيرات للموارد بحمولة 25k مورد فقط للعودة الفورية.
  4. مساعدة ونقل الموارد (Resource Transport): إمداد القلاع الحليفة.
  5. استكشاف الأطلال (Ruins Exploration): مسيرة واحدة حصراً لجمع الجوائز.
  6. القتال الشامل (Combat): نخبة العفريت / الغزاة / المتمردين (خيار محدد).
  7. الهجوم على المعاقل والملاجئ العامة (Stronghold): تدمير المعاقل المحددة.
  8. جمع الذهب في أراضي التحالفات (Alliance Gold Gather): استثمار مناجم التحالف.
  9. جمع الموارد الخارجية (World Gather): استهلاك كافة الفيالق الشاغرة المتبقية لجمع الموارد.
"""

from __future__ import annotations

import sys
import os
import asyncio
import copy
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
from tasks.transport import TransportTask
from tasks.ruins import RuinsTask
from tasks.monster import MonsterTask
from tasks.stronghold import StrongholdTask
from tasks.elf_boss import ElfBossTask
from tasks.gold_gather import GoldGatherTask
from tasks.gather import GatherTask
from game_client import GameConnection

# ── تعريفات مهام الهيبة اليومية (Prestige Constants) ─────────────────
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    "invaders": 4112028,     # مهاجمة الغزاة (5 هجمات)
    "stronghold": 4112030,   # احتلال المعقل / الملجأ (مرتان)
    "food": 4112000,         # جمع القمح (25,000)
    "wood": 4112001,         # جمع الخشب (25,000)
    "stone": 4112002,        # جمع الحجر (4,000)
    "iron": 4112003,         # جمع الحديد (2,000)
}

PRESTIGE_RESOURCES = [
    {"type": 2, "name": "مزارع القمح (Food)",  "icon": "🌾", "res_code": 1001, "quest_id": 4112000},
    {"type": 3, "name": "مناشر الخشب (Wood)",  "icon": "🪵", "res_code": 1002, "quest_id": 4112001},
    {"type": 4, "name": "مناجم الحجر (Stone)", "icon": "🪨", "res_code": 1003, "quest_id": 4112002},
    {"type": 5, "name": "مناجم الحديد (Iron)",  "icon": "⛏️", "res_code": 1004, "quest_id": 4112003},
]

UNIT_LOAD_RATES: Dict[int, int] = {
    7: 100,  # عربات الحصار والنقل
    4: 30,   # مشاة
    5: 25,   # فرسان
    6: 28,   # رماة
}


def get_unit_load(tid: int) -> int:
    """إرجاع سعة الحمولة التقديرية لوحدة الجندي بناءً على فئته."""
    category = tid // 100
    return UNIT_LOAD_RATES.get(category, 25)


def select_prestige_army(available: Dict[int, int], target_capacity: int = 25000) -> Tuple[List[Dict[str, int]], int]:
    """
    اختيار تشكيلة جيش محسوبة الحمولة بدقة بالغة بحيث لا تتجاوز سعتها القصوى 25,000 مورد.
    سيرفر اللعبة ينهي الجمع فور امتلاء حمولة الجيش بنسبة 100%،
    لذا تعود القوات فوراً فور جمع 25k مورد وتكتمل مهمة الهيبة دون هدر وقت الفيلق.
    """
    carts, others = [], []
    for tid, count in available.items():
        if count <= 0:
            continue
        cat = tid // 100
        if cat == 7:
            carts.append((tid, count, get_unit_load(tid)))
        else:
            others.append((tid, count, get_unit_load(tid)))

    # العربات أولاً
    carts.sort(key=lambda x: x[0], reverse=True)
    others.sort(key=lambda x: x[0], reverse=True)
    pool = carts + others

    selected = []
    accum_cap = 0
    for tid, count, rate in pool:
        if accum_cap >= target_capacity:
            break
        needed_cap = target_capacity - accum_cap
        needed_units = max(1, (needed_cap + rate - 1) // rate)
        take = min(count, needed_units)
        if take > 0:
            selected.append({"id": tid, "num": take})
            accum_cap += take * rate

    return selected, accum_cap


def pick_available_hero(heroes: list, busy: Set[int]) -> Optional[int]:
    """اختيار أول بطل شاغر وغير مشغول في مسيرة."""
    for h in heroes:
        hid = h.get("id") if isinstance(h, dict) else h
        if hid and int(hid) not in busy:
            return int(hid)
    return None


def pick_available_pet(conn: GameConnection, used_pets: Set[int]) -> List[int]:
    """اختيار الحيوان الأليف المتاح وغير المستخدم."""
    try:
        pets_data = conn.init_data.get("petCtrl", {}).get("pets", {})
        for pid in pets_data.keys():
            if str(pid).isdigit():
                pid_int = int(pid)
                if pid_int not in used_pets:
                    used_pets.add(pid_int)
                    return [pid_int]
    except Exception:
        pass
    return []


# ════════════════════════════════════════════════════════════════════
#  كلاس مهمة منسق الفيالق الموحد (MarchManagerTask)
# ════════════════════════════════════════════════════════════════════

class MarchManagerTask(BaseTask):
    """
    منسق الفيالق والمسيرات الذكي الموحد (March Orchestrator):
    ينفذ أولويات الخريطة التسع بالترتيب المعتمد مع احترام سعة الطوابير ومتابعة حالة المهام.
    """

    DEFAULT_PRIORITY_ORDER = [
        "prestige_invaders",
        "prestige_stronghold",
        "prestige_gather",
        "transport",
        "ruins",
        "combat",
        "stronghold",
        "gold_gather",
        "gather",
    ]

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config or {})
        self.max_queues = int(self.config.get("max_queues", 6))
        self.duration_minutes = float(self.config.get("duration_minutes", 20))
        self.priority_order = self.config.get("priority_order") or self.DEFAULT_PRIORITY_ORDER

        self._busy_heroes: Set[int] = set()
        self._used_army: Dict[int, int] = {}
        self._used_pets: Set[int] = set()
        self._excluded_targets: Set[str] = set()
        self._heroes: List[Dict[str, Any]] = []

    async def on_start(self):
        """التهيئة الأولية واستعلام الأبطال والقلعة."""
        await super().on_start()
        await self._load_heroes()

    async def _load_heroes(self):
        """تحميل قائمة الأبطال المتاحين بالقلعة."""
        self._heroes = []
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
        try:
            r = await self.conn.query('3080', '2', {'isSelf': True, 'uids': [uid_int]}, timeout=4)
            if r and 'data' in r:
                pages = r['data'].get('list', {}).get(str(uid_int), {}).get('pages', {})
                if isinstance(pages, dict):
                    for page in pages.values():
                        if isinstance(page, dict):
                            for h in page.get('heros', []):
                                hid = h.get('id') if isinstance(h, dict) else h
                                if hid:
                                    self._heroes.append({'id': int(hid)})
        except Exception as e:
            self.log.debug(f"خطأ غير حرج أثناء استعلام الأبطال: {e}")

    def get_quest_info(self, quest_key_or_id: str | int) -> Dict[str, Any]:
        """فحص حالة مهمة الهيبة من السيرفر (meritoriousTaskCtrl)."""
        qid = PRESTIGE_QUEST_IDS.get(str(quest_key_or_id), quest_key_or_id if isinstance(quest_key_or_id, int) else 0)
        merit = self.conn.init_data.get("meritoriousTaskCtrl", {})
        tasks = merit.get("tasks", []) if isinstance(merit, dict) else []

        for t in tasks:
            if isinstance(t, dict) and t.get("taskId") == qid:
                c_num = int(t.get("c_num", 0))
                l_num = int(t.get("l_num", 0))
                is_done = bool(t.get("is_finish", 0) == 1) or (l_num > 0 and c_num >= l_num)
                remaining = max(0, l_num - c_num)
                return {"found": True, "c_num": c_num, "l_num": l_num, "is_done": is_done, "remaining": remaining}

        return {"found": False, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

    def get_active_marches_count(self) -> int:
        """حساب عدد الفيالق النشطة في الوقت الحالي خارج القلعة."""
        active = 0
        lq = getattr(self.conn, "local_queues", None)
        if isinstance(lq, list):
            for item in lq:
                q_list = item.get('data', []) if isinstance(item, dict) else (item if isinstance(item, list) else [])
                for q in q_list:
                    if isinstance(q, dict) and q.get('status') in (1, 2):
                        active += 1
        return active

    def get_free_queues_count(self) -> int:
        """حساب عدد الفيالق الشاغرة المتاحة للإرسال."""
        active = self.get_active_marches_count()
        return max(0, self.max_queues - active)

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 1: قتل غزاة الهيبة (Prestige Invaders)
    # ────────────────────────────────────────────────────────────────
    async def _run_priority_prestige_invaders(self) -> Dict[str, Any]:
        cfg = self.config.get("prestige_invaders", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 1] تم تخطي قتل غزاة الهيبة (معطلة).")
            return {"skipped": True}

        q_info = self.get_quest_info("invaders")
        if q_info["is_done"]:
            self.log.info(f"✨ [أولوية 1] مهمة قتال غزاة الهيبة مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}).")
            return {"skipped": True, "already_done": True}

        needed = cfg.get("count", 5)
        if q_info["found"] and q_info["remaining"] > 0:
            needed = min(needed, q_info["remaining"])

        self.log.info(f"👾 [أولوية 1] بدء قتل غزاة الهيبة (مطلوب: {needed} هجمات)...")
        task_cfg = {
            "monster_type": "invaders",
            "min_lv": 1,
            "max_lv": cfg.get("max_lv", 30),
            "max_marches": needed,
            "search_range": 80,
            "formation_id": cfg.get("formation_id", 1),
            "wait_for_queue": False,
        }
        task = MonsterTask(self.conn, task_cfg)
        res = await task.run()
        return {"success": res.success, "message": res.message}

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 2: الهجوم على معقل الهيبة (Prestige Stronghold)
    # ────────────────────────────────────────────────────────────────
    async def _run_priority_prestige_stronghold(self) -> Dict[str, Any]:
        cfg = self.config.get("prestige_stronghold", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 2] تم تخطي معقل الهيبة (معطلة).")
            return {"skipped": True}

        q_info = self.get_quest_info("stronghold")
        if q_info["is_done"]:
            self.log.info(f"✨ [أولوية 2] مهمة معقل الهيبة مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}).")
            return {"skipped": True, "already_done": True}

        needed = cfg.get("count", 2)
        if q_info["found"] and q_info["remaining"] > 0:
            needed = min(needed, q_info["remaining"])

        self.log.info(f"🏰 [أولوية 2] بدء الهجوم على معقل الهيبة (مطلوب: {needed} هجمات)...")
        task_cfg = {
            "min_lv": 1,
            "max_lv": cfg.get("max_lv", 30),
            "max_marches": needed,
            "search_range": 80,
            "formation_id": cfg.get("formation_id", 1),
            "wait_for_queue": False,
        }
        task = StrongholdTask(self.conn, task_cfg)
        res = await task.run()
        return {"success": res.success, "message": res.message}

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 3: جمع موارد الهيبة (Prestige Gather - 25k)
    # ────────────────────────────────────────────────────────────────
    async def _run_priority_prestige_gather(self) -> Dict[str, Any]:
        cfg = self.config.get("prestige_gather", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 3] تم تخطي جمع موارد الهيبة (معطلة).")
            return {"skipped": True}

        # فحص الموارد غير المكتملة
        pending = []
        for r_meta in PRESTIGE_RESOURCES:
            q_info = self.get_quest_info(r_meta["quest_id"])
            if not q_info["is_done"]:
                pending.append(r_meta)

        if not pending:
            self.log.info("✨ [أولوية 3] مهام جمع الموارد الأربعة للهيبة مكتملة مسبقاً.")
            return {"skipped": True, "already_done": True}

        self.log.info(f"🌾 [أولوية 3] بدء جمع موارد الهيبة بحمولة 25k ({len(pending)} موارد متبقية)...")

        # جلب إحداثيات القلعة
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
        r_c = await self.conn.query('1006', '25', {"uid": uid_int}, timeout=5)
        if not r_c or not r_c.get('retData'):
            return {"success": False, "message": "فشل تحديد إحداثيات القلعة"}

        cx, cy = r_c['retData'].get('x'), r_c['retData'].get('y')
        kingdom_id = self.conn.kingdom_id or 0

        # جلب الجيش المتاح
        r_army = await self.conn.query('1005', '1', {}, timeout=5)
        available_troops = {}
        if r_army and 'data' in r_army:
            for k, v in r_army['data'].get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available_troops[int(k)] = int(v)

        target_cap = int(cfg.get("load_capacity", 25000))
        dispatched = 0

        for r_meta in pending:
            if self.get_free_queues_count() <= 0:
                self.log.warning("⚠️ امتلأت طوابير الفيالق المتاحة أثناء جمع موارد الهيبة.")
                break

            hero_id = pick_available_hero(self._heroes, self._busy_heroes)
            chosen_heroes = [hero_id] if hero_id else []
            chosen_pets = pick_available_pet(self.conn, self._used_pets)

            # احتساب الجيش المتبقي
            curr_avail = {tid: max(0, cnt - self._used_army.get(tid, 0)) for tid, cnt in available_troops.items() if cnt > self._used_army.get(tid, 0)}
            army_list, calc_cap = select_prestige_army(curr_avail, target_capacity=target_cap)
            if not army_list:
                self.log.warning(f"⚠️ لا توجد قوات كافية لمسيرة جمع {r_meta['name']}.")
                continue

            # البحث عن أقرب حقل
            r_search = await self.conn.query('2011', '3', {
                "mapType": 5, "subType": r_meta["type"], "num": 5, "x": cx, "y": cy,
                "exclude": {tid: True for tid in self._excluded_targets},
                "minLv": 1, "maxLv": 5, "range": 60
            }, timeout=5)

            candidates = r_search.get('result', []) if (r_search and isinstance(r_search, dict)) else []
            if not candidates:
                continue

            target = candidates[0]
            tid, tx, ty = target.get('id'), target.get('x'), target.get('y')
            self._excluded_targets.add(str(tid))

            # إرسال المسيرة بحمولة 25000
            payload = {
                "needSend": False, "runePages": {}, "heros": chosen_heroes,
                "matrixType": 3, "mapId": int(kingdom_id), "moveLineType": 3,
                "data": {
                    "data": {"currentSourceNum": target_cap, "resourceType": r_meta["res_code"]},
                    "to": {"x": int(tx), "y": int(ty), "id": str(tid)},
                    "army": army_list
                },
                "pets": chosen_pets
            }
            r_march = await self.conn.query('1007', '2', payload, timeout=8)
            if r_march and str(r_march.get('err', '0')) == '0':
                dispatched += 1
                if hero_id:
                    self._busy_heroes.add(hero_id)
                for item in army_list:
                    self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                self.log.info(f"🚀 تم إرسال مسيرة {r_meta['name']} بنجاح بحمولة ~{calc_cap:,} مورد.")
                await asyncio.sleep(round(random.uniform(2.0, 3.5), 2))

        return {"success": True, "dispatched": dispatched}

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 4: مساعدة ونقل الموارد (Resource Transport)
    # ────────────────────────────────────────────────────────────────
    async def _run_priority_transport(self) -> Dict[str, Any]:
        cfg = self.config.get("transport", {})
        if not cfg.get("enabled", False):
            self.log.info("⏭️ [أولوية 4] مساعدة الموارد معطلة.")
            return {"skipped": True}

        tx, ty = cfg.get("target_x"), cfg.get("target_y")
        if not tx or not ty:
            self.log.warning("⚠️ [أولوية 4] إحداثيات القلعة الهدف غير محددة لمساعدة الموارد.")
            return {"skipped": True, "error": "missing_coords"}

        self.log.info(f"🚚 [أولوية 4] بدء نقل الموارد إلى الهدف ({tx}, {ty})...")
        task = TransportTask(self.conn, cfg)
        res = await task.run()
        return {"success": res.success, "message": res.message}

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 5: استكشاف الأطلال (Ruins Exploration)
    # ────────────────────────────────────────────────────────────────
    async def _run_priority_ruins(self) -> Dict[str, Any]:
        cfg = self.config.get("ruins", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 5] استكشاف الأطلال معطل.")
            return {"skipped": True}

        self.log.info("🏛️ [أولوية 5] بدء استكشاف الأطلال (مسيرة واحدة حصراً)...")
        task = RuinsTask(self.conn, cfg)
        res = await task.run()
        return {"success": res.success, "message": res.message}

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 6: القتال الشامل (Combat: Elf / Invaders / Rebels)
    # ────────────────────────────────────────────────────────────────
    async def _run_priority_combat(self) -> Dict[str, Any]:
        cfg = self.config.get("combat", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 6] أولوية القتال الشامل معطلة.")
            return {"skipped": True}

        choice = cfg.get("choice", "elf").lower()
        self.log.info(f"⚔️ [أولوية 6] بدء القتال الشامل (الخيار المعتمد: {choice})...")

        if choice == "elf":
            task = ElfBossTask(self.conn, cfg)
            res = await task.run()
            return {"success": res.success, "message": res.message}

        elif choice in ("invaders", "rebels"):
            m_cfg = {
                "monster_type": choice,
                "min_lv": cfg.get("level", 30),
                "max_lv": cfg.get("level", 30),
                "max_marches": 1,
                "formation_id": cfg.get("formation_id", 1),
                "wait_for_queue": False,
            }
            task = MonsterTask(self.conn, m_cfg)
            res = await task.run()
            return {"success": res.success, "message": res.message}

        return {"skipped": True, "message": f"خيار قتال غير معروف: {choice}"}

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 7: الهجوم على المعاقل والملاجئ العامة (Stronghold)
    # ────────────────────────────────────────────────────────────────
    async def _run_priority_stronghold(self) -> Dict[str, Any]:
        cfg = self.config.get("stronghold", {})
        if not cfg.get("enabled", False):
            self.log.info("⏭️ [أولوية 7] الهجوم على المعاقل العامة معطل.")
            return {"skipped": True}

        self.log.info(f"🏯 [أولوية 7] بدء الهجوم على المعاقل والملاجئ العامة (مستوى {cfg.get('level', 30)})...")
        task_cfg = {
            "min_lv": cfg.get("level", 30),
            "max_lv": cfg.get("level", 30),
            "max_marches": cfg.get("count", 2),
            "formation_id": cfg.get("formation_id", 1),
            "wait_for_queue": False,
        }
        task = StrongholdTask(self.conn, task_cfg)
        res = await task.run()
        return {"success": res.success, "message": res.message}

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 8: جمع الذهب في أراضي التحالفات (Gold Gather)
    # ────────────────────────────────────────────────────────────────
    async def _run_priority_gold_gather(self) -> Dict[str, Any]:
        cfg = self.config.get("gold_gather", {})
        if not cfg.get("enabled", False):
            self.log.info("⏭️ [أولوية 8] جمع الذهب في أراضي التحالفات معطل.")
            return {"skipped": True}

        self.log.info("🪙 [أولوية 8] بدء جمع الذهب في أراضي التحالفات...")
        task = GoldGatherTask(self.conn, cfg)
        res = await task.run()
        return {"success": res.success, "message": res.message}

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 9: جمع الموارد الخارجية بالفيالق الشاغرة (Gather)
    # ────────────────────────────────────────────────────────────────
    async def _run_priority_gather(self) -> Dict[str, Any]:
        cfg = self.config.get("gather", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 9] جمع الموارد الخارجية معطل.")
            return {"skipped": True}

        free_q = self.get_free_queues_count()
        if free_q <= 0:
            self.log.info("ℹ️ [أولوية 9] لا توجد فيالق شاغرة لجمع الموارد الخارجية (كافة الطوابير ممتلئة).")
            return {"skipped": True, "reason": "queues_full"}

        self.log.info(f"🌾 [أولوية 9] بدء جمع الموارد بالفيالق الشاغرة ({free_q} فيالق متاحة حتى سقف {self.max_queues})...")
        task_cfg = copy.deepcopy(cfg)
        task_cfg["max_marches"] = free_q
        task = GatherTask(self.conn, task_cfg)
        res = await task.run()
        return {"success": res.success, "message": res.message}

    # ────────────────────────────────────────────────────────────────
    #  محرك التنفيذ المركزي (Execution Pipeline)
    # ────────────────────────────────────────────────────────────────
    async def run(self) -> TaskResult:
        """تشغيل مصفوفة الأولويات التسلسلية للفيالق."""
        self.log.info("🎖️" + "═" * 58)
        self.log.info(f"🎖️ بدء مهمة منسق الفيالق والمسيرات الذكي الموحد (سعة الفيالق: {self.max_queues}):")
        self.log.info("   • ترتيب الأولويات المعتمد:")
        for idx, p_key in enumerate(self.priority_order, 1):
            self.log.info(f"     {idx}. {p_key}")
        self.log.info("🎖️" + "═" * 58)

        results: Dict[str, Any] = {}
        handlers = {
            "prestige_invaders": self._run_priority_prestige_invaders,
            "prestige_stronghold": self._run_priority_prestige_stronghold,
            "prestige_gather": self._run_priority_prestige_gather,
            "transport": self._run_priority_transport,
            "ruins": self._run_priority_ruins,
            "combat": self._run_priority_combat,
            "stronghold": self._run_priority_stronghold,
            "gold_gather": self._run_priority_gold_gather,
            "gather": self._run_priority_gather,
        }

        for p_key in self.priority_order:
            handler = handlers.get(p_key)
            if not handler:
                continue

            try:
                r = await handler()
                results[p_key] = r
            except Exception as e:
                self.log.error(f"❌ خطأ أثناء تنفيذ أولوية {p_key}: {e}", exc_info=True)
                results[p_key] = {"success": False, "error": str(e)}

            await asyncio.sleep(round(random.uniform(1.5, 2.5), 2))

        active_final = self.get_active_marches_count()
        msg = f"تم إنجاز تسلسل منسق الفيالق بنجاح ({active_final}/{self.max_queues} فيالق نشطة خارج القلعة)"
        self.log.info(f"🎉 {msg}")
        return TaskResult.ok(msg, data=results)
