# -*- coding: utf-8 -*-
"""
tasks/ruins.py — مهمة استكشاف الأطلال (Relics / Ruins Exploration)
═════════════════════════════════════════════════════════════════

تُرسِل مسيرة واحدة فقط لاستكشاف الأطلال على الخريطة (Relics Exploration).

ملاحظات ميكانيكا اللعبة:
    • الأطلال ليس لها مستويات على الخريطة (تظهر بلفل 0، واستعلام البحث لا يتضمن أي لفل).
    • مسيرة واحدة فقط مسموحة دائماً لكل قلعة (خطأ 8037 عند محاولة إرسال مسيرة ثانية).
    • مدة الاستكشاف المتاحة باللعبة (4 فترات فقط): 15 دقيقة (900ث)، 1 ساعة (3600ث)، 4 ساعات (14400ث)، 8 ساعات (28800ث).

البحث:
    • "mapType": 7 , "subType": 0

أمر المسير (1007/2):
    • "moveLineType": 4
    • "matrixType": 1
    • "exploreTime": 900 (15 دقيقة افتراضياً)
    • الحيوانات والرونات والجيش من التشكيلة المحفوظة (1005/7)

الاستخدام:
    python tasks/ruins.py --email "saad444505@icloud.com" --time 28800 
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
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection
from tasks.exclude_manager import get_manager as _get_exclude_manager
from tasks.march_capacity import get_castle_march_capacity, record_learned_march_capacity, enforce_safe_march_troops


# ════════════════════════════════════════════════════════════════════
#  إعدادات افتراضية في رأس الملف (قابلة للتعديل والربط بـ Firebase)
# ════════════════════════════════════════════════════════════════════

MAX_MARCHES                = 1                # مسيرة واحدة فقط مسموحة دائماً للأطلال في اللعبة
DEFAULT_MAX_ATTEMPTS       = 10               # الحد الأقصى لمحاولات تجربة أهداف بديلة عند الفشل
DEFAULT_SEARCH_RANGE       = 100              # نطاق البحث (كم)
DEFAULT_FORMATION_ID       = 1                # رقم التشكيلة المفضلة (1..5)
DEFAULT_EXPLORE_TIME       = 900              # مدة الاستكشاف بالثواني (900 = 15 دقيقة)
VALID_EXPLORE_TIMES        = (900, 3600, 14400, 28800) # المدد الرسمية المدعومة حصراً ببروتوكول اللعبة
DEFAULT_TROOPS_COUNT       = 1000             # احتياطي فقط عند غياب التشكيلة


# ════════════════════════════════════════════════════════════════════
#  جدول القوة القتالية الرسمية لرتب الجنود (Combat Power FC per Troop)
# ════════════════════════════════════════════════════════════════════

TROOP_TIER_FC: Dict[int, float] = {
    1: 2.5,
    2: 4.0,
    3: 6.0,
    4: 8.0,
    5: 12.0,
    6: 18.0,
    7: 26.0,
    8: 36.0,
    9: 50.0,
    10: 68.0,
    11: 90.0,
    12: 120.0,
    13: 160.0,
    14: 200.0,
}

def get_troop_tier(tid: int) -> int:
    """استخراج رتبة الجندي (1..14) من معرفه (مثال: 410 -> 10)."""
    return tid % 100

def get_troop_branch(tid: int) -> str:
    """تحديد الفرع التكتيكي للجندي (مشاة، فرسان، رماة، عربات)."""
    if 400 <= tid < 500:
        return "infantry"
    elif 500 <= tid < 600:
        return "cavalry"
    elif 600 <= tid < 700:
        return "archers"
    elif 700 <= tid < 800:
        return "siege"
    return "other"

def get_troop_unit_fc(tid: int) -> float:
    """حساب القوة القتالية للجندي الواحد بناءً على رتبته الرسمية."""
    tier = get_troop_tier(tid)
    return TROOP_TIER_FC.get(tier, max(2.5, float(tier) * 5.0))

# ════════════════════════════════════════════════════════════════════
#  اختيار أبطال الحرب والقتال الصارمين (War Heroes Selection)
# ════════════════════════════════════════════════════════════════════

def _pick_combat_heroes(
    heroes: list,
    max_count: int = 2,
    busy: Set[int] = None,
    dominant_branch: str = "cavalry"
) -> List[int]:
    """
    اختيار أفضل أبطال قتال وحرب (5501xxx) حصراً وبشكل صارم:
    - حظر تام لأبطال جمع الموارد (5502xxx) وأبطال الدعم (5503xxx).
    - أولوية لأبطال الحرب 5501xxx المتخصصين في نفس الصنف التكتيكي للجيش (مشاة / فرسان / رماة).
    - الترتيب حسب: المهارات القتالية المتوافقة، النجوم، والمستوى.
    - يضمن دائماً اختيار بطلي حرب ما لم تكن القلعة فارغة من أبطال الحرب.
    """
    busy = busy or set()
    tier1_matching, tier2_war, tier3_other = [], [], []

    # مهارات التخصص القتالي: 5610xxx (مشاة)، 5620xxx (فرسان)، 5630xxx (رماة)، 5640xxx (قتال عام)
    branch_skill_prefixes = {
        "infantry": ("5610", "5640"),
        "cavalry":  ("5620", "5640"),
        "archers":  ("5630", "5640"),
        "siege":    ("5640",)
    }.get(dominant_branch, ("5640",))

    for hero in heroes:
        if not isinstance(hero, dict):
            continue
        hid = hero.get('id')
        if not hid or hid in busy:
            continue
        if hero.get('status', {}).get('state', 0) != 0:
            continue

        hid_str = str(hid)
        # 🛑 حظر تام ومطلق لأبطال جمع الموارد والدعم
        if hid_str.startswith('5502') or hid_str.startswith('5503'):
            continue

        lv = int(hero.get('lv', 1))
        star = int(hero.get('star', 1))
        score = lv * 10 + star * 50

        skills = hero.get('skillList', {})
        has_branch_skills = False
        if isinstance(skills, dict):
            for s in skills.values():
                if isinstance(s, dict):
                    sid = str(s.get('id', ''))
                    if any(sid.startswith(p) for p in branch_skill_prefixes):
                        has_branch_skills = True
                        score += 300
                        break

        if hid_str.startswith('5501'):
            if has_branch_skills:
                tier1_matching.append((int(hid), score))
            else:
                tier2_war.append((int(hid), score))
        else:
            tier3_other.append((int(hid), score))

    tier1_matching.sort(key=lambda x: x[1], reverse=True)
    tier2_war.sort(key=lambda x: x[1], reverse=True)
    tier3_other.sort(key=lambda x: x[1], reverse=True)

    candidates = [h[0] for h in tier1_matching] + [h[0] for h in tier2_war] + [h[0] for h in tier3_other]
    return candidates[:max_count] if max_count else candidates

# ════════════════════════════════════════════════════════════════════
#  مهمة استكشاف الأطلال (RuinsTask)
# ════════════════════════════════════════════════════════════════════

class RuinsTask(BaseTask):
    """
    مهمة استكشاف الأطلال على الخريطة (Relics / Ruins Exploration).
    """
    name = "ruins"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self._heroes    : list     = []
        self._busy      : Set[int] = set()
        self._used_army : Dict[int, int] = {}
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

    async def is_ruins_march_active(self) -> bool:
        """
        فحص هل توجد مسيرة استكشاف أطلال نشطة بالخارج حالياً من الذاكرة الحية فورياً (Zero-Request).
        يعتمد على نوع المسار (moveLineType = 4) أو نوع خريطة الهدف (mapType = 7).
        """
        all_queue_data = []
        if getattr(self.conn, 'local_queues', None):
            all_queue_data.extend(self.conn.local_queues)
        for p in self.conn.cached_packets.values():
            if isinstance(p, dict):
                d = p.get('data', {})
                if isinstance(d, dict) and d.get('notifyID') == 'NOTIFY_LOCAL_QUEUE_SYNC':
                    nd = d.get('notifyData', [])
                    if isinstance(nd, list):
                        all_queue_data.extend(nd)

        for item in all_queue_data:
            q_list = item.get('data', []) if (isinstance(item, dict) and 'data' in item) else ([item] if isinstance(item, dict) else (item if isinstance(item, list) else []))
            for q in q_list:
                if not isinstance(q, dict):
                    continue
                if q.get('status') in (0, 1, 2, 3, 4, 7):
                    if q.get('moveLineType') == 4:
                        return True
                    to_info = q.get('to', {})
                    if isinstance(to_info, dict) and to_info.get('mapType') == 7:
                        return True
        return False

    # ── المهمة الرئيسية ───────────────────────────────────────────

    async def run(self) -> TaskResult:
        cfg = self.config
        raw_explore_time = int(cfg.get('explore_time', DEFAULT_EXPLORE_TIME))
        if raw_explore_time in VALID_EXPLORE_TIMES:
            explore_time = raw_explore_time
        else:
            explore_time = min(VALID_EXPLORE_TIMES, key=lambda x: abs(x - raw_explore_time))
            self.log.warning(
                f"⚠️ مدة استكشاف الأطلال غير مدعومة باللعبة ({raw_explore_time} ثانية) — "
                f"تم تصحيحها تلقائياً إلى أقرب مدة رسمية مدعومة ({explore_time} ثانية)."
            )
        search_range    = int(cfg.get('search_range', DEFAULT_SEARCH_RANGE))
        formation_id    = int(cfg.get('formation_id', DEFAULT_FORMATION_ID))
        max_attempts    = int(cfg.get('max_attempts', DEFAULT_MAX_ATTEMPTS))
        troops_cfg      = int(cfg.get('troops_count', DEFAULT_TROOPS_COUNT))
        max_marches     = MAX_MARCHES

        time_desc = {
            900: "15 دقيقة",
            3600: "1 ساعة",
            14400: "4 ساعات",
            28800: "8 ساعات",
        }.get(explore_time, f"{explore_time // 3600} ساعة" if explore_time % 3600 == 0 else f"{explore_time} ثانية")
        self.log.info(f"🏛️ [الأطلال] بدء الاستكشاف (مدة: {time_desc} | نطاق: {search_range} كم)")

        # 1. فحص استباقي: هل توجد مسيرة أطلال نشطة بالخارج بالفعل؟
        if await self.is_ruins_march_active():
            self.log.info("🏛️ توجد مسيرة استكشاف أطلال نشطة بالخارج بالفعل — تخطي المهمة فوراً (لمنع خطأ 8037).")
            return TaskResult.ok("مسيرة استكشاف أطلال نشطة بالخارج بالفعل", sent=0, already_active=True)

        if not self._heroes:
            await self._load_heroes()

        sent_count = 0
        attempts = 0
        consecutive_errors = 0
        self._busy      = set(cfg.get('busy_heroes', cfg.get('busy', [])))
        self._used_army = {}
        cur_range       = search_range
        cmd_opting_retries = 0
        last_result = None
        result_code = None

        while sent_count < max_marches and attempts < max_attempts:
            # فحص أمان سريع للتأكد من عدم انطلاق مسيرة أطلال أثناء المحاولات
            if sent_count > 0 or attempts > 0:
                if await self.is_ruins_march_active():
                    self.log.info("🛑 تم رصد مسيرة أطلال نشطة بالخارج — إنهاء المحاولات بنجاح.")
                    break

            # ── 🧪 اختبار: قراءة الفيالق المتاحة قبل الإرسال ──
            before_avail = await self.get_available_marches_count(force_sync=True)
            self.log.info(f"🔬 [MARCH_TEST] قبل الإرسال #{sent_count + 1}: الفيالق المتاحة = {before_avail}")
            if before_avail == 0:
                self.log.info("🏁 اكتملت جميع الفيالق وطوابير المسيرات للقلعة (طوابير ممتلئة بالكامل).")
                last_result = "QUEUE_FULL"
                result_code = "QUEUE_FULL"
                break

            attempts += 1
            self.log.debug(f"🚀 محاولة استكشاف الأطلال ({sent_count + 1}/{max_marches})...")
            result_code = await self._send_one_ruins(cur_range, formation_id, explore_time, troops_cfg)
            last_result = result_code

            if result_code == "SUCCESS":
                sent_count += 1
                consecutive_errors = 0
                cmd_opting_retries = 0
                if sent_count < max_marches:
                    await asyncio.sleep(round(random.uniform(4.5, 7.5), 2))  # حماية من الحظر - تأخير عشوائي بين المسيرات
            elif result_code in ("QUEUE_FULL", "ALREADY_ACTIVE", "8037"):
                self.log.info(f"🛑 تم إيقاف المحاولات لاكتمال مسيرات القلعة أو وجود مسيرة أطلال نشطة ({result_code}).")
                break
            elif result_code in ("STAMINA_EMPTY", "8032"):
                self.log.warning("🛑 نفدت طاقة اللورد بالكامل لمتابعة استكشاف الأطلال (كود 8032).")
                break
            elif result_code in ("NO_ARMY", "8009"):
                self.log.warning("⚠️ نفدت القوات المتاحة بالقلعة لإرسال مسيرة استكشاف أطلال.")
                break
            elif result_code in ("CMD_OPTING", "16001", "CMD_OPTING_FAILED"):
                cmd_opting_retries += 1
                if cmd_opting_retries <= 2:
                    wait_time = round(random.uniform(10.0, 16.0), 2)
                    self.log.warning(
                        f"⏳ [خادم اللعبة مشغول - كود 16001] انتظار {wait_time} ثانية لفك القفل "
                        f"ثم إعادة تجهيز مسيرة استكشاف الأطلال نظيفاً من البداية (محاولة {cmd_opting_retries}/2)..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    self.log.warning("🏁 استمر انشغال خادم اللعبة (كود 16001) بعد المحاولات — إيقاف الدورة مؤقتاً.")
                    break
            elif result_code == "NO_HEROES":
                return TaskResult.no_heroes()
            elif result_code in ("HERO_BUSY", "TARGET_OCCUPIED", "INVALID_TIME_OR_EXPIRING"):
                consecutive_errors += 1
                if consecutive_errors >= max_attempts:
                    self.log.warning(f"⚠️ استنفاد الحد الأقصى للمحاولات ({max_attempts} محاولة متتالية) — توقف مؤقت.")
                    break
                # توسيع نطاق البحث تدريجياً إذا كانت الأهداف القريبة مشغولة بكود 8035
                if consecutive_errors >= 2 and cur_range < 300:
                    cur_range = min(300, cur_range + 25)
                    self.log.info(f"🔄 توسيع نطاق البحث إلى {cur_range} كم لتجاوز الأطلال المشغولة...")
                self.log.info(f"🔄 جاري تجربة هدف أطلال بديل متاح (محاولة {attempts + 1}/{max_attempts})...")
                await asyncio.sleep(round(random.uniform(1.2, 2.5), 2))  # مهلة عشوائية قبل تجربة الهدف التالي
                continue
            elif result_code == "NO_TARGET":
                self.log.warning(f"⚠️ لم يتم العثور على أي أطلال متاحة في نطاق {cur_range} كم — إنهاء البحث.")
                break
            else:
                consecutive_errors += 1
                if consecutive_errors >= 4:
                    self.log.warning(f"⚠️ 4 أخطاء متتالية ({result_code}) — إنهاء المهمة.")
                    break
                await asyncio.sleep(round(random.uniform(1.8, 3.2), 2))

        self.log.info(f"🏁 [الأطلال] تم إرسال {sent_count}/{max_marches} مسيرة بنجاح")
        if sent_count > 0:
            return TaskResult.ok(f"✅ تم إرسال {sent_count} مسيرة استكشاف أطلال", sent=sent_count)
        if result_code in ("ALREADY_ACTIVE", "8037") or last_result in ("ALREADY_ACTIVE", "8037"):
            return TaskResult.ok("مسيرة استكشاف أطلال نشطة بالخارج بالفعل", sent=0, already_active=True)
        if result_code == "QUEUE_FULL" or last_result == "QUEUE_FULL":
            return TaskResult.queue_full()
        return TaskResult.fail("لم يتم إرسال أي مسيرة استكشاف أطلال", retry_after=120)

    # ── إرسال مسيرة استكشاف واحدة ─────────────────────────────────

    async def _send_one_ruins(self, search_range: int, formation_id: int, explore_time: int, troops_cfg: int) -> str:
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. جلب إحداثيات القلعة من الذاكرة الحية cityCtrl (Zero-Request)
        pos = self.conn.init_data.get('cityCtrl', {}).get('cinfo', {}).get('pos', {}) if hasattr(self.conn, 'init_data') else {}
        if pos and 'x' in pos and 'y' in pos:
            cx, cy = int(pos['x']), int(pos['y'])
        else:
            try:
                self.log.warning("🛑🛑🛑🛑🛑🛑")
                r_castle = await self.conn.query('1006', '25', {"uid": uid_int})
                if not r_castle or not r_castle.get('retData'):
                    return "ERROR"
                cx, cy = int(r_castle['retData'].get('x')), int(r_castle['retData'].get('y'))
            except Exception:
                return "ERROR"

        # 2. جلب معرف المملكة من الذاكرة الحية (Zero-Request)
        kingdom_id = 0
        if getattr(self.conn, 'kingdom_id', None):
            try: kingdom_id = int(self.conn.kingdom_id)
            except Exception: pass
        if not kingdom_id:
            lord_base = self.conn.init_data.get('lordInfoCtrl', {}).get('base', {}) if hasattr(self.conn, 'init_data') else {}
            if isinstance(lord_base, dict):
                kingdom_id = int(lord_base.get('partition', 0))
        if not kingdom_id:
            kingdom_id = 4


        # 3. البحث عن الأطلال (mapType: 7, subType: 0)
        exclude_map = await self._exclude_mgr.get_exclude_map(self.uid, kingdom_id=kingdom_id)
        r_search = await self.conn.query('2011', '3', {
            "mapType": 7,
            "subType": 0,
            "num": 10,
            "y": cy,
            "x": cx,
            "exclude": exclude_map,
            "range": search_range
        })
        candidates = r_search.get('result', []) if r_search else []
        target = None
        for cand in candidates:
            cid = cand.get('id')
            if cid and str(cid) not in exclude_map:
                target = cand
                break

        if not target:
            self.log.warning(f"⚠️ لا توجد أطلال متاحة غير مستبعدة في نطاق {search_range}!")
            return "NO_TARGET"

        target_id = target.get('id')
        tx, ty    = target.get('x'), target.get('y')
        self.log.info(f"🎯 هدف الأطلال: ID={target_id} عند ({tx}, {ty})")
        # حجز مؤقت في الذاكرة المشتركة للمملكة — لن يُثبت في الملف إلا بعد نجاح الإرسال
        await self._exclude_mgr.reserve(self.uid, target_id, kingdom_id=kingdom_id)

        # 3.5 فحص مسبق لبيانات الطلل (العمر المتبقي لمنع أخطاء 8035 و 8008 عند طلب مدد طويلة كـ 8 ساعات)
        try:
            r_info = await self.conn.query('1006', '15', {
                "x": int(tx),
                "y": int(ty),
                "id": str(target_id),
                "kingdomId": int(kingdom_id)
            }, timeout=3)
            if r_info and isinstance(r_info, dict):
                relics_info = r_info.get('retData', {}).get('relics', {})
                if isinstance(relics_info, dict):
                    left_time = int(relics_info.get('leftTime', 0))
                    if left_time > 0 and left_time < explore_time:
                        self.log.info(
                            f"ℹ️ الوقت المتبقي للطلل {target_id} ({left_time:,} ثانية) "
                            f"أقل من مدة الاستكشاف المطلوبة ({explore_time:,} ثانية) — استبعاده فوراً وتجربة بديل ذي عمر كافٍ"
                        )
                        await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                        return "TARGET_OCCUPIED"
        except Exception:
            pass


        # 4. جلب القوات المتوفرة بالقلعة من الذاكرة الحية مباشرة (Zero-Request)
        available: Dict[int, int] = {}
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        if isinstance(army_ctrl, dict):
            for k, v in army_ctrl.get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)

        if not available:
            try:
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


        # تحديد الفرع التكتيكي المهيمن في التشكيلة لتوجيه اختيار أبطال الحرب المتطابقين
        dominant_branch = "cavalry"
        branch_counts = {"infantry": 0, "cavalry": 0, "archers": 0, "siege": 0}
        if form_army_dict:
            for k, v in form_army_dict.items():
                if str(k).isdigit() and str(v).isdigit() and not (800 <= int(k) < 900):
                    b = get_troop_branch(int(k))
                    if b in branch_counts:
                        branch_counts[b] += int(v)
            best_b = max(branch_counts.items(), key=lambda x: x[1])
            if best_b[1] > 0:
                dominant_branch = best_b[0]

        # 6. اختيار الأبطال (ضمان بطلي حرب اثنين حصراً لنصر حاسم)
        chosen_heroes = []
        if not self._heroes:
            await self._load_heroes()

        # استخراج هويات أبطال التشكيلة المحفوظة بكافة الأشكال
        raw_form_hero_ids: List[int] = []
        if form_heroes:
            if isinstance(form_heroes, list):
                for item in form_heroes:
                    if isinstance(item, dict) and 'id' in item:
                        raw_form_hero_ids.append(int(item['id']))
                    elif item and str(item).isdigit() and int(item) > 0:
                        raw_form_hero_ids.append(int(item))
            elif isinstance(form_heroes, dict):
                for sub in form_heroes.values():
                    if isinstance(sub, list):
                        for item in sub:
                            if isinstance(item, dict) and 'id' in item:
                                raw_form_hero_ids.append(int(item['id']))
                            elif item and str(item).isdigit() and int(item) > 0:
                                raw_form_hero_ids.append(int(item))
                    elif isinstance(sub, dict) and 'id' in sub:
                        raw_form_hero_ids.append(int(sub['id']))
                    elif sub and str(sub).isdigit() and int(sub) > 0:
                        raw_form_hero_ids.append(int(sub))

        available_form_heroes = []
        diagnostics = []
        for hid in raw_form_hero_ids:
            h_data = next((x for x in self._heroes if x.get('id') == hid), None)
            if not h_data:
                diagnostics.append(f"بطل {hid}: غير مسجل بالقلعة")
            elif hid in self._busy:
                diagnostics.append(f"بطل {hid}: محجوز للمسيرة الحالية")
            else:
                st = h_data.get('status', {}).get('state', 0)
                if st == 0:
                    available_form_heroes.append(hid)
                    diagnostics.append(f"بطل {hid}: متاح بالقلعة")
                else:
                    diagnostics.append(f"بطل {hid}: بالخارج في مسيرة أخرى (state={st})")

        if raw_form_hero_ids:
            self.log.info(f"📋 حالة أبطال التشكيلة #{formation_id}: {' | '.join(diagnostics)}")

        if len(available_form_heroes) >= 2:
            chosen_heroes = available_form_heroes[:2]
            self.log.info(f"🎖️ تم اعتماد بطلي التشكيلة المحفوظة #{formation_id}: {chosen_heroes}")
        elif len(available_form_heroes) == 1:
            h1 = available_form_heroes[0]
            self.log.info(f"ℹ️ البطل الأول متاح من التشكيلة ({h1}) — جاري إكمال البطل الثاني بأفضل بطل حرب متاح...")
            extra_busy = set(self._busy) | {h1}
            fillers = _pick_combat_heroes(self._heroes, max_count=1, busy=extra_busy, dominant_branch=dominant_branch)
            if fillers:
                chosen_heroes = [h1, fillers[0]]
                self.log.info(f"⚔️ تشكيلة الأبطال المكتملة (بطلان اثنان): {chosen_heroes}")
            else:
                chosen_heroes = [h1]
                self.log.info(f"⚔️ بطل واحد متاح من التشكيلة: {chosen_heroes}")
        else:
            self.log.info(f"🔄 أبطال التشكيلة بالخارج — اختيار تلقائي لأفضل أبطال الحرب المتوافقين مع صنف ({dominant_branch})...")
            chosen_heroes = _pick_combat_heroes(self._heroes, max_count=2, busy=self._busy, dominant_branch=dominant_branch)
            if len(chosen_heroes) == 2:
                self.log.info(f"⚔️ أبطال الحرب المختارون تلقائياً (بطلان اثنان): {chosen_heroes}")
            elif len(chosen_heroes) == 1:
                self.log.info(f"⚔️ بطل حرب واحد متاح بالقلعة: {chosen_heroes}")
            else:
                any_cands = [int(h['id']) for h in self._heroes if isinstance(h, dict) and h.get('id') and int(h['id']) not in self._busy and h.get('status', {}).get('state', 0) == 0]
                if any_cands:
                    chosen_heroes = any_cands[:2]
                    self.log.info(f"⚠️ بديل اضطراري: تم اختيار أي أبطال متاحين بالقلعة ({len(chosen_heroes)}): {chosen_heroes}")
                else:
                    self.log.warning("⚠️ لا يوجد أي بطل متاح بالقلعة نهائياً!")
                    return "NO_HEROES"

        if not chosen_heroes:
            return "NO_HEROES"

        # 7. تكوين جيش المسيرة بالذكاء الخارق (التعويض بالقوة القتالية FC والحفاظ على صنف الجيش)
        army_list = []
        max_safe_capacity = get_castle_march_capacity(self.conn, chosen_heroes=chosen_heroes)

        # حساب القوة القتالية المستهدفة للتشكيلة ونسب الأصناف
        # استبعاد فخاخ الجدار 800..899
        clean_form_req: Dict[int, int] = {}
        for k, v in form_army_dict.items():
            if str(k).isdigit() and str(v).isdigit():
                tid = int(k)
                if not (800 <= tid < 900) and int(v) > 0:
                    clean_form_req[tid] = int(v)

        total_form_req_troops = sum(clean_form_req.values())
        target_form_fc = sum(cnt * get_troop_unit_fc(tid) for tid, cnt in clean_form_req.items())

        self.log.info(
            f"🎯 [معايير التشكيلة #{formation_id}] إجمالي جنودها: {total_form_req_troops:,} | "
            f"القوة القتالية المستهدفة (Target FC): {target_form_fc:,.0f} | سعة مسيرة اللورد القصوى: {max_safe_capacity:,}"
        )

        army_map: Dict[int, int] = {}
        missing_fc_by_branch: Dict[str, float] = {"infantry": 0.0, "cavalry": 0.0, "archers": 0.0, "siege": 0.0}

        # الخطوة أ: أخذ المتوفر مباشرة من كل صنف في التشكيلة
        for tid, req in clean_form_req.items():
            avail = available.get(tid, 0)
            take = min(req, avail)
            if take > 0:
                army_map[tid] = army_map.get(tid, 0) + take
                available[tid] -= take
            if take < req:
                unit_fc = get_troop_unit_fc(tid)
                branch = get_troop_branch(tid)
                missing_fc = (req - take) * unit_fc
                missing_fc_by_branch[branch] = missing_fc_by_branch.get(branch, 0.0) + missing_fc

        # الخطوة ب: تعويض القوة القتالية الناقصة داخل نفس الفرع (أعلى رتبة تنازلياً T14 -> T1)
        branch_available: Dict[str, List[Tuple[int, int]]] = {
            "infantry": [], "cavalry": [], "archers": [], "siege": []
        }
        for tid, count in available.items():
            if count <= 0 or (800 <= tid < 900):
                continue
            b = get_troop_branch(tid)
            if b in branch_available:
                branch_available[b].append((tid, count))

        for b in branch_available:
            branch_available[b].sort(key=lambda x: x[0], reverse=True)

        for branch, miss_fc in list(missing_fc_by_branch.items()):
            if miss_fc <= 0:
                continue
            for tid, count in branch_available.get(branch, []):
                if miss_fc <= 0:
                    break
                avail = available.get(tid, 0)
                if avail <= 0:
                    continue
                unit_fc = get_troop_unit_fc(tid)
                needed = math.ceil(miss_fc / unit_fc)
                take = min(needed, avail)
                if take > 0:
                    army_map[tid] = army_map.get(tid, 0) + take
                    available[tid] -= take
                    miss_fc -= take * unit_fc
            missing_fc_by_branch[branch] = miss_fc

        # الخطوة ج: إذا ما زال هناك نقص بالقوة في فرع استُنفد تماماً، تعويضها بأعلى رتب حرب من باقي الفروع القتالية (بما فيها فئة 700)
        remaining_missing_fc = sum(max(0.0, fc) for fc in missing_fc_by_branch.values())
        if remaining_missing_fc > 0:
            all_combat_avail: List[Tuple[int, int]] = []
            for b in ("infantry", "cavalry", "archers", "siege"):
                all_combat_avail.extend(branch_available.get(b, []))
            all_combat_avail.sort(key=lambda x: x[0], reverse=True)

            for tid, count in all_combat_avail:
                if remaining_missing_fc <= 0:
                    break
                avail = available.get(tid, 0)
                if avail <= 0:
                    continue
                unit_fc = get_troop_unit_fc(tid)
                needed = math.ceil(remaining_missing_fc / unit_fc)
                take = min(needed, avail)
                if take > 0:
                    army_map[tid] = army_map.get(tid, 0) + take
                    available[tid] -= take
                    remaining_missing_fc -= take * unit_fc

        # إذا كانت التشكيلة الأصلية فارغة تماماً بالقلعة من الأساس:
        if not army_map:
            if formation_id > 0:
                self.log.info(f"⚠️ التشكيلة المحفوظة (#{formation_id}) فارغة أو لا يوجد أي من قواتها — تجميع أفضل جيش قتالي من أعلى الرتب...")
            all_combat_avail = []
            for b in ("infantry", "cavalry", "archers", "siege"):
                all_combat_avail.extend(branch_available.get(b, []))
            all_combat_avail.sort(key=lambda x: x[0], reverse=True)
            rem_cap = max_safe_capacity
            for tid, count in all_combat_avail:
                if rem_cap <= 0: break
                avail = available.get(tid, 0)
                if avail <= 0: continue
                take = min(rem_cap, avail)
                if take > 0:
                    army_map[tid] = take
                    available[tid] -= take
                    rem_cap -= take

        # الخطوة د: ضبط السعة القصوى مع صمام الأمان
        army_list = [{"id": tid, "num": cnt} for tid, cnt in army_map.items() if cnt > 0]
        cur_troops = sum(x['num'] for x in army_list)

        if cur_troops > max_safe_capacity:
            excess = cur_troops - max_safe_capacity
            self.log.debug(f"⚖️ ضبط حجم المسيرة ({cur_troops:,} جندي) لعدم تجاوز سعة اللورد القصوى ({max_safe_capacity:,})...")
            # تخفيض الزيادة من أقل الرتب أولاً للحفاظ على أعلى قوة قتالية ممكنة
            army_list.sort(key=lambda x: x['id'])
            for item in army_list:
                if excess <= 0: break
                trim = min(excess, item['num'] - 1)
                if trim > 0:
                    item['num'] -= trim
                    available[item['id']] = available.get(item['id'], 0) + trim
                    excess -= trim
            army_list = [x for x in army_list if x['num'] > 0]

        total_troops = sum(x['num'] for x in army_list)
        actual_march_fc = sum(x['num'] * get_troop_unit_fc(x['id']) for x in army_list)

        # 🛑 الركيزة الرابعة: صمام أمان الانتصار الحاسم (Victory Assurance)
        if total_troops <= 0:
            active_marches = await self.get_active_marches_count(force_sync=True)
            if active_marches >= 1:
                self.log.info(f"⏳ [القوات في المسيرة] لا تتوفر قوات بالقلعة لوجود {active_marches} مسيرة نشطة بالخارج.")
                return "QUEUE_FULL"
            else:
                self.log.warning("⚠️ لا توجد أي قوات متاحة بالقلعة ولا توجد مسيرات بالخارج!")
                return "NO_ARMY"

        if target_form_fc > 0:
            fc_ratio = actual_march_fc / target_form_fc
            self.log.debug(
                f"🛡️ [فحص القوة القتالية] القوة المحققة: {actual_march_fc:,.0f} FC "
                f"({fc_ratio:.1%} من قوة التشكيلة المستهدفة {target_form_fc:,.0f} FC) | إجمالي الجنود: {total_troops:,}"
            )

        # 8. اختيار الحيوان الأليف والرونات من التشكيلة
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

        self.log.debug(f"🛡️ تشكيلة الأطلال: إجمالي جنود: {total_troops:,}")

        # 9. إرسال حزمة الأطلال 1007/2
        attack_payload = {
            "needSend": False,
            "runePages": rune_pages_list,
            "heros": chosen_heroes,
            "matrixType": 1,
            "mapId": int(kingdom_id),
            "moveLineType": 4,               # 4 = استكشاف الأطلال (Relics Explore)
            "data": {
                "data": {
                    "exploreTime": int(explore_time)
                },
                "to": {
                    "y": int(ty),
                    "x": int(tx),
                    "id": str(target_id)
                },
                "army": army_list
            },
            "pets": pets_list if pets_list else {}
        }

        r_attack = await self.conn.query('1007', '2', attack_payload)
        if not r_attack:
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "ERROR"

        err = str(r_attack.get('err', '0'))
        if err == '0':
            self.log.info(f"✅ [الأطلال] إرسال مسيرة استكشاف إلى الأطلال ({tx}, {ty}) | جنود: {total_troops:,}")
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
        elif err == '8037':
            self.log.info(f"🛑 القلعة لديها مسيرة استكشاف أطلال نشطة بالفعل حالياً (كود {err})")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "ALREADY_ACTIVE"
        elif err == '8009':
            self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            active_marches = await self.get_active_marches_count(force_sync=True)
            if active_marches >= 1:
                self.log.info(f"⏳ [القوات في المسيرة] نقص قوات عند الإرسال لوجود {active_marches} مسيرة نشطة بالخارج.")
                return "QUEUE_FULL"
            else:
                self.log.warning("⚠️ نقص حقيقي في القوات ولا توجد مسيرات نشطة بالخارج!")
                return "NO_ARMY"
        elif err == '9007020':
            for hid in chosen_heroes:
                self._busy.add(hid)
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "HERO_BUSY"
        elif err == '8046':
            self.log.warning(f"⚠️ تعذر استكشاف الأطلال {target_id} (كود 8046: مدة الاستكشاف غير مقبولة أو صلاحية الهدف تنتهي قريباً) — تحرير الهدف وتجربة بديل")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "INVALID_TIME_OR_EXPIRING"
        elif err == '8035':
            # 🛑 كود 8035 = تجاوز سعة مسيرة اللورد وليس انشغال الأطلال!
            current_total = sum(item['num'] for item in army_list)
            reduced_troops = max(50, int(current_total * 0.82))
            record_learned_march_capacity(self.conn, reduced_troops)
            self.log.warning(
                f"⚠️ كود 8035 (تجاوز سعة مسيرة اللورد لـ {current_total:,} جندي) — "
                f"إعادة المحاولة فوراً بضبط القوات إلى {reduced_troops:,} جندي..."
            )
            if current_total > 50:
                army_list = enforce_safe_march_troops(army_list, reduced_troops)
                total_troops = sum(itm['num'] for itm in army_list)
                attack_payload['data']['army'] = army_list
                r_retry = await self.conn.query('1007', '2', attack_payload)
                if r_retry and str(r_retry.get('err', '0')) == '0':
                    self.log.info(f"✅ [الأطلال] إرسال مسيرة استكشاف بعد الضبط ({tx}, {ty}) | جنود: {total_troops:,}")
                    await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                    for hid in chosen_heroes:
                        self._busy.add(hid)
                    for item in army_list:
                        self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                    return "SUCCESS"
                elif r_retry and str(r_retry.get('err', '0')) == '8035':
                    # محاولة ثانية بتقليص أعمق
                    reduced_second = max(50, int(total_troops * 0.75))
                    record_learned_march_capacity(self.conn, reduced_second)
                    army_list = enforce_safe_march_troops(army_list, reduced_second)
                    total_troops = sum(itm['num'] for itm in army_list)
                    attack_payload['data']['army'] = army_list
                    self.log.warning(f"⚠️ تكرر كود 8035 — محاولة ثانية وأخيرة بضبط القوات إلى {total_troops:,} جندي...")
                    r_retry2 = await self.conn.query('1007', '2', attack_payload)
                    if r_retry2 and str(r_retry2.get('err', '0')) == '0':
                        self.log.info(f"✅ [الأطلال] إرسال مسيرة استكشاف بعد الضبط الثاني ({tx}, {ty}) | جنود: {total_troops:,}")
                        await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                        for hid in chosen_heroes:
                            self._busy.add(hid)
                        for item in army_list:
                            self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                        return "SUCCESS"
            # تحرير الهدف لأن الخطأ في سعة الجيش وليس في شغل الأطلال
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "TARGET_OCCUPIED"
        elif err in ('8032', '10002', '10003'):
            self.log.warning(f"🛑 نفدت طاقة اللورد بالكامل (كود {err}: Err_MAP_QUEUE_PHY_NOT_ENGHOUT)")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "STAMINA_EMPTY"
        elif err in ('8062', '8063', '8060', '8002', '9007062') or (err.isdigit() and 8000 <= int(err) < 8100 and err not in ('8035', '8032')):
            self.log.info(f"ℹ️ الأطلال {target_id} مشغولة حالياً (كود {err}) — استبعادها وتجربة هدف بديل فوراً")
            # الأطلال مشغولة فعلاً — نثبت الاستبعاد
            await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
            return "TARGET_OCCUPIED"
        elif err == '16001':
            self.log.warning(
                f"   ⚠️ خادم اللعبة مشغول بعملية سابقة (كود 16001: Err_CMD_OPTING) — "
                f"تحرير الأطلال {target_id} لإعادة تجهيز المسيرة نظيفاً من البداية..."
            )
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "CMD_OPTING"
        else:
            self.log.error(f"❌ خطأ غير معروف: {err} | الهدف={target_id}")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "ERROR"


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Empire Ruins Exploration Bot — مهمة استكشاف الأطلال (مسيرة واحدة فقط حصراً)"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument(
        "--time", "-t", type=int, default=DEFAULT_EXPLORE_TIME,
        choices=[900, 3600, 14400, 28800],
        help="مدة الاستكشاف بالثواني [الفترات الـ 4 المتاحة فقط باللعبة: 900 (15 دقيقة), 3600 (1 ساعة), 14400 (4 ساعات), 28800 (8 ساعات)] (افتراضي: 900)"
    )
    parser.add_argument("--range", "-r", type=int, default=DEFAULT_SEARCH_RANGE, help=f"نطاق البحث بالكيلومتر [افتراضي: {DEFAULT_SEARCH_RANGE}]")
    parser.add_argument("--formation", "-f", type=int, default=DEFAULT_FORMATION_ID, choices=[1, 2, 3, 4, 5], help=f"رقم التشكيلة 1..5 [افتراضي: {DEFAULT_FORMATION_ID}]")
    parser.add_argument("--attempts", "-a", type=int, default=DEFAULT_MAX_ATTEMPTS, help=f"سقف المحاولات البديلة عند انشغال الأهداف [افتراضي: {DEFAULT_MAX_ATTEMPTS}]")
    parser.add_argument("--troops", type=int, default=DEFAULT_TROOPS_COUNT, help=f"عدد الجنود المطلوب إرسالهم [افتراضي: {DEFAULT_TROOPS_COUNT}]")
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
            "explore_time": args.time,
            "search_range": args.range,
            "formation_id": args.formation,
            "max_attempts": args.attempts,
            "troops_count": args.troops
        }

        task = RuinsTask(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
