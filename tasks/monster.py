# -*- coding: utf-8 -*-
"""
tasks/monster.py — مهمة الهجوم على الغزاة والمتمردين (Monsters & Rebels Attack)
══════════════════════════════════════════════════════════════════════════════
# الهجوم على المتمردين (Rebels):
python tasks/monster.py --email "azjfhf48@gmail.com" --type rebels --minlv 1 --maxlv 20 --marches 33

# أو الهجوم على الغزاة (Invaders):
python tasks/monster.py --email "azjfhf48@gmail.com" --type invaders --minlv 30 --maxlv 35 --marches 6



تُرسِل مسيرات هجوم وقتال متتالية ضد الغزاة (Invaders) أو المتمردين (Rebels).

أنواع الأهداف:
    • "rebels"   : 🏴‍☠️ متمردين  (mapType=35, subType=0)
    • "invaders" : 👾 غزاة      (mapType=6,  subType=0)

نظام التشكيلة والأبطال:
    1. استخدام أبطال وحيوانات وجيوش التشكيلة المحفوظة (1005/7) إن كانوا متاحين.
    2. إذا كان أبطال التشكيلة مشغولين:
       - يُرسل أبطال الحرب والقتال فقط (5501xxx) الذين يمتلكون مهارات قتال وهجوم (5610xxx / 5640xxx).
       - يُستبعد أبطال الجمع (5502xxx) وأبطال الدعم الداخلي (5503xxx) تماماً.

الإعدادات (config / Firebase):
    monster_type : نوع الهدف ("rebels" أو "invaders") [افتراضي: "rebels"]
    min_lv       : أدنى مستوى للهدف [افتراضي: 1]
    max_lv       : أعلى مستوى للهدف [افتراضي: 30]
    max_marches  : الحد الأقصى للمسيرات [افتراضي: 6]
    search_range : نطاق البحث على الخريطة [افتراضي: 50]
    formation_id : رقم التشكيلة المحفوظة [افتراضي: 1]
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

# ── ملف تاريخ الاستبعاد ──────────────────────────────────────────
HISTORY_FILE = os.path.join(_ROOT_DIR, "exclude_history.json")


# ════════════════════════════════════════════════════════════════════
#  إعدادات افتراضية في رأس الملف (قابلة للتعديل والربط بـ Firebase)
# ════════════════════════════════════════════════════════════════════

DEFAULT_MONSTER_TYPE       = "invaders"         # "rebels" (متمردين: 35) أو "invaders" (غزاة: 6)
DEFAULT_MIN_LV             = 1                # أدنى مستوى
DEFAULT_MAX_LV             = 30               # أقصى مستوى
DEFAULT_MAX_MARCHES        = 64                # الحد الأقصى للمسيرات
DEFAULT_SEARCH_RANGE       = 100               # نطاق البحث
DEFAULT_FORMATION_ID       = 1                # رقم التشكيلة المفضلة (1..5) [0 = تلقائي ذكي بدون تشكيلة ثابتة]
DEFAULT_TROOPS_COUNT       = 30000            # عدد الجنود الافتراضي في حال عدم وجود تشكيلة

# خريطة أنواع الأهداف
MONSTER_TYPES = {
    "rebels":   {"mapType": 35, "subType": 0, "name": "🏴‍☠️ متمردين (Rebels)"},
    "invaders": {"mapType": 6,  "subType": 0, "name": "👾 غزاة (Invaders)"},
}


# ════════════════════════════════════════════════════════════════════
#  إدارة استبعاد الأهداف المكررة
# ════════════════════════════════════════════════════════════════════

def _get_exclude(uid: Any) -> Dict[str, bool]:
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {str(i): True for i in data.get(str(uid), [])}
    except Exception:
        return {}


def _add_exclude(uid: Any, target_id: Any):
    data: dict = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

    key = str(uid)
    arr = data.setdefault(key, [])
    t   = str(target_id)
    if t not in arr:
        arr.append(t)
    while len(arr) > 20:
        arr.pop(0)
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
#  اختيار أبطال الحرب والقتال (Combat Heroes Selection)
# ════════════════════════════════════════════════════════════════════

def _pick_combat_heroes(heroes: list, max_count: int = 2, busy: Set[int] = None) -> List[int]:
    """
    يختار أفضل أبطال قتال وحرب (5501xxx) وفق هرمية المهارات القتالية والمستوى:
    1. أبطال حرب 5501xxx يمتلكون مهارات هجومية/قتالية (5610xxx / 5640xxx).
    2. أبطال حرب 5501xxx متاحين.
    ملاحظة: يتم استبعاد أبطال الجمع (5502xxx) والدعم (5503xxx) تماماً.
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
        # قبول أبطال الحرب والقتال فقط (5501xxx) أو أي بطل غير 5502 و 5503
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
#  حساب القوة الموصى بها وسعة الجيش الذكية (Recommended Power & Smart Troops)
# ════════════════════════════════════════════════════════════════════

