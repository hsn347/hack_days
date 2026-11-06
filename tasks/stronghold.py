# -*- coding: utf-8 -*-
"""
tasks/stronghold.py — مهمة الهجوم على المعقل / الملجأ (Stronghold Attack)
═══════════════════════════════════════════════════════════════════════

تُرسِل مسيرات للهجوم على المعاقل / الملاجئ على الخريطة (Stronghold / Shelter Attack).

البحث:
    • "mapType": 26 , "subType": 0

أمر المسير (1007/2):
    • "moveLineType": 3
    • "matrixType": 1
    • "judianState": 1
    • الحيوانات والرونات والجيش والأبطال من التشكيلة المحفوظة (1005/7)

الاستخدام:
    python tasks/stronghold.py --email "mohamedfarg6233@gmil.com" --minlv 1 --maxlv 30 --marches 2
"""

from __future__ import annotations

import sys
import os

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import json
import logging
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection
from tasks.monster import get_monster_recommended_power, calculate_smart_combat_troops
from tasks.exclude_manager import get_manager as _get_exclude_manager
from tasks.march_capacity import get_castle_march_capacity, enforce_safe_march_troops, record_learned_march_capacity


# ════════════════════════════════════════════════════════════════════
#  إعدادات افتراضية في رأس الملف (قابلة للتعديل والربط بـ Firebase)
# ════════════════════════════════════════════════════════════════════

DEFAULT_MIN_LV             = 1                # أدنى مستوى للمعقل
DEFAULT_MAX_LV             = 35               # أقصى مستوى للمعقل
DEFAULT_MAX_MARCHES        = 6                # الحد الأقصى للمسيرات
DEFAULT_SEARCH_RANGE       = 100              # نطاق البحث
DEFAULT_FORMATION_ID       = 1                # رقم التشكيلة المفضلة (1..5) [0 = تلقائي ذكي بدون تشكيلة ثابتة]
DEFAULT_TROOPS_COUNT       = 30000            # عدد الجنود الافتراضي / المناسب للمسيرة


# ════════════════════════════════════════════════════════════════════
#  إدارة استبعاد الأهداف المكررة (مدير مركزي موحد)
#  → تم نقلها إلى tasks/exclude_manager.py
# ════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════
#  اختيار أبطال الحرب والقتال (Combat Heroes Selection)
# ════════════════════════════════════════════════════════════════════

def _pick_combat_heroes(heroes: list, max_count: int = 2, busy: Set[int] = None) -> List[int]:
    """
    يختار أفضل أبطال قتال وحرب (5501xxx) وفق هرمية المهارات القتالية والمستوى:
    1. أبطال حرب 5501xxx يمتلكون مهارات هجومية/قتالية (5610xxx / 5640xxx).
    2. أبطال حرب 5501xxx متاحين.
    ملاحظة: يتم استبعاد أبطال الجمع (5502xxx) والدعم (5503xxx) تماماً.
    في حال عدم توفر أبطال حرب، يتم اختيار أي أبطال متاحين كخطة احتياطية.
    """
    busy = busy or set()
    tier1, tier2, tier3 = [], [], []

    for hero in heroes:
        if not isinstance(hero, dict):
            continue
        hid = hero.get('id')
        if not hid or hid in busy:
            continue
        if hero.get('status', {}).get('state', 0) != 0:
            continue

        hid_str = str(hid)
        if hid_str.startswith('5502') or hid_str.startswith('5503'):
            continue

        skills = hero.get('skillList', {})
        has_combat_skills = False
        if isinstance(skills, dict):
            has_combat_skills = any(
                str(s.get('id', '')).startswith('5610') or str(s.get('id', '')).startswith('5640')
                for s in skills.values() if isinstance(s, dict)
            )

        lv = int(hero.get('lv', 1))
        star = int(hero.get('star', 1))
        score = lv * 10 + star * 50

        if hid_str.startswith('5501'):
            if has_combat_skills:
                tier1.append((int(hid), score))
            else:
                tier2.append((int(hid), score))
        else:
            tier3.append((int(hid), score))

    tier1.sort(key=lambda x: x[1], reverse=True)
    tier2.sort(key=lambda x: x[1], reverse=True)
    tier3.sort(key=lambda x: x[1], reverse=True)

    chosen = [h[0] for h in tier1] + [h[0] for h in tier2] + [h[0] for h in tier3]

    # خطة احتياطية: أي بطل متاح في حال عدم وجود أبطال حرب مخصصين
    if not chosen:
        for hero in heroes:
            if isinstance(hero, dict):
                hid = hero.get('id')
                if hid and hid not in busy and hero.get('status', {}).get('state', 0) == 0:
                    chosen.append(int(hid))
                    if len(chosen) >= (max_count or 2):
                        break

    return chosen[:max_count] if max_count else chosen


# ════════════════════════════════════════════════════════════════════
#  اختيار جيش القتال التلقائي المتوازن (Balanced Combat Army Selection)
# ════════════════════════════════════════════════════════════════════

