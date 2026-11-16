# -*- coding: utf-8 -*-
"""

  python tasks/elf_boss.py --email "hmzawyha44@gmail.com" --formation 2
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
import math
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# ════════════════════════════════════════════════════════════════════
#  الثوابت الأساسية لمهمة العفريت
# ════════════════════════════════════════════════════════════════════

# فئات زعماء العفاريت على الخريطة:
# فئة 10 = نخبة العفريت (Hero Battle Boss Tier 4 / Elite) - mapType: 24
# فئة 9 = العفريت العادي (Hero Battle Boss Tier 3 / Normal) - mapType: 23
ELITE_ELF_BOSS_TYPE     = 10   # نخبة العفريت
NORMAL_ELF_BOSS_TYPE    = 9    # العفريت العادي
DEFAULT_BOSS_TYPE       = 10   # الافتراضي: نخبة العفريت (bossType 10)
ELF_BOSS_TYPES          = [10, 9, 6, 5]
ELF_MAIN_INSTANCE_TYPE  = 24   # نوع الحدث الرئيسي الثابت لنخبة العفريت
ELF_MASS_TIME           = 300  # مدة التجمع والحشد بالثواني (5 دقائق)
ELF_MOVE_LINE_TYPE      = 7    # نوع مسار مسيرة الحشد

DEFAULT_FORMATION_ID    = 1    # التشكيلة الافتراضية
DEFAULT_TROOPS_COUNT    = 50000
MAX_CASTLE_LEGIONS      = 6    # أقصى عدد فيالق ومسيرات ممكنة لأي قلعة
DEFAULT_ATTACK_DELAY    = 35.0 # فترة الأمان الافتراضية الموسعة بين كل هجوم والآخر بالثواني (30 إلى 50 ثانية)
MAX_ELF_SEARCH_DISTANCE = 250.0 # الحد الأقصى المطلق لمسافة البحث عن العفريت (250 كم)
_CASTLE_COORDS_CACHE: Dict[str, Tuple[int, int]] = {} # كاش إحداثيات القلعة العام لمنع الاستعلام المتكرر للسيرفر


# ════════════════════════════════════════════════════════════════════
#  اختيار أفضل أبطال الحرب والقتال (Combat Heroes Selection)
# ════════════════════════════════════════════════════════════════════

def _pick_combat_heroes(heroes: list, max_count: int = 2, busy: Set[int] = None) -> List[int]:
    """
    اختيار أفضل أبطال حرب وقتال (5501xxx) بدقة عند انشغال أبطال التشكيلة:
      1. الأولوية الأولى: أبطال حرب (5501xxx) يمتلكون مهارات هجومية وقتالية (5610xxx / 5640xxx).
      2. الأولوية الثانية: بقية أبطال الحرب (5501xxx) المتاحين مرتبين حسب المستوى والنجوم.
      3. استبعاد أبطال الجمع (5502xxx) وأبطال الإدارة والدعم (5503xxx) والمشغولين.
    """
    busy = busy or set()
    tier1, tier2, tier3 = [], [], []

    for hero in heroes:
        if not isinstance(hero, dict):
            continue
        hid = hero.get('id')
        if not hid:
            continue
        try:
            hid_int = int(hid)
        except Exception:
            continue

        if hid_int in busy:
            continue
        if hero.get('status', {}).get('state', 0) != 0:
            continue

        hid_str = str(hid_int)
        # استبعاد أبطال الجمع والدعم الإداري
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
                tier1.append((hid_int, score))
            else:
                tier2.append((hid_int, score))
        else:
            tier3.append((hid_int, score))

    tier1.sort(key=lambda x: x[1], reverse=True)
    tier2.sort(key=lambda x: x[1], reverse=True)
    tier3.sort(key=lambda x: x[1], reverse=True)

    chosen = [h[0] for h in tier1] + [h[0] for h in tier2] + [h[0] for h in tier3]
    return chosen[:max_count] if max_count else chosen


# ════════════════════════════════════════════════════════════════════
#  اختيار جيش القتال الاحتياطي (Combat Army Fallback)
# ════════════════════════════════════════════════════════════════════

def select_combat_army(available: Dict[int, int], needed_count: int = DEFAULT_TROOPS_COUNT) -> List[Dict[str, int]]:
    """
    اختيار تشكيلة جيش قتالية متوازنة بالعدد المناسب:
    توزيع متوازن بين المشاة، الفرسان، والرماة بحسب المتاح في القلعة من الرتب الأعلى.
    1. المشاة (401..414)
    2. الفرسان (501..514)
    3. الرماة (601..614)
    4. عربات الحصار (701..714) كاحتياط
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
#  دالة تعطيل مهمة العفريت لقلعة محددة حصراً في قاعدة البيانات
# ════════════════════════════════════════════════════════════════════

def disable_elf_task(identifier: Optional[str] = None) -> bool:
    """
    تعطيل مهمة العفريت لقلعة محددة حصراً في قاعدة البيانات (عمود config):
    تضبط قيمة "elf": {"enabled": False, ...} مع الحفاظ التام على رقم التشكيلة المحدد.

    :param identifier: البريد الإلكتروني للقلعة (email) أو معرف القلعة (castle_id).
    :return: True عند نجاح الحفظ في SQLite، و False عند الفشل أو عدم العثور على القلعة.
    """
    if not identifier:
        logging.getLogger("task.elf_boss").warning("⚠️ تعذر تعطيل مهمة العفريت: لم يتم تمرير معرّف القلعة أو البريد.")
        return False

    clean_id = str(identifier).strip()
    try:
        from core.database import get_castle, update_castle_config
        c = get_castle(clean_id)
        if not c:
            logging.getLogger("task.elf_boss").warning(f"⚠️ القلعة غير مسجلة في قاعدة البيانات ({clean_id}).")
            return False

        cid = c.get("castle_id")
        if not cid:
            return False

        # الحفاظ على رقم التشكيلة المسجل مسبقاً للقلعة
        existing_formation = 1
        raw_cfg = c.get("config")
        if isinstance(raw_cfg, str):
            try:
                import json
                raw_cfg = json.loads(raw_cfg)
            except Exception:
                raw_cfg = {}
        if isinstance(raw_cfg, dict):
            elf_val = raw_cfg.get("elf")
            if isinstance(elf_val, dict):
                existing_formation = int(elf_val.get("formation_id", 1))

        patch = {
            "elf": {
                "enabled": False,
                "formation_id": existing_formation,
            }
        }
        res = update_castle_config(cid, patch)
        ok = bool(res.get("success", False)) if isinstance(res, dict) else bool(res)
        if ok:
            logging.getLogger("task.elf_boss").info(f"🛑 تم بنجاح تعطيل مهمة العفريت للقلعة {clean_id} (elf.enabled = False) في قاعدة البيانات.")
        return ok
    except Exception as e:
        logging.getLogger("task.elf_boss").error(f"❌ خطأ أثناء تعطيل مهمة العفريت للقلعة {clean_id}: {e}")
        return False




# ════════════════════════════════════════════════════════════════════
#  كلاس مهمة الهجوم على العفريت (ElfBossTask)
# ════════════════════════════════════════════════════════════════════