def get_monster_recommended_power(target_type: str, level: int) -> int:
    """
    حساب / إرجاع القوة الموصى بها (Recommended Power) المعروضة في واجهة اللعبة للهدف:
    - نخبة المتمردين (Rebels): من لفل 1 إلى 5 (لفل 5 = 7,518,000 بالضبط كما باللعبة).
    - الغزاة (Invaders): من لفل 1 إلى 35.
    - المعاقل (Stronghold): من لفل 1 إلى 30.
    """
    m_type = str(target_type).lower().strip()
    lv = max(1, int(level))
    if m_type in ("rebels", "متمردين", "35"):
        table = {
            1: 1200000,
            2: 2500000,
            3: 3900000,
            4: 5500000,
            5: 7518000,   # القيمة الدقيقة الرسمية في اللعبة لنخبة المتمردين لفل 5
        }
        if lv in table:
            return table[lv]
        return int(7518000 * (1 + (lv - 5) * 0.25))
    elif m_type in ("invaders", "غزاة", "6"):
        if lv <= 5:
            return lv * 50000
        elif lv <= 12:
            return 250000 + (lv - 5) * 125000
        elif lv <= 20:
            return 1125000 + (lv - 12) * 265000
        elif lv <= 28:
            return 3245000 + (lv - 20) * 450000
        else:
            return 6845000 + (lv - 28) * 800000
    elif m_type in ("stronghold", "معقل", "ملاجئ", "26"):
        if lv <= 10:
            return 500000 + lv * 150000
        elif lv <= 20:
            return 2000000 + (lv - 10) * 250000
        else:
            return 4500000 + (lv - 20) * 350000
    return 0