def select_combat_army(available: Dict[int, int], needed_count: int = DEFAULT_TROOPS_COUNT) -> List[Dict[str, int]]:
    """
    اختيار تشكيلة جيش قتالية متوازنة بالعدد المناسب:
    توزيع متوازن بين المشاة، الفرسان، والرماة بحسب المتاح في القلعة من الرتب الأعلى.
    1. المشاة (401..414)
    2. الفرسان (501..514)
    3. الرماة (601..614)
    4. القوات الخاصة (800+)
    5. عربات الحصار (701..714) كاحتياط
    """
    infantry = []   # 401..414
    cavalry  = []   # 501..514
    archers  = []   # 601..614
    carts    = []   # 701..714 كاحتياط

    for tid, count in available.items():
        if count <= 0:
            continue
        # يُمنع بتاتاً تضمين أسلحة الدفاع وفخاخ الجدار (800 فما فوق) لأنها تسبب خطأ 8062
        if 800 <= tid < 900:
            continue
        if 400 <= tid < 500:
            infantry.append((tid, count))
        elif 500 <= tid < 600:
            cavalry.append((tid, count))
        elif 600 <= tid < 700:
            archers.append((tid, count))
        elif 700 <= tid < 800:
            carts.append((tid, count))

    infantry.sort(key=lambda x: x[0], reverse=True)
    cavalry.sort(key=lambda x: x[0], reverse=True)
    archers.sort(key=lambda x: x[0], reverse=True)
    carts.sort(key=lambda x: x[0], reverse=True)

    combat_branches = [b for b in [infantry, cavalry, archers] if b]
    if not combat_branches:
        combat_branches = [carts] if carts else []

    if not combat_branches:
        return []

    army_map: Dict[int, int] = {}
    remaining_needed = needed_count

    # جولة 1: توزيع متوازن متساوٍ بين الأصناف القتالية المتوفرة
    branch_quota = max(1, remaining_needed // len(combat_branches))
    for branch in combat_branches:
        quota = min(branch_quota, remaining_needed)
        branch_taken = 0
        for tid, count in branch:
            avail = available.get(tid, 0)
            if avail <= 0:
                continue
            take = min(avail, quota - branch_taken)
            if take > 0:
                army_map[tid] = army_map.get(tid, 0) + take
                available[tid] -= take
                branch_taken += take
                remaining_needed -= take
                if branch_taken >= quota or remaining_needed <= 0:
                    break
        if remaining_needed <= 0:
            break

    # جولة 2: استكمال العدد المتبقي من أي قوات قتالية متاحة (بالترتيب من الأعلى للأدنى)
    if remaining_needed > 0:
        all_branches = combat_branches + ([carts] if carts and carts not in combat_branches else [])
        for branch in all_branches:
            for tid, count in branch:
                avail = available.get(tid, 0)
                if avail <= 0:
                    continue
                take = min(avail, remaining_needed)
                if take > 0:
                    army_map[tid] = army_map.get(tid, 0) + take
                    available[tid] -= take
                    remaining_needed -= take
                    if remaining_needed <= 0:
                        break
            if remaining_needed <= 0:
                break

    return [{"id": tid, "num": num} for tid, num in army_map.items() if num > 0]


# ════════════════════════════════════════════════════════════════════
#  اختيار الحيوان الأليف للقتال (Combat Pet Selection)
# ════════════════════════════════════════════════════════════════════

def select_combat_pet(conn: GameConnection, used_pets: Set[int]) -> List[int]:
    """
    اختيار أعلى حيوان قتالي متاح في القلعة.
    """
    pets_data = conn.init_data.get('petCtrl', {}).get('pets', {})
    if not pets_data:
        return []

    available_pets = []
    for pid_str, pinfo in pets_data.items():
        try:
            pid = int(pid_str)
            if pid not in used_pets:
                lv = int(pinfo.get('lv', 1))
                available_pets.append((pid, lv))
        except Exception:
            continue

    if not available_pets:
        return []

    available_pets.sort(key=lambda x: x[1], reverse=True)
    chosen_pet = available_pets[0][0]
    used_pets.add(chosen_pet)
    return [chosen_pet]


# ════════════════════════════════════════════════════════════════════
#  مهمة الهجوم على المعقل (StrongholdTask)
# ════════════════════════════════════════════════════════════════════

class StrongholdTask(BaseTask):
    """
    مهمة الهجوم على المعقل / الملجأ (Stronghold / Shelter Attack).
    """
    name = "stronghold"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self._heroes    : list     = []
        self._busy      : Set[int] = set()
        self._used_army : Dict[int, int] = {}
        self._used_pets : Set[int] = set()
        self._exclude_mgr = _get_exclude_manager()

    async def on_start(self):
        for _ in range(20):
            if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
                break
            if self.conn.init_data:
                break
            await asyncio.sleep(0.5)
        await self._load_heroes()

    async def _load_heroes(self):
        """جلب بيانات أبطال الحساب من الذاكرة الحية."""
        hctrl = self.conn.init_data.get('heroCtrl') if hasattr(self.conn, 'init_data') else None
        if isinstance(hctrl, list) and hctrl:
            self._heroes = list(hctrl)
            return

        # احتياطي نادر إذا كانت الذاكرة غير محملة
        self._heroes = []
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        for h_list in army_ctrl.get('compileHeros', {}).values():
            if isinstance(h_list, list):
                for hid in h_list:
                    if str(hid).isdigit() and int(hid) > 0:
                        int_hid = int(hid)
                        if not any(h.get('id') == int_hid for h in self._heroes):
                            self._heroes.append({'id': int_hid, 'status': {'state': 0}, 'skillList': {}})


    # ── المهمة الرئيسية ───────────────────────────────────────────

    async def run(self) -> TaskResult:
        cfg = self.config
        min_lv          = int(cfg.get('min_lv', DEFAULT_MIN_LV))
        max_lv          = int(cfg.get('max_lv', DEFAULT_MAX_LV))
        max_marches     = int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))
        search_range    = int(cfg.get('search_range', DEFAULT_SEARCH_RANGE))
        formation_id    = int(cfg.get('formation_id', DEFAULT_FORMATION_ID))
        troops_cfg      = int(cfg.get('troops_count', DEFAULT_TROOPS_COUNT))

        self.log.info(f"🏰 [المعقل] بدء الهجوم (لفل: {min_lv}-{max_lv} | المطلوب: {max_marches})")

        if not self._heroes:
            await self._load_heroes()

        sent_count = 0
        consecutive_errors = 0
        self._busy      = set(cfg.get('busy_heroes', cfg.get('busy', [])))
        self._used_army = {}
        self._used_pets = set()

        wait_for_queue = bool(cfg.get('wait_for_queue', cfg.get('wait_queue', False)))
        wait_interval  = float(cfg.get('wait_interval', 15.0))
        max_wait_cycles = int(cfg.get('max_wait_cycles', 40))
        wait_cycles = 0
        cmd_opting_retries = 0
        last_result = None

        while sent_count < max_marches:
            current_target_idx = sent_count + 1
            self.log.debug(f"🚀 محاولة إرسال مسيرة المعقل رقم ({current_target_idx}/{max_marches})...")
            result_code = await self._send_one_stronghold(min_lv, max_lv, search_range, formation_id, troops_cfg)
            last_result = result_code

            if result_code == "SUCCESS":
                sent_count += 1
                consecutive_errors = 0
                cmd_opting_retries = 0
                wait_cycles = 0
                if sent_count < max_marches:
                    spacing = round(random.uniform(4.5, 7.5), 2)
                    self.log.debug(f"🛡️ انتظار {spacing} ثانية قبل مسيرة المعقل التالية...")
                    await asyncio.sleep(spacing)
            elif result_code == "QUEUE_FULL":
                if not wait_for_queue or wait_cycles >= max_wait_cycles:
                    self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل.")
                    break

                cur_act = await self.get_active_marches_count()
                max_q = max(getattr(self, '_max_castle_queues', 0), max(1, cur_act))
                self._max_castle_queues = max_q

                queue_freed = False
                while wait_for_queue and wait_cycles < max_wait_cycles:
                    wait_cycles += 1
                    self.log.info(
                        f"⏳ [طوابير ممتلئة ({cur_act}/{max_q}) - دورة {wait_cycles}/{max_wait_cycles}] "
                        f"جميع الفيالق مشغولة بالخارج — الانتظار {wait_interval:.0f} ثانية لتفريغ فيلق للمعقل..."
                    )
                    await asyncio.sleep(wait_interval)

                    cur_act = await self.get_active_marches_count()
                    self.log.info(f"🔍 [فحص الفيالق] الفيالق النشطة بالخارج حالياً: {cur_act}/{max_q}")
                    if cur_act < max_q:
                        self.log.info(
                            f"✅ [توفر فيلق شاغر] عاد أحد الفيالق إلى القلعة بنجاح ({cur_act}/{max_q}) "
                            f"— استئناف هجوم المعقل الآن!"
                        )
                        queue_freed = True
                        break
                    else:
                        self.log.info(
                            f"⏳ [الفيالق لا تزال ممتلئة ({cur_act}/{max_q})] "
                            f"لم يعد أي فيلق بعد — مواصلة الانتظار {wait_interval:.0f} ثانية أخرى دون إرسال محاولات فاشلة..."
                        )

                if queue_freed:
                    self._busy.clear()
                    self._used_army.clear()
                    await self._load_heroes()
                    continue
                else:
                    self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل بعد استنفاد دورات الانتظار.")
                    break
            elif result_code in ("HERO_BUSY", "NO_HEROES"):
                # إذا كان البطل مشغولاً وتوجد أبطال قتال بديلة متاحة: تجربة البطل التالي فوراً
                avail_combat_heroes = [h for h in self._heroes if isinstance(h, dict) and h.get('id') not in self._busy and str(h.get('id', '')).startswith('5501')]
                if result_code == "HERO_BUSY" and avail_combat_heroes:
                    self.log.info(f"🔄 البطل السابق في مسيرة — تجربة بطل قتالي بديل فوراً ({len(avail_combat_heroes)} متاح بالقلعة)...")
                    continue
                if wait_for_queue and wait_cycles < max_wait_cycles:
                    wait_cycles += 1
                    self.log.info(f"⏳ [أبطال مشغولون ({wait_cycles}/{max_wait_cycles})] بانتظار عودة الأبطال من المسيرات (انتظار {wait_interval:.0f} ثانية)...")
                    await asyncio.sleep(wait_interval)
                    self._busy.clear()
                    self._used_army.clear()
                    await self._load_heroes()
                    continue
                else:
                    self.log.warning("⚠️ لا يتوفر أبطال متاحون حالياً بالقلعة.")
                    break
            elif result_code == "NO_ARMY":
                if wait_for_queue and wait_cycles < max_wait_cycles:
                    wait_cycles += 1
                    self.log.info(f"⏳ [القوات في مسيرات ({wait_cycles}/{max_wait_cycles})] بانتظار عودة الجيش إلى القلعة (انتظار {wait_interval:.0f} ثانية)...")
                    await asyncio.sleep(wait_interval)
                    self._busy.clear()
                    self._used_army.clear()
                    continue
                else:
                    self.log.warning("⚠️ نفدت القوات المتاحة بالقلعة.")
                    break
            elif result_code == "STAMINA_EMPTY":
                self.log.warning("🛑 نفدت طاقة اللورد بالكامل — إيقاف محاولات الهجوم على المعقل.")
                break
            elif result_code in ("CMD_OPTING", "16001", "CMD_OPTING_FAILED"):
                cmd_opting_retries += 1
                if cmd_opting_retries <= 2:
                    wait_time = round(random.uniform(10.0, 16.0), 2)
                    self.log.warning(
                        f"⏳ [خادم اللعبة مشغول - كود 16001] انتظار {wait_time} ثانية لفك القفل "
                        f"ثم إعادة تجهيز مسيرة المعقل نظيفاً من البداية (محاولة {cmd_opting_retries}/2)..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    self.log.warning("🏁 استمر انشغال خادم اللعبة (كود 16001) بعد المحاولات — إيقاف الدورة مؤقتاً.")
                    break
            elif result_code in ("NO_TARGET", "TARGET_OCCUPIED"):
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    self.log.warning("⚠️ 3 محاولات بحث متتالية دون جدوى — إنهاء المهمة.")
                    break
                await asyncio.sleep(round(random.uniform(1.8, 3.2), 2))
                continue
            else:
                consecutive_errors += 1
                if consecutive_errors >= 2:
                    break
                await asyncio.sleep(round(random.uniform(1.8, 3.2), 2))

        self.log.info(f"🏁 [المعقل] تم إرسال {sent_count}/{max_marches} مسيرة بنجاح")
        if sent_count > 0:
            return TaskResult.ok(
                f"✅ تم إرسال {sent_count} مسيرة هجوم على المعقل",
                sent=sent_count,
                queue_full=(last_result == "QUEUE_FULL"),
                stop_reason=last_result
            )
        if last_result == "QUEUE_FULL":
            return TaskResult.fail("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل (كود 8004: QUEUE_FULL)", queue_full=True, stop_reason="QUEUE_FULL")
        if last_result == "STAMINA_EMPTY":
            return TaskResult.fail("🛑 نفدت طاقة اللورد بالكامل", stop_reason="STAMINA_EMPTY")
        return TaskResult.fail("لم يتم إرسال أي مسيرة هجوم على المعقل", retry_after=120)

    # ── إرسال مسيرة معقل واحدة ────────────────────────────────────

    async def _send_one_stronghold(self, min_lv: int, max_lv: int, search_range: int, formation_id: int, troops_cfg: int) -> str:
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. جلب إحداثيات البحث من الذاكرة الحية cityCtrl (Zero-Request)
        cx = self.config.get('center_x') or self.config.get('x')
        cy = self.config.get('center_y') or self.config.get('y')
        if cx is None or cy is None:
            pos = self.conn.init_data.get('cityCtrl', {}).get('cinfo', {}).get('pos', {}) if hasattr(self.conn, 'init_data') else {}
            if pos and 'x' in pos and 'y' in pos:
                cx, cy = int(pos['x']), int(pos['y'])
            else:
                try:
                    self.log.warning("🛑🛑🛑🛑🛑🛑")
                    r_castle = await self.conn.query('1006', '25', {"uid": uid_int})
                    if not r_castle or not r_castle.get('retData'):
                        return "ERROR"
                    cx = r_castle['retData'].get('x')
                    cy = r_castle['retData'].get('y')
                except Exception:
                    return "ERROR"
        else:
            cx = int(cx)
            cy = int(cy)

        # 2. جلب معرف المملكة من الذاكرة الحية (Zero-Request)
        kingdom_id = 0
        if getattr(self.conn, 'kingdom_id', None):
            try: kingdom_id = int(self.conn.kingdom_id)
            except: pass
        if not kingdom_id and hasattr(self.conn, 'init_data'):
            kingdom_id = self.conn.init_data.get('lordInfoCtrl', {}).get('base', {}).get('partition', 0)
        if not kingdom_id:
            try:
                self.log.warning("🛑🛑🛑🛑🛑🛑")
                r_map = await self.conn.query('1002', '7', {"uid": uid_int})
                if r_map and 'data' in r_map:
                    kingdom_id = r_map['data'].get('base', {}).get('partition', 0)
            except Exception:
                pass
        if not kingdom_id:
            kingdom_id = 4


        # 3. البحث عن المعاقل (mapType: 26, subType: 0)
        exclude_map = await self._exclude_mgr.get_exclude_map(self.uid, kingdom_id=kingdom_id)
        search_payload = {
            "mapType": 26,
            "subType": 0,
            "num": 5,
            "y": cy,
            "x": cx,
            "exclude": exclude_map,
            "range": search_range,
        }
        if min_lv and max_lv:
            search_payload["minLv"] = min_lv
            search_payload["maxLv"] = max_lv

        r_search = await self.conn.query('2011', '3', search_payload)
        raw_candidates = r_search.get('result', []) if r_search else []
        candidates = [c for c in raw_candidates if str(c.get('id', '')) not in exclude_map]
        if not candidates:
            self.log.warning(f"⚠️ لا توجد معاقل متاحة في نطاق {search_range}!")
            return "NO_TARGET"



        # 4. جلب القوات المتوفرة بالقلعة من الذاكرة الحية مباشرة (Zero-Request)
        available: Dict[int, int] = {}
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        if isinstance(army_ctrl, dict):
            for k, v in army_ctrl.get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)

        if not available:
            try:
                self.log.warning("🛑🛑🛑🛑🛑🛑")
                r_army = await self.conn.query('1005', '1', {})
                if r_army and 'data' in r_army:
                    for k, v in r_army['data'].get('totalArmy', {}).items():
                        if str(k).isdigit() and str(v).isdigit():
                            available[int(k)] = int(v)
            except Exception:
                pass

        for tid, used in self._used_army.items():
            if tid in available:
                available[tid] = max(0, available[tid] - used)

        # 5. جلب بيانات التشكيلة المحفوظة من الذاكرة الحية مباشرة (Zero-Request)
        form_heroes     = []
        form_pets       = []
        form_rune_pages = []
        form_army_dict  = {}
        if formation_id and formation_id > 0:
            army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
            if isinstance(army_ctrl, dict):
                fid_str = str(formation_id)
                c_heroes = army_ctrl.get('compileHeros', {})
                if isinstance(c_heroes, dict) and fid_str in c_heroes:
                    form_heroes = c_heroes[fid_str]

                c_pets = army_ctrl.get('compilePets', {})
                if isinstance(c_pets, dict) and fid_str in c_pets:
                    form_pets = c_pets[fid_str]

                c_runes = army_ctrl.get('compileRunePages', {})
                if isinstance(c_runes, dict) and fid_str in c_runes:
                    form_rune_pages = c_runes[fid_str]

                c_army = army_ctrl.get('compileArmy', {})
                if isinstance(c_army, dict) and fid_str in c_army:
                    form_army_dict = c_army[fid_str]

            if not form_heroes and not form_army_dict:
                try:
                    self.log.warning("🛑🛑🛑🛑🛑🛑")
                    r_form = await self.conn.query('1005', '7', {"compiletype": formation_id})
                    if r_form and 'data' in r_form:
                        form_heroes     = r_form['data'].get('compileHeros', [])
                        form_pets       = r_form['data'].get('compilePets', [])
                        form_rune_pages = r_form['data'].get('compileRunePages', [1])
                        form_army_dict  = r_form['data'].get('compileArmy', {})
                except Exception:
                    pass


        # 6. اختيار الأبطال
        chosen_heroes = []
        if not self._heroes:
            await self._load_heroes()

        if form_heroes:
            flat_heroes = []
            if isinstance(form_heroes, list):
                flat_heroes = form_heroes
            elif isinstance(form_heroes, dict):
                for sub in form_heroes.values():
                    if isinstance(sub, list): flat_heroes.extend(sub)
                    elif sub: flat_heroes.append(sub)

            available_form_heroes = []
            for h in flat_heroes:
                if h and str(h).isdigit():
                    hid = int(h)
                    if hid not in self._busy:
                        hero_data = next((x for x in self._heroes if x.get('id') == hid), None)
                        if hero_data and hero_data.get('status', {}).get('state', 0) == 0:
                            available_form_heroes.append(hid)

            if len(available_form_heroes) >= 2:
                chosen_heroes = available_form_heroes[:2]
                self.log.debug(f"🎖️ أبطال التشكيلة: {chosen_heroes}")
            elif len(available_form_heroes) == 1:
                hero1 = available_form_heroes[0]
                extra_busy = set(self._busy) | {hero1}
                filler = _pick_combat_heroes(self._heroes, max_count=1, busy=extra_busy)
                if filler:
                    chosen_heroes = [hero1, filler[0]]
                else:
                    chosen_heroes = [hero1]
                self.log.debug(f"⚔️ تشكيلة الأبطال: {chosen_heroes}")

        if not chosen_heroes:
            chosen_heroes = _pick_combat_heroes(self._heroes, max_count=2, busy=self._busy)
            if len(chosen_heroes) == 2:
                self.log.debug(f"⚔️ أبطال الحرب البدلاء: {chosen_heroes}")
            elif len(chosen_heroes) == 1:
                self.log.debug(f"⚔️ بطل حرب واحد متاح: {chosen_heroes}")
            else:
                any_cands = [int(h['id']) for h in self._heroes if isinstance(h, dict) and h.get('id') and int(h['id']) not in self._busy and h.get('status', {}).get('state', 0) == 0]
                if any_cands:
                    chosen_heroes = any_cands[:2]
                    self.log.debug(f"⚠️ بديل اضطراري: {chosen_heroes}")
                else:
                    self.log.warning("⚠️ لا يوجد أي بطل متاح بالقلعة نهائياً!")
                    return "NO_HEROES"

        # 7. تكوين جيش المسيرة الذكي (التشكيلة مع الإكمال التلقائي للنقص بالجنود المناسبين)
        # جلب قوة القلعة الإجمالية من بيانات الجلسة لفحص القوة الموصى بها
        castle_power = 0
        try:
            fc_info = self.conn.init_data.get("lordInfoCtrl", {}).get("fcInfo", {})
            castle_power = int(fc_info.get("totalFc", 0))
            if not castle_power:
                castle_power = int(self.conn.init_data.get("charInfo", {}).get("power", 0))
        except Exception:
            pass

        target_lv = int(candidates[0].get('level', max_lv)) if candidates else max_lv
        smart_troops, rec_power, power_status = calculate_smart_combat_troops(
            target_type="stronghold",
            target_level=target_lv,
            castle_power=castle_power,
            user_troops_cfg=troops_cfg
        )

        army_list = []
        # احتساب سعة مسيرة اللورد الحقيقية مع الأبطال المختارين ديناميكياً بدلاً من رقم ثابت
        max_safe_capacity = get_castle_march_capacity(self.conn, chosen_heroes=chosen_heroes)

        if form_army_dict and formation_id > 0:
            # حساب إجمالي القوات المطلوبة في التشكيلة المحفوظة باللعبة (مع استبعاد فخاخ الجدار 800-899)
            total_form_req = sum(
                int(v) for k, v in form_army_dict.items()
                if str(k).isdigit() and str(v).isdigit() and not (800 <= int(k) < 900)
            )

            # اعتماد التشكيلة المحفوظة بالكامل بما لا يتجاوز سعة مسيرة اللورد الحقيقية
            scale = 1.0
            if total_form_req > max_safe_capacity:
                scale = float(max_safe_capacity) / float(total_form_req)
                needed_target = max_safe_capacity
                self.log.info(
                    f"🎖️ [التشكيلة المحفوظة #{formation_id}] إجمالي جنودها ({total_form_req:,}) يتجاوز سعة مسيرة القلعة ({max_safe_capacity:,}) — "
                    f"تم ضبطها لـ {needed_target:,} جندي بأعلى نسبة أمان لمنع خطأ 8035"
                )
            else:
                needed_target = total_form_req
                self.log.info(
                    f"🎖️ [التشكيلة المحفوظة #{formation_id}] اعتماد كامل جنود التشكيلة ({needed_target:,} جندي) ضمن سعة القلعة ({max_safe_capacity:,})"
                )

            for k, v in form_army_dict.items():
                if str(k).isdigit() and str(v).isdigit():
                    tid = int(k)
                    if 800 <= tid < 900:
                        continue
                    req = int(v)
                    scaled_req = max(1, int(req * scale)) if scale < 1.0 else req
                    avail = available.get(tid, 0)
                    take = min(scaled_req, avail)
                    if take > 0:
                        army_list.append({"id": tid, "num": take})
                        available[tid] -= take
        else:
            needed_target = min(smart_troops, max_safe_capacity)
            if rec_power > 0:
                self.log.info(
                    f"🎯 [فحص القوة الذكي] الهدف: معقل (لفل {target_lv}) | "
                    f"القوة الموصى بها: {rec_power:,} | قوة قلعتك: {castle_power:,} | الحالة: {power_status}"
                )
                self.log.info(
                    f"⚔️ [حساب الجيش الذكي] تم احتساب سعة المسيرة ديناميكياً: {needed_target:,} جندي (سعة اللورد القصوى: {max_safe_capacity:,})"
                )

        form_troops_count = sum(item['num'] for item in army_list)

        if form_troops_count == 0:
            if formation_id > 0:
                self.log.info(f"⚠️ التشكيلة المحفوظة ({formation_id}) فارغة أو لا تتوفر أي من قواتها بالقلعة — جاري اختيار جيش قتالي متوازن بالكامل ({needed_target:,} جندي)...")
            army_list = select_combat_army(available, needed_count=needed_target)
        elif form_troops_count < needed_target:
            deficit = needed_target - form_troops_count
            self.log.info(
                f"ℹ️ جنود التشكيلة ({formation_id}) غير كافيين بالقلعة ({form_troops_count:,}/{needed_target:,} جندي) — "
                f"جاري إكمال النقص ({deficit:,} جندي) تلقائياً بأفضل قوات قتالية متوازنة..."
            )
            extra_army = select_combat_army(available, needed_count=deficit)
            if extra_army:
                army_dict_combined: Dict[int, int] = {}
                for item in army_list:
                    army_dict_combined[item['id']] = army_dict_combined.get(item['id'], 0) + item['num']
                for item in extra_army:
                    army_dict_combined[item['id']] = army_dict_combined.get(item['id'], 0) + item['num']
                army_list = [{"id": tid, "num": cnt} for tid, cnt in army_dict_combined.items() if cnt > 0]
        elif form_troops_count > needed_target:
            # ضبط الزيادة الناتجة عن التقريب لضمان عدم تجاوز الحد الأقصى للمسيرة
            excess = form_troops_count - needed_target
            for item in sorted(army_list, key=lambda x: x['num'], reverse=True):
                if excess <= 0:
                    break
                trim = min(excess, item['num'] - 1)
                if trim > 0:
                    item['num'] -= trim
                    available[item['id']] = available.get(item['id'], 0) + trim
                    excess -= trim

        # تطبيق صمام الأمان الصارم لمنع تجاوز سعة مسيرة اللورد برمجياً
        army_list = enforce_safe_march_troops(army_list, max_safe_capacity)

        if not army_list:
            self.log.warning("⚠️ لا توجد قوات متوفرة بالقلعة لإرسال المسيرة!")
            return "NO_ARMY"

        total_troops = sum(item['num'] for item in army_list)

        # 8. اختيار الحيوان الأليف والرونات
        pets_list = []
        if form_pets:
            flat_pets = []
            if isinstance(form_pets, list):
                flat_pets = form_pets
            elif isinstance(form_pets, dict):
                for sub in form_pets.values():
                    if isinstance(sub, list): flat_pets.extend(sub)
                    elif sub: flat_pets.append(sub)

            for p in flat_pets:
                if p and str(p).isdigit() and int(p) > 0:
                    pets_list = [int(p)]
                    break

        if not pets_list:
            pets_list = select_combat_pet(self.conn, self._used_pets)

        rune_pages_list = [1]
        if isinstance(form_rune_pages, list) and form_rune_pages:
            rune_pages_list = [int(x) for x in form_rune_pages if str(x).isdigit()]
        elif isinstance(form_rune_pages, dict) and form_rune_pages:
            for v in form_rune_pages.values():
                if isinstance(v, list) and v:
                    rune_pages_list = [int(x) for x in v if str(x).isdigit()]
                    break
                elif str(v).isdigit():
                    rune_pages_list = [int(v)]
                    break
        if not rune_pages_list:
            rune_pages_list = [1]

        self.log.debug(f"🛡️ تشكيلة المعقل: إجمالي جنود: {total_troops:,}")

        # 9. محاولة إرسال مسيرة المعقل على أهداف القائمة تباعاً
        for target in candidates:
            target_id = target.get('id')
            tx, ty    = target.get('x'), target.get('y')
            t_lv      = target.get('level', '?')
            self.log.debug(f"🎯 محاولة استهداف معقل: ID={target_id} عند ({tx}, {ty}) لفل={t_lv}")
            # حجز مؤقت في الذاكرة فقط — لن يُثبت في الملف إلا بعد نجاح الهجوم
            await self._exclude_mgr.reserve(self.uid, target_id, kingdom_id=kingdom_id)

            # ── فحص مسبق شامل (1006/22 + 1006/1000): هل المعقل مشغول بمعركة أو مسيرة متجهة له حالياً؟ ──
            is_busy, busy_reason, _ = await self.check_target_busy_or_marched(
                target_id=target_id,
                tx=tx,
                ty=ty,
                kingdom_id=kingdom_id,
                is_stronghold=True
            )
            if is_busy:
                self.log.warning(f"⚠️ المعقل {target_id} مستبعد: {busy_reason} — تخطي للبديل...")
                await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                continue

            attack_payload = {
                "needSend": False,
                "runePages": rune_pages_list,
                "heros": chosen_heroes,
                "matrixType": 1,
                "mapId": int(kingdom_id),
                "moveLineType": 3,               # 3 = مسار الهجوم على المعقل
                "data": {
                    "data": {
                        "judianState": 1         # 1 = حالة المعقل (judianState)
                    },
                    "to": {
                        "y": int(ty),
                        "x": int(tx),
                        "id": str(target_id)
                    },
                    "army": army_list
                },
                "pets": pets_list
            }

            r_attack = await self.conn.query('1007', '2', attack_payload)
            if not r_attack:
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                continue

            err = str(r_attack.get('err', '0'))
            if err == '0':
                self.log.info(f"✅ [المعقل] إرسال مسيرة بنجاح إلى معقل لفل {t_lv} عند ({tx}, {ty}) | جنود: {total_troops:,}")
                # ✅ نجاح — تثبيت الاستبعاد في الملف
                await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                for hid in chosen_heroes:
                    self._busy.add(hid)
                for item in army_list:
                    self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                return "SUCCESS"
            elif err in ('8004', '9007004'):
                self.log.info(f"🛑 اكتملت طوابير المسيرات للقلعة (كود {err})")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "QUEUE_FULL"
            elif err == '8009':
                self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "NO_ARMY"
            elif err in ('8032', '10002', '10003'):
                self.log.warning(f"🛑 نفدت طاقة اللورد بالكامل (كود {err})")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "STAMINA_EMPTY"
            elif err == '9007020':
                for hid in chosen_heroes:
                    self._busy.add(hid)
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "HERO_BUSY"
            elif err == '8035':
                current_total = sum(item['num'] for item in army_list)
                if current_total > 400:
                    reduced_troops = max(300, int(current_total * 0.85))
                    record_learned_march_capacity(self.conn, reduced_troops)
                    self.log.warning(f"⚠️ خطأ 8035 (تجاوز سعة مسيرة اللورد) | إعادة المحاولة فوراً بضبط القوات ({reduced_troops:,} جندي)...")
                    army_list = enforce_safe_march_troops(army_list, reduced_troops)
                    total_troops = sum(itm['num'] for itm in army_list)
                    attack_payload['data']['army'] = army_list
                    r_retry = await self.conn.query('1007', '2', attack_payload)
                    if r_retry and str(r_retry.get('err', '0')) == '0':
                        self.log.info(f"✅ تم إرسال مسيرة المعقل بنجاح بعد ضبط القوات! → {target_id} (لفل {t_lv}) | أبطال={chosen_heroes} | جنود={total_troops:,}")
                        await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                        for hid in chosen_heroes:
                            self._busy.add(hid)
                        for item in army_list:
                            self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                        return "SUCCESS"
                # تنبيه: خطأ 8035 هو خطأ سعة مسيرة وليس انشغال معقل — لا نستبعد المعقل من قاعدة البيانات
                self.log.warning(f"⚠️ خطأ 8035 في المعقل {target_id} | تحرير الهدف وتعديل سقف السعة دون حظر المعقل...")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                continue
            elif err == '16001':
                self.log.warning(
                    f"   ⚠️ خادم اللعبة مشغول بعملية سابقة (كود 16001: Err_CMD_OPTING) — "
                    f"تحرير المعقل {target_id} لإعادة تجهيز المسيرة نظيفاً من البداية..."
                )
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "CMD_OPTING"
            elif err in ('8062', '8063', '8060', '8013', '8002', '8026', '8003', '9007062') or (err.isdigit() and 8000 <= int(err) < 8100 and err not in ('8004', '8009', '8032')):
                self.log.warning(f"⚠️ المعقل {target_id} غير متاح أو مشغول بمعركة أخرى (كود {err}) — فحص معقل بديل فوراً...")
                # المعقل مشغول فعلاً — نثبت الاستبعاد
                await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                continue
            else:
                self.log.error(f"❌ خطأ غير معروف: {err} | الهدف={target_id}")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "ERROR"

        return "TARGET_OCCUPIED"


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Stronghold Attack Bot — الهجوم على المعقل / الملجأ")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--minlv", type=int, default=DEFAULT_MIN_LV, help=f"أدنى لفل للمعقل [افتراضي: {DEFAULT_MIN_LV}]")
    parser.add_argument("--maxlv", type=int, default=DEFAULT_MAX_LV, help=f"أعلى لفل للمعقل [افتراضي: {DEFAULT_MAX_LV}]")
    parser.add_argument("--marches", "-m", type=int, default=DEFAULT_MAX_MARCHES, help=f"الحد الأقصى للمسيرات [افتراضي: {DEFAULT_MAX_MARCHES}]")
    parser.add_argument("--range", type=int, default=DEFAULT_SEARCH_RANGE, help=f"نطاق البحث [افتراضي: {DEFAULT_SEARCH_RANGE}]")
    parser.add_argument("--formation", "-f", type=int, default=DEFAULT_FORMATION_ID, help=f"رقم التشكيلة [افتراضي: {DEFAULT_FORMATION_ID}]")
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
            await asyncio.sleep(2.0)  # حماية من الحظر
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "min_lv": args.minlv,
            "max_lv": args.maxlv,
            "max_marches": args.marches,
            "search_range": args.range,
            "formation_id": args.formation
        }

        task = StrongholdTask(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