class ElfBossTask(BaseTask):
    """
    مهمة البحث والهجوم على نخبة العفريت (Hero Battle Boss) وتشكيل حشود القتال بكل الفيالق المتوفرة.
    """
    name = "elf_boss"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self.formation_id : int = int(self.config.get('formation', self.config.get('formation_id', DEFAULT_FORMATION_ID)))
        cfg_dist = self.config.get('max_distance')
        # سقف مسافة إلزامي لا يتجاوز 100 كم أبداً
        self.max_distance : float = min(float(cfg_dist), MAX_ELF_SEARCH_DISTANCE) if cfg_dist is not None else MAX_ELF_SEARCH_DISTANCE
        
        # دعم الهجوم بكل الفيالق المتوفرة (افتراضياً مفعل) أو تحديد عدد معين
        cfg_count = self.config.get('count', self.config.get('marches'))
        self.all_legions  : bool = bool(self.config.get('all_legions', cfg_count is None))
        self.attack_count : int = int(cfg_count) if cfg_count is not None else MAX_CASTLE_LEGIONS

        # نوع العفريت المستهدف: 10 = نخبة العفريت (الافتراضي)، 9 = العفريت العادي
        self.boss_type : int = int(self.config.get('boss_type', self.config.get('bossType', DEFAULT_BOSS_TYPE)))

        # مهلة الأمان الأساسية بين كل هجوم والآخر بالثواني مع دعم التباين العشوائي
        self.attack_delay : float = float(self.config.get('delay', self.config.get('attack_delay', DEFAULT_ATTACK_DELAY)))
        # سعة المسيرة القصوى الآمنة لمنع خطأ تجاوز سعة مسيرة اللورد (كود 8035)
        self.max_march_troops: int = int(self.config.get('max_march_troops', 200000))
        # وضع الأمان الفائق الشامل ومحاكاة السلوك البشري الموسع
        self.ultra_safe      : bool = bool(self.config.get('ultra_safe', False))

        self._heroes          : List[Dict[str, Any]] = []
        self._busy_heroes     : Set[int] = set(self.config.get('busy_heroes', self.config.get('busy', [])))
        self._targeted_bosses : Set[Tuple[int, int]] = set()
        self._targeted_boss_ids: Set[str] = set()
        self._template_army   : Dict[str, int] = {}
        self._template_pets   : List[int] = []
        self._template_runes  : List[int] = [1]
        self._castle_x        : int = 0
        self._castle_y        : int = 0
        self._map_id          : int = 0
        self._cached_formation_data: Optional[Tuple[List[int], List[int], List[int], Dict[str, int]]] = None
        self._cached_boss_pool: List[Tuple[int, int, int, int, str, float]] = []

    def _remove_from_cached_pool(self, bx: int, by: int, tid: Optional[str] = None):
        """إزالة الزعيم المشغول أو المنتهي من كاش الذاكرة فوراً لمنع تكرار اختياره."""
        self._cached_boss_pool = [
            c for c in self._cached_boss_pool
            if not (c[0] == bx and c[1] == by) and (not tid or c[4] != tid)
        ]

    def disable_elf_task(self, castle_id_or_email: Optional[str] = None) -> bool:
        """
        تعطيل مهمة العفريت للقلعة الحالية (أو المحددة) في قاعدة البيانات والذاكرة الحية:
        يضبط 'elf': {'enabled': False} مع الحفاظ التام على رقم التشكيلة وبقية الإعدادات.
        """
        cid = (
            castle_id_or_email
            or getattr(self, "email", None)
            or (getattr(getattr(self, "conn", None), "account", None) and getattr(self.conn.account, "email", None))
            or getattr(getattr(self, "conn", None), "castle_id", None)
            or getattr(self, "uid", None)
        )
        ok = disable_elf_task(cid)
        if isinstance(self.config, dict) and "elf" in self.config:
            if isinstance(self.config["elf"], dict):
                self.config["elf"]["enabled"] = False
        if hasattr(self.conn, "castle_config") and isinstance(self.conn.castle_config, dict):
            if "elf" in self.conn.castle_config and isinstance(self.conn.castle_config["elf"], dict):
                self.conn.castle_config["elf"]["enabled"] = False
        return ok

    async def on_start(self):
        """انتظار تحميل حزم البيانات الأساسية وتحميل سجل الأبطال وموقع القلعة ومعرف الخريطة ومزامنة الطوابير."""
        for _ in range(15):
            has_city = "cityCtrl" in self.conn.init_data
            has_heroes = bool((self.conn._gate and getattr(self.conn._gate, 'heroes', None)) or self.conn.init_data.get('heroCtrl'))
            if has_city and has_heroes:
                break
            await asyncio.sleep(0.3)

        # تحديث قائمة الطوابير فقط إذا لم تكن متوفرة بالذاكرة الحية
        if not getattr(self.conn, 'local_queues', None):
            try:
                await self.conn.query('1007', '16', {}, timeout=4)
            except Exception:
                pass


        await self._load_castle_coords()
        await self._load_map_id()
        await self._load_heroes()
        self._detect_busy_heroes()

    async def is_event_active(self) -> Tuple[bool, str]:
        """
        التحقق الفوري من حالة حدث نخبة العفريت عبر الذاكرة الحية (Zero-Request):
        يتم فحص وحدة التحكم activityShowCtrl بالذاكرة الحية ومزامنة إشعارات السيرفر
        للمعرف الرسمي للحدث 9001083 (elite_boss_title_01).
        حالات الفعالية الرسمية (gActivityState):
          - state = 3 (OPEN): الحدث مفتوح ونشط حالياً في المملكة.
          - state = 2 (PREPARE): الحدث في مرحلة الاستعداد/المعاينة قبل البدء.
          - state = 1 (CLOSE): الحدث مغلق أو منتهٍ.
        """
        ELF_ACTIVITY_ID = "9001083"
        init_data = getattr(self.conn, 'init_data', {}) or {}
        act_show = init_data.get('activityShowCtrl', {})

        # 1. جلب البيانات الأولية من الذاكرة الحية
        act_info = dict(act_show.get(ELF_ACTIVITY_ID, {})) if isinstance(act_show, dict) and isinstance(act_show.get(ELF_ACTIVITY_ID), dict) else {}

        # 2. فحص أحدث إشعارات السيرفر المباشرة لتحديث الحالة بالثانية (NOTIFY_ACTIVITY_SHOW_CHANGE_TIME)
        cached_packets = getattr(self.conn, 'cached_packets', {}) or {}
        for p in cached_packets.values():
            if isinstance(p, dict):
                d = p.get('data', {})
                if isinstance(d, dict) and d.get('notifyID') == 'NOTIFY_ACTIVITY_SHOW_CHANGE_TIME':
                    nd = d.get('notifyData') or d.get('data') or []
                    items = nd if isinstance(nd, list) else [nd]
                    for item in items:
                        if isinstance(item, dict) and ELF_ACTIVITY_ID in item:
                            val = item[ELF_ACTIVITY_ID]
                            if isinstance(val, dict):
                                act_info.update(val)

        # إذا كانت بيانات الفعاليات غير متوفرة إطلاقاً بالذاكرة الحية (حالات نادرة جداً قبل التهيئة)
        if not act_show or not isinstance(act_show, dict):
            return True, "بيانات الفعاليات بالذاكرة الحية قيد التحميل — المتابعة المباشرة للبحث"

        if not act_info:
            return False, "حدث نخبة العفريت غير مدرج في جدول فعاليات السيرفر الحالية (معرف 9001083)"

        state = int(act_info.get('state', 1))
        begintime = int(act_info.get('begintime', 0))
        endtime = int(act_info.get('endtime', 0))
        now = time.time()

        if state == 3:
            if endtime > 0 and now >= endtime:
                end_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(endtime))
                return False, f"حدث نخبة العفريت انتهى وقته (انتهى عند {end_str})"
            left_seconds = max(0, int(endtime - now)) if endtime > 0 else 0
            left_str = f" (متبقي {left_seconds // 3600}س و{(left_seconds % 3600) // 60}د)" if left_seconds > 0 else ""
            return True, f"حدث نخبة العفريت نشط ومفتوح في المملكة{left_str}"
        elif state == 2:
            begin_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(begintime)) if begintime > 0 else "قريباً"
            return False, f"حدث نخبة العفريت في مرحلة التحضير ولم يبدأ بعد (سيبدأ عند {begin_str})"
        else:
            return False, "حدث نخبة العفريت مغلق حالياً على السيرفر (state=CLOSE)"

    async def _load_castle_coords(self):
        """جلب إحداثيات قلعة اللاعب على الخريطة من الذاكرة الحية (Zero-Request)."""
        # 1. إذا كانت محملة بالفعل في الكائن الحالي
        if self._castle_x > 0 and self._castle_y > 0:
            return

        uid_key = str(self.uid)
        # 2. فحص الكاش العام بالذاكرة لمنع تكرار أي استعلام
        if uid_key in _CASTLE_COORDS_CACHE:
            self._castle_x, self._castle_y = _CASTLE_COORDS_CACHE[uid_key]
            self.log.debug(f"🏰 موقع قلعة اللورد (من الكاش): ({self._castle_x}, {self._castle_y})")
            return

        # 3. قراءة الإحداثيات مباشرة من الذاكرة الحية cityCtrl (Zero-Request)
        pos = self.conn.init_data.get('cityCtrl', {}).get('cinfo', {}).get('pos', {}) if hasattr(self.conn, 'init_data') else {}
        if pos and 'x' in pos and 'y' in pos:
            self._castle_x, self._castle_y = int(pos['x']), int(pos['y'])
            _CASTLE_COORDS_CACHE[uid_key] = (self._castle_x, self._castle_y)
            self.log.debug(f"🏰 موقع قلعة اللورد (من الذاكرة الحية): ({self._castle_x}, {self._castle_y})")
            return

        # 4. الاستعلام من السيرفر كخطة طوارئ احتياطية فقط
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
        try:
            self.log.warning("🛑🛑🛑🛑🛑🛑")
            r_castle = await self.conn.query('1006', '25', {"uid": uid_int}, timeout=4)
            if r_castle and 'retData' in r_castle:
                self._castle_x = int(r_castle['retData'].get('x', 0))
                self._castle_y = int(r_castle['retData'].get('y', 0))
                if self._castle_x > 0 and self._castle_y > 0:
                    _CASTLE_COORDS_CACHE[uid_key] = (self._castle_x, self._castle_y)
                self.log.debug(f"🏰 موقع قلعة اللورد: ({self._castle_x}, {self._castle_y})")
        except Exception as e:
            self.log.warning(f"⚠️ تعذر جلب إحداثيات القلعة: {e}")

    def _resolve_map_id(self) -> int:
        """جلب معرف الخريطة والمملكة (mapId / kingdomId) تلقائياً من بيانات الحساب."""
        kmap = self.conn.init_data.get('kingdomMapCtrl', {})
        if isinstance(kmap, dict):
            mid = kmap.get('mapId') or kmap.get('kingdomId')
            if mid and str(mid).isdigit() and int(mid) > 0:
                return int(mid)

        if self.conn.kingdom_id:
            try:
                kid = int(self.conn.kingdom_id)
                if kid > 0:
                    return kid
            except Exception:
                pass

        lord_base = self.conn.init_data.get('lordInfoCtrl', {}).get('base', {})
        if isinstance(lord_base, dict):
            part = lord_base.get('partition')
            if part and str(part).isdigit() and int(part) > 0:
                return int(part)

        lord = self.conn.init_data.get('lord', {})
        if isinstance(lord, dict):
            part = lord.get('partition') or lord.get('kingdomId')
            if part and str(part).isdigit() and int(part) > 0:
                return int(part)

        return 0

    async def _load_map_id(self):
        """تحديد معرف الخريطة والمملكة (mapId) تلقائياً للحساب."""
        self._map_id = await self.get_kingdom_id()
        if not self._map_id:
            uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
            try:
                self.log.warning("🛑🛑🛑🛑🛑🛑")
                r_player = await self.conn.query('1002', '7', {"uid": uid_int}, timeout=4)
                if r_player and 'data' in r_player:
                    part = r_player['data'].get('base', {}).get('partition')
                    if part and str(part).isdigit() and int(part) > 0:
                        self._map_id = int(part)
            except Exception as e:
                self.log.warning(f"⚠️ تعذر جلب معرف الخريطة من 1002/7: {e}")

        self.log.debug(f"🗺️ معرف خريطة ومملكة اللورد (mapId): {self._map_id}")

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

    def _detect_busy_heroes(self):
        """استخراج الأبطال المشغولين في مسيرات الخريطة الحالية بدقة 100% من الذاكرة الحية (Live Memory Engine)."""
        if not hasattr(self, '_busy_heroes') or self._busy_heroes is None:
            self._busy_heroes = set(self.config.get('busy_heroes', self.config.get('busy', [])))
        else:
            self._busy_heroes.update(self.config.get('busy_heroes', self.config.get('busy', [])))

        queues = self._read_live_local_queues(self.conn)
        my_uid = str(getattr(self, "uid", "") or "").strip()

        active_march_count = 0
        for q in queues:
            if not isinstance(q, dict):
                continue
            q_uid = q.get("uid")
            if my_uid and q_uid not in (None, "", 0, "0") and str(q_uid).strip() != my_uid:
                continue
            # مسيرات نشطة (سائرة أو مرابطة أو حشد - 0 = Rally, 1 = Moving, 2 = Working/Battling, 3 = Returning, 4, 7)
            if q.get('status') in (0, 1, 2, 3, 4, 7):
                active_march_count += 1
                h_list = q.get('heros') or q.get('data', {}).get('heros') or []
                if isinstance(h_list, list):
                    for h in h_list:
                        hid = h if isinstance(h, int) else (h.get('id') if isinstance(h, dict) else None)
                        if hid and str(hid).isdigit():
                            self._busy_heroes.add(int(hid))

        # فحص أبطال الذاكرة الحية من heroCtrl إذا كانت حالتهم state != 0
        for h in self._heroes:
            if isinstance(h, dict):
                hid = h.get('id')
                if hid and str(hid).isdigit():
                    st = h.get('status', {}).get('state', 0) if isinstance(h.get('status'), dict) else 0
                    if st != 0:
                        self._busy_heroes.add(int(hid))

        if self._busy_heroes:
            self.log.debug(f"⏳ أبطال مشغولون في مسيرات قائمة (الذاكرة الحية): {list(self._busy_heroes)} (عدد المسيرات النشطة: {active_march_count})")

    def _get_active_boss_targets(self) -> Tuple[Set[Tuple[int, int]], Set[str]]:
        """
        استخراج إحداثيات ومعرفات العفاريت التي يوجد فيلق نشط في الطريق إليها حالياً (سائر أو حشد):
        (status in (0, 1, 2) لمنع تكرار الهجوم وخطأ 8026).
        """
        active_coords: Set[Tuple[int, int]] = set()
        active_ids: Set[str] = set()

        queues = self._read_live_local_queues(self.conn)
        my_uid = str(getattr(self, "uid", "") or "").strip()

        for q in queues:
            if not isinstance(q, dict):
                continue
            q_uid = q.get("uid")
            if my_uid and q_uid not in (None, "", 0, "0") and str(q_uid).strip() != my_uid:
                continue
            status = q.get("status")
            if status not in (0, 1, 2):  # 0=Rally, 1=Moving to target, 2=Battling
                continue
            to_data = q.get("to") or q.get("data", {}).get("to") or {}
            if isinstance(to_data, dict):
                tid = str(to_data.get("id") or "").strip()
                if tid:
                    active_ids.add(tid)
                    try:
                        parts = tid.split("-")
                        active_coords.add((int(parts[0]), int(parts[1])))
                    except Exception:
                        pass
                tx = to_data.get("x")
                ty = to_data.get("y")
                if tx is not None and ty is not None:
                    active_coords.add((int(tx) + 1, int(ty) + 1))

        return active_coords, active_ids

    async def _find_unique_elf_boss(
        self,
        excluded_coords: Optional[Set[Tuple[int, int]]] = None,
        excluded_ids: Optional[Set[str]] = None
    ) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int], Optional[str], float, str]:
        """
        البحث الاحترافي الذكي المباشر عن نخبة العفريت وزعماء الأبطال (Hero Battle Boss):
          1. استعلام رادار الزعماء المباشر (2011/4) كأولوية أولى كما تفعل واجهة اللعبة الرسمية.
          2. استعلام الخريطة الشامل (2011/3) بنطاق المسافة الأقصى مباشرة دون تدرج متثاقل أو فترات نوم مصطنعة.
          3. استخراج الإحداثيات الحقيقية المعتمدة من المعرف ID لضمان التطابق 100% ومنع خطأ 8002.
        تعيد: (bx, by, boss_type, boss_instance_type, target_map_id, distance, status_msg)
        """
        if excluded_coords is None:
            excluded_coords = self._targeted_bosses
        if excluded_ids is None:
            excluded_ids = self._targeted_boss_ids

        if self._castle_x <= 0 or self._castle_y <= 0:
            await self._load_castle_coords()

        cx = self._castle_x
        cy = self._castle_y

        if cx <= 0 or cy <= 0:
            self.log.error("❌ تعذر تحديد إحداثيات القلعة — إلغاء البحث لمنع أي مسيرات شاذة.")
            return None, None, None, None, None, 0.0, "تعذر تحديد موقع القلعة بدقة"

        max_limit = min(float(self.max_distance or MAX_ELF_SEARCH_DISTANCE), MAX_ELF_SEARCH_DISTANCE)
        candidates = []
        seen_ids = set(excluded_ids)
        seen_coords = set(excluded_coords)

        # تحديد فئات الزعماء ونوع الخريطة حسب نوع الهدف
        is_elite = (self.boss_type in (10, 6) or self.boss_type == DEFAULT_BOSS_TYPE)
        map_type = 24 if is_elite else 23

        # ── 0. فحص كاش الأهداف المحفوظة بالذاكرة أولاً (Target Pool Cache) ──
        if self._cached_boss_pool:
            pool_candidates = [
                c for c in self._cached_boss_pool
                if c[4] not in seen_ids and (c[0], c[1]) not in seen_coords and c[5] <= max_limit
            ]
            if pool_candidates:
                pool_candidates.sort(key=lambda c: c[5])
                best_bx, best_by, best_btype, best_itype, best_tid, best_dist = pool_candidates[0]
                boss_label = "نخبة العفريت (Elite Boss)" if best_btype in (10, 6) else f"العفريت العادي (فئة {best_btype})"
                rem_cnt = len(pool_candidates) - 1
                self.log.info(
                    f"🎯 [من كاش الأهداف المباشر] تم اختيار {boss_label} عند ({best_bx}, {best_by}) "
                    f"[ID: {best_tid}] | المسافة: {best_dist:.1f} كم (المتبقي بالكاش: {rem_cnt} زعيم)"
                )
                return best_bx, best_by, best_btype, best_itype, best_tid, best_dist, "OK"

        # ── استعلام الخريطة الشامل (2011/3) لجمع مسبح الأهداف المتاحة ──
        search_range = int(max_limit or 250)
        try:
            self.log.info(f"😍😍😍😍😍😍")
            resp_map = await self.conn.query('2011', '3', {
                "mapType": map_type,
                "num": 10,
                "y": cy,
                "x": cx,
                "range": search_range
            }, timeout=5)

            if resp_map and isinstance(resp_map.get('result'), list):
                # اعتماد بيانات 2011/3 كأهداف جديدة، وتحديث الاستبعاد ليقتصر على المسيرات النشطة فقط لمنع 8026
                active_coords, active_ids = self._get_active_boss_targets()
                self._targeted_bosses = set(active_coords)
                self._targeted_boss_ids = set(active_ids)
                self._cached_boss_pool.clear()

                fresh_seen_ids = set(active_ids)
                fresh_seen_coords = set(active_coords)

                for item in resp_map['result']:
                    if not isinstance(item, dict):
                        continue
                    tid = str(item.get('id', '')).strip()
                    if not tid or tid in fresh_seen_ids:
                        continue

                    # استخراج الإحداثيات الحقيقية المعتمدة من المعرف ID مباشرة
                    try:
                        parts = tid.split('-')
                        real_x = int(parts[0])
                        real_y = int(parts[1])
                        btype = int(parts[-1])
                    except Exception:
                        real_x = int(item.get('x', 0)) + 1
                        real_y = int(item.get('y', 0)) + 1
                        btype = self.boss_type

                    if (real_x, real_y) in fresh_seen_coords:
                        continue

                    dist = math.hypot(real_x - cx, real_y - cy)
                    if dist > max_limit:
                        continue

                    fresh_seen_ids.add(tid)
                    fresh_seen_coords.add((real_x, real_y))
                    candidates.append((real_x, real_y, btype, map_type, tid, dist))
        except Exception as e:
            self.log.debug(f"خطأ أثناء استعلام الخريطة 2011/3: {e}")

        # حفظ كافة الأهداف المكتشفة في كاش الذاكرة للفيالق التالية
        if candidates:
            cached_ids = {c[4] for c in self._cached_boss_pool}
            for c in candidates:
                if c[4] not in cached_ids:
                    self._cached_boss_pool.append(c)

        if not candidates:
            target_desc = "نخبة العفريت" if is_elite else f"العفريت (فئة {self.boss_type})"
            return None, None, None, None, None, 0.0, f"لم يتم العثور على أي {target_desc} ضمن نطاق {max_limit} كم"

        # فرز المرشحين واختيار الأقرب مسافة إلى القلعة
        candidates.sort(key=lambda c: c[5])
        best_bx, best_by, best_btype, best_itype, best_tid, best_dist = candidates[0]
        boss_label = "نخبة العفريت (Elite Boss)" if best_btype in (10, 6) else f"العفريت العادي (فئة {best_btype})"
        self.log.debug(
            f"🎯 تم اختيار {boss_label} عند ({best_bx}, {best_by}) "
            f"[ID: {best_tid}] | المسافة: {best_dist:.1f} كم من القلعة"
        )
        return best_bx, best_by, best_btype, best_itype, best_tid, best_dist, "OK"

    async def _load_formation(self, fid: int) -> Tuple[List[int], List[int], List[int], Dict[str, int]]:
        """
        استخراج بيانات التشكيلة المطلوبة من الذاكرة الحية (RAM) فورياً (0ms):
        تعيد: (أبطال_التشكيلة, حيوانات_التشكيلة, صفحات_الرون, جيش_التشكيلة)
        """
        if self._cached_formation_data is not None:
            return self._cached_formation_data

        fid_str = str(fid)

        # 1. قراءة فورية من الذاكرة الحية (RAM)
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        data = army_ctrl if (isinstance(army_ctrl, dict) and 'compileArmy' in army_ctrl) else {}

        # 2. استعلام احتياطي فقط إذا لم تكن التشكيلة مخزنة بالذاكرة
        if not data:
            try:
                self.log.debug(f"🛑🛑🛑🛑🛑🛑🛑 جاري استدعاء 1005/7 لجلب بيانات التشكيلة رقم {fid}")
                resp = await self.conn.query('1005', '7', {"compiletype": fid}, timeout=4)
                if resp and resp.get('data'):
                    data = resp.get('data', {})
            except Exception:
                pass

        if not data:
            self.log.warning(f"⚠️ تعذر جلب بيانات التشكيلة {fid}، سيتم استخدام الإعدادات التلقائية.")
            return [], [], [1], {}

        # 1. استخراج الأبطال
        raw_heroes = data.get('compileHeros', [])
        if isinstance(raw_heroes, dict):
            raw_heroes = raw_heroes.get(fid_str, raw_heroes.get(1, []))
        heroes = []
        if isinstance(raw_heroes, list):
            heroes = [int(h) for h in raw_heroes if str(h).isdigit() and int(h) > 0]

        # 2. استخراج الحيوانات الأليفة
        raw_pets = data.get('compilePets', [])
        if isinstance(raw_pets, dict):
            raw_pets = raw_pets.get(fid_str, raw_pets.get(1, []))
        pets = []
        if isinstance(raw_pets, list):
            pets = [int(p) for p in raw_pets if str(p).isdigit() and int(p) > 0]

        # 3. استخراج صفحات الرون
        raw_runes = data.get('compileRunePages', [1])
        if isinstance(raw_runes, dict):
            raw_runes = raw_runes.get(fid_str, [1])
        runes = [1]
        if isinstance(raw_runes, list) and raw_runes:
            runes = [int(r) for r in raw_runes if str(r).isdigit() and int(r) > 0] or [1]

        # 4. استخراج الجيش
        raw_army = data.get('compileArmy', {})
        if isinstance(raw_army, dict) and fid_str in raw_army:
            raw_army = raw_army[fid_str]
        army = {}
        if isinstance(raw_army, dict):
            for k, v in raw_army.items():
                if str(k).isdigit() and str(v).isdigit() and int(v) > 0:
                    army[str(k)] = int(v)

        self._cached_formation_data = (heroes, pets, runes, army)
        return heroes, pets, runes, army

    def _resolve_combat_heroes(self, form_heroes: List[int], fid_label: str = "") -> List[int]:
        """
        التحقق من أبطال التشكيلة أو الاستبدال التلقائي بأبطال حرب شاغرين (مطابق لمعيار monster.py و stronghold.py):
        """
        available_form: List[int] = []
        for h in form_heroes:
            if h and str(h).isdigit():
                hid = int(h)
                if hid not in self._busy_heroes:
                    hdata = next((x for x in self._heroes if x.get('id') and int(x['id']) == hid), None)
                    if hdata and hdata.get('status', {}).get('state', 0) == 0:
                        available_form.append(hid)

        if len(available_form) >= 2:
            chosen = available_form[:2]
            self.log.info(f"🎖️ تم اختيار أبطال التشكيلة المحفوظة ({fid_label}): {chosen}")
            return chosen

        if available_form:
            hero1 = available_form[0]
            self.log.debug(f"ℹ️ أحد أبطال التشكيلة متاح ({hero1}) والآخر مشغول — إكمال البطل الثاني...")
            extra_busy = set(self._busy_heroes) | {hero1}
            fillers = _pick_combat_heroes(self._heroes, max_count=1, busy=extra_busy)
            if fillers:
                chosen = [hero1, fillers[0]]
                self.log.info(f"⚔️ تشكيلة الأبطال المكتملة (بطل التشكيلة {hero1} + بديل {fillers[0]}): {chosen}")
                return chosen
            else:
                chosen = [hero1]
                self.log.info(f"⚔️ بطل واحد متاح من التشكيلة: {chosen}")
                return chosen

        self.log.debug(f"⚠️ أبطال التشكيلة ({fid_label}) مشغولون أو غير متاحين — اختيار أفضل أبطال الحرب تلقائياً...")
        chosen = _pick_combat_heroes(self._heroes, max_count=2, busy=self._busy_heroes)
        if len(chosen) == 2:
            self.log.info(f"⚔️ أبطال الحرب البدلاء المختارون (بطلان اثنان): {chosen}")
            return chosen
        elif len(chosen) == 1:
            self.log.info(f"⚔️ بطل حرب واحد متاح بالقلعة: {chosen}")
            return chosen
        else:
            any_cands = [int(h['id']) for h in self._heroes if isinstance(h, dict) and h.get('id') and int(h['id']) not in self._busy_heroes and h.get('status', {}).get('state', 0) == 0]
            if any_cands:
                chosen_any = any_cands[:2]
                self.log.info(f"⚠️ بديل اضطراري: تم اختيار أي أبطال متاحين بالقلعة ({len(chosen_any)}): {chosen_any}")
                return chosen_any

        self.log.warning("⚠️ لا يتوفر أي بطل شاغر بالقلعة نهائياً!")
        return []

    async def _resolve_army(self, form_army: Dict[str, int]) -> List[Dict[str, int]]:
        """
        تجهيز قوات المسيرة بمطابقة تشكيلة الجيش المتاحة بالقلعة من الذاكرة الحية (0ms).
        """
        available: Dict[int, int] = {}

        # 1. قراءة فورية من الذاكرة الحية (RAM)
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        total_army = army_ctrl.get('totalArmy', {}) if isinstance(army_ctrl, dict) else {}

        if isinstance(total_army, dict) and total_army:
            for k, v in total_army.items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)
        else:
            # 2. استعلام احتياطي فقط إذا لم تكن الذاكرة محملة
            try:
                self.log.debug("🛑🛑🛑🛑🛑🛑🛑 جاري استدعاء 1005/1 للجيش")
                r_army = await self.conn.query('1005', '1', {}, timeout=4)
                if r_army and 'data' in r_army:
                    for k, v in r_army['data'].get('totalArmy', {}).items():
                        if str(k).isdigit() and str(v).isdigit():
                            available[int(k)] = int(v)
            except Exception as e:
                self.log.debug(f"خطأ أثناء استعلام 1005/1 للجيش: {e}")

        march_army = []
        target_army = form_army or self._template_army
        if not target_army:
            self.log.warning(f"⚠️ التشكيلة المحددة ({self.formation_id}) فارغة ولا تحتوي على جنود محفوظين بالقلعة!")
            return []

        # استبعاد فخاخ الجدار وأسلحة الدفاع (800..899)
        clean_target = {
            int(k): int(v) for k, v in target_army.items()
            if int(v) > 0 and not (800 <= int(k) < 900)
        }
        if not clean_target:
            self.log.warning(f"⚠️ لا توجد قوات صالحة في التشكيلة المحددة ({self.formation_id})!")
            return []

        # ضبط القوات بنسب متوازنة مع سعة مسيرة اللورد لمنع تجاوز السعة وتجنب خطأ السيرفر 8035
        total_req = sum(clean_target.values())
        max_troops = getattr(self, "max_march_troops", 200000) or 200000
        scale = 1.0
        if total_req > max_troops:
            scale = max_troops / float(total_req)

        expected_march_troops = min(total_req, max_troops)
        min_required_troops = int(expected_march_troops * 0.70)

        for tid, req_cnt in clean_target.items():
            avail = available.get(tid, 0)
            scaled_req = max(1, int(req_cnt * scale)) if scale < 1.0 else req_cnt
            take = min(scaled_req, avail)
            if take > 0:
                march_army.append({"id": tid, "num": take})
                available[tid] -= take

        total_march = sum(x["num"] for x in march_army)
        # التحقق من شرط قوة التشكيلة (70% كحد أدنى إلزامي لمنع إرسال فيالق ضعيفة)
        if total_march < min_required_troops:
            self.log.warning(
                f"🛑 [قوة التشكيلة غير كافية] القوات المتاحة بالقلعة من جنود التشكيلة ({self.formation_id}) "
                f"غير كافية ({total_march:,} جندي) — أقل من 70% من قوة التشكيلة ({min_required_troops:,} من أصل {expected_march_troops:,}). "
                f"التوقف الآمن والانتظار لعودة الفيالق النشطة."
            )
            return []

        self.log.debug(
            f"🛡️ تم تجهيز القوات ({total_march / expected_march_troops * 100:.1f}% من التشكيلة {self.formation_id}): "
            f"إجمالي {total_march:,} جندي عبر {len(march_army)} فئة قتالية."
        )
        return march_army

    async def _get_queue_id(self) -> str:
        """جلب معرف الطابور من الذاكرة الحية دون استعلام شبكي (0ms)."""
        queues = self._read_live_local_queues(self.conn)
        for q in queues:
            if isinstance(q, dict):
                qid = q.get('queueId') or q.get('id')
                if qid:
                    return str(qid)

        # 2. استعلام احتياطي فقط إذا لم تتوفر بالذاكرة
        try:
            self.log.debug("🛑🛑🛑🛑🛑🛑🛑 جاري استدعاء 1007/16 للطوابير")
            resp = await self.conn.query('1007', '16', {}, timeout=4)
            if resp and 'data' in resp:
                queues = resp['data']
                if isinstance(queues, list):
                    for q in queues:
                        if isinstance(q, dict):
                            qid = q.get('queueId') or q.get('id')
                            if qid:
                                return str(qid)
                elif isinstance(queues, dict):
                    for qid in queues.keys():
                        return str(qid)
        except Exception:
            pass

        return f"{self.uid}-1"

    async def _send_elf_attack(
        self,
        bx: int,
        by: int,
        boss_type: int = 10,
        boss_instance_type: int = 24,
        target_map_id: Optional[str] = None,
        legion_idx: int = 1
    ) -> Tuple[bool, str]:
        """
        تجهيز وإرسال حزمة الهجوم على نخبة العفريت (1007/2) للفيلق المحدد.
        """
        # 1. تثبيت الاعتماد 100% على التشكيلة المحددة لجميع الفيالق
        target_fid = self.formation_id
        self.log.info(f"{target_fid} 🥰🥰🥰🥰🥰")

        # 2. جلب بيانات التشكيلة
        form_heroes, form_pets, form_runes, form_army = await self._load_formation(target_fid)
        self.log.info(f"{form_heroes} 🚴🏻‍♀️🚴🏻‍♀️🚴🏻‍♀️🚴🏻‍♀️")
        self.log.info(f"{form_pets} 🐴🐴🐴🐴🐴")
        self.log.info(f"{form_runes} 🥰🥰🥰🥰🥰")
        self.log.info(f"{form_army} 👨🏻👩🏻👩🏻👨🏻👨🏻👨🏻")

        # حفظ قوالب التشكيلة للاستخدام في الفيالق اللاحقة إذا كانت التشكيلات الأخرى فارغة
        if form_army and not self._template_army:
            self._template_army = dict(form_army)
        if form_pets and not self._template_pets:
            self._template_pets = list(form_pets)
        if form_runes and not self._template_runes:
            self._template_runes = list(form_runes)

        # 3. تحديد الأبطال
        if not self._heroes:
            await self._load_heroes()
        avail_heroes_before = [int(h['id']) for h in self._heroes if isinstance(h, dict) and h.get('id') and int(h['id']) not in self._busy_heroes and h.get('status', {}).get('state', 0) == 0]
        self.log.info(f"{avail_heroes_before} 🧝🏻‍♂️🧝🏻‍♂️🧝🏻‍♂️🧝🏻‍♂️🧝🏻‍♂️")
        chosen_heroes = self._resolve_combat_heroes(form_heroes, fid_label=f"تشكيلة {target_fid}")
        if not chosen_heroes:
            return False, "NO_HEROES"

        afasf = await self.get_available_troops()

        self.log.info(f"{afasf} 🧧🧧🧧🧧🧧🧧🧧🧧🧧🧧🧧")


        # 4. تحديد الجيش
        march_army = await self._resolve_army(form_army)
        self.log.info(f"{march_army} 👱🏻‍♀️👱🏻‍♀️👱🏻‍♀️👱🏻‍♀️")
        if not march_army:
            return False, "INSUFFICIENT_ARMY"

        total_troops = sum(a['num'] for a in march_army)

        # 5. تحديد الحيوان الأليف وصفحات الرون (فارغ إذا لم يكن محدداً بالتشكيلة لمنع خطأ 800001)
        pets_list = list(form_pets) if form_pets else (list(self._template_pets) if self._template_pets else [])
        runes_list = list(form_runes) if form_runes else (list(self._template_runes) if self._template_runes else [1])

        # 6. تحديد نوع الكائن ومعرف الموقع على الخريطة
        if not target_map_id:
            target_map_id = f"{bx}-{by}-{boss_instance_type}-0-{boss_type}"
        map_id = self._map_id or self._resolve_map_id()

        # إحداثيات بلاطة التثبيت على شبكة الخريطة (الزعيم يشغل 2x2 وبلاطة الإرسال هي الركن العلوي الأيسر bx-1, by-1)
        target_tile_x = bx - 1
        target_tile_y = by - 1

        payload = {
            "needSend": True,
            "mapId": map_id,
            "moveLineType": ELF_MOVE_LINE_TYPE,
            "data": {
                "data": {
                    "mainInstanceType": boss_instance_type,
                    "massTime": ELF_MASS_TIME
                },
                "to": {
                    "y": target_tile_y,
                    "x": target_tile_x,
                    "id": target_map_id,
                },
                "army": march_army
            },
            "needArmyList": {},
            "pets": pets_list,
            "runePages": runes_list,
            "matrixType": 1,
            "heros": chosen_heroes
        }

        # محاكاة التفاعل البشري الطبيعي والسريع (فتح الهدف واختيار التشكيلة وإطلاق المسيرة)
        human_prep = round(random.uniform(1.8, 3.2), 2)
        self.log.debug(f"⏳ تجهيز تفاصيل الفيلق {legion_idx} واختيار القوات ({human_prep} ثانية)...")
        await asyncio.sleep(human_prep)

        self.log.info(f"🚀 [العفريت] إرسال فيلق {legion_idx} نحو ({bx}, {by}) | جنود: {total_troops:,}")

        if not getattr(self.conn, 'is_connected', False):
            return False, "SOCKET_DISCONNECTED"

        resp = await self.conn.query('1007', '2', payload, timeout=8)
        if not resp:
            if not getattr(self.conn, 'is_connected', False):
                return False, "SOCKET_DISCONNECTED"
            return False, "انتهت مهلة استجابة السيرفر أثناء إرسال المسيرة"

        err = str(resp.get('err', '0'))
        if err == '0':
            for hid in chosen_heroes:
                self._busy_heroes.add(hid)
            self._targeted_bosses.add((bx, by))
            if target_map_id:
                self._targeted_boss_ids.add(target_map_id)

            avail_heroes_after = [int(h['id']) for h in self._heroes if isinstance(h, dict) and h.get('id') and int(h['id']) not in self._busy_heroes and h.get('status', {}).get('state', 0) == 0]
            self.log.info(f"{avail_heroes_after} 🏹🏹🏹🏹🏹")
                        # استخراج معرف المسيرة (queueId) فورياً من رد السيرفر المباشر أو الذاكرة الحية
            self.log.debug(f"🔍 رد 1007/2: {resp}")
            resp_data = resp.get('data') or resp.get('retData') or {}
            q_id = str(resp.get('queueId') or "")
            if not q_id and isinstance(resp_data, dict):
                q_obj = resp_data.get('queue') if isinstance(resp_data.get('queue'), dict) else {}
                q_id = str(q_obj.get('id') or resp_data.get('queueId') or resp_data.get('id') or
                           resp_data.get('queue_id') or resp_data.get('marchId') or "")

            # فحص فوري من طوابير الذاكرة الحية (RAM) دون طلبات شبكية
            if not q_id or q_id == "0":
                if getattr(self.conn, 'local_queues', None):
                    for item in self.conn.local_queues:
                        q_list = item.get('data', []) if isinstance(item, dict) else (item if isinstance(item, list) else [])
                        for q in q_list:
                            if isinstance(q, dict):
                                qid = q.get('queueId') or q.get('id')
                                if qid:
                                    q_id = str(qid)
                                    break
                        if q_id and q_id != "0":
                            break

            # استعلام احتياطي فقط إذا تعذر كلياً
            if not q_id or q_id == "0":
                try:
                    self.log.debug("🛑🛑🛑🛑🛑🛑🛑 جاري استدعاء 1007/16 لجلب معرف المسيرة")
                    r16 = await self.conn.query('1007', '16', {}, timeout=4)
                    if r16 and isinstance(r16.get('data'), list):
                        for q in r16['data']:
                            if isinstance(q, dict):
                                qid = q.get('queueId') or q.get('id')
                                if qid:
                                    q_id = str(qid)
                                    break
                except Exception as e:
                    self.log.debug(f"تعذر جلب queueId من 1007/16: {e}")

            if not q_id or q_id == "0":
                q_id = f"{self.uid}-1"
            self.log.debug(f"🆔 معرف مسيرة العفريت: {q_id}")

            return True, q_id


        elif err == '8002':
            self._targeted_bosses.add((bx, by))
            if target_map_id:
                self._targeted_boss_ids.add(target_map_id)
            self._remove_from_cached_pool(bx, by, target_map_id)
            return False, "8002: الهدف غير متاح أو تغيرت حالته/انتهى على الخريطة"
        elif err == '8026':
            self._targeted_bosses.add((bx, by))
            if target_map_id:
                self._targeted_boss_ids.add(target_map_id)
            self._remove_from_cached_pool(bx, by, target_map_id)
            return False, "8026: يوجد حشد جماعي نشط لك بالفعل ضد هذا العفريت حالياً"
        elif err == '800001':
            return False, "800001: الحيوان الأليف غير مفتوح بالحساب (Err_PET_UNLOCK_ERROR_DEBRIS_COUNT_NOTENOUGH)"
        elif err == '8035':
            self._targeted_bosses.add((bx, by))
            if target_map_id:
                self._targeted_boss_ids.add(target_map_id)
            self._remove_from_cached_pool(bx, by, target_map_id)
            return False, "8035: الهدف مشغول بمعركة أو حشد آخر حالياً وصل للحد الأقصى أو تغيرت حالته (Err_MAP_QUEUE_BATTLE_NUM_OUT)"
        elif err in ('8032', '10002', '10003'):
            return False, "STAMINA_EMPTY: طاقة اللورد غير كافية لإرسال الهجوم على العفريت (كود 8032)"
        elif err == '8009':
            return False, "NO_ARMY: نقص في القوات المتاحة بالقلعة (كود 8009)"
        elif err == '9007020':
            for hid in chosen_heroes:
                self._busy_heroes.add(hid)
            return False, f"HERO_BUSY: 9007020: أبطال التشكيلة {chosen_heroes} مشغولون حالياً في مسيرة أو حشد قائم"
        elif err in ('8004', '9007004'):
            return False, "QUEUE_FULL: طوابير المسيرات بالقلعة مكتملة بالكامل"
        elif err == '16001':
            return False, "CMD_OPTING: 16001: خادم اللعبة مشغول بعملية سابقة"
        else:
            # قاطع الدائرة الفوري: أي خطأ غير معروف يُعامل كخلل بالحساب/السيرفر دون افتراض أنه خطأ زعيم
            return False, f"CIRCUIT_BREAKER: خطأ سيرفر غير معروف ({err})"

    async def run(self) -> TaskResult:
        """
        تنفيذ جلسة الهجوم المستمر على نخبة العفريت بكافة الفيالق المتوفرة:
        - تستمر الجلسة لمدة يحددها المستدعي (افتراضياً: 40 دقيقة).
        - ترسل الفيالق المتاحة حتى امتلاء الطوابير، ثم تنتظر 3 دقائق (180 ثانية) لمعاودة الهجوم.
        - تقوم بتعطيل المهمة تلقائياً عبر disable_elf_task() عند نفاد طاقة اللورد أو انتهاء الحدث.
        """
        duration_minutes = float(self.config.get("duration", self.config.get("duration_minutes", 40)))
        deadline = time.time() + (duration_minutes * 60.0)
        boss_desc = "نخبة العفريت (فئة 10)" if self.boss_type == 10 else f"العفريت (فئة {self.boss_type})"
        self.log.info(f"👹 [العفريت] بدء استهداف نخبة العفريت فئة {self.boss_type} (مدة الجلسة: {duration_minutes:.0f} دقيقة)...")

        total_attacks = 0
        last_error = ""
        cycle_num = 0
        empty_map_attempts = 0

        # تحميل إحداثيات القلعة ومعرف الخريطة لمرة واحدة فقط
        await self._load_castle_coords()
        await self._load_map_id()

        while time.time() < deadline and not self.is_stopped():
            cycle_num += 1

            # 1. التحقق من حالة الفعالية في المملكة عبر الذاكرة الحية
            is_active, active_reason = await self.is_event_active()
            if not is_active:
                msg = f"⚠️ حدث العفريت غير نشط حالياً على السيرفر ({active_reason}) — تعطيل المهمة للقلعة."
                self.log.warning(msg)
                self.disable_elf_task()
                return TaskResult.fail(msg, error=active_reason, event_active=False, attacks=total_attacks)

            # 2. تحديث بيانات الأبطال والمشغولين قبل بدء دورة إرسال الفيالق
            await self._load_heroes()
            self._detect_busy_heroes()

            successful_attacks = 0
            consecutive_errors = 0
            cmd_opting_retries = 0
            attempt = 0
            max_attempts = self.attack_count * 3

            while successful_attacks < self.attack_count and attempt < max_attempts and time.time() < deadline and not self.is_stopped():
                attempt += 1
                current_legion = total_attacks + successful_attacks + 1
                self.log.debug(f"⚔️ تجهيز الفيلق رقم ({current_legion})...")

                available = await self.get_available_marches_count(allow_network=False)
                self.log.info(f"{available} ⚔️⚔️⚔️⚔️⚔️")
                if available <= 0:
                    self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل.")
                    break


                bx, by, btype, itype, tid, dist, status = await self._find_unique_elf_boss()

                if status != "OK" or bx is None or by is None or btype is None:
                    last_error = status
                    self.log.info(f"🏁 لا توجد نخبة عفريت متاحة حالياً على الخريطة ({status}).")
                    break

                empty_map_attempts = 0

                # إرسال الهجوم
                success, err_or_qid = await self._send_elf_attack(
                    bx, by,
                    boss_type=btype,
                    boss_instance_type=itype or 24,
                    target_map_id=tid,
                    legion_idx=current_legion
                )

                if success:
                    successful_attacks += 1
                    total_attacks += 1
                    consecutive_errors = 0
                    cmd_opting_retries = 0
                    march_queue_id = err_or_qid
                    self.log.debug(f"🎉 الفيلق ({total_attacks}) أُطلق بنجاح على نخبة العفريت عند ({bx}, {by}) [queueId={march_queue_id}]")
                    if successful_attacks < self.attack_count and time.time() < deadline:
                        safe_delay = round(random.uniform(8.0, 14.0), 2)
                        self.log.debug(f"🛡️ تم إرسال الفيلق بنجاح — انتظار {safe_delay:.1f} ثانية (فاصل أمان بشري) قبل تجهيز الفيلق التالي...")
                        await asyncio.sleep(safe_delay)
                else:
                    err_msg = err_or_qid
                    last_error = err_msg
                    consecutive_errors += 1
                    self.log.warning(f"⚠️ تعذر إرسال الفيلق {current_legion}: {err_msg}")

                    if "SOCKET_DISCONNECTED" in err_msg or not getattr(self.conn, 'is_connected', False):
                        self.log.warning("⚡ انقطع الاتصال بالسيرفر أثناء إرسال الفيلق.")
                        return TaskResult.fail("انقطاع الاتصال بالسيرفر", error="SOCKET_DISCONNECTED", attacks=total_attacks)

                    if "STAMINA_EMPTY" in err_msg or "8032" in err_msg:
                        self.log.info("🛑 نفدت طاقة اللورد — تعطيل مهمة العفريت للقلعة وإنهاء الجلسة.")
                        self.disable_elf_task()
                        return TaskResult.fail("🛑 نفدت طاقة اللورد وتم تعطيل مهمة العفريت للقلعة", error="STAMINA_EMPTY", attacks=total_attacks)

                    if "QUEUE_FULL" in err_msg:
                        self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل.")
                        break

                    if "NO_ARMY" in err_msg or "INSUFFICIENT_ARMY" in err_msg:
                        self.log.info("🛑 القوات المتاحة بالقلعة لا تكفي لتشكيل فيلق بقوة 70% من التشكيلة.")
                        break

                    if "HERO_BUSY" in err_msg or "HEROES_BUSY" in err_msg or "9007020" in err_msg:
                        # إذا كان البطل مشغولاً وتوجد أبطال قتال بديلة متاحة: تجربة البطل التالي فوراً (مطابق لمعيار monster.py و stronghold.py)
                        avail_combat_heroes = [
                            h for h in self._heroes
                            if isinstance(h, dict) and h.get('id') and int(h['id']) not in self._busy_heroes
                            and str(h.get('id', '')).startswith('5501')
                        ]
                        if avail_combat_heroes:
                            self.log.info(f"🔄 البطل السابق في مسيرة — تجربة بطل قتالي بديل فوراً ({len(avail_combat_heroes)} متاح بالقلعة)...")
                            continue
                        self.log.info("🛑 كافة أبطال الحرب بالقلعة في مسيرات نشطة حالياً.")
                        break

                    if "NO_HEROES" in err_msg:
                        self.log.info("🛑 لا يتوفر أبطال شاغرون بالقلعة حالياً.")
                        break

                    if "16001" in err_msg or "CMD_OPTING" in err_msg:
                        cmd_opting_retries += 1
                        if cmd_opting_retries <= 2:
                            wait_time = round(random.uniform(10.0, 16.0), 2)
                            self.log.warning(
                                f"⏳ [خادم اللعبة مشغول - كود 16001] انتظار {wait_time} ثانية لفك القفل "
                                f"ثم إعادة تجهيز الهجوم على العفريت نظيفاً من البداية (محاولة {cmd_opting_retries}/2)..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            self.log.warning("🏁 استمر انشغال خادم اللعبة (كود 16001) بعد المحاولات.")
                            break

                    if "8026" in err_msg or "8002" in err_msg or "8035" in err_msg:
                        max_retries = max(4, min(10, len(self._cached_boss_pool)))
                        if consecutive_errors >= max_retries:
                            self.log.warning(f"🛑 [قاطع الدائرة] استنفاد المحاولات البديلة للزعماء المتاحين ({consecutive_errors} محاولات | {err_msg}).")
                            break
                        retry_desc = "حشد مكرر" if "8026" in err_msg else ("زعيم انتهى" if "8002" in err_msg else "معركة ممتلئة")
                        self.log.warning(f"⚠️ ({retry_desc}) للهدف ({bx}, {by}) — تجربة هدف بديل من الكاش...")
                        retry_wait = round(random.uniform(2.0, 4.0), 2)
                        await asyncio.sleep(retry_wait)
                        continue

                    self.log.warning(f"🛑 [قاطع الدائرة الفوري] خطأ سيرفر ({err_msg}) — إيقاف الدورة.")
                    break

            # فحص انتهاء وقت الجلسة أو طلب الإيقاف
            remaining_seconds = deadline - time.time()
            if remaining_seconds <= 0 or self.is_stopped():
                break

            # التحقق هل التوقف سببه انشغال الفيالق بالخارج (امتلاء الطوابير أو انتظار عودة القوات والأبطال)
            active_marches = await self.get_active_marches_count(force_sync=False)
            avail_cap = await self.get_available_marches_count(force_sync=False, allow_network=False)
            waiting_for_legions = (avail_cap <= 0) or (active_marches > 0 and (
                "INSUFFICIENT_ARMY" in last_error or "NO_ARMY" in last_error or
                "NO_HEROES" in last_error or "HERO_BUSY" in last_error or
                "HEROES_BUSY" in last_error or "9007020" in last_error
            ))

            if waiting_for_legions:
                # 🔄 الانتظار الذكي لعودة أي فيلق شاغر لاستعادة الطوابير والقوات والأبطال
                if avail_cap <= 0:
                    wait_reason = "طوابير الفيالق ممتلئة بالكامل"
                elif "HERO_BUSY" in last_error or "HEROES_BUSY" in last_error or "9007020" in last_error or "NO_HEROES" in last_error:
                    wait_reason = "أبطال الحرب في مسيرات نشطة بالخارج بانتظار عودتهم"
                else:
                    wait_reason = "قوة الجيش غير مكتملة (<70%) بانتظار عودة الفيالق النشطة"
                self.log.info(f"⏳ {wait_reason} (يوجد {active_marches} فيلق بالخارج | المتبقي للجلسة: {int(remaining_seconds // 60)}د)...")
                queue_freed = False
                wait_start = time.time()
                max_queue_wait = min(remaining_seconds, 900.0)
                initial_active = active_marches

                while (time.time() - wait_start) < max_queue_wait and not self.is_stopped():
                    if not getattr(self.conn, 'is_connected', False):
                        return TaskResult.fail("انقطاع الاتصال أثناء انتظار الفيالق", error="SOCKET_DISCONNECTED", attacks=total_attacks)

                    # فحص فوري للطوابير والمسيرات النشطة من الذاكرة الحية (Zero-Request)
                    curr_active = await self.get_active_marches_count(force_sync=False)
                    curr_avail = await self.get_available_marches_count(force_sync=False, allow_network=False)

                    # إذا عاد فيلق إلى القلعة (انخفض عدد الفيالق بالخارج أو فُرغ طابور مسيرة)
                    if curr_active < initial_active or (avail_cap <= 0 and curr_avail > 0):
                        self.log.info(f"🐎 عاد فيلق إلى القلعة (المسيرات بالخارج الآن: {curr_active}) — استعادة القوات وانطلاق فوري لمهاجمة العفريت!")
                        queue_freed = True
                        break

                    # نبضة نوم سريعة 1 ثانية، مع استجابة فورية كل 0.25 ثانية لزر الإيقاف
                    slept = 0.0
                    while slept < 1.0:
                        if self.is_stopped():
                            break
                        await asyncio.sleep(0.25)
                        slept += 0.25

                    if self.is_stopped():
                        break

                if not queue_freed and not self.is_stopped() and getattr(self.conn, 'is_connected', False):
                    # مزامنة احتياطية إذا طال الانتظار للتأكد من حالة الطوابير
                    try:
                        await self.get_available_marches_count(force_sync=True, allow_network=True)
                    except Exception:
                        pass

                    synced_active = await self.get_active_marches_count(force_sync=False)
                    synced_avail = await self.get_available_marches_count(force_sync=False, allow_network=False)
                    if synced_active >= initial_active and (avail_cap <= 0 and synced_avail <= 0 or avail_cap > 0):
                        self.log.warning(
                            "⏳ استمرت الفيالق بالخارج بعد 15 دقيقة والمزامنة الاحتياطية (1007/1000) — "
                            "إنهاء الجلسة فوراً والانتظار حتى رأس الساعة (:00)."
                        )
                        break

                if queue_freed:
                    self._busy_heroes.clear()
                    await self._load_heroes()
                    avail_heroes_freed = [int(h['id']) for h in self._heroes if isinstance(h, dict) and h.get('id') and int(h['id']) not in self._busy_heroes and h.get('status', {}).get('state', 0) == 0]
                    self.log.info(f"{avail_heroes_freed} 🏰🏰🏰🏰🏰")
                    continue
            elif "INSUFFICIENT_ARMY" in last_error or "NO_ARMY" in last_error:
                # لا توجد فيالق بالخارج، ومع ذلك قوات القلعة لا تبلغ 70% من التشكيلة
                self.log.warning(
                    f"🛑 لا توجد أي فيالق بالخارج وقوات القلعة لا تبلغ 70% من التشكيلة ({self.formation_id}) — "
                    "إنهاء الجلسة فوراً لحين تدريب قوات جديدة."
                )
                break
            else:
                # الطوابير شاغرة لكن لا توجد أهداف صالحة على الخريطة حالياً
                empty_map_attempts += 1
                if empty_map_attempts >= 2:
                    self.log.warning("🏁 تأكد خلو الخريطة من العفاريت بعد محاولتي بحث — إنهاء الجلسة فوراً والانتظار حتى رأس الساعة (:00).")
                    break

                wait_refresh = min(remaining_seconds, 60.0)
                self.log.info(f"⏳ لم يتم العثور على أي عفريت متاح (محاولة 1/2) — انتظار دقيقة كاملة ({int(wait_refresh)} ثانية) لإعادة البحث...")
                self._cached_boss_pool.clear()  # تفريغ الكاش لإعادة البحث بالخريطة
                slept = 0.0
                while slept < wait_refresh:
                    if self.is_stopped():
                        break
                    await asyncio.sleep(0.25)
                    slept += 0.25

        # إرجاع النتيجة النهائية للجلسة
        if total_attacks > 0:
            msg = f"✅ تم تنفيذ جلسة الهجوم على {boss_desc} بنجاح (إجمالي الفيالق المرسلة: {total_attacks})."
            return TaskResult.ok(msg, attacks=total_attacks, status="success", boss_type=self.boss_type)
        else:
            msg = f"⚠️ لم يتم إرسال أي فيلق ضد {boss_desc} خلال الجلسة (السبب: {last_error or 'انتهاء الوقت'})."
            return TaskResult.fail(msg, error=last_error, attacks=0, boss_type=self.boss_type)

# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone CLI)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(description="Elf Boss Attack Task — مهمة الهجوم على نخبة العفريت بكل الفيالق المتوفرة")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--formation", "-f", type=int, default=DEFAULT_FORMATION_ID, help="رقم التشكيلة الأساسية (1..6) [افتراضي: 1]")
    parser.add_argument("--boss-type", "-b", type=int, default=DEFAULT_BOSS_TYPE, choices=[10, 9], help="نوع العفريت: 10 = نخبة العفريت (الافتراضي)، 9 = العفريت العادي [افتراضي: 10]")
    parser.add_argument("--max-distance", "-d", type=float, default=None, help="أقصى مسافة مسموحة للعفريت بالكيلومتر [افتراضي: بدون حد]")
    parser.add_argument("--count", "-c", type=int, default=None, help="عدد الفيالق المستهدفة [افتراضي: كل الفيالق المتوفرة بالقلعة]")
    parser.add_argument("--all-legions", "-a", action="store_true", default=True, help="الهجوم بكل الفيالق المتوفرة حتى امتلاء الطوابير [افتراضي: مفعل]")
    parser.add_argument("--delay", "--attack-delay", type=float, default=DEFAULT_ATTACK_DELAY, help=f"فترة الأمان الأساسية بالثواني بين كل هجوم والآخر [افتراضي: {DEFAULT_ATTACK_DELAY}]")
    parser.add_argument("--loop", "-l", action="store_true", help="تكرار المهمة باستمرار وانتظار انتهاء الحشود أو ظهور عفاريت جديدة")
    parser.add_argument("--interval", type=int, default=60, help="فترة الانتظار بالثواني بين دورات الفحص عند تفعيل --loop [افتراضي: 60]")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

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

        for _ in range(15):
            await asyncio.sleep(0.3)
            if "cityCtrl" in conn.init_data:
                break
        await asyncio.sleep(0.5)

        task_cfg = {
            "formation_id": args.formation,
            "boss_type": args.boss_type,
            "max_distance": args.max_distance,
            "count": args.count,
            "all_legions": args.count is None or args.all_legions,
            "delay": args.delay,
        }

        task = ElfBossTask(conn, task_cfg)
        await task.on_start()

        round_num = 1
        while True:
            if args.loop:
                print(f"\n🔄 [دورة رقم {round_num}] بدء فحص وهجوم نخبة العفريت...")
            result = await task.run()
            print(f"\n📊 النتيجة: {result.message} | تفاصيل: {result.data}")

            if not args.loop:
                break

            round_num += 1
            print(f"⏳ انتظار {args.interval} ثانية قبل دورة الفحص التالية...")
            await asyncio.sleep(args.interval)

            # إعادة فحص جاهزية القلعة وتفريغ المشغولين المنتهين
            task._busy_heroes.clear()
            task._targeted_bosses.clear()
            task._targeted_boss_ids.clear()
            await task._load_heroes()
            task._detect_busy_heroes()

        await conn.close()

    asyncio.run(_main())