def calculate_smart_combat_troops(
    target_type: str,
    target_level: int,
    castle_power: int = 0,
    user_troops_cfg: Optional[int] = None,
    max_safe_march: int = 170000
) -> Tuple[int, int, str]:
    """
    دالة ذكية ومرنة لحساب عدد جنود المسيرة الأمثل وفحص القوة الموصى بها:
    1. تستعلم القوة الموصى بها للهدف.
    2. تفحص قوة القلعة الحالية ومستوى الأمان ونسبة الجاهزية.
    3. تحسب عدد الجنود المطلوب بدقة لضمان النصر الحاسم بصفر خسائر ودون تجاوز سعة مسيرة اللورد.
    """
    m_type = str(target_type).lower().strip()
    lv = max(1, int(target_level))
    rec_power = get_monster_recommended_power(m_type, lv)

    # حساب نسبة الجاهزية والأمان
    status_desc = "جاهزية تامة"
    if castle_power > 0 and rec_power > 0:
        ratio = castle_power / float(rec_power)
        pct = int(ratio * 100)
        if ratio >= 1.25:
            status_desc = f"جاهزية ساحقة وتفوق كامل ({pct}%)"
        elif ratio >= 1.0:
            status_desc = f"مؤهل بنجاح ({pct}%)"
        elif ratio >= 0.75:
            status_desc = f"متكافئ مع الهدف ({pct}%)"
        else:
            status_desc = f"قوة القلعة أقل من الموصى بها ({pct}%)"

    # إذا حدد المستخدم رقماً مخصصاً صريحاً في الإعدادات (وليس القيمة الافتراضية 30 ألف القديمة)
    if user_troops_cfg and user_troops_cfg not in (0, 30000):
        troops = min(max_safe_march, max(5000, user_troops_cfg))
        return troops, rec_power, status_desc

    # الحساب الديناميكي المرن لعدد الجنود حسب نوع الهدف ومستواه لضمان سحق الهدف دون تجاوز سعة اللورد
    if m_type in ("rebels", "متمردين", "35"):
        # نخبة المتمردين: حشد يحتاج جيشاً متدرجاً قوياً لسحق الهدف بصفر خسائر
        base_troops_map = {1: 50000, 2: 75000, 3: 110000, 4: 140000, 5: 165000}
        needed = base_troops_map.get(lv, min(max_safe_march, 165000))
    elif m_type in ("invaders", "غزاة", "6"):
        # الغزاة: هجوم فردي يتدرج من 30 ألف حتى 165 ألف
        if lv <= 5:
            needed = 30000
        elif lv <= 12:
            needed = 60000
        elif lv <= 20:
            needed = 95000
        elif lv <= 28:
            needed = 130000
        else:
            needed = min(max_safe_march, 165000)
    elif m_type in ("stronghold", "معقل", "ملاجئ", "26"):
        if lv <= 10:
            needed = 60000
        elif lv <= 20:
            needed = 110000
        else:
            needed = min(max_safe_march, 165000)
    else:
        needed = 120000

    optimal_troops = min(max_safe_march, max(5000, int(needed)))
    return optimal_troops, rec_power, status_desc


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

    # ترتيب كل صنف من الرتبة الأعلى إلى الأدنى
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
#  مهمة الهجوم على الوحوش والمتمردين (MonsterTask)
# ════════════════════════════════════════════════════════════════════

