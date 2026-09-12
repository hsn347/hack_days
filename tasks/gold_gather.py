# -*- coding: utf-8 -*-
"""
tasks/gold_gather.py — مهمة جمع الذهب وموارد التحالف الذكية والشاملة
═════════════════════════════════════════════════════════════════════════════

الاستخدام الشامل (يعتمد على رمز التحالف وإحداثيات قيادة التحالف المستهدف):

  1. فحص واكتشاف حقول الذهب المتاحة فقط دون إرسال مسيرات:
     python tasks/gold_gather.py --email "burcudemr@gmail.com" --tag "POL" -x 241 -y 260 --check-only

  2. إرسال مسيرات جمع للذهب التابع لتحالف POL حول مركزه (241, 260):
     python tasks/gold_gather.py --email "burcudemr@gmail.com" --tag "POL" -x 241 -y 260 --marches 1

  3. دعم اختصار الإحداثيات --coords "241,260":
     python tasks/gold_gather.py --email "burcudemr@gmail.com" --tag "POL" --coords "241,260" --marches 4


   python tasks/gold_gather.py --email "hmzawyha44@gmail.com" --tag "A22" -x 347 -y 244
  

🚩 آلية العمل الذكية:
  1. التحقق الميداني من مبنى قيادة التحالف عند (x, y) عبر 1006/136.
  2. مسح موارد الذهب المتاحة حول المركز عبر 2011/3 بنطاق دائري قابل للتعديل.
  3. فحص كل حقل عبر 1006/22 والتأكد أنه:
     - يقع فعلياً داخل أراضي التحالف المستهدف (مطابقة رمز التحالف في terr).
     - غير مشغول من قبل أي لاعب آخر (currentCollectNum == 0).
     - يحتوي على رصيد موارد متبقي (remainSourceNum > 0).
  4. ترتيب الحقول تصاعدياً حسب المسافة من مركز التحالف (الأقرب للقيادة أولاً).
  5. اختيار أبطال الجمع تلقائياً (أولوية لأبطال الجمع ومهارات الجمع 5620).
  6. تشكيل الجيش آلياً (عربات النقل 701..714 أولاً لتعظيم الحمولة).
  7. إرسال المسيرة بحزمة 1007/2 مع مراعاة فترات الأمان لمكافحة الحظر.
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
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# ── ملف تاريخ الاستبعاد المشترك عبر الحسابات والجلسات ──────────────
SHARED_HISTORY_FILE = os.path.join(_ROOT_DIR, "shared_gather_history.json")
SHARED_HISTORY_TTL  = 45 * 60  # صلاحية حجز الهدف: 45 دقيقة (مدة الذهاب والجمع والعودة)


# ════════════════════════════════════════════════════════════════════
#  إعدادات وثوابت الموارد
# ════════════════════════════════════════════════════════════════════

SUBTYPE_GOLD          = 1      # مناجم الذهب في أراضي التحالف (كود الخريطة: 1 ثابت)
SUBTYPE_MITHRIL       = 1      # مناجم الميثريل / ذهب السماء (Sky Gold) (كود الخريطة: 1)

DEFAULT_MIN_LV        = 1      # أدنى مستوى لحقل المورد
DEFAULT_MAX_LV        = 7      # أقصى مستوى لحقل المورد
DEFAULT_MAX_MARCHES   = 0      # 0 = إرسال بجميع الفيالق المتاحة بالقلعة حتى امتلاء الطوابير
DEFAULT_SEARCH_RANGE  = 65     # نطاق البحث الدائري حول مركز التحالف
DEFAULT_MIN_RESOURCES = 15     # الحد الأدنى من الرصيد المتبقي بالمنجم لتجنب المناجم المستهلكة
DEFAULT_MIN_RES_RATIO = 0.70   # نسبة الموارد المتبقية من إجمالي المنجم (70% فما فوق لقبول الحقل)


# ════════════════════════════════════════════════════════════════════
#  إدارة تاريخ الاستبعاد المشترك والذكي
# ════════════════════════════════════════════════════════════════════

def get_active_shared_history(ttl: int = SHARED_HISTORY_TTL) -> Tuple[Dict[str, dict], Set[Tuple[int, int]]]:
    """
    قراءة سجل الأهداف المشترك بين كافة الحسابات، وتنظيف الأهداف المنتهية بعد 45 دقيقة تلقائياً.
    يعيد (قاموس المعرفات النشطة, مجموعة الإحداثيات النشطة).
    """
    now = time.time()
    active_targets: Dict[str, dict] = {}
    active_coords: Set[Tuple[int, int]] = set()

    if not os.path.exists(SHARED_HISTORY_FILE):
        return active_targets, active_coords

    try:
        with open(SHARED_HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return active_targets, active_coords

        cleaned = {}
        for target_id, info in data.items():
            if not isinstance(info, dict):
                continue
            ts = float(info.get('time', 0))
            if (now - ts) < ttl:
                cleaned[target_id] = info
                active_targets[str(target_id)] = info
                tx, ty = info.get('x'), info.get('y')
                if tx is not None and ty is not None:
                    try:
                        active_coords.add((int(tx), int(ty)))
                    except Exception:
                        pass

        # إعادة حفظ النسخة المُنظَّفة إذا حُذفت سجلات قديمة
        if len(cleaned) != len(data):
            try:
                with open(SHARED_HISTORY_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cleaned, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
    except Exception:
        pass

    return active_targets, active_coords


def record_shared_target(target_id: str, x: int, y: int, email: str = "", uid: Any = "", tag: str = ""):
    """تسجيل منجم تم إرسال مسيرة إليه لحظياً ليتم استبعاده عبر كافة الحسابات"""
    now = time.time()
    time_str = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S")

    data = {}
    if os.path.exists(SHARED_HISTORY_FILE):
        try:
            with open(SHARED_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}

    data[str(target_id)] = {
        "id": str(target_id),
        "x": int(x),
        "y": int(y),
        "time": now,
        "time_str": time_str,
        "email": str(email),
        "uid": str(uid),
        "tag": str(tag)
    }

    try:
        with open(SHARED_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def generate_covering_centers(points: List[Tuple[float, float]], radius: float = 25.0) -> List[Tuple[int, int]]:
    """توليد مراكز بحث تغطي كافة النقاط والرايات بدقة بنطاق محدد"""
    uncovered = set(points)
    centers = []
    while uncovered:
        best_cand = None
        best_covered = set()
        for cand in uncovered:
            cov = {p for p in uncovered if max(abs(p[0] - cand[0]), abs(p[1] - cand[1])) <= radius}
            if len(cov) > len(best_covered):
                best_covered = cov
                best_cand = cand
        if not best_cand:
            break
        centers.append((int(round(best_cand[0])), int(round(best_cand[1]))))
        uncovered -= best_covered
    return centers


def check_territory_inclusion(
    mx: float, my: float,
    hq: Optional[Tuple[float, float]],
    flags: List[Tuple[float, float]],
    hq_radius: float = 5.0,
    flag_radius: float = 2.5
) -> Tuple[bool, Optional[str], float]:
    """
    التحقق من وقوع الإحداثي (mx, my) ضمن حدود التحالف:
    - قلعة القيادة: مسافة 5 كيلو حول المبنى من كل الجهات
    - الرايات: مسافة 2.5 كيلو حول الراية من كل الجهات
    """
    if hq is not None:
        hx, hy = hq
        dx = abs(mx - hx)
        dy = abs(my - hy)
        if dx <= hq_radius and dy <= hq_radius:
            dist = math.hypot(dx, dy)
            return True, f"🏰 قلعة القيادة ({hx}, {hy})", dist

    best_flag = None
    min_dist = 999.0
    for fx, fy in flags:
        dx = abs(mx - fx)
        dy = abs(my - fy)
        if dx <= flag_radius and dy <= flag_radius:
            dist = math.hypot(dx, dy)
            if dist < min_dist:
                min_dist = dist
                best_flag = (fx, fy)

    if best_flag is not None:
        return True, f"🚩 راية ({best_flag[0]}, {best_flag[1]})", min_dist

    return False, None, 999.0


# ════════════════════════════════════════════════════════════════════
#  اختيار أبطال الجمع
# ════════════════════════════════════════════════════════════════════

def _pick_gather_heroes(heroes: list, max_count: int = 1, busy: Set[int] = None) -> List[int]:
    """
    يختار أفضل بطل جمع وفق 3 مستويات أولوية:
    1. بطل 5502 + مهارة 5620 (أعلى كفاءة جمع)
    2. بطل 5502 بدون مهارة 5620
    3. أي بطل متاح في القلعة (احتياطي)
    """
    busy = busy or set()
    t1, t2, t3 = [], [], []

    for hero in heroes:
        if not isinstance(hero, dict):
            continue
        hid = hero.get('id')
        if not hid or hid in busy:
            continue
        if hero.get('status', {}).get('state', 0) != 0:
            continue

        skills = hero.get('skillList', {})
        has5620 = isinstance(skills, dict) and any(
            str(s.get('id', '')).startswith('5620')
            for s in skills.values() if isinstance(s, dict)
        )

        if str(hid).startswith('5502'):
            (t1 if has5620 else t2).append(int(hid))
        else:
            t3.append(int(hid))

    pool = t1 or t2 or t3
    return pool[:max_count] if max_count else pool


# ════════════════════════════════════════════════════════════════════
#  اختيار تشكيلة الجيش التلقائي (عربات النقل أولاً)
# ════════════════════════════════════════════════════════════════════

def select_gathering_army(available: Dict[int, int], needed_count: int = 25000) -> List[Dict[str, int]]:
    """
    أولوية اختيار الجيش:
    1. عربات النقل (701..714) لتعظيم حمولة الموارد وتقليل استهلاك الجنود
    2. مشاة (400..499)
    3. فرسان (500..599)
    4. رماة (600..699)
    ملاحظة هامة: يُمنع بتاتاً تضمين أسلحة الدفاع وفخاخ الجدار (800 فما فوق) لأن إرسالها يسبب خطأ 8062 من السيرفر.
    """
    carts    = []
    infantry = []
    cavalry  = []
    archers  = []

    for tid, count in available.items():
        if count <= 0:
            continue
        if 700 <= tid < 800:
            carts.append((tid, count))
        elif 400 <= tid < 500:
            infantry.append((tid, count))
        elif 500 <= tid < 600:
            cavalry.append((tid, count))
        elif 600 <= tid < 700:
            archers.append((tid, count))

    carts.sort(key=lambda x: x[0], reverse=True)
    infantry.sort(key=lambda x: x[0], reverse=True)
    cavalry.sort(key=lambda x: x[0], reverse=True)
    archers.sort(key=lambda x: x[0], reverse=True)

    army_list = []
    remaining = needed_count

    for group in [carts, infantry, cavalry, archers]:
        for tid, count in group:
            avail = available.get(tid, 0)
            if avail <= 0:
                continue
            take = min(avail, remaining)
            if take > 0:
                army_list.append({"id": tid, "num": take})
                available[tid] -= take
                remaining -= take
                if remaining <= 0:
                    break
        if remaining <= 0:
            break

    return army_list


# ════════════════════════════════════════════════════════════════════
#  اختيار الحيوان الأليف
# ════════════════════════════════════════════════════════════════════

def select_gathering_pet(conn: GameConnection, used_pets: Set[int]) -> List[int]:
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
#  مهمة جمع موارد التحالف (GoldGatherTask)
# ════════════════════════════════════════════════════════════════════

class GoldGatherTask(BaseTask):
    """
    مهمة جمع الذهب في أراضي التحالف المستهدف.
    تعتمد على رمز التحالف المستهدف (--tag) وإحداثيات قيادة التحالف (--center-x, --center-y).
    """
    name = "gold_gather"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self.alliance_tag       : str    = ""
        self.flags              : List[Tuple[float, float]] = []
        self.flags_file         : str    = ""
        self._heroes            : list   = []
        self._busy              : Set[int] = set()
        self._used_army         : Dict[int, int] = {}
        self._used_pets         : Set[int] = set()
        self._exclude           : Set[str] = set()
        self._my_active_queues  : list   = []
        self.kingdom_id         : int    = 0
        self.min_res            : int    = DEFAULT_MIN_RESOURCES
        self.min_ratio          : float  = DEFAULT_MIN_RES_RATIO

    def _capture_local_queues(self, cmd, sub, packet):
        if isinstance(packet, dict):
            data = packet.get('data', {})
            if isinstance(data, dict) and data.get('notifyID') == 'NOTIFY_LOCAL_QUEUE_SYNC':
                nd = data.get('notifyData', [])
                if isinstance(nd, list):
                    self._my_active_queues = nd

    async def on_start(self):
        """تهيئة الاتصال وتحميل بيانات الأبطال والمسيرات وتثبيت معرف المملكة"""
        self.conn.add_packet_listener(self._capture_local_queues)
        for _ in range(25):
            if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
                break
            if self.conn.init_data and 'heroCtrl' in self.conn.init_data:
                break
            await asyncio.sleep(0.5)
        await self._load_heroes()

        # تثبيت معرف المملكة (kingdom_id / partition) مسبقاً لاستعلامات 1006/1000
        if self.conn.kingdom_id:
            try:
                self.kingdom_id = int(self.conn.kingdom_id)
            except Exception:
                pass
        if not self.kingdom_id:
            uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
            try:
                r_map = await self.conn.query('1002', '7', {"uid": uid_int}, timeout=4)
                if r_map and 'data' in r_map:
                    self.kingdom_id = int(r_map['data'].get('base', {}).get('partition', 0))
            except Exception:
                pass

    def _get_my_active_targets(self) -> Tuple[Set[str], Set[Tuple[int, int]]]:
        """استخراج أهداف وإحداثيات كافة المسيرات النشطة الخاصة بقلعتنا لمنع استهدافها مجدداً"""
        target_ids: Set[str] = set()
        target_coords: Set[Tuple[int, int]] = set()

        all_queue_data = []
        if getattr(self, '_my_active_queues', None):
            all_queue_data.extend(self._my_active_queues)
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
            q_list = item.get('data', []) if isinstance(item, dict) else (item if isinstance(item, list) else [])
            for q in q_list:
                if not isinstance(q, dict):
                    continue
                # status: 1 = متجه للهدف, 2 = يجمع حالياً بالهدف
                if q.get('status') in (1, 2):
                    to_info = q.get('to', {})
                    if isinstance(to_info, dict):
                        tid = to_info.get('id') or to_info.get('mapObjId')
                        if tid:
                            target_ids.add(str(tid))
                        tx, ty = to_info.get('x'), to_info.get('y')
                        if tx is not None and ty is not None:
                            try:
                                target_coords.add((int(tx), int(ty)))
                            except Exception:
                                pass

                    # حفظ الأبطال المشغولين في المسيرة لتجنب اختيارهم
                    h_list = q.get('heros') or q.get('data', {}).get('heros') or []
                    if isinstance(h_list, list):
                        for h in h_list:
                            hid = h if isinstance(h, int) else (h.get('id') if isinstance(h, dict) else None)
                            if hid:
                                self._busy.add(int(hid))

        return target_ids, target_coords

    async def _load_heroes(self):
        """تحميل قائمة الأبطال عبر init_data أو heroCtrl أو 3080/2"""
        self._heroes = []
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
            self._heroes = list(self.conn._gate.heroes)
            if self._heroes:
                self.log.info(f"📋 تم تحميل {len(self._heroes)} بطل من init_data")
                return

        hctrl = self.conn.init_data.get('heroCtrl')
        if isinstance(hctrl, list) and hctrl:
            self._heroes = list(hctrl)
            self.log.info(f"📋 تم تحميل {len(self._heroes)} بطل من heroCtrl (قائمة)")
            return
        elif isinstance(hctrl, dict) and hctrl:
            hlist = hctrl.get('heroList', hctrl)
            if isinstance(hlist, dict):
                self._heroes = list(hlist.values())
            elif isinstance(hlist, list):
                self._heroes = list(hlist)
            if self._heroes:
                self.log.info(f"📋 تم تحميل {len(self._heroes)} بطل من heroCtrl (قاموس)")
                return

        # محاولة طلب الأبطال الاحتياطية عبر 3080/2
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

        if self._heroes:
            self.log.info(f"📋 تم العثور على {len(self._heroes)} بطل عبر 3080/2")
        else:
            self.log.warning("⚠️ لم يتم العثور على أبطال بعد — سيتم الاستعلام عند أول مسيرة")

    # ── فحص مركز التحالف ──────────────────────────────────────────

    async def _verify_alliance_center(self, cx: int, cy: int, alliance_tag: str) -> bool:
        """فحص مبنى مركز/قيادة التحالف أو نقطة الارتكاز الجغرافية عبر 1006/136"""
        kid = int(self.conn.kingdom_id) if self.conn.kingdom_id else 0
        try:
            r136 = await self.conn.query('1006', '136', {"x": cx, "y": cy, "kingdomId": kid}, timeout=4)
            ret = r136.get('retData') if (r136 and isinstance(r136, dict)) else None
            if ret:
                name = ret.get('allianceName')
                abbr = ret.get('allianceAbbr')
                aid  = ret.get('aid')
                mtype = ret.get('mapType')

                # إذا كانت الإحداثيات لمبنى تحالف فعلي (معقل أو مقر)
                if abbr or name:
                    self.log.info(f"🏛️ مبنى قيادة التحالف عند ({cx}, {cy}): [{abbr}] {name} (AID: {aid})")
                    if alliance_tag.upper() in str(abbr).upper():
                        self.log.info(f"✅ تطابق مؤكد مع التحالف المستهدف [{alliance_tag}]!")
                        return True
                    else:
                        self.log.warning(f"⚠️ اختصار المبنى [{abbr}] يختلف عن المطلوب [{alliance_tag}]، سيتم البحث عن حقول تابعة لـ [{alliance_tag}]")
                        return True
                else:
                    # الإحداثيات هي نقطة ارتكاز جغرافية لوسط أراضي التحالف وليست مبنى المعقل نفسه
                    self.log.info(f"📍 نقطة الارتكاز عند ({cx}, {cy}) — جاري مسح حقول أراضي [{alliance_tag}] في محيطها")
                    return True
        except Exception as e:
            self.log.info(f"📍 نقطة الارتكاز عند ({cx}, {cy}) — جاري مسح حقول أراضي [{alliance_tag}] في محيطها")
        return True

    # ── استخراج رموز التحالف من terr ──────────────────────────────

    @staticmethod
    def _extract_tags(terr_data: Any, direct_tag: Any = None) -> List[str]:
        tags = []
        if isinstance(terr_data, list):
            for item in terr_data:
                if isinstance(item, dict):
                    t = item.get('leagueAbbrName') or item.get('leagueName') or item.get('abbr')
                    if t:
                        tags.append(str(t).strip().upper())
        elif isinstance(terr_data, dict) and terr_data:
            t = terr_data.get('leagueAbbrName') or terr_data.get('leagueName') or terr_data.get('abbr')
            if t:
                tags.append(str(t).strip().upper())

        if direct_tag:
            tags.append(str(direct_tag).strip().upper())

        return list(dict.fromkeys(tags))

    # ── البحث الذكي عن حقول الذهب ─────────────────────────────────

    async def _find_target_mines(
        self,
        cx: int,
        cy: int,
        alliance_tag: str,
        subtype_mode: Any,
        min_lv: int,
        max_lv: int,
        search_range: int,
        min_dist: float = 0.0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        يبحث عن حقول الذهب المتاحة داخل حدود التحالف المستهدف.
        يدعم الاكتشاف التلقائي لنمط المورد (subtype 5 أو 1).
        """
        exclude_map = {str(ex_id): True for ex_id in self._exclude}

        subtypes_to_try = []
        if str(subtype_mode).lower() in ("auto", "0", ""):
            subtypes_to_try = [SUBTYPE_GOLD, SUBTYPE_MITHRIL]
        else:
            try:
                st = int(subtype_mode)
                subtypes_to_try = [st]
            except Exception:
                subtypes_to_try = [SUBTYPE_GOLD]

        subtypes_to_try = list(dict.fromkeys(subtypes_to_try))
        best_mines: List[Dict[str, Any]] = []
        matched_subtype: int = SUBTYPE_GOLD

        for st in subtypes_to_try:
            st_name = "🪙 ذهب التحالف (Gold)" if st == SUBTYPE_GOLD else "🔮 ميثريل/ذهب السماء (Sky Gold)"

            all_candidates = []
            seen_ids = set()

            if self.flags:
                # نمط المسح المتقدم عبر كامل رايات وحدود التحالف (مثل scan_alliance_gold.py)
                all_targets = list(self.flags)
                if cx is not None and cy is not None:
                    all_targets.append((float(cx), float(cy)))
                search_centers = generate_covering_centers(all_targets, radius=25.0)
                self.log.info(
                    f"🎯 نمط حدود التحالف نشط: جاري مسح {len(search_centers)} مركزاً استراتيجياً "
                    f"لتغطية {len(self.flags)} راية ومقر القيادة بالكامل لـ {st_name}..."
                )
                for scx, scy in search_centers:
                    r_search = await self.conn.query('2011', '3', {
                        "mapType": 5,
                        "subType": st,
                        "num": 60,
                        "x": scx,
                        "y": scy,
                        "minLv": min_lv,
                        "maxLv": max_lv,
                        "range": 30,
                        "exclude": exclude_map
                    })
                    cands = r_search.get('result', []) if (r_search and isinstance(r_search, dict)) else []
                    for c in cands:
                        cid = str(c.get('id', ''))
                        if cid and cid not in seen_ids:
                            seen_ids.add(cid)
                            all_candidates.append(c)
                    await asyncio.sleep(0.1)
            else:
                # النمط الكلاسيكي حول المركز المحدد
                self.log.info(f"🔍 جاري مسح الخريطة لـ {st_name} (subType={st}) حول ({cx}, {cy}) بنطاق {search_range}...")
                r_search = await self.conn.query('2011', '3', {
                    "mapType": 5,
                    "subType": st,
                    "num": 100,
                    "x": int(cx),
                    "y": int(cy),
                    "minLv": min_lv,
                    "maxLv": max_lv,
                    "range": search_range,
                    "exclude": exclude_map
                })
                all_candidates = r_search.get('result', []) if (r_search and isinstance(r_search, dict)) else []

            candidates = all_candidates
            self.log.info(f"📡 عثرت أجهزة الاستشعار على {len(candidates)} حقل مرشح، جاري التحقق من ملكية الأراضي والنشاط...")

            my_target_ids, my_target_coords = self._get_my_active_targets()
            shared_targets, shared_coords = get_active_shared_history()

            for cand in candidates:
                cid = str(cand.get('id', ''))
                tx, ty = int(cand.get('x', 0)), int(cand.get('y', 0))

                # إذا كانت الرايات محملة، نتحقق هندسياً من الوقوع داخل حدود التحالف:
                # 5 كم حول القيادة، أو 2.5 كم حول أي راية
                if self.flags:
                    hq_pt = (float(cx), float(cy)) if (cx is not None and cy is not None) else None
                    is_in, bound_desc, b_dist = check_territory_inclusion(tx, ty, hq_pt, self.flags, hq_radius=5.0, flag_radius=2.5)
                    if not is_in:
                        self._exclude.add(cid)
                        continue

                # 1. تخطي الحقول المستبعدة أو التي تستهدفها قلعتنا بالفعل حالياً
                if cid in self._exclude or cid in exclude_map or cid in my_target_ids or (tx, ty) in my_target_coords:
                    self._exclude.add(cid)
                    continue

                # 2. تخطي الحقول التي أُرسلت إليها مسيرة مؤخراً من أي من حساباتنا (حماية الـ 45 دقيقة)
                if cid in shared_targets or (tx, ty) in shared_coords:
                    self._exclude.add(cid)
                    hist = shared_targets.get(cid, {})
                    acc_label = hist.get('email') or hist.get('uid') or 'حسابك'
                    elapsed_min = round((time.time() - float(hist.get('time', time.time()))) / 60, 1)
                    self.log.info(f"ℹ️ تخطي الحقل ({tx}, {ty}): تم إرسال مسيرة إليه مؤخراً من [{acc_label}] قبل {elapsed_min} دقيقة")
                    continue

                tlv    = cand.get('level', '?')
                dist   = round(((tx - cx) ** 2 + (ty - cy) ** 2) ** 0.5, 1)

                try:
                    r22 = await self.conn.query('1006', '22', {"x": tx, "y": ty, "id": str(cid)}, timeout=2.0)
                    ret22 = r22.get('retData', {}) if (r22 and isinstance(r22, dict)) else {}

                    tags = self._extract_tags(
                        ret22.get('terr'),
                        ret22.get('leagueAbbrName') or ret22.get('abbr') or ret22.get('leagueName')
                    )

                    is_our_tag = any(str(alliance_tag).strip().upper() in str(t).strip().upper() for t in tags)

                    # إذا لم تكن هناك رايات محملة، نلزم مطابقة الوسم من السيرفر
                    # أما إذا تم التحقق الهندسي وكان الوسم فارغاً بمحاذاة القيادة فيُقبل
                    if not is_our_tag and not self.flags:
                        self._exclude.add(cid)
                        continue

                    tag_label = ",".join(tags)

                    collect_num = int(ret22.get('currentCollectNum', 0))
                    collect_spd = float(ret22.get('collectSpeed', 0))
                    remain      = int(ret22.get('remainSourceNum', 0))
                    total_res   = int(ret22.get('totalSourceNum', 0))

                    # 1. التحقق من خلو الحقل من أي جامع حالي
                    if collect_num > 0 or collect_spd > 0:
                        self._exclude.add(cid)
                        continue

                    # 2. التحقق من وجود رصيد موارد صالح
                    if remain <= 0:
                        self._exclude.add(cid)
                        continue

                    # 3. حماية حاسمة: استبعاد المناجم المستهلكة أو التي تم الهجوم عليها مسبقاً وبقي فيها فتات
                    min_required = max(self.min_res, int(total_res * self.min_ratio)) if total_res > 0 else self.min_res
                    if remain < min_required:
                        self._exclude.add(cid)
                        self.log.info(
                            f"⚠️ تخطي الحقل ({tx}, {ty}) لفل={tlv}: الرصيد المتبقي ({remain:,}/{total_res:,}) "
                            f"أقل من المطلوب ({min_required:,}) — تم استهلاكه أو الهجوم عليه مسبقاً"
                        )
                        continue

                    best_mines.append({
                        "id": cid,
                        "x": tx,
                        "y": ty,
                        "lv": tlv,
                        "dist": dist,
                        "remain": remain,
                        "total": total_res,
                        "subtype": st,
                        "tags": tags,
                        "is_our_tag": is_our_tag,
                        "cand": cand
                    })
                except Exception:
                    continue

            if best_mines:
                matched_subtype = st
                break

        # ترتيب الحقول:
        # إذا كانت الرايات محملة: نفضل أعلى مستوى أولاً (لفل 5 ثم 4...)، ثم أعلى رصيد متبقي، ثم الأقرب
        if self.flags:
            best_mines.sort(key=lambda m: (
                0 if (min_dist <= 0 or m["dist"] >= min_dist) else 1,
                -int(m.get("lv", 0)),
                -int(m.get("remain", 0)),
                m["dist"]
            ))
        else:
            # الترتيب الكلاسيكي: الأقرب للمركز أولاً
            best_mines.sort(key=lambda m: (
                0 if (min_dist <= 0 or m["dist"] >= min_dist) else 1,
                m["dist"]
            ))
        return best_mines, matched_subtype

    # ── المهمة الرئيسية ───────────────────────────────────────────

    async def run(self) -> TaskResult:
        cfg = self.config
        alliance_tag  = str(cfg.get('alliance_tag') or "").strip().upper()
        self.alliance_tag = alliance_tag
        center_x      = cfg.get('center_x')
        center_y      = cfg.get('center_y')
        subtype_mode  = cfg.get('subtype', 'auto')
        min_lv        = int(cfg.get('min_lv', DEFAULT_MIN_LV))
        max_lv        = int(cfg.get('max_lv', DEFAULT_MAX_LV))
        search_range  = int(cfg.get('search_range', DEFAULT_SEARCH_RANGE))
        min_dist      = float(cfg.get('min_dist', 0.0))
        max_marches   = int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))
        check_only    = bool(cfg.get('check_only', False))
        troops_cfg    = cfg.get('troops_count')

        self.min_res   = int(cfg.get('min_res', DEFAULT_MIN_RESOURCES))
        self.min_ratio = float(cfg.get('min_ratio', DEFAULT_MIN_RES_RATIO))

        # استخراج الإحداثيات إذا أُدخلت كنص "x,y"
        if not center_x or not center_y:
            coords = cfg.get('coords')
            if coords and ',' in str(coords):
                parts = str(coords).split(',')
                center_x, center_y = int(parts[0].strip()), int(parts[1].strip())

        # محاولة تحميل رايات التحالف لتطبيق حدود التحالف الدقيقة
        flags_file = cfg.get('flags_file')
        if not flags_file:
            candidates = [
                f"flags_{alliance_tag}.json",
                f"flags_{alliance_tag.lower()}.json",
                "flags_181.json" if alliance_tag == "181" else None
            ]
            for cf in candidates:
                if cf and os.path.exists(cf):
                    flags_file = cf
                    break

        if flags_file and os.path.exists(flags_file):
            try:
                with open(flags_file, 'r', encoding='utf-8') as f:
                    f_data = json.load(f)
                raw_flags = f_data.get('flags', [])
                # تطبيق قاعدة التعديل: نقص 1 من x و y للحصول على الإحداثيات الحقيقية
                self.flags = [(fl['x'] - 1, fl['y'] - 1) for fl in raw_flags if 'x' in fl and 'y' in fl]
                self.flags_file = flags_file
                self.log.info(f"🚩 تم تحميل {len(self.flags)} راية لتحالف [{alliance_tag}] من {flags_file} وتطبيق قاعدة الإزاحة (-1)")
            except Exception as e:
                self.log.warning(f"⚠️ فشل قراءة ملف الرايات {flags_file}: {e}")

        if center_x is None or center_y is None:
            if not self.flags:
                self.log.error("❌ لم تُحدَّد إحداثيات مركز التحالف (--center-x, --center-y أو --coords) ولا توجد رايات محملة!")
                return TaskResult.fail("لم تُحدَّد إحداثيات مركز التحالف المستهدف")
            else:
                cx, cy = int(self.flags[0][0]), int(self.flags[0][1])
                self.log.info(f"ℹ️ لم يتم تحديد قلعة القيادة، سيتم الاعتماد على أول راية كمركز ارتكاز ({cx}, {cy})")
        else:
            cx, cy = int(center_x), int(center_y)

        self.log.info(
            f"🪙 بدء مهمة جمع الذهب | تحالف=[{alliance_tag}] | مركز=({cx}, {cy}) | "
            f"نطاق={search_range} (أدنى مسافة={min_dist}) | لفل={min_lv}-{max_lv} | مسيرات={max_marches} | "
            f"حماية الموارد: رصيد>={self.min_res} ونسبة>={int(self.min_ratio*100)}%"
        )

        # 1. فحص مبنى قيادة التحالف (إن وُجد)
        if center_x is not None and center_y is not None:
            await self._verify_alliance_center(cx, cy, alliance_tag)

        # 2. البحث الذكي عن حقول الذهب المتاحة في أراضي التحالف
        current_range = search_range
        max_search_range = 100

        mines, active_subtype = await self._find_target_mines(
            cx, cy, alliance_tag, subtype_mode, min_lv, max_lv, current_range, min_dist=min_dist
        )

        # إذا لم يُعثر على حقول كافية في النطاق الأولي، نوسع النطاق تلقائياً حتى 100
        while not mines and current_range < max_search_range:
            current_range = min(max_search_range, current_range + 20)
            self.log.info(f"🔄 لم يتم العثور على حقول في النطاق السابق، جاري توسيع النطاق إلى {current_range} مربعات...")
            mines, active_subtype = await self._find_target_mines(
                cx, cy, alliance_tag, subtype_mode, min_lv, max_lv, current_range, min_dist=min_dist
            )

        if not mines:
            self.log.warning(f"⚠️ لم يُعثر على أي حقول ذهب متاحة وغير مشغولة تابعة لـ [{alliance_tag}] حول ({cx}, {cy}) حتى نطاق {current_range}!")
            return TaskResult.fail(f"لا توجد حقول ذهب شاغرة تتبع تحالف {alliance_tag}", retry_after=60)

        res_title = "🪙 ذهب التحالف (Gold)" if active_subtype == SUBTYPE_GOLD else "🔮 ميثريل/ذهب السماء (Sky Gold)"
        self.log.info(f"🎯 تم العثور على {len(mines)} حقل مؤكد وتابع لـ [{alliance_tag}] من نوع {res_title}:")
        for idx, m in enumerate(mines[:8], 1):
            tot_str = f"/{m['total']:,}" if m.get('total') else ""
            self.log.info(
                f"   {idx}. حقل ({m['x']}, {m['y']}) لفل={m['lv']} | مسافة={m['dist']} مربعات | "
                f"متبقي={m['remain']:,}{tot_str} | ID={m['id']} [{','.join(m['tags'])}]"
            )

        # في حال طلب الفحص فقط (--check-only)
        if check_only:
            return TaskResult.ok(
                f"✅ تم اكتشاف {len(mines)} حقل ذهب متاح تابع لـ [{alliance_tag}]",
                total_found=len(mines),
                sample_mines=mines[:5]
            )

        # 3. استعلام طوابير القلعة المشغولة حالياً وأهدافها
        my_target_ids, my_target_coords = self._get_my_active_targets()
        current_active_queues = len(my_target_coords)
        self.log.info(f"🚩 طوابير المسيرات المشغولة حالياً بقلعتك: {current_active_queues}")
        for (mx, my) in my_target_coords:
            self.log.info(f"   ↳ مسيرة نشطة سابقة متجهة نحو ({mx}, {my})")

        # نمط جميع الفيالق المتوفرة بالقلعة
        all_marches_mode = (max_marches <= 0)
        target_limit = 10 if all_marches_mode else max_marches
        self.log.info(f"⚔️ خطة الإرسال: {'استغلال جميع الفيالق المتوفرة بالقلعة حتى امتلاء الطوابير 🚀' if all_marches_mode else f'إرسال حتى {max_marches} فيالق'}")

        if not self._heroes:
            await self._load_heroes()

        sent_count = 0
        self._busy      = set()
        self._used_army = {}
        self._used_pets = set()

        failed_attempts = 0
        max_failed_attempts = 15

        current_range = search_range
        max_search_range = 100

        while (all_marches_mode or sent_count < max_marches):
            if not mines:
                # إذا فرغت الحقول المتاحة وما زالت هناك طوابير شاغرة بالقلعة:
                if current_range < max_search_range:
                    current_range = min(max_search_range, current_range + 20)
                    self.log.info(
                        f"🔄 توسيع نطاق البحث تلقائياً إلى {current_range} مربعات لجلب حقول جديدة تابعة لـ [{alliance_tag}]..."
                    )
                    more_mines, _ = await self._find_target_mines(
                        cx, cy, alliance_tag, active_subtype, min_lv, max_lv, current_range, min_dist=min_dist
                    )
                    if more_mines:
                        mines = more_mines
                        self.log.info(f"✨ تم العثور على {len(mines)} حقل إضافي بعد توسيع النطاق إلى {current_range}!")
                        continue

                self.log.info(f"ℹ️ استُنفدت جميع حقول الذهب المكتشفة في هذا النطاق (أقصى نطاق تم مسحه: {current_range}).")
                break

            if failed_attempts >= max_failed_attempts:
                self.log.warning(f"⚠️ تم الوصول للحد الأقصى من المحاولات المتتالية غير الناجحة ({max_failed_attempts}).")
                break

            target_mine = mines.pop(0)
            march_label = f"({sent_count + 1})" if all_marches_mode else f"({sent_count + 1}/{max_marches})"
            self.log.info(f"🚀 محاولة إرسال مسيرة الجمع رقم {march_label} نحو ({target_mine['x']}, {target_mine['y']})...")

            result_code = await self._send_one_march(target_mine, active_subtype, troops_cfg)

            if result_code == "SUCCESS":
                sent_count += 1
                self._exclude.add(target_mine['id'])
                # تسجيل الحقل في سجل الحماية المشترك بين الحسابات لمنع أي حساب آخر من استهدافه
                record_shared_target(
                    target_id=target_mine['id'],
                    x=target_mine['x'],
                    y=target_mine['y'],
                    email=getattr(self.conn.creds, 'email', str(self.uid)),
                    uid=self.uid,
                    tag=alliance_tag
                )
                failed_attempts = 0
                await asyncio.sleep(5.0)  # تأخير آمن بين المسيرات لحماية الحساب من الحظر
            elif result_code == "QUEUE_FULL":
                self.log.info("🛑 تم إشغال جميع الفيالق المتاحة للقلعة بنجاح (طوابير المسيرات مكتملة 100%).")
                break
            elif result_code == "NO_ARMY":
                self.log.warning(f"⚠️ نفدت القوات المتاحة بالقلعة لإرسال مسيرات إضافية (تم إرسال {sent_count} مسيرات).")
                break
            elif result_code == "NO_HEROES":
                self.log.warning(f"⚠️ نفد أبطال الجمع المتاحون بالقلعة (تم إرسال {sent_count} مسيرات).")
                break
            elif result_code in ("TARGET_OCCUPIED", "HERO_BUSY"):
                failed_attempts += 1
                if result_code == "TARGET_OCCUPIED":
                    self._exclude.add(target_mine['id'])
                continue
            else:
                failed_attempts += 1
                self.log.warning(f"⚠️ تعذر إرسال المسيرة (كود: {result_code}) — الانتقال للحقل التالي")
                continue

        self.log.info(f"🏁 إجمالي مسيرات جمع الذهب المُرسَلة بنجاح: {sent_count}")
        if sent_count > 0:
            return TaskResult.ok(f"✅ تم إرسال {sent_count} مسيرة جمع ذهب لتحالف [{alliance_tag}]", sent=sent_count)
        return TaskResult.fail("لم يتم إرسال أي مسيرة جمع ذهب", retry_after=120)

    # ── فحص إشغال وحجز المورد قبل الهجوم (حماية ضد صدام المسيرات) ───

    async def _is_tile_locked(self, mine: Dict[str, Any], kingdom_id: int) -> Tuple[bool, str, int]:
        """
        فحص أمني دقيق وشامل ومباشر للمورد قبل إرسال المسيرة:
        1. فحص سجل الحماية المشترك بين كافة الحسابات (حماية الـ 45 دقيقة).
        2. فحص طوابير ومسيرات قلعتنا النشطة (منع استهداف نفس الحقل مجدداً).
        3. فحص 1006/22: التحقق من عدم وجود لاعب يجمع بالمورد حالياً وكفاية الرصيد.
        4. فحص 1006/1000 ومزامنة الخريطة (NOTIFY_MAP_SYNC 1009/201): كافة المسيرات المتجهة للحقل.
        5. فحص كائن المورد في قطع الخريطة (ADD_PIECE_MAP) للتأكد من خلوه من أي شاغل.
        """
        target_id = mine['id']
        tx, ty    = mine['x'], mine['y']
        parts     = str(target_id).split('-')
        gx        = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else tx
        gy        = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else ty
        fresh_rem = 0

        # -1. فحص سجل الحماية المشترك بين الحسابات
        shared_targets, shared_coords = get_active_shared_history()
        if str(target_id) in shared_targets or (tx, ty) in shared_coords:
            hist = shared_targets.get(str(target_id), {})
            acc_name = hist.get('email') or hist.get('uid') or 'حساب آخر'
            elapsed_min = round((time.time() - float(hist.get('time', time.time()))) / 60, 1)
            return True, f"تم إرسال مسيرة لهذا الحقل مؤخراً من [{acc_name}] قبل {elapsed_min} دقيقة", 0

        # 0. فحص مسبق مباشر: هل قلعتنا تتجه لهذا الحقل أو تجمعه حالياً؟
        my_target_ids, my_target_coords = self._get_my_active_targets()
        if str(target_id) in my_target_ids or (tx, ty) in my_target_coords:
            return True, "قلعتك متجهة بالفعل نحو هذا الحقل أو تجمعه حالياً (مسيرة نشطة لك)", 0

        # 1. فحص 1006/22 الآني
        try:
            r22 = await self.conn.query('1006', '22', {"x": tx, "y": ty, "id": str(target_id)}, timeout=2.5)
            if r22 and isinstance(r22, dict):
                ret22 = r22.get('retData', {})
                c_num = int(ret22.get('currentCollectNum', 0))
                c_spd = float(ret22.get('collectSpeed', 0))
                fresh_rem = int(ret22.get('remainSourceNum', 0))
                fresh_tot = int(ret22.get('totalSourceNum', 0))

                # تحقق إضافي حاسم قبل الإرسال مباشرة بأن الحقل ما زال يتبع تحالفنا حصراً
                if self.alliance_tag:
                    fresh_tags = self._extract_tags(
                        ret22.get('terr'),
                        ret22.get('leagueAbbrName') or ret22.get('abbr') or ret22.get('leagueName')
                    )
                    if not any(str(self.alliance_tag).strip().upper() in str(t).strip().upper() for t in fresh_tags):
                        return True, f"الحقل غير تابع لأراضي تحالف [{self.alliance_tag}] (الأراضي الحالية: {fresh_tags})", 0

                if c_num > 0 or c_spd > 0:
                    return True, f"لاعب آخر يجمع المورد حالياً (currentCollectNum={c_num}, collectSpeed={c_spd})", 0
                if fresh_rem <= 0:
                    return True, "رصيد موارد الحقل نفد تماماً (remainSourceNum=0)", 0

                # فحص تدني الرصيد والاستهلاك المسبق
                min_req = max(self.min_res, int(fresh_tot * self.min_ratio)) if fresh_tot > 0 else self.min_res
                if fresh_rem < min_req:
                    return True, f"رصيد المورد متدنٍ ({fresh_rem}/{fresh_tot}) وتم استهلاكه أو الهجوم عليه مسبقاً", 0
        except Exception as e:
            self.log.warning(f"⚠️ تعذر استعلام 1006/22 للحقل {target_id}: {e}")

        # 2. فحص مسيرات الخريطة عبر مزامنة 1006/1000 والتقاط 1009/201
        sync_packets = []
        def _capture_sync(cmd, sub, content):
            if str(cmd) == '1009' and str(sub) == '201':
                sync_packets.append(content)

        target_kid = int(kingdom_id or self.kingdom_id or 0)
        self.conn.add_packet_listener(_capture_sync)
        try:
            await self.conn.query('1006', '1000', {
                'centerX': tx,
                'centerY': ty,
                'centerKid': target_kid
            }, timeout=3.0)
            await asyncio.sleep(0.4)
        except Exception as e:
            self.log.warning(f"⚠️ استعلام 1006/1000 للحقل {target_id}: {e}")
        finally:
            self.conn.remove_packet_listener(_capture_sync)

        cached_sync = self.conn.cached_packets.get(('1009', '201'))
        if cached_sync and cached_sync not in sync_packets:
            sync_packets.append(cached_sync)

        our_uid_str = str(self.uid)

        for pkt in sync_packets:
            if not isinstance(pkt, dict):
                continue
            p_data = pkt.get('data')
            if isinstance(p_data, dict):
                notify_list = p_data.get('notifyData', [])
            elif isinstance(p_data, list):
                notify_list = p_data
            else:
                notify_list = []

            if not isinstance(notify_list, list):
                continue

            for msg in notify_list:
                if not isinstance(msg, dict):
                    continue
                m_type = msg.get('msgType')
                m_data = msg.get('data')

                # فحص طوابير ومسيرات التحرك (11: ADD_PIECE_QUEUE, 12: ADD_QUEUE, 14: UPDATE_QUEUE)
                if m_type in (11, 12, 14):
                    q_items = []
                    if isinstance(m_data, dict):
                        for k, v in m_data.items():
                            if isinstance(v, list):
                                q_items.extend([x for x in v if isinstance(x, dict)])
                            elif isinstance(v, dict):
                                for qid, qd in v.items():
                                    if isinstance(qd, dict):
                                        q_items.append(qd)
                                if 'to' in v:
                                    q_items.append(v)
                    elif isinstance(m_data, list):
                        q_items.extend([x for x in m_data if isinstance(x, dict)])

                    for q in q_items:
                        to_info = q.get('to', {})
                        q_to_x = to_info.get('x')
                        q_to_y = to_info.get('y')
                        q_to_id = to_info.get('id') or to_info.get('mapObjId')
                        q_uid = q.get('playerID') or q.get('uid') or q.get('from', {}).get('uid')
                        p_name = q.get('playerName', '')

                        # مطابقة الوجهة مع الحقل
                        is_target = False
                        if q_to_id and str(q_to_id) == str(target_id):
                            is_target = True
                        elif q_to_x is not None and q_to_y is not None:
                            try:
                                qx, qy = int(q_to_x), int(q_to_y)
                                if (qx, qy) in ((tx, ty), (gx, gy), (tx + 1, ty + 1), (gx - 1, gy - 1)):
                                    is_target = True
                            except Exception:
                                pass

                        if is_target:
                            if q_uid and str(q_uid) == our_uid_str:
                                return True, "قلعتك متجهة بالفعل نحو هذا الحقل حالياً (مسيرة نشطة لك)", 0
                            elif q_uid:
                                return True, f"مسيرة نشطة للاعب آخر ({p_name or q_uid}) متجهة نحو هذا الحقل حالياً على الخريطة", 0
                            else:
                                return True, "توجد مسيرة نشطة متجهة نحو هذا الحقل حالياً على الخريطة", 0

                # فحص كائنات الخريطة (1: ADD_PIECE_MAP)
                elif m_type == 1:
                    if isinstance(m_data, dict):
                        for kid_k, p_dict in m_data.items():
                            if isinstance(p_dict, dict):
                                for piece_id, objs in p_dict.items():
                                    if isinstance(objs, list):
                                        for obj in objs:
                                            if isinstance(obj, dict) and obj.get('id') == target_id:
                                                res_obj = obj.get('resource', {})
                                                r_uid = res_obj.get('uid') or res_obj.get('playerID')
                                                occupier = res_obj.get('occupier') or obj.get('occupier') or obj.get('user')
                                                occ = occupier or r_uid
                                                if occ:
                                                    if str(occ) == our_uid_str:
                                                        return True, "قلعتك تشغل هذا الحقل وتجمع منه حالياً", 0
                                                    else:
                                                        return True, f"كائن الحقل مسجل كشاغل للاعب آخر ({occ})", 0

        return False, "", fresh_rem

    async def _send_one_march(
        self,
        mine: Dict[str, Any],
        actual_subtype: int,
        troops_cfg: Optional[int] = None
    ) -> str:
        target_id = mine['id']
        tx, ty    = mine['x'], mine['y']
        cur_res   = mine['remain']

        # 1. اختيار بطل الجمع تلقائياً
        if not self._heroes:
            await self._load_heroes()
        heroes = _pick_gather_heroes(self._heroes, max_count=1, busy=self._busy)
        if not heroes:
            self.log.warning("⚠️ لا يوجد بطل جمع متاح بالقلعة!")
            return "NO_HEROES"

        chosen_hero = heroes[0]

        # 2. حساب عدد الجنود المطلوب (عربة النقل تحمل ~25 مورد)
        if troops_cfg:
            needed_troops = int(troops_cfg)
        elif cur_res > 0:
            # إذا كان ذهب عادي (31500) نحتاج ~1500-25000 عربة
            needed_troops = max(15000, cur_res // 25)
        else:
            needed_troops = 25000

        # 3. جلب القوات المتوفرة بالقلعة لحظياً من السيرفر (فقط الجنود المتنقلون 400..799)
        available: Dict[int, int] = {}
        r_army = await self.conn.query('1005', '1', {})
        if r_army and 'data' in r_army:
            for k, v in r_army['data'].get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    tid = int(k)
                    # استبعاد أسلحة وفخاخ الجدار (800+) لأنها لا تسير في المسيرات
                    if 400 <= tid < 800:
                        val = int(v)
                        if val > 0:
                            available[tid] = val

        # 4. تشكيل الجيش (عربات نقل أولاً)
        army_list = select_gathering_army(available, needed_count=needed_troops)
        if not army_list:
            self.log.warning("⚠️ لا توجد قوات متوفرة بالقلعة لإرسال المسيرة!")
            return "NO_ARMY"

        total_troops = sum(item['num'] for item in army_list)

        # 5. اختيار الحيوان الأليف تلقائياً
        pets_list = select_gathering_pet(self.conn, self._used_pets)

        # 6. جلب معرف المملكة (kingdom_id)
        kingdom_id = 0
        if self.conn.kingdom_id:
            try: kingdom_id = int(self.conn.kingdom_id)
            except: pass
        if not kingdom_id:
            uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
            r_map = await self.conn.query('1002', '7', {"uid": uid_int})
            if r_map and 'data' in r_map:
                kingdom_id = r_map['data'].get('base', {}).get('partition', 0)

        # نوع المورد في حزمة المسيرة 1007/2 هو: 1000 + actual_subtype
        resource_type_id = 1000 + int(actual_subtype)

        # 6.5 فحص فوري ثانٍ آني وشامل (Just-In-Time) قبل لحظة الإرسال مباشرة لتفادي مسيرات الآخرين وحروب الموارد
        is_locked, lock_reason, fresh_rem = await self._is_tile_locked(mine, kingdom_id)
        if is_locked:
            self.log.warning(
                f"🛡️ تنبيه أمان: الحقل {target_id} عند ({tx}, {ty}) محجوز أو مستهدف! ({lock_reason}) — سيتم تخطيه فوراً لتفادي الصدام الحربي."
            )
            self._exclude.add(target_id)
            return "TARGET_OCCUPIED"
        if fresh_rem > 0:
            cur_res = fresh_rem

        self.log.info(
            f"🛡️ إعداد المسيرة → الحقل ({tx}, {ty}) | بطل={chosen_hero} | "
            f"جنود={total_troops:,} | نوع المورد={resource_type_id} | حيوان={pets_list}"
        )

        # 7. إرسال حزمة المسيرة 1007/2
        r_march = await self.conn.query('1007', '2', {
            "needSend": False,
            "runePages": {},
            "heros": [chosen_hero],
            "matrixType": 3,
            "mapId": int(kingdom_id),
            "moveLineType": 3,
            "data": {
                "data": {
                    "currentSourceNum": cur_res,
                    "resourceType": resource_type_id
                },
                "to": {
                    "y": int(ty),
                    "x": int(tx),
                    "id": str(target_id)
                },
                "army": army_list
            },
            "pets": pets_list
        })

        if not r_march:
            return "ERROR"

        err = str(r_march.get('err', '0'))
        if err == '0':
            self.log.info(f"✅ مسيرة جمع ناجحة! → {target_id} عند ({tx}, {ty})")
            self._busy.add(chosen_hero)
            for item in army_list:
                self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
            return "SUCCESS"
        elif err in ('8004', '9007004'):
            self.log.info(f"🛑 اكتملت طوابير المسيرات (كود {err})")
            return "QUEUE_FULL"
        elif err == '8009':
            self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
            return "NO_ARMY"
        elif err == '9007020':
            self._busy.add(chosen_hero)
            return "HERO_BUSY"
        elif err in ('8062', '8063', '8060', '9007062'):
            self.log.warning(f"⚠️ الهدف {target_id} مشغول أو ممتلئ (كود {err}) — تخطي")
            self._exclude.add(target_id)
            return "TARGET_OCCUPIED"
        else:
            self.log.error(f"❌ خطأ غير معروف في حزمة المسيرة: {err} | الهدف={target_id}")
            return "ERROR"


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (CLI Standalone)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Empire Alliance Gold Gathering — مهمة جمع الذهب في أراضي التحالف"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--tag", "-t", required=True,
                        help="اختصار التحالف المستهدف (مثال: POL, SKY, KRT)")
    parser.add_argument("--center-x", "-x", type=int, default=None,
                        help="إحداثي X لقيادة التحالف المستهدف")
    parser.add_argument("--center-y", "-y", type=int, default=None,
                        help="إحداثي Y لقيادة التحالف المستهدف")
    parser.add_argument("--coords", type=str, default=None,
                        help="إحداثيات مركز التحالف بصيغة X,Y (مثال: 241,260)")
    parser.add_argument("--subtype", "-r", type=str, default="auto",
                        help="نوع مورد الذهب: 5=ذهب/فضة عادي، 1=ميثريل/ذهب سماء، auto=تلقائي [افتراضي: auto]")
    parser.add_argument("--flags-file", type=str, default=None,
                        help="ملف بيانات رايات التحالف لاستخراج حدود التحالف تلقائياً")
    parser.add_argument("--hq-x", type=int, default=None,
                        help="إحداثي X لقلعة القيادة (مرادف لـ --center-x)")
    parser.add_argument("--hq-y", type=int, default=None,
                        help="إحداثي Y لقلعة القيادة (مرادف لـ --center-y)")
    parser.add_argument("--minlv", type=int, default=DEFAULT_MIN_LV,
                        help=f"أدنى لفل لحقل المورد [افتراضي: {DEFAULT_MIN_LV}]")
    parser.add_argument("--maxlv", type=int, default=DEFAULT_MAX_LV,
                        help=f"أعلى لفل لحقل المورد [افتراضي: {DEFAULT_MAX_LV}]")
    parser.add_argument("--range", type=int, default=DEFAULT_SEARCH_RANGE,
                        help=f"نطاق البحث حول مركز التحالف [افتراضي: {DEFAULT_SEARCH_RANGE}]")
    parser.add_argument("--min-dist", type=float, default=0.0,
                        help="أدنى مسافة من مركز التحالف لتجنب التزاحم على الحقول الملاصقة للمقر [افتراضي: 0.0]")
    parser.add_argument("--marches", "-m", type=int, default=DEFAULT_MAX_MARCHES,
                        help="عدد المسيرات المطلوب إرسالها (0 = جميع الفيالق المتوفرة بالقلعة) [افتراضي: 0]")
    parser.add_argument("--troops", type=int, default=None,
                        help="تحديد عدد الجنود لكل مسيرة يدوياً (اختياري)")
    parser.add_argument("--min-res", type=int, default=DEFAULT_MIN_RESOURCES,
                        help=f"أدنى رصيد متبقي لحقل المورد لقبوله [افتراضي: {DEFAULT_MIN_RESOURCES}]")
    parser.add_argument("--min-ratio", type=float, default=DEFAULT_MIN_RES_RATIO,
                        help=f"أدنى نسبة متبقية من إجمالي موارد الحقل [افتراضي: {DEFAULT_MIN_RES_RATIO}]")
    parser.add_argument("--check-only", action="store_true",
                        help="وضع الفحص فقط: اكتشاف وعرض حقول الذهب المتاحة دون إرسال مسيرات")

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
            print(f"❌ الحساب {target_email} غير موجود في session_cache.json!")
            return

        conn = GameConnection(acc)
        if not await conn.connect():
            print("❌ فشل الاتصال بخادم اللعبة!")
            return

        for _ in range(12):
            await asyncio.sleep(1.0)
            if len(conn.init_data) > 0:
                break

        # معالجة إحداثيات المركز والقيادة
        cx = args.center_x if args.center_x is not None else args.hq_x
        cy = args.center_y if args.center_y is not None else args.hq_y
        if (cx is None or cy is None) and args.coords:
            try:
                parts = args.coords.split(',')
                cx, cy = int(parts[0].strip()), int(parts[1].strip())
            except Exception:
                pass

        task_cfg = {
            "alliance_tag": args.tag,
            "center_x":     cx,
            "center_y":     cy,
            "coords":       args.coords,
            "flags_file":   args.flags_file,
            "subtype":      args.subtype,
            "min_lv":       args.minlv,
            "max_lv":       args.maxlv,
            "search_range": args.range,
            "min_dist":     args.min_dist,
            "min_res":      args.min_res,
            "min_ratio":    args.min_ratio,
            "max_marches":  args.marches,
            "troops_count": args.troops,
            "check_only":   args.check_only
        }

        task = GoldGatherTask(conn, task_cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message}")
        if result.data:
            print(f"📋 تفاصيل النتيجة: {json.dumps(result.data, ensure_ascii=False, indent=2)}")

        await conn.close()

    asyncio.run(_main())
