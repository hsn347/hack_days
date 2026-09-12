# -*- coding: utf-8 -*-
"""
tasks/elf_boss.py — مهمة الهجوم على نخبة العفريت وزعماء الأبطال (Elf Elite / Battle Boss Attack)
══════════════════════════════════════════════════════════════════════════════════════════════════

بروتوكول البحث والهجوم على نخبة العفريت (Hero Battle Boss):
  1. البحث عن العفريت الأقرب (Find Boss):
     cmd: "2011", subcmd: "4", data: {"bossType": 10}
     - يعيد السيرفر موقع العفريت: {"rspdata": {"x": bx, "y": by, "bossType": 10}}
  2. استخراج التشكيلة المحفوظة (Get Formation):
     cmd: "1005", subcmd: "7", data: {"compiletype": formation_id}
     - جلب أبطال التشكيلة والحيوان والرونات والجيش المحفوظ.
  3. فحص جاهزية الأبطال واختيار البدائل القتالية (Combat Fallback):
     - إذا كان أبطال التشكيلة متاحين يتم إرسالهم فوراً.
     - إذا كان أحدهما أو كلاهما مشغولاً في مسيرة أو دفاع، يتم تلقائياً اختيار أفضل أبطال
       الحرب (5501xxx) الذين يمتلكون مهارات قتالية وهجومية (5610xxx / 5640xxx) بأعلى رتبة ومستوى.
  4. إرسال هجوم الحشد الجماعي (Send Mass March):
     cmd: "1007", subcmd: "2", data: {
         "needSend": true,
         "mapId": dynamic_map_id,
         "moveLineType": 7,
         "data": {
             "data": {"mainInstanceType": 24, "massTime": 300},
             "to": {"x": bx, "y": by, "id": f"{bx+1}-{by+1}-24-0-10"},
             "army": [...]
         },
         "pets": [...],
         "runePages": [1],
         "matrixType": 1,
         "heros": [...]
     }

المدخلات من المستخدم:
  - formation_id: رقم التشكيلة الأساسية (1..6) [افتراضي: 1]
  - max_distance: أقصى مسافة مقبولة للعفريت من القلعة (اختياري)
  - count: عدد الفيالق المراد إرسالها [افتراضي: جميع الفيالق المتوفرة بالقلعة]
  - all_legions: تفعيل الهجوم بكافة الفيالق المتاحة حتى امتلاء الطوابير

أمر التشغيل المباشر:
  python tasks/elf_boss.py --email "meik.gaertner2306.MGr@gmail.com" --formation 1
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
DEFAULT_ATTACK_DELAY    = 22.0 # فترة الأمان الافتراضية الموسعة بين كل هجوم والآخر بالثواني (محاكاة السلوك البشري وأقصى درجات مكافحة الحظر)


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
    اختيار تشكيلة جيش قتالية متوازنة في حال كانت قوات التشكيلة غير كافية:
      1. المشاة (401..414)
      2. الفرسان (501..514)
      3. الرماة (601..614)
      4. القوات الخاصة (800+)
      5. عربات الحصار (701..714)
    """
    infantry = []
    cavalry  = []
    archers  = []
    carts    = []

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

    priority_groups = [infantry, cavalry, archers, carts]
    army_list = []
    remaining = needed_count

    for group in priority_groups:
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
        self.max_distance : Optional[float] = float(self.config['max_distance']) if self.config.get('max_distance') is not None else None
        
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
        self._busy_heroes     : Set[int] = set()
        self._hero_busy_until : Dict[int, float] = {}
        self._used_army       : Dict[int, int] = {}
        self._targeted_bosses : Set[Tuple[int, int]] = set()
        self._targeted_boss_ids: Set[str] = set()
        self._template_army   : Dict[str, int] = {}
        self._template_pets   : List[int] = []
        self._template_runes  : List[int] = [1]
        self._castle_x        : int = 0
        self._castle_y        : int = 0
        self._map_id          : int = 0

    async def on_start(self):
        """انتظار تحميل حزم البيانات الأساسية وتحميل سجل الأبطال وموقع القلعة ومعرف الخريطة ومزامنة الطوابير."""
        for _ in range(15):
            has_city = "cityCtrl" in self.conn.init_data
            has_heroes = bool((self.conn._gate and getattr(self.conn._gate, 'heroes', None)) or self.conn.init_data.get('heroCtrl'))
            if has_city and has_heroes:
                break
            await asyncio.sleep(0.3)

        # تحديث قائمة الطوابير والمسيرات النشطة حالياً
        try:
            await self.conn.query('1007', '16', {}, timeout=4)
        except Exception:
            pass

        await self._load_castle_coords()
        await self._load_map_id()
        await self._load_heroes()
        self._detect_busy_heroes()

    async def _load_castle_coords(self):
        """جلب إحداثيات قلعة اللاعب على الخريطة."""
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
        try:
            r_castle = await self.conn.query('1006', '25', {"uid": uid_int}, timeout=4)
            if r_castle and 'retData' in r_castle:
                self._castle_x = int(r_castle['retData'].get('x', 0))
                self._castle_y = int(r_castle['retData'].get('y', 0))
                self.log.info(f"🏰 موقع قلعة اللورد: ({self._castle_x}, {self._castle_y})")
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
        self._map_id = self._resolve_map_id()
        if not self._map_id:
            uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
            try:
                r_player = await self.conn.query('1002', '7', {"uid": uid_int}, timeout=4)
                if r_player and 'data' in r_player:
                    part = r_player['data'].get('base', {}).get('partition')
                    if part and str(part).isdigit() and int(part) > 0:
                        self._map_id = int(part)
            except Exception as e:
                self.log.warning(f"⚠️ تعذر جلب معرف الخريطة من 1002/7: {e}")

        self.log.info(f"🗺️ معرف خريطة ومملكة اللورد (mapId): {self._map_id}")

    async def _load_heroes(self):
        """تحميل قائمة أبطال القلعة مع الاسترداد الاحتياطي."""
        self._heroes = []
        if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
            self._heroes = list(self.conn._gate.heroes)
            self.log.info(f"📋 تم تحميل {len(self._heroes)} بطل من Gate")
            return

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

    def _detect_busy_heroes(self):
        """استخراج الأبطال المشغولين في مسيرات الخريطة الحالية وتقدير عدد الفيالق النشطة."""
        self._busy_heroes = set()
        all_queues = []
        if getattr(self.conn, 'local_queues', None):
            all_queues.extend(self.conn.local_queues)

        for p in self.conn.cached_packets.values():
            if isinstance(p, dict):
                d = p.get('data', {})
                if isinstance(d, dict) and d.get('notifyID') == 'NOTIFY_LOCAL_QUEUE_SYNC':
                    nd = d.get('notifyData', [])
                    if isinstance(nd, list):
                        all_queues.extend(nd)

        active_march_count = 0
        for item in all_queues:
            q_list = item.get('data', []) if isinstance(item, dict) else (item if isinstance(item, list) else [])
            for q in q_list:
                if not isinstance(q, dict):
                    continue
                # مسيرات نشطة (سائرة أو مرابطة أو حشد)
                if q.get('status') in (1, 2, 3, 4, 7):
                    active_march_count += 1
                    h_list = q.get('heros') or q.get('data', {}).get('heros') or []
                    if isinstance(h_list, list):
                        for h in h_list:
                            hid = h if isinstance(h, int) else (h.get('id') if isinstance(h, dict) else None)
                            if hid and str(hid).isdigit():
                                self._busy_heroes.add(int(hid))

        # تنظيف ودمج الأبطال المشغولين في حشود ومسيرات العفريت الزمنية
        now = time.time()
        self._hero_busy_until = {hid: ts for hid, ts in self._hero_busy_until.items() if ts > now}
        self._busy_heroes.update(self._hero_busy_until.keys())

        if self._busy_heroes:
            self.log.info(f"⏳ أبطال مشغولون في مسيرات قائمة: {list(self._busy_heroes)} (عدد المسيرات النشطة: {active_march_count})")

    async def _reset_viewport_to_castle(self):
        """إعادة توجيه عدسة الخريطة (Viewport) إلى قلعة اللاعب لتحديث نقطة ارتكاز البحث."""
        if self._castle_x and self._castle_y:
            castle_client_x = self._castle_x - 1
            castle_client_y = self._castle_y - 1
            map_id = self._map_id or self._resolve_map_id()
            try:
                # محاكاة إزاحة الكاميرا وعودتها للقلعة بعد إطلاق المسيرة
                await asyncio.sleep(round(random.uniform(1.2, 2.5), 2))
                await self.conn.query('1006', '1000', {
                    "centerKid": map_id,
                    "centerX": castle_client_x,
                    "centerY": castle_client_y
                }, timeout=4)
                await self.conn.query('1006', '47', {"switchFlag": 2}, timeout=2)
            except Exception:
                pass

    async def _reconnect_session(self) -> bool:
        """
        إعادة مزامنة وتجديد جلسة الاتصال بالسيرفر لإفراغ كاش رادار الخريطة وجلب عفريت جديد.
        """
        self.log.info("🔌 جاري تجديد جلسة الاتصال بالسيرفر لتحديث رادار الأهداف على الخريطة...")
        prev_busy = set(self._busy_heroes)
        try:
            await self.conn.close()
        except Exception:
            pass
        await asyncio.sleep(1.5)

        ok = await self.conn.connect()
        if not ok:
            self.log.warning("⚠️ فشل تجديد الاتصال بالسيرفر")
            return False

        for _ in range(15):
            has_city = "cityCtrl" in self.conn.init_data
            has_heroes = bool((self.conn._gate and getattr(self.conn._gate, 'heroes', None)) or self.conn.init_data.get('heroCtrl'))
            if has_city and has_heroes:
                break
            await asyncio.sleep(0.3)

        await self._load_castle_coords()
        await self._load_map_id()
        await self._load_heroes()
        self._detect_busy_heroes()
        self._busy_heroes.update(prev_busy)
        await self._reset_viewport_to_castle()
        self.log.info("✅ تم تجديد الجلسة بنجاح وتحديث رادار الأهداف.")
        return True

    async def _find_unique_elf_boss(
        self,
        excluded_coords: Optional[Set[Tuple[int, int]]] = None,
        excluded_ids: Optional[Set[str]] = None
    ) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int], Optional[str], float, str]:
        """
        البحث الاحترافي الشامل عن نخبة العفريت وزعماء الأبطال (Hero Battle Boss) عبر الخريطة:
          1. الطريقة الاحترافية الأساسية: استعلام الخريطة الشامل (2011/3) لفئات الزعماء (mapType 24 و 23)
             والذي يعيد قائمة كاملة بكافة العفاريت المنتشرة على الخريطة مرتبة حسب المسافة،
             مع استبعاد أي هدف تم استهدافه سابقاً في هذه الجلسة بالمعرف (ID) أو الإحداثيات.
          2. الطريقة البديلة (Fallback): استعلام رادار الزعماء الفردي (2011/4) لفئات الزعماء [10, 9, 6, 5].
        تعيد: (bx, by, boss_type, boss_instance_type, target_map_id, distance, status_msg)
        """
        if excluded_coords is None:
            excluded_coords = self._targeted_bosses
        if excluded_ids is None:
            excluded_ids = self._targeted_boss_ids

        cx = self._castle_x
        cy = self._castle_y

        candidates = []

        # ── 1. الاستعلام الاحترافي الشامل عبر الخريطة (2011/3) ──
        # تحديد mapType المستهدف بدقة: 24 لنخبة العفريت (فئة 10) و 23 للعفريت العادي (فئة 9)
        if self.boss_type == 10:
            target_map_types = [24]
        elif self.boss_type == 9:
            target_map_types = [23]
        else:
            target_map_types = [24, 23]

        # محاكاة فتح خريطة المملكة والبحث البشري الطبيعي
        map_search_wait = round(random.uniform(3.5, 6.0) if getattr(self, 'ultra_safe', False) else random.uniform(2.2, 4.2), 2)
        await asyncio.sleep(map_search_wait)

        for mt in target_map_types:
            try:
                self.log.debug(f"🔍 استعلام الخريطة الشامل للزعماء (2011/3) للنوع {mt}...")
                resp = await self.conn.query('2011', '3', {
                    "mapType": mt,
                    "num": 20,
                    "y": cy,
                    "x": cx,
                    "range": int(self.max_distance) if self.max_distance else 2000
                }, timeout=4)
                if resp and isinstance(resp.get('result'), list):
                    for item in resp['result']:
                        if not isinstance(item, dict):
                            continue
                        tid = item.get('id')
                        tx = item.get('x')
                        ty = item.get('y')
                        if tx is None or ty is None or not tid:
                            continue
                        bx = tx + 1
                        by = ty + 1

                        if tid in excluded_ids or (bx, by) in excluded_coords:
                            continue

                        dist = math.hypot(tx - cx, ty - cy)
                        if self.max_distance is not None and dist > self.max_distance:
                            continue

                        btype = 10 if mt == 24 else 9
                        if '-' in tid:
                            try:
                                btype = int(tid.split('-')[-1])
                            except Exception:
                                pass

                        # مطابقة نوع العفريت المستهدف بدقة (نخبة العفريت 10 أو العادي 9)
                        if self.boss_type and btype != self.boss_type:
                            continue

                        candidates.append((bx, by, btype, mt, tid, dist))
            except Exception as e:
                self.log.debug(f"خطأ أثناء استعلام 2011/3 للنوع {mt}: {e}")

        # ── 2. الطريقة الاحتياطية (2011/4) إذا لم يُعثر على نتائج في 2011/3 ──
        if not candidates:
            fallback_btypes = [self.boss_type] if self.boss_type in (10, 9) else [10]
            self.log.debug(f"ℹ️ استخدام رادار الزعماء الفردي (2011/4) كخيار احتياطي للنوع {fallback_btypes}...")
            for btype in fallback_btypes:
                try:
                    resp = await self.conn.query('2011', '4', {"bossType": btype}, timeout=4)
                    if not resp or str(resp.get('err', '0')) != '0':
                        continue
                    rspdata = resp.get('rspdata', {})
                    bx = rspdata.get('x')
                    by = rspdata.get('y')
                    if bx is None or by is None:
                        continue
                    itype = 24 if btype == 10 else 23
                    tid = f"{bx}-{by}-{itype}-0-{btype}"

                    if (bx, by) in excluded_coords or tid in excluded_ids:
                        continue

                    tx = bx - 1
                    ty = by - 1
                    dist = math.hypot(tx - cx, ty - cy)
                    if self.max_distance is not None and dist > self.max_distance:
                        continue

                    candidates.append((bx, by, btype, itype, tid, dist))
                except Exception as e:
                    self.log.debug(f"خطأ أثناء فحص bossType {btype}: {e}")

        if not candidates:
            target_desc = "نخبة العفريت (فئة 10)" if self.boss_type == 10 else f"العفريت (فئة {self.boss_type})"
            return None, None, None, None, None, 0.0, f"لم يتم العثور على أي {target_desc}"

        # فرز المرشحين واختيار الأقرب مسافة إلى القلعة
        candidates.sort(key=lambda c: c[5])
        best_bx, best_by, best_btype, best_itype, best_tid, best_dist = candidates[0]
        boss_label = "نخبة العفريت (فئة 10 - Elite Boss)" if best_btype == 10 else f"العفريت العادي (فئة {best_btype})"
        self.log.info(
            f"🎯 تم العثور على {boss_label} عند ({best_bx-1}, {best_by-1}) "
            f"[ID: {best_tid}] | المسافة: {best_dist:.1f} كم من القلعة"
        )
        return best_bx, best_by, best_btype, best_itype, best_tid, best_dist, "OK"

    async def _load_formation(self, fid: int) -> Tuple[List[int], List[int], List[int], Dict[str, int]]:
        """
        استخراج بيانات التشكيلة المطلوبة من السيرفر (1005/7):
        تعيد: (أبطال_التشكيلة, حيوانات_التشكيلة, صفحات_الرون, جيش_التشكيلة)
        """
        self.log.info(f"📂 جلب بيانات التشكيلة رقم {fid} من القلعة...")
        resp = await self.conn.query('1005', '7', {"compiletype": fid}, timeout=5)
        if not resp or not resp.get('data'):
            self.log.warning(f"⚠️ تعذر جلب بيانات التشكيلة {fid}، سيتم استخدام الإعدادات التلقائية.")
            return [], [], [1], {}

        data = resp.get('data', {})
        fid_str = str(fid)

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

        return heroes, pets, runes, army

    def _resolve_combat_heroes(self, form_heroes: List[int], fid_label: str = "") -> List[int]:
        """
        التحقق من أبطال التشكيلة أو الاستبدال التلقائي بأبطال حرب شاغرين:
        """
        available_form = []
        for hid in form_heroes:
            if hid not in self._busy_heroes:
                hdata = next((x for x in self._heroes if x.get('id') == hid), None)
                if hdata and hdata.get('status', {}).get('state', 0) == 0:
                    available_form.append(hid)

        if len(available_form) >= 2:
            self.log.info(f"🎖️ تم اختيار أبطال التشكيلة المحفوظة ({fid_label}): {available_form[:2]}")
            return available_form[:2]

        if available_form:
            self.log.info(f"ℹ️ أحد أبطال التشكيلة متاح ({available_form[0]}) والآخر مشغول، جاري إكمال التشكيلة بأفضل بطل حرب متاح...")
            extra_busy = set(self._busy_heroes) | {available_form[0]}
            fillers = _pick_combat_heroes(self._heroes, max_count=1, busy=extra_busy)
            chosen = [available_form[0]] + fillers
            self.log.info(f"⚔️ تشكيلة الأبطال الهجينة: {chosen}")
            return chosen

        self.log.info("⚠️ أبطال التشكيلة المحفوظة غير متاحين أو مشغولون بالكامل — جاري اختيار نخبة أبطال الحرب (5501xxx) تلقائياً...")
        chosen = _pick_combat_heroes(self._heroes, max_count=2, busy=self._busy_heroes)
        if chosen:
            self.log.info(f"⚔️ تم اختيار أبطال الحرب البدلاء بنجاح: {chosen}")
            return chosen

        self.log.warning("⚠️ لا يتوفر أي بطل حرب شاغر بالقلعة حالياً!")
        return []

    async def _resolve_army(self, form_army: Dict[str, int]) -> List[Dict[str, int]]:
        """
        تجهيز قوات المسيرة بمطابقة تشكيلة الجيش المتاحة بالقلعة مع دعم التشكيلات الاحتياطية.
        """
        available: Dict[int, int] = {}
        r_army = await self.conn.query('1005', '1', {}, timeout=4)
        if r_army and 'data' in r_army:
            for k, v in r_army['data'].get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)

        for tid, used in self._used_army.items():
            if tid in available:
                available[tid] = max(0, available[tid] - used)

        march_army = []
        target_army = form_army or self._template_army
        if target_army:
            # ضبط القوات بنسب متوازنة مع سعة مسيرة اللورد لمنع تجاوز السعة وتجنب خطأ السيرفر 8035
            total_req = sum(int(cnt) for cnt in target_army.values() if int(cnt) > 0)
            max_troops = getattr(self, "max_march_troops", 200000) or 200000
            scale = 1.0
            if total_req > max_troops:
                scale = max_troops / float(total_req)

            for tid_str, req_cnt in target_army.items():
                tid = int(tid_str)
                avail = available.get(tid, 0)
                scaled_req = max(1, int(req_cnt * scale)) if scale < 1.0 else req_cnt
                take = min(scaled_req, avail)
                if take > 0:
                    march_army.append({"id": tid, "num": take})
                    available[tid] -= take

        if not march_army:
            self.log.info("ℹ️ جنود التشكيلة المحددة غير متوفرين بالكامل، جاري اختيار أفضل قوات قتالية متاحة...")
            march_army = select_combat_army(available, needed_count=DEFAULT_TROOPS_COUNT)

        return march_army

    async def _get_queue_id(self) -> str:
        """جلب معرف الطابور النشط الأول من بيانات المسيرات الحالية."""
        try:
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
        # 1. تحديد رقم التشكيلة المفضلة لهذا الفيلق
        # إذا حدد المستخدم تشكيلة 1 مثلاً، الفيلق 1 يبدأ بـ 1، والفيلق 2 يجرب 2، وهكذا
        target_fid = self.formation_id + (legion_idx - 1)
        if target_fid > 6:
            target_fid = ((target_fid - 1) % 6) + 1

        # 2. جلب بيانات التشكيلة
        form_heroes, form_pets, form_runes, form_army = await self._load_formation(target_fid)

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
        chosen_heroes = self._resolve_combat_heroes(form_heroes, fid_label=f"تشكيلة {target_fid}")
        if not chosen_heroes:
            return False, "NO_HEROES"

        # 4. تحديد الجيش
        march_army = await self._resolve_army(form_army)
        if not march_army:
            return False, "NO_ARMY"

        total_troops = sum(a['num'] for a in march_army)

        # 5. تحديد الحيوان الأليف وصفحات الرون
        pets_list = form_pets or self._template_pets or [1263]
        runes_list = form_runes or self._template_runes or [1]

        # 6. تحديد نوع الكائن ومعرف الموقع على الخريطة
        if not target_map_id:
            target_map_id = f"{bx}-{by}-{boss_instance_type}-0-{boss_type}"
        target_client_x = bx - 1
        target_client_y = by - 1
        map_id = self._map_id or self._resolve_map_id()

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
                    "y": target_client_y,
                    "x": target_client_x,
                    "id": target_map_id
                },
                "army": march_army
            },
            "needArmyList": {},
            "pets": pets_list,
            "runePages": runes_list,
            "matrixType": 1,
            "heros": chosen_heroes
        }

        # 7. مزامنة وتحميل بقعة الخريطة للهدف (1006/1000)
        try:
            await self.conn.query('1006', '1000', {"centerKid": map_id, "centerX": target_client_x, "centerY": target_client_y}, timeout=5)
        except Exception:
            pass

        # محاكاة التفاعل البشري الطبيعي والموسع لمكافحة الحظر (فتح الهدف واختيار التشكيلة والضغط)
        min_prep = 7.0 if getattr(self, 'ultra_safe', False) else 5.0
        max_prep = 12.0 if getattr(self, 'ultra_safe', False) else 8.5
        human_prep = round(random.uniform(min_prep, max_prep), 2)
        self.log.info(f"⏳ [محاكاة بشرية فائقة الأمان] تجهيز تفاصيل الفيلق {legion_idx} واختيار القوات ({human_prep} ثانية)...")
        await asyncio.sleep(human_prep)

        boss_desc = "نخبة العفريت (فئة 10 - Elite)" if boss_type == 10 else f"العفريت العادي (فئة {boss_type})"
        self.log.info(
            f"🚀 [الفيلق {legion_idx}] إرسال مسيرة حشد {boss_desc} (5 دقائق) → ({target_client_x}, {target_client_y}) [ID: {target_map_id}] | "
            f"أبطال: {chosen_heroes} | جنود: {total_troops:,} | حيوان: {pets_list}..."
        )

        resp = await self.conn.query('1007', '2', payload, timeout=8)
        if not resp:
            return False, "انتهت مهلة استجابة السيرفر أثناء إرسال المسيرة"

        err = str(resp.get('err', '0'))
        if err == '0':
            # تحديث المشغولين بمدة حشد ومسيرة واقعية (5 دقائق حشد + 2 دقيقة ذهاب وعودة = 420 ثانية)
            now = time.time()
            for hid in chosen_heroes:
                self._busy_heroes.add(hid)
                self._hero_busy_until[hid] = now + 420.0
            for item in march_army:
                self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
            self._targeted_bosses.add((bx, by))
            if target_map_id:
                self._targeted_boss_ids.add(target_map_id)
            # استخراج معرف المسيرة (queueId) من رد السيرفر
            q_id = ""
            self.log.info(f"🔍 [DEBUG] رد 1007/2 كامل: {resp}")
            resp_data = resp.get('data') or resp.get('retData') or {}
            if isinstance(resp_data, dict):
                q_id = str(resp_data.get('queueId') or resp_data.get('id') or
                           resp_data.get('queue_id') or resp_data.get('marchId') or "")
            # محاولة جلب queueId من 1007/16 إذا لم يُعثر عليه في الرد المباشر
            if not q_id or q_id == "0":
                try:
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
            if not q_id:
                q_id = f"{self.uid}-1"
            self.log.info(f"🆔 معرف مسيرة العفريت: {q_id}")

            # محاكاة عودة عدسة الكاميرا إلى القلعة تلقائياً كما يفعل تطبيق الجوال الرسمي
            try:
                await self._reset_viewport_to_castle()
            except Exception:
                pass

            return True, q_id

        elif err == '8002':
            self._targeted_bosses.add((bx, by))
            if target_map_id:
                self._targeted_boss_ids.add(target_map_id)
            return False, "8002: الهدف غير متاح أو تغيرت حالته/انتهى على الخريطة"
        elif err == '8026':
            self._targeted_bosses.add((bx, by))
            if target_map_id:
                self._targeted_boss_ids.add(target_map_id)
            return False, "8026: يوجد حشد جماعي نشط لك بالفعل ضد هذا العفريت حالياً"
        elif err == '8035':
            self._targeted_bosses.add((bx, by))
            if target_map_id:
                self._targeted_boss_ids.add(target_map_id)
            return False, "8035: الهدف مشغول بمعركة أو حشد آخر حالياً وصل للحد الأقصى أو تغيرت حالته (Err_MAP_QUEUE_BATTLE_NUM_OUT)"
        elif err.startswith('80') and err != '8004':
            self._targeted_bosses.add((bx, by))
            if target_map_id:
                self._targeted_boss_ids.add(target_map_id)
            return False, f"كود خريطة {err}: الهدف غير متاح حالياً"
        elif err == '9007020':
            now = time.time()
            for hid in chosen_heroes:
                self._busy_heroes.add(hid)
                self._hero_busy_until[hid] = now + 240.0
            return False, f"HEROES_BUSY: 9007020: أبطال التشكيلة {chosen_heroes} مشغولون حالياً في مسيرة أو حشد قائم"
        elif err in ('8004', '9007004'):
            return False, "QUEUE_FULL: طوابير المسيرات بالقلعة مكتملة بالكامل"
        elif err in ('10002', '10003'):
            return False, "STAMINA_EMPTY: طاقة اللورد غير كافية لإرسال الهجوم على العفريت"
        elif err == '16001':
            return False, "انقطع الاتصال أو سجل حساب آخر الدخول"
        else:
            return False, f"كود خطأ سيرفر: {err}"

    async def run(self) -> TaskResult:
        """تنفيذ دورة الهجوم على نخبة العفريت بكافة الفيالق المتوفرة."""
        target_mode_desc = "كافة الفيالق المتوفرة حتى امتلاء الطوابير" if self.all_legions else f"{self.attack_count} فيالق"
        boss_desc = "نخبة العفريت (Elite Boss - فئة 10)" if self.boss_type == 10 else f"العفريت العادي (فئة {self.boss_type})"
        self.log.info(
            f"👹 بدء مهمة الهجوم على {boss_desc} | "
            f"التشكيلة الأساسية: {self.formation_id} | الهدف: {target_mode_desc}"
        )

        successful_attacks = 0
        last_error = ""
        consecutive_errors = 0
        attempt = 0
        max_attempts = self.attack_count * 3

        while successful_attacks < self.attack_count and attempt < max_attempts:
            attempt += 1
            current_legion = successful_attacks + 1
            self.log.info(f"⚔️ تجهيز الفيلق رقم ({current_legion}/{self.attack_count})...")

            bx, by, btype, itype, tid, dist, status = await self._find_unique_elf_boss()

            if status != "OK" or bx is None or by is None or btype is None:
                if successful_attacks > 0:
                    self.log.info(
                        f"🏁 تم استهداف جميع زعماء العفاريت المتاحين حالياً على الخريطة بنجاح "
                        f"(إجمالي الفيالق المُرسَلة: {successful_attacks} فيالق)."
                    )
                    break
                else:
                    msg = f"⚠️ لم يتم العثور على أي نخبة عفريت متاحة: {status}"
                    self.log.warning(msg)
                    return TaskResult.fail(msg, error=status)

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
                consecutive_errors = 0
                march_queue_id = err_or_qid
                self.log.info(
                    f"🎉 الفيلق ({successful_attacks}) أُطلق بنجاح على نخبة العفريت فئة {btype} عند ({bx-1}, {by-1})! 🏹 [queueId={march_queue_id}]"
                )
                if successful_attacks < self.attack_count:
                    # تباين عشوائي يمنع أي نمط توقيت ثابت لكشف الروبوت
                    min_wait = 28.0 if getattr(self, 'ultra_safe', False) else 20.0
                    safe_delay = max(min_wait, round(self.attack_delay + random.uniform(3.5, 11.5), 2))
                    self.log.info(
                        f"🛡️ [أمان ومكافحة حظر] تم إرسال الفيلق بنجاح — انتظار {safe_delay:.1f} ثانية "
                        f"بمؤقت عشوائي آمن قبل تجهيز الفيلق التالي..."
                    )
                    await asyncio.sleep(safe_delay)
            else:
                err_msg = err_or_qid
                last_error = err_msg
                consecutive_errors += 1
                self.log.warning(f"⚠️ تعذر إرسال الفيلق {current_legion}: {err_msg}")

                if "QUEUE_FULL" in err_msg:
                    self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل.")
                    break
                if "NO_ARMY" in err_msg:
                    self.log.info("🛑 نفدت القوات المتاحة بالقلعة.")
                    break
                if "STAMINA_EMPTY" in err_msg:
                    self.log.info("🛑 نفدت طاقة اللورد.")
                    break
                if "NO_HEROES" in err_msg:
                    self.log.info("🛑 لا يتوفر أبطال شاغرون بالقلعة.")
                    break
                # 8026 = حشد نشط على هذا العفريت بالفعل
                if "8026" in err_msg:
                    self.log.warning(
                        f"⚠️ يوجد حشد جماعي نشط لك بالفعل ضد هذا العفريت ({bx-1}, {by-1}) فئة {btype} — "
                        "إضافته لقائمة الأهداف المستهدفة والبحث عن عفريت آخر..."
                    )
                    retry_wait = round(random.uniform(2.0, 3.5), 2)
                    self.log.info(f"🛡️ [أمان] انتظار {retry_wait:.1f} ثانية قبل إعادة البحث...")
                    await asyncio.sleep(retry_wait)
                    continue
                # 8002 = العفريت اختفى أو انتهى
                if "8002" in err_msg:
                    self.log.warning(f"⚠️ العفريت ({bx-1}, {by-1}) فئة {btype} لم يعد متاحاً على الخريطة.")
                    retry_wait = round(random.uniform(1.5, 2.5), 2)
                    self.log.info(f"🛡️ [أمان] انتظار {retry_wait:.1f} ثانية قبل إعادة البحث...")
                    await asyncio.sleep(retry_wait)
                    continue
                if consecutive_errors >= 4:
                    self.log.warning("⚠️ 4 أخطاء متتالية — إيقاف الهجوم.")
                    break

        boss_desc = "نخبة العفريت (فئة 10)" if self.boss_type == 10 else f"العفريت (فئة {self.boss_type})"
        if successful_attacks > 0:
            msg = f"✅ تم الهجوم بـ ({successful_attacks}) فيلق ضد {boss_desc} بنجاح! 🎉"
            return TaskResult.ok(msg, status="success", attacks=successful_attacks, boss_type=self.boss_type)
        else:
            msg = f"⚠️ لم يتم إرسال أي فيلق ضد {boss_desc} (السبب: {last_error})"
            return TaskResult.fail(msg, error=last_error, boss_type=self.boss_type)


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
            task._used_army.clear()
            task._targeted_bosses.clear()
            task._targeted_boss_ids.clear()
            await task._load_heroes()
            task._detect_busy_heroes()

        await conn.close()

    asyncio.run(_main())