class MonsterTask(BaseTask):
    """
    مهمة الهجوم على الغزاة أو المتمردين بالتشكيلة أو أبطال الحرب.
    """
    name = "monster"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self._heroes    : list     = []
        self._busy      : Set[int] = set()
        self._used_army : Dict[int, int] = {}
        self._used_pets : Set[int] = set()

    async def on_start(self):
        for _ in range(20):
            if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
                break
            if self.conn.init_data:
                break
            await asyncio.sleep(0.5)
        await self._load_heroes()

    async def _load_heroes(self):
        """تحميل سجل أبطال القلعة مع خطط الاسترداد المتعددة."""
        self._heroes = []
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. من الـ Gate مباشرة
        if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
            self._heroes = list(self.conn._gate.heroes)
            if self._heroes:
                self.log.info(f"📋 {len(self._heroes)} بطل من Gate")
                return

        # 2. من init_data heroCtrl مباشرة
        hctrl = self.conn.init_data.get('heroCtrl')
        if isinstance(hctrl, list) and hctrl:
            self._heroes = list(hctrl)
            self.log.info(f"📋 تم تحميل {len(self._heroes)} بطل من heroCtrl")
            return
        elif isinstance(hctrl, dict) and hctrl:
            hlist = hctrl.get('heroList', hctrl)
            if isinstance(hlist, dict):
                self._heroes = list(hlist.values())
            elif isinstance(hlist, list):
                self._heroes = list(hlist)
            if self._heroes:
                self.log.info(f"📋 تم تحميل {len(self._heroes)} بطل من heroCtrl")
                return

        # 3. إرسال 1000/1 والانتظار
        if self.conn._gate and self.conn._gate._writer and self.conn._gate.is_connected:
            try:
                from onemt_bot import pack_request
                self.conn._gate._writer.write(pack_request('1000', '1', {}, session=0))
                await self.conn._gate._writer.drain()
                for _ in range(12):
                    await asyncio.sleep(0.2)
                    if self.conn._gate.heroes:
                        self._heroes = list(self.conn._gate.heroes)
                        self.log.info(f"📋 {len(self._heroes)} بطل (من 1000/1)")
                        return
            except Exception:
                pass

        # 4. خطة احتياطية: جلب أبطال التشكيلات السريعة (3080/2)
        try:
            r_3080 = await self.conn.query('3080', '2', {'isSelf': True, 'uids': [uid_int]}, timeout=3)
            if r_3080 and 'data' in r_3080:
                list_data = r_3080['data'].get('list', {}).get(str(uid_int), {})
                pages = list_data.get('pages', {})
                if isinstance(pages, dict):
                    for page in pages.values():
                        if isinstance(page, dict):
                            for h_obj in page.get('heros', []):
                                hid = h_obj.get('id') if isinstance(h_obj, dict) else h_obj
                                if hid and not any(h.get('id') == hid for h in self._heroes):
                                    self._heroes.append({'id': int(hid), 'status': {'state': 0}, 'skillList': {}})
        except Exception:
            pass

        # 5. خطة احتياطية: جلب أبطال تشكيلات الجيش (1005/7)
        for ctype in range(1, 6):
            try:
                form_res = await self.conn.query('1005', '7', {"compiletype": ctype}, timeout=2)
                if form_res and 'data' in form_res:
                    c_heroes = form_res['data'].get('compileHeros', [])
                    if isinstance(c_heroes, list):
                        for hid in c_heroes:
                            if hid and str(hid).isdigit():
                                int_hid = int(hid)
                                if not any(h.get('id') == int_hid for h in self._heroes):
                                    self._heroes.append({'id': int_hid, 'status': {'state': 0}, 'skillList': {}})
            except Exception:
                pass

        if self._heroes:
            self.log.info(f"📋 تم العثور على {len(self._heroes)} بطل")
        else:
            self.log.warning("⚠️ لم يتم العثور على أبطال مسجلين في هذا الحساب")

    # ── المهمة الرئيسية ───────────────────────────────────────────

    async def run(self) -> TaskResult:
        cfg = self.config
        target_type_str = str(cfg.get('monster_type', DEFAULT_MONSTER_TYPE)).lower().strip()
        min_lv          = int(cfg.get('min_lv', DEFAULT_MIN_LV))
        max_lv          = int(cfg.get('max_lv', DEFAULT_MAX_LV))
        max_marches     = int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))
        search_range    = int(cfg.get('search_range', DEFAULT_SEARCH_RANGE))
        formation_id    = int(cfg.get('formation_id', DEFAULT_FORMATION_ID))
        troops_cfg      = int(cfg.get('troops_count', DEFAULT_TROOPS_COUNT))

        target_info = MONSTER_TYPES.get(target_type_str, MONSTER_TYPES["rebels"])
        map_type = target_info["mapType"]
        sub_type = target_info["subType"]
        type_name = target_info["name"]

        self.log.info(f"⚔️ بدء مهمة الهجوم على [{type_name}] | لفل: {min_lv}-{max_lv} | الحد الأقصى للمسيرات: {max_marches}")

        if not self._heroes:
            await self._load_heroes()

        sent_count = 0
        consecutive_errors = 0
        self._busy      = set(cfg.get('busy_heroes', cfg.get('busy', [])))
        self._used_army = {}
        self._used_pets = set()

        wait_for_queue = bool(cfg.get('wait_for_queue', cfg.get('wait_queue', False)))
        wait_interval  = float(cfg.get('wait_interval', 15.0))
        max_wait_cycles = int(cfg.get('max_wait_cycles', 35))
        wait_cycles = 0
        last_result = None

        while sent_count < max_marches:
            current_target_idx = sent_count + 1
            self.log.info(f"🚀 محاولة إرسال مسيرة الهجوم رقم ({current_target_idx}/{max_marches})...")
            result_code = await self._send_one_attack(map_type, sub_type, min_lv, max_lv, search_range, formation_id, troops_cfg)
            last_result = result_code

            if result_code == "SUCCESS":
                sent_count += 1
                consecutive_errors = 0
                wait_cycles = 0
                if sent_count < max_marches:
                    spacing = round(random.uniform(4.5, 7.5), 2)
                    self.log.info(f"🛡️ [أمان ومكافحة حظر] انتظار {spacing} ثانية قبل تجهيز المسيرة التالية...")
                    await asyncio.sleep(spacing)
            elif result_code == "QUEUE_FULL":
                if wait_for_queue and wait_cycles < max_wait_cycles:
                    wait_cycles += 1
                    self.log.info(f"⏳ [طوابير ممتلئة ({wait_cycles}/{max_wait_cycles})] بانتظار عودة أحد الفيالق لتفريغ مسيرة (انتظار {wait_interval:.0f} ثانية)...")
                    await asyncio.sleep(wait_interval)
                    self._busy.clear()
                    self._used_army.clear()
                    await self._load_heroes()
                    continue
                else:
                    self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل.")
                    break
            elif result_code == "STAMINA_EMPTY":
                self.log.warning("🛑 نفدت طاقة اللورد بالكامل — إنهاء المهمة.")
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
            elif result_code in ("NO_TARGET", "TARGET_OCCUPIED"):
                consecutive_errors += 1
                if consecutive_errors >= 4:
                    self.log.warning("⚠️ تعذر العثور على أهداف جديدة في النطاق المحدد — توقف مؤقت")
                    break
                await asyncio.sleep(3.0)
                continue
            else:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    break
                await asyncio.sleep(3.0)

        self.log.info(f"🏁 إجمالي مسيرات الهجوم المُرسَلة: {sent_count}/{max_marches}")
        if sent_count > 0:
            return TaskResult.ok(
                f"✅ تم إرسال {sent_count} مسيرة هجوم على {type_name}",
                sent=sent_count,
                queue_full=(last_result == "QUEUE_FULL"),
                stop_reason=last_result
            )
        if last_result == "QUEUE_FULL":
            return TaskResult.fail("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل (كود 8004: QUEUE_FULL)", queue_full=True, stop_reason="QUEUE_FULL")
        if last_result == "STAMINA_EMPTY":
            return TaskResult.fail("🛑 نفدت طاقة اللورد بالكامل", stop_reason="STAMINA_EMPTY")
        if last_result == "NO_ARMY":
            return TaskResult.fail("🛑 نفدت القوات المتاحة بالقلعة", stop_reason="NO_ARMY")
        if last_result in ("NO_HEROES", "HERO_BUSY"):
            return TaskResult.fail("🛑 لا يتوفر أبطال متاحون بالقلعة", stop_reason="NO_HEROES")
        if last_result in ("NO_TARGET", "TARGET_OCCUPIED"):
            return TaskResult.fail(f"⚠️ لم يتم العثور على أهداف متاحة لـ {type_name} في النطاق المحدد", stop_reason="NO_TARGET")
        return TaskResult.fail(f"لم يتم إرسال أي مسيرة هجوم على {type_name}", retry_after=120, stop_reason=str(last_result))

    # ── إرسال مسيرة هجوم واحدة ──────────────────────────────────

    async def _send_one_attack(self, map_type: int, sub_type: int, min_lv: int, max_lv: int, search_range: int, formation_id: int, troops_cfg: int) -> str:
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
        target_type_str = str(self.config.get('monster_type', 'rebels' if map_type == 35 else 'invaders')).lower().strip()
        target_info = MONSTER_TYPES.get(target_type_str, MONSTER_TYPES.get("rebels", {}))
        type_name = target_info.get("name", "متمردين" if map_type == 35 else "غزاة")

        # 1. جلب إحداثيات البحث (موقع المنطقة المحددة أو موقع القلعة تلقائياً)
        cx = self.config.get('center_x') or self.config.get('x')
        cy = self.config.get('center_y') or self.config.get('y')
        if cx is None or cy is None:
            r_castle = await self.conn.query('1006', '25', {"uid": uid_int})
            if not r_castle or not r_castle.get('retData'):
                return "ERROR"
            cx = r_castle['retData'].get('x')
            cy = r_castle['retData'].get('y')
        else:
            cx = int(cx)
            cy = int(cy)

        # 2. البحث عن الأهداف (متمردين 35 أو غزاة 6)
        r_search = await self.conn.query('2011', '3', {
            "mapType": map_type,
            "num": 5,
            "subType": sub_type,
            "y": cy,
            "x": cx,
            "exclude": _get_exclude(self.uid),
            "minLv": min_lv,
            "maxLv": max_lv,
            "range": search_range
        })
        candidates = r_search.get('result', []) if r_search else []
        if not candidates:
            self.log.warning(f"⚠️ لا توجد أهداف متاحة من هذا النوع في نطاق {search_range}!")
            return "NO_TARGET"

        # 3. جلب معرف المملكة (kingdom_id)
        kingdom_id = 0
        if self.conn.kingdom_id:
            try: kingdom_id = int(self.conn.kingdom_id)
            except: pass
        if not kingdom_id:
            r_map = await self.conn.query('1002', '7', {"uid": uid_int})
            if r_map and 'data' in r_map:
                kingdom_id = r_map['data'].get('base', {}).get('partition', 0)
        if not kingdom_id:
            kingdom_id = 4

        # 4. جلب القوات المتوفرة بالقلعة
        available: Dict[int, int] = {}
        r_army = await self.conn.query('1005', '1', {})
        if r_army and 'data' in r_army:
            for k, v in r_army['data'].get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)

        for tid, used in self._used_army.items():
            if tid in available:
                available[tid] = max(0, available[tid] - used)

        # 5. استعلام التشكيلة المحفوظة (1005/7) إن كانت محددة
        form_heroes = []
        form_pets = []
        form_rune_pages = []
        form_army_dict = {}
        if formation_id and formation_id > 0:
            r_form = await self.conn.query('1005', '7', {"compiletype": formation_id})
            if r_form and 'data' in r_form:
                form_heroes     = r_form['data'].get('compileHeros', [])
                form_pets       = r_form['data'].get('compilePets', [])
                form_rune_pages = r_form['data'].get('compileRunePages', [1])
                form_army_dict  = r_form['data'].get('compileArmy', {})

        # 6. فحص أبطال التشكيلة: هل هم متاحون وغير مشغولين؟
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
                self.log.info(f"🎖️ تم اختيار بطلي التشكيلة المحفوظة ({formation_id}): {chosen_heroes}")
            elif len(available_form_heroes) == 1:
                hero1 = available_form_heroes[0]
                self.log.info(f"ℹ️ أحد أبطال التشكيلة متاح ({hero1}) والآخر مشغول — جاري إكمال البطل الثاني بأفضل بطل حرب متاح...")
                extra_busy = set(self._busy) | {hero1}
                filler = _pick_combat_heroes(self._heroes, max_count=1, busy=extra_busy)
                chosen_heroes = [hero1] + filler
                self.log.info(f"⚔️ تشكيلة الأبطال المكتملة: {chosen_heroes}")

        # إذا كانت أبطال التشكيلة مشغولة أو بدون تشكيلة ثابتة: اختيار أبطال الحرب تلقائياً
        if not chosen_heroes:
            if formation_id > 0:
                self.log.info("⚠️ أبطال التشكيلة مشغولون — جاري اختيار أفضل أبطال الحرب (5501xxx) تلقائياً...")
            else:
                self.log.info("⚔️ اختيار أبطال الحرب والقتال تلقائياً بالعدد المناسب (بدون تشكيلة ثابتة)...")
            chosen_heroes = _pick_combat_heroes(self._heroes, max_count=2, busy=self._busy)
            if not chosen_heroes:
                self.log.warning("⚠️ لا يوجد أي بطل حرب متاح بالقلعة!")
                return "NO_HEROES"
            self.log.info(f"⚔️ أبطال الحرب المختارون: {chosen_heroes}")

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
            target_type=target_type_str,
            target_level=target_lv,
            castle_power=castle_power,
            user_troops_cfg=troops_cfg
        )

        army_list = []
        max_safe_capacity = 170000  # سقف أمان سعة مسيرة اللورد القصوى لمنع خطأ 8035

        if form_army_dict and formation_id > 0:
            # حساب إجمالي القوات المطلوبة في التشكيلة المحفوظة باللعبة (مع استبعاد فخاخ الجدار 800-899)
            total_form_req = sum(
                int(v) for k, v in form_army_dict.items()
                if str(k).isdigit() and str(v).isdigit() and not (800 <= int(k) < 900)
            )

            # اعتماد التشكيلة المحفوظة بالكامل كما هي دون تقليصها إلى 30 ألف
            scale = 1.0
            if total_form_req > max_safe_capacity:
                scale = float(max_safe_capacity) / float(total_form_req)
                needed_target = max_safe_capacity
                self.log.info(
                    f"🎖️ [التشكيلة المحفوظة #{formation_id}] إجمالي جنودها المسجل باللعبة ({total_form_req:,}) يتجاوز سعة مسيرة اللورد — "
                    f"تم ضبطها لـ {needed_target:,} جندي بأعلى نسبة أمان لمنع خطأ 8035"
                )
            else:
                needed_target = total_form_req
                self.log.info(
                    f"🎖️ [التشكيلة المحفوظة #{formation_id}] اعتماد كامل جنود التشكيلة المسجلة باللعبة ({needed_target:,} جندي) دون أي تقليص"
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
            needed_target = smart_troops
            if rec_power > 0:
                self.log.info(
                    f"🎯 [فحص القوة الذكي] الهدف: {type_name} (لفل {target_lv}) | "
                    f"القوة الموصى بها: {rec_power:,} | قوة قلعتك: {castle_power:,} | الحالة: {power_status}"
                )
                self.log.info(
                    f"⚔️ [حساب الجيش الذكي] تم احتساب سعة المسيرة ديناميكياً: {needed_target:,} جندي (وفق فحص الهدف وسعة اللورد)"
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

        if not army_list:
            self.log.warning("⚠️ لا توجد قوات قتالية متوفرة بالقلعة لإرسال المسيرة!")
            return "NO_ARMY"

        total_troops = sum(item['num'] for item in army_list)

        # 8. اختيار الحيوان الأليف والرونات (الحيوان يمكن إرساله في كل المسيرات معاً)
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
            pets_list = select_combat_pet(self.conn, set())

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

        self.log.info(f"🛡️ تشكيلة القتال: {army_list[:3]}... (إجمالي جنود: {total_troops:,}) | حيوان: {pets_list}")

        # 9. محاولة إرسال الهجوم على أهداف القائمة تباعاً حتى ينجح أحدها
        for target in candidates:
            target_id = target.get('id')
            tx, ty    = target.get('x'), target.get('y')
            t_lv      = target.get('level', '?')
            self.log.info(f"🎯 محاولة استهداف: ID={target_id} عند ({tx}, {ty}) لفل={t_lv}")
            _add_exclude(self.uid, target_id)

            if map_type == 35:
                # 🏴‍☠️ المتمردين: مسيرة حشد (Mass / Rally - moveLineType 7)
                attack_payload = {
                    "needSend": True,
                    "mapId": int(kingdom_id),
                    "moveLineType": 7,
                    "matrixType": 1,
                    "runePages": rune_pages_list,
                    "needArmyList": {},
                    "heros": chosen_heroes,
                    "pets": pets_list,
                    "data": {
                        "data": {
                            "mainInstanceType": 35,
                            "massTime": 300
                        },
                        "to": {
                            "y": int(ty),
                            "x": int(tx),
                            "id": str(target_id)
                        },
                        "army": army_list
                    }
                }
            else:
                # 👾 الغزاة: مسيرة هجوم فردية (Solo Attack - moveLineType 1)
                attack_payload = {
                    "needSend": False,
                    "mapId": int(kingdom_id),
                    "moveLineType": 1,
                    "matrixType": 1,
                    "runePages": rune_pages_list,
                    "heros": chosen_heroes,
                    "pets": pets_list,
                    "data": {
                        "data": {},
                        "to": {
                            "y": int(ty),
                            "x": int(tx),
                            "id": str(target_id)
                        },
                        "army": army_list
                    }
                }

            r_attack = await self.conn.query('1007', '2', attack_payload)
            if not r_attack:
                continue

            err = str(r_attack.get('err', '0'))
            if err == '0':
                self.log.info(f"✅ هجوم ناجح! → {target_id} (لفل {t_lv}) | أبطال={chosen_heroes} | جنود={total_troops:,}")
                for hid in chosen_heroes:
                    self._busy.add(hid)
                for item in army_list:
                    self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                return "SUCCESS"
            elif err in ('8004', '9007004'):
                self.log.info(f"🛑 اكتملت طوابير المسيرات للقلعة (كود {err})")
                return "QUEUE_FULL"
            elif err == '8009':
                self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
                return "NO_ARMY"
            elif err in ('10002', '10003'):
                self.log.warning(f"🛑 نفدت طاقة اللورد بالكامل (كود {err})")
                return "STAMINA_EMPTY"
            elif err == '9007020':
                for hid in chosen_heroes:
                    self._busy.add(hid)
                return "HERO_BUSY"
            elif err == '8035':
                current_total = sum(item['num'] for item in army_list)
                if current_total > 5000:
                    reduced_troops = max(1000, int(current_total * 0.88))
                    self.log.warning(f"⚠️ خطأ 8035 (تجاوز سعة مسيرة اللورد) | إعادة المحاولة فوراً بضبط القوات ({reduced_troops:,} جندي)...")
                    scale_down = reduced_troops / float(current_total)
                    for itm in army_list:
                        itm['num'] = max(1, int(itm['num'] * scale_down))
                    total_troops = sum(itm['num'] for itm in army_list)
                    attack_payload['data']['army'] = army_list
                    r_retry = await self.conn.query('1007', '2', attack_payload)
                    if r_retry and str(r_retry.get('err', '0')) == '0':
                        self.log.info(f"✅ هجوم ناجح بعد ضبط القوات! → {target_id} (لفل {t_lv}) | أبطال={chosen_heroes} | جنود={total_troops:,}")
                        for hid in chosen_heroes:
                            self._busy.add(hid)
                        for item in army_list:
                            self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                        return "SUCCESS"
                self.log.warning(f"⚠️ الهدف {target_id} غير متاح أو مشغول بمعركة أخرى (كود {err}) — فحص هدف بديل فوراً...")
                continue
            elif err in ('8062', '8063', '8060', '8013', '8002', '8026', '8003', '9007062') or (err.startswith('80') and err not in ('8004', '8009')):
                self.log.warning(f"⚠️ الهدف {target_id} غير متاح أو مشغول بمعركة أخرى (كود {err}) — فحص هدف بديل فوراً...")
                continue
            else:
                self.log.warning(f"⚠️ تعذر استهداف {target_id} (كود {err}) — تجربة هدف بديل...")
                continue

        return "TARGET_OCCUPIED"


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Monster Attack Bot — الهجوم على الغزاة والمتمردين")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--type", "-t", choices=["rebels", "invaders"], default=DEFAULT_MONSTER_TYPE, help="نوع الهدف: rebels (متمردين) أو invaders (غزاة) [افتراضي: rebels]")
    parser.add_argument("--minlv", type=int, default=DEFAULT_MIN_LV, help=f"أدنى لفل للهدف [افتراضي: {DEFAULT_MIN_LV}]")
    parser.add_argument("--maxlv", type=int, default=DEFAULT_MAX_LV, help=f"أعلى لفل للهدف [افتراضي: {DEFAULT_MAX_LV}]")
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
            "monster_type": args.type,
            "min_lv": args.minlv,
            "max_lv": args.maxlv,
            "max_marches": args.marches,
            "search_range": args.range,
            "formation_id": args.formation
        }

        task = MonsterTask(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
