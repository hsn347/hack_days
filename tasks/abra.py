# -*- coding: utf-8 -*-
"""
tasks/abra.py — مهمة الهجوم على وحش الذهب (Abra Boss / God Beast Attack Task)
═════════════════════════════════════════════════════════════════════════════════

بروتوكول فحص ومهاجمة وحش الذهب (Abra / God Beast):
  1. التحقق من تواجد الحدث واليوم:
     - الحدث يقام أسبوعياً كل إثنين وأربعاء (Monday & Wednesday).
     - التحقق الاستباقي من السيرفر عبر استعلام 1087/3 (God Beast Member Info).
     - فحص وجود الوحش فعلياً على الخريطة عبر 1006/15 ومطابقة نقاط دمه المتبقية (leftLife).
  2. فحص الهجمات المتبقية للقلعة:
     - الحد الأقصى للهجمات اليومية المسموح بها للقلعة الواحدة هو 20 هجمة.
  3. استراتيجية الضربة القاضية (Killing Blow Strategy):
     - إذا فعّل المستخدم "أخذ الضربة القاضية": يستمر بالهجوم حتى نفاذ الهجمات الـ 20 أو القضاء على الوحش.
     - إذا عطّل المستخدم "أخذ الضربة القاضية": يتوقف الهجوم فوراً عند وصول دم الوحش إلى 1,350,000 أو أقل
       للحفاظ على الضربة الأخيرة لقلعة أخرى تابعة للمستخدم.
  4. إرسال الهجوم الفردي المباشر (Solo March):
     cmd: "1007", subcmd: "2", data: {
         "needSend": false,
         "mapId": map_id,
         "moveLineType": 1,
         "matrixType": 1,
         "data": {
             "data": {},
             "to": {"x": x, "y": y, "id": f"{x+1}-{y+1}-25-0-4302"},
             "army": [...]
         },
         "heros": [...],
         "pets": [...],
         "runePages": [1]
     }
     python tasks/abra.py --email "johan2003@yopmail.com" -x 479 -y 387 --no-killing-blow --formation 1

     - إرسال فيلق واحد في كل مرة مع الانتظار حتى وصوله للوحش وتحديث نقاط الدم،
       لتجنب توجيه الضربة القاضية بالخطأ.
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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection
from tasks.monster import (
    _pick_combat_heroes,
    select_combat_army,
    calculate_castle_march_capacity,
    get_unit_power,
    get_unit_tier,
)

# ── الثوابت الأساسية لوحش الذهب (Abra) ──
ABRA_MAP_TYPE         = 25     # mapTypeGodBeast = 25
ABRA_CLASS_ID_NORMAL  = 4302   # وحش الذهب العادي
ABRA_CLASS_ID_SPECIAL = 4301   # وحش الذهب الخاص
MAX_DAILY_ATTACKS     = 20     # الحد الأقصى اليومي للهجمات للقلعة
KILL_BLOW_THRESHOLD   = 1350000# حد التوقف عند عدم الرغبة بالضربة القاضية (1.35 مليون دم)


class ReturningMarch:
    """معلومات الفيلق العائد إلى القلعة في الخلفية."""
    __slots__ = ("qid", "heroes", "finish_time")

    def __init__(self, qid: str, heroes: List[int], finish_time: float):
        self.qid = qid
        self.heroes = heroes
        self.finish_time = finish_time


class AbraTask(BaseTask):
    """
    مهمة الهجوم على وحش الذهب Abra على الخريطة في أيام الحدث (إثنين وأربعاء)
    مع التحكم الدقيق في إحداثيات الهدف واستهلاك الهجمات والضربة القاضية،
    ودعم استبدال الأبطال المنشغلين والجنود المكافئين آلياً.
    """
    name = "abra"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.target_x       : int  = int(self.config.get("x", 0) or 0)
        self.target_y       : int  = int(self.config.get("y", 0) or 0)
        self.killing_blow   : bool = bool(self.config.get("killing_blow", False))
        self.formation_id   : int  = int(self.config.get("formation_id", self.config.get("formation", 1)) or 1)
        self.stop_threshold : int  = int(self.config.get("stop_hp_threshold", KILL_BLOW_THRESHOLD))
        self.class_id       : int  = int(self.config.get("class_id", ABRA_CLASS_ID_NORMAL))

        self._map_id        : int  = 0
        self._castle_x      : int  = 0
        self._castle_y      : int  = 0
        self._heroes        : List[Dict[str, Any]] = []
        self._busy_heroes   : Set[int] = set()

    async def on_start(self):
        """تهيئة بيانات الخريطة وموقع القلعة وقائمة الأبطال."""
        await self._load_castle_coords()
        await self._load_map_id()
        await self._load_heroes()

    def _resolve_map_id(self) -> int:
        """جلب معرف الخريطة والمملكة تلقائياً."""
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

    def _get_lord_stamina(self) -> int:
        """جلب رصيد طاقة اللورد الحالي من بيانات القلعة المحملة (lordInfoCtrl.base.health)."""
        try:
            if not hasattr(self.conn, 'init_data') or not self.conn.init_data:
                return 100
            init = self.conn.init_data
            base = (
                init.get('lordInfoCtrl', {}).get('base', {})
                or init.get('loginDataInitCtrl', {}).get('base', {})
            )
            val = base.get('health')
            if val is not None:
                return int(float(val))
            return 100
        except Exception:
            return 100

    async def _load_map_id(self):
        self._map_id = self._resolve_map_id()
        if not self._map_id:
            uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
            try:
                self.log.debug("🛑🛑🛑🛑🛑🛑🛑 جاري استدعاء 1002/7")
                r_player = await self.conn.query('1002', '7', {"uid": uid_int}, timeout=4)
                if r_player and 'data' in r_player:
                    part = r_player['data'].get('base', {}).get('partition')
                    if part and str(part).isdigit() and int(part) > 0:
                        self._map_id = int(part)
            except Exception:
                pass

    async def _load_castle_coords(self):
        # 1. قراءة فورية من الذاكرة الحية
        pos = self.conn.init_data.get('cityCtrl', {}).get('cinfo', {}).get('pos', {})
        if pos and 'x' in pos and 'y' in pos:
            self._castle_x = int(pos.get('x', 0))
            self._castle_y = int(pos.get('y', 0))
            return

        # 2. استعلام احتياطي لو كانت الذاكرة غير محملة
        self.log.debug("🛑🛑🛑🛑🛑🛑🛑")
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
        try:
            r_castle = await self.conn.query('1006', '25', {"uid": uid_int}, timeout=4)
            if r_castle and 'retData' in r_castle:
                self._castle_x = int(r_castle['retData'].get('x', 0))
                self._castle_y = int(r_castle['retData'].get('y', 0))
        except Exception:
            pass

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

    def _build_target_id(self, x: int, y: int, class_id: int) -> str:
        """بناء المعرف الشبكي للوحش على الخريطة: x+1-y+1-25-0-classId."""
        return f"{x + 1}-{y + 1}-{ABRA_MAP_TYPE}-0-{class_id}"

    async def get_monster_hp(self, x: int, y: int) -> Tuple[Optional[int], int]:
        """
        استعلام السيرفر لجلب نقاط دم الوحش الحالي عند الإحداثيات المحددة.
        يعيد: (نقاط_الدم, class_id_الفعلية).
        """
        # إزالة التكرار في معرفات الوحش لمنع إرسال طلبات مكررة لنفس الكائن
        seen_cids = set()
        cids_to_try = [cid for cid in (self.class_id, ABRA_CLASS_ID_NORMAL, ABRA_CLASS_ID_SPECIAL) if not (cid in seen_cids or seen_cids.add(cid))]

        for cid in cids_to_try:
            target_id = self._build_target_id(x, y, cid)
            try:
                # 1. إرسال مزامنة قطعة الخريطة أولاً لمطابقة تصرف اللعبة
                await self.conn.query('1006', '1000', {
                    "centerX": x,
                    "centerY": y,
                    "centerKid": self._map_id
                }, timeout=3)
            except Exception:
                pass
            
            await asyncio.sleep(round(random.uniform(0.65, 0.95), 2))

            try:
                # 2. استعلام تفاصيل كائن الخريطة 1006/15
                r_tile = await self.conn.query('1006', '15', {
                    "x": x,
                    "y": y,
                    "id": target_id,
                    "kingdomId": self._map_id
                }, timeout=4)

                if not r_tile:
                    continue

                hp = self._extract_hp_from_tile_response(r_tile)
                if hp is not None:
                    return hp, cid
            except Exception as e:
                self.log.debug(f"خطأ أثناء استعلام تفاصيل الوحش {target_id}: {e}")

        return None, self.class_id

    def _extract_hp_from_tile_response(self, resp: dict) -> Optional[int]:
        """استخراج قيمة leftLife من استجابة السيرفر بشكل مرن."""
        if not isinstance(resp, dict):
            return None
        for container in (resp.get('data'), resp.get('retData'), resp):
            if not isinstance(container, dict):
                continue
            if 'leftLife' in container:
                try:
                    return int(container['leftLife'])
                except Exception:
                    pass
            boss = container.get('boss')
            if isinstance(boss, dict) and 'leftLife' in boss:
                try:
                    return int(boss['leftLife'])
                except Exception:
                    pass
            for key in ('bossData', 'npc', 'instance'):
                obj = container.get(key)
                if isinstance(obj, dict) and 'leftLife' in obj:
                    try:
                        return int(obj['leftLife'])
                    except Exception:
                        pass
        return None

    async def get_daily_attack_count(self) -> int:
        """جلب عدد الهجمات اليومية من الذاكرة الحية (Zero-Request)."""
        # 1. قراءة فورية من الذاكرة الحية (RAM)
        gb_ctrl = self.conn.init_data.get('godBeastCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        if isinstance(gb_ctrl, dict) and gb_ctrl:
            person = gb_ctrl.get('godbeastperson', {})
            if isinstance(person, dict) and 'attackNum' in person:
                return int(person['attackNum'])

        # 2. استعلام احتياطي فقط إذا لم تكن الذاكرة محملة
        try:
            self.log.debug("🛑🛑🛑🛑🛑🛑🛑 جاري استدعاء 1087/3")
            r = await self.conn.query('1087', '3', {}, timeout=4)
            if r and isinstance(r.get('data'), dict):
                member_data = r['data'].get('memberdata') or r['data']
                if isinstance(member_data, dict) and 'attackNum' in member_data:
                    return int(member_data['attackNum'])
        except Exception:
            pass

        return 0

    async def _load_formation(self, fid: int) -> Tuple[List[int], List[int], List[int], Dict[int, int]]:
        """استخراج بيانات التشكيلة من الذاكرة الحية فورياً بصفر طلبات شبكية."""
        fid_str = str(fid)
        heroes, pets, runes, army_dict = [], [], [1], {}

        # 1. قراءة فورية من الذاكرة الحية (RAM)
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        data = army_ctrl if (isinstance(army_ctrl, dict) and 'compileArmy' in army_ctrl) else {}

        # 2. استعلام احتياطي فقط إذا لم تكن التشكيلة مخزنة بالذاكرة
        if not data:
            try:
                self.log.debug("🛑🛑🛑🛑🛑🛑🛑 جاري استدعاء 1005/7")
                resp = await self.conn.query('1005', '7', {"compiletype": fid}, timeout=4)
                if resp and resp.get('data'):
                    data = resp.get('data', {})
            except Exception:
                pass

        if not data:
            return heroes, pets, runes, army_dict

        # 1. الأبطال
        raw_heroes = data.get('compileHeros', [])
        if isinstance(raw_heroes, dict):
            raw_heroes = raw_heroes.get(fid_str, raw_heroes.get(1, []))
        if isinstance(raw_heroes, list):
            heroes = [int(h) for h in raw_heroes if str(h).isdigit() and int(h) > 0]

        # 2. الحيوانات
        raw_pets = data.get('compilePets', [])
        if isinstance(raw_pets, dict):
            raw_pets = raw_pets.get(fid_str, raw_pets.get(1, []))
        if isinstance(raw_pets, list):
            pets = [int(p) for p in raw_pets if str(p).isdigit() and int(p) > 0]

        # 3. الرونات
        raw_runes = data.get('compileRunePages', [1])
        if isinstance(raw_runes, dict):
            raw_runes = raw_runes.get(fid_str, [1])
        if isinstance(raw_runes, list) and raw_runes:
            runes = [int(r) for r in raw_runes if str(r).isdigit() and int(r) > 0] or [1]

        # 4. الجيش
        raw_army = data.get('compileArmy', {})
        if isinstance(raw_army, dict) and fid_str in raw_army:
            raw_army = raw_army[fid_str]
        if isinstance(raw_army, dict):
            for k, v in raw_army.items():
                if str(k).isdigit() and str(v).isdigit() and int(v) > 0:
                    army_dict[int(k)] = int(v)

        return heroes, pets, runes, army_dict

    def _resolve_combat_heroes(self, form_heroes: List[int]) -> List[int]:
        """
        التحقق الذكي من توفر أبطال التشكيلة أو اختيار بدائل حرب مكافئة:
        1. إذا كان بطلا التشكيلة متاحين وغير مشغولين -> اعتمادهما فوراً.
        2. إذا كان أحدهما متاحاً والآخر مشغولاً -> إبقاء المتاح واستدعاء أفضل بطل حرب بديل (5501xxx) شاغر.
        3. إذا كان كلاهما مشغولين (أو التشكيلة فارغة) -> استدعاء أفضل بطلي حرب بديلين (5501xxx) متاحين بالقلعة.
        ملاحظة: استبعاد أبطال الجمع (5502xxx) والدعم (5503xxx) والمشغولين في مسيرات أخرى تماماً.
        """
        available_form_heroes: List[int] = []
        for h in form_heroes:
            if h and str(h).isdigit():
                hid = int(h)
                if hid not in self._busy_heroes:
                    h_data = next((x for x in self._heroes if isinstance(x, dict) and x.get('id') == hid), None)
                    if h_data and h_data.get('status', {}).get('state', 0) == 0:
                        available_form_heroes.append(hid)

        # حالة 1: كلا بطلي التشكيلة متاحين
        if len(available_form_heroes) >= 2:
            chosen = available_form_heroes[:2]
            self.log.info(f"🎖️ تم اعتماد بطلي التشكيلة #{self.formation_id}: {chosen}")
            return chosen

        # حالة 2: بطل واحد من التشكيلة متاح والآخر مشغول
        if len(available_form_heroes) == 1:
            h1 = available_form_heroes[0]
            extra_busy = set(self._busy_heroes) | {h1}
            filler = _pick_combat_heroes(self._heroes, max_count=1, busy=extra_busy)
            if filler:
                chosen = [h1, filler[0]]
                self.log.info(f"ℹ️ تم إبقاء بطل التشكيلة #{self.formation_id} ({h1}) واستبدال البطل المنشغل بأفضل بطل حرب بديل ({filler[0]}): {chosen}")
                return chosen
            else:
                self.log.info(f"ℹ️ بطل واحد من التشكيلة متاح ({h1}) ولا توجد بدائل حرب متاحة: {[h1]}")
                return [h1]

        # حالة 3: كلاهما مشغولان أو التشكيلة فارغة من الأبطال
        war_heroes = _pick_combat_heroes(self._heroes, max_count=2, busy=self._busy_heroes)
        if war_heroes:
            if form_heroes:
                self.log.info(f"⚠️ أبطال التشكيلة #{self.formation_id} مشغولون — تم استدعاء أفضل أبطال الحرب المتاحين بالقلعة: {war_heroes}")
            else:
                self.log.info(f"⚔️ تم اختيار أفضل أبطال الحرب المتاحين بالقلعة: {war_heroes}")
            return war_heroes

        # خطة طوارئ: أي بطل متاح بالقلعة غير أبطال الجمع والدعم
        any_cands = [
            int(h['id']) for h in self._heroes
            if isinstance(h, dict) and h.get('id')
            and int(h['id']) not in self._busy_heroes
            and not (str(h['id']).startswith('5502') or str(h['id']).startswith('5503'))
            and h.get('status', {}).get('state', 0) == 0
        ]
        if any_cands:
            chosen = any_cands[:2]
            self.log.warning(f"⚠️ بديل اضطراري: تم اختيار أبطال متاحين بالقلعة ({chosen})")
            return chosen

        return []

    async def ensure_connection(self, max_retries: int = 5, wait_sec: int = 10) -> bool:
        """
        التحقق الصارم من صحة الاتصال وإعادة الاتصال التلقائي عند انقطاعه (WinError 10054 / connection_lost):
        1. فحص self.is_connected
        2. إذا انقطع: إغلاق المقبس الميت، وانتظار مهلة أمان قصيرة، وإعادة طلب conn.connect().
        3. انتظار حزم التهيئة الأساسية (cityCtrl, heroCtrl).
        4. إعادة شحن الأبطال وبيانات القلعة لمتابعة الهجمات دون أي اضطراب.
        """
        if self.is_connected:
            return True

        self.log.warning("⚠️ [انقطاع الاتصال] رُصد انقطاع الاتصال بالسيرفر أثناء مهمة Abra — جاري إعادة الاتصال التلقائي...")
        for attempt in range(1, max_retries + 1):
            if self.is_stopped():
                return False
            try:
                await self.conn.close()
            except Exception:
                pass

            self.log.info(f"⏳ [محاولة {attempt}/{max_retries}] انتظار {wait_sec}ث قبل إعادة الدخول...")
            await asyncio.sleep(round(wait_sec + random.uniform(0.5, 2.5), 2))

            try:
                ok = await self.conn.connect()
            except Exception as e:
                self.log.warning(f"❌ استثناء أثناء إعادة الاتصال: {e}")
                ok = False

            if ok:
                # انتظار حزم التهيئة
                for _ in range(25):
                    if len(getattr(self.conn, 'init_data', {})) > 0 and ("cityCtrl" in self.conn.init_data or "heroCtrl" in self.conn.init_data):
                        break
                    await asyncio.sleep(round(random.uniform(0.2, 0.45), 2))
                # إعادة شحن الأبطال والإحداثيات
                try:
                    await self._load_castle_coords()
                    await self._load_heroes()
                except Exception:
                    pass
                self.log.info("✅ تم استعادة الاتصال بالسيرفر بنجاح واستئناف مهمة Abra!")
                return True
            else:
                self.log.warning(f"❌ فشلت المحاولة {attempt} لإعادة الاتصال بالسيرفر.")

        return False

    async def _get_available_troops(self) -> Dict[int, int]:
        """استخراج الرصيد الحالي للقوات من الذاكرة الحية فورياً بصفر طلبات شبكية."""
        available: Dict[int, int] = {}

        # 1. قراءة فورية من الذاكرة الحية (RAM)
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        total_army = army_ctrl.get('totalArmy', {}) if isinstance(army_ctrl, dict) else {}

        if isinstance(total_army, dict) and total_army:
            for k, v in total_army.items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)
            return available

        # 2. استعلام احتياطي فقط إذا لم تكن الذاكرة محملة أو بعد انقطاع الاتصال
        try:
            self.log.debug("🛑🛑🛑🛑🛑🛑🛑 جاري استدعاء 1005/1 للجيش")
            r_army = await self.conn.query('1005', '1', {}, timeout=4)
            if r_army and 'data' in r_army:
                for k, v in r_army['data'].get('totalArmy', {}).items():
                    if str(k).isdigit() and str(v).isdigit():
                        available[int(k)] = int(v)
        except Exception as e:
            self.log.debug(f"خطأ أثناء استعلام 1005/1 للجيش: {e}")

        return available

    async def _resolve_combat_army(
        self,
        form_army_dict: Dict[int, int],
        chosen_heroes: List[int]
    ) -> List[Dict[str, int]]:
        """
        تجهيز جيش القتال المتكامل مع استبدال الجنود المكافئين:
        1. استعلام القوات المتاحة بالقلعة (1005/1).
        2. حساب سعة المسيرة القصوى الحقيقية للقلعة (castle_capacity) بموجب ساحة التدريب وبونص الأبطال.
        3. لكل نوع وحدة في التشكيلة:
           - سحب المتوفر منها بالقلعة.
           - في حال وجود عجز، استبدال النقص بوحدات مكافئة من نفس الفئة العسكرية:
             * المشاة: 401..414
             * الفرسان: 501..514
             * الرماة: 601..614
             * العربات: 701..714
             مرتبة من أعلى رتبة (Tier) وقوة قتالية إلى الأدنى.
        4. في حال بقاء أي عجز في سعة المسيرة، يتم استكمال الفيلق عبر select_combat_army
           لضمان إرسال فيلق بأقصى طاقة قتالية ممكنة دون أي إهدار للسعة.
        """
        available = await self._get_available_troops()
        castle_capacity = calculate_castle_march_capacity(
            init_data=self.conn.init_data,
            heroes_info=self._heroes,
            chosen_hero_ids=chosen_heroes
        )

        # استبعاد فخاخ الجدار وأسلحة الدفاع (800..899)
        clean_form_dict = {
            tid: num for tid, num in form_army_dict.items()
            if not (800 <= tid < 900) and num > 0
        }
        total_form_req = sum(clean_form_dict.values())

        army_map: Dict[int, int] = {}
        substitutions_made = 0

        if clean_form_dict:
            # وزن التشكيلة إذا كانت تتجاوز سعة المسيرة القصوى للقلعة
            scale = 1.0
            if total_form_req > castle_capacity:
                scale = float(castle_capacity) / float(total_form_req)
                target_req = castle_capacity
                self.log.debug(
                    f"🛡️ جنود التشكيلة #{self.formation_id} ({total_form_req:,}) يتجاوز سعة مسيرة اللورد ({castle_capacity:,}) — تم ضبطها بنسبة {scale:.2%}"
                )
            else:
                target_req = total_form_req

            for tid, raw_req in clean_form_dict.items():
                req = max(1, int(raw_req * scale)) if scale < 1.0 else raw_req
                avail = available.get(tid, 0)
                take = min(req, avail)
                if take > 0:
                    army_map[tid] = army_map.get(tid, 0) + take
                    available[tid] -= take

                deficit = req - take
                if deficit > 0:
                    # ── استبدال مكافئ من نفس الفئة العسكرية (Same military branch) ──
                    branch_prefix = tid // 100  # 4=مشاة, 5=فرسان, 6=رماة, 7=عربات
                    # البحث عن جميع وحدات نفس الفئة المتوفرة بالقلعة
                    candidates = [
                        cand_id for cand_id, cnt in available.items()
                        if cnt > 0
                        and (cand_id // 100 == branch_prefix)
                        and not (800 <= cand_id < 900)
                        and cand_id != tid
                    ]
                    # ترتيب البدائل بالأعلى رتبة وقوة قتالية أولاً
                    candidates.sort(key=lambda c: (get_unit_power(c), c), reverse=True)

                    for cand in candidates:
                        cand_avail = available.get(cand, 0)
                        if cand_avail <= 0:
                            continue
                        sub_take = min(deficit, cand_avail)
                        if sub_take > 0:
                            army_map[cand] = army_map.get(cand, 0) + sub_take
                            available[cand] -= sub_take
                            deficit -= sub_take
                            substitutions_made += sub_take
                            if deficit <= 0:
                                break

            current_troops_count = sum(army_map.values())
            # إذا بقي عجز عن سعة الهدف المطلوب (target_req)، إكماله بجيش قتالي متوازن
            remaining_deficit = max(0, min(target_req, castle_capacity) - current_troops_count)
            if remaining_deficit > 0:
                balanced_extra = select_combat_army(available, needed_count=remaining_deficit)
                for item in balanced_extra:
                    it_id = item['id']
                    it_num = item['num']
                    army_map[it_id] = army_map.get(it_id, 0) + it_num
                    available[it_id] = max(0, available.get(it_id, 0) - it_num)
        else:
            # التشكيلة فارغة بالكامل: تكوين جيش قتالي متوازن تلقائي حتى كامل سعة المسيرة
            self.log.info(f"⚠️ التشكيلة #{self.formation_id} لا تحتوي على جيش محفوظ، تكوين جيش قتالي متوازن تلقائياً...")
            balanced_army = select_combat_army(available, needed_count=castle_capacity)
            for item in balanced_army:
                army_map[item['id']] = item['num']

        final_army = [{"id": tid, "num": num} for tid, num in army_map.items() if num > 0]
        total_selected = sum(item['num'] for item in final_army)

        if substitutions_made > 0:
            self.log.info(
                f"🔄 تم تعويض نقص بعض وحدات التشكيلة بوحدات مكافئة من نفس الفئة ({substitutions_made:,} جندي تم استبدالهم) | إجمالي الفيلق: {total_selected:,}/{castle_capacity:,}"
            )
        elif final_army and total_form_req > 0:
            self.log.info(f"🛡️ تم تجهيز جيش التشكيلة #{self.formation_id} بالكامل ({total_selected:,}/{castle_capacity:,} جندي)")
        else:
            self.log.info(f"⚔️ تم تشكيل جيش قتالي متوازن جاهز للهجوم ({total_selected:,}/{castle_capacity:,} جندي)")

        return final_army

    async def _wait_for_outbound_hit(self, queue_id: str, one_way_seconds: int = 60) -> Optional[int]:
        """الانتظار المنضبط لمسيرة الذهاب فقط حتى وصول الفيلق للوحش وتوجيه الضربة وقراءة دم الوحش المحدث مع نبضات حية للإبقاء على الاتصال."""
        one_way = max(20, int(one_way_seconds))
        self.log.info(f"⏳ مسيرة الذهاب نحو الوحش بدأت (المدة المقدرة للوصول: {one_way}ث)...")

        waited = 0
        while waited < one_way + 2:
            if self.is_stopped():
                return None
            step = min(15, (one_way + 2) - waited)
            await asyncio.sleep(step)
            waited += step

            rem = (one_way + 2) - waited
            if rem > 5:
                self.log.info(f"⏳ الفيلق في الطريق نحو الوحش... متبقي {rem}ث على الضربة.")

        # انتظار وجيز لتسجيل الضرر في خادم اللعبة مع تشتيت النمط
        await asyncio.sleep(round(random.uniform(1.2, 2.2), 2))

        # التحقق من سلامة الاتصال قبل استعلام دم الوحش بعد الضربة
        if not self.is_connected:
            await self.ensure_connection()

        # استعلام دم الوحش فور وقوع الضربة
        hp_after_hit, _ = await self.get_monster_hp(self.target_x, self.target_y)
        if hp_after_hit is not None:
            self.log.info(f"💥 وقعت الضربة بنجاح وسجل السيرفر الضرر! دم الوحش الآن: {hp_after_hit:,}")

        return hp_after_hit

    async def _wait_for_returning_march(self, queue_id: str, finish_time: float):
        """الانتظار حتى دخول الفيلق العائد إلى القلعة بالكامل وتفريغ قواته وأبطاله مع نبضات حية للإبقاء على الاتصال."""
        now = time.time()
        while now < finish_time:
            if self.is_stopped():
                return
            rem = int(finish_time - now)
            if rem > 15:
                self.log.info(f"🔙 الفيلق في طريق العودة... متبقي {rem}ث لدخول القلعة.")
            step = min(15, max(1, rem))
            await asyncio.sleep(step)

            now = time.time()
        self.log.info("🏠 وصلت القوات بالكامل إلى القلعة وأصبحت التشكيلة جاهزة للهجمة التالية.")
        await asyncio.sleep(round(random.uniform(0.8, 1.8), 2))

    async def run(self) -> TaskResult:
        """تنفيذ مهمة الهجوم على الوحش Abra بنظام التدفق المتتابع السريع (Pipelined Marching)."""
        # 0. تهيئة بيانات الخريطة ومعرف المملكة وموقع القلعة والأبطال
        await self.on_start()
        if not self._map_id and self.conn.kingdom_id:
            try:
                self._map_id = int(self.conn.kingdom_id)
            except Exception:
                pass

        # 1. التحقق من الإحداثيات المدخلة
        if self.target_x <= 0 or self.target_y <= 0:
            msg = f"⚠️ إحداثيات الوحش Abra غير صالحة ({self.target_x}, {self.target_y}) — يرجى تحديد موقع الوحش بالخريطة من الواجهة."
            self.log.warning(msg)
            return TaskResult.fail(msg, status="target_not_found")

        # 1.5 فحص طاقة اللورد (الحالة 6: نفاذ طاقة اللورد)
        lord_stamina = self._get_lord_stamina()
        if lord_stamina < 10:
            msg = f"🛑 [الحالة 6: نفاذ طاقة اللورد] طاقة اللورد الحالية ({lord_stamina}) غير كافية لمهاجمة الوحش Abra (مطلوب 10 على الأقل)."
            self.log.warning(msg)
            return TaskResult.ok(msg, status="stamina_empty", stamina=lord_stamina)

        # 2. فحص اليوم والحدث (إثنين وأربعاء)
        now_utc = datetime.now(timezone.utc)
        # weekday: 0 = الإثنين (Monday), 2 = الأربعاء (Wednesday)
        is_event_day = bool(self.config.get("force", False)) or (now_utc.weekday() in (0, 2))

        # 3. فحص تواجد الوحش فعلياً ونقاط دمه
        initial_hp, actual_cid = await self.get_monster_hp(self.target_x, self.target_y)
        if initial_hp is None:
            if not is_event_day:
                msg = "⏭️ تم تخطي مهمة Abra: اليوم ليس يوم الحدث (يقام كل إثنين وأربعاء)، ولم يُعثر على الوحش."
                self.log.info(msg)
                return TaskResult.ok(msg, status="skipped", skipped=True)
            msg = f"⚠️ [الحالة 4: خطأ بالهدف] لم يتم العثور على وحش Abra عند الإحداثيات ({self.target_x}, {self.target_y}) على الخريطة."
            self.log.warning(msg)
            return TaskResult.fail(msg, status="target_not_found")

        if initial_hp <= 0:
            msg = f"🏆 [الحالة 4: الهدف مكتمل] الوحش Abra عند ({self.target_x}, {self.target_y}) ميت بالفعل (نقاط الدم = 0)."
            self.log.info(msg)
            return TaskResult.ok(msg, status="defeated", defeated=True)

        # 4. فحص شرط الضربة القاضية مبدئياً
        if not self.killing_blow and initial_hp <= self.stop_threshold:
            msg = f"🛑 [الحالة 5: أمان الضربة القاضية] دم الوحش ({initial_hp:,}) أقل من أو يساوي الحد الآمن ({self.stop_threshold:,}) لحفظ الضربة لقلعة أخرى."
            self.log.info(msg)
            return TaskResult.ok(msg, status="safe_hp_stop", stopped_early=True, current_hp=initial_hp)

        # 5. استعلام عدد الهجمات المنجزة اليوم
        attacks_done = await self.get_daily_attack_count()
        if attacks_done >= MAX_DAILY_ATTACKS:
            msg = f"🛑 [الحالة 5: اكتمال الهجمات] تم استهلاك جميع الهجمات المسموح بها اليوم ضد الوحش Abra ({attacks_done}/{MAX_DAILY_ATTACKS})."
            self.log.info(msg)
            return TaskResult.ok(msg, status="attacks_completed", attacks_completed=True)

        target_id = self._build_target_id(self.target_x, self.target_y, actual_cid)
        self.log.info(
            f"🐉 بدء مهمة الهجوم على الوحش Abra عند ({self.target_x}, {self.target_y}) "
            f"| دم الوحش: {initial_hp:,} | الهجمات المنفذة سابقاً: {attacks_done}/{MAX_DAILY_ATTACKS} "
            f"| خيار الضربة القاضية: {'مفعل' if self.killing_blow else f'معطل (توقف عند {self.stop_threshold:,})'}..."
        )

        # 6. جلب التشكيلة المحددة
        form_heroes, form_pets, form_runes, form_army_dict = await self._load_formation(self.formation_id)

        session_attacks = 0
        current_hp = initial_hp
        returning_marches: List[ReturningMarch] = []

        # سقف طوابير المسيرات للقلعة (يبدأ من إعدادات القلعة إن وُجدت، أو 6 افتراضياً ويتكيف ذاتياً عند ظهور 8004)
        configured_max_q = int(self.config.get("max_queues", 0)) if isinstance(self.config, dict) else 0
        max_castle_queues = configured_max_q if configured_max_q > 0 else (getattr(self.conn, 'max_queues', 6) or 6)

        def cleanup_returned_marches():
            nonlocal returning_marches
            now = time.time()
            still_returning = []
            for m in returning_marches:
                if now >= m.finish_time:
                    self._busy_heroes.difference_update(m.heroes)
                else:
                    still_returning.append(m)
            returning_marches = still_returning

        # 7. حلقة الهجوم (نظام التدفق المتتابع السريع - Pipelined Marching)
        while attacks_done < MAX_DAILY_ATTACKS and not self.is_stopped():
            # التحقق من سلامة الاتصال بالسيرفر واستعادته فوراً إذا انقطع
            if not self.is_connected:
                ok = await self.ensure_connection()
                if not ok:
                    msg = "❌ تعذر استعادة الاتصال بالسيرفر أثناء دورات هجمات Abra."
                    self.log.error(msg)
                    return TaskResult.fail(msg, status="disconnected")

            # تنظيف أي فيالق دخلت القلعة في هذه الأثناء
            cleanup_returned_marches()

            # فحص دم الوحش الحالي
            cur_hp, _ = await self.get_monster_hp(self.target_x, self.target_y)
            if cur_hp is not None:
                current_hp = cur_hp

            if current_hp <= 0:
                self.log.info("🏆 تم القضاء على الوحش Abra بالكامل!")
                break

            # ── أمان الضربة القاضية الصارم (Killing Blow Safety Check) ──
            if not self.killing_blow and current_hp <= self.stop_threshold:
                self.log.info(
                    f"🛑 [أمان الضربة القاضية] تم إيقاف الهجمات فوراً: دم الوحش ({current_hp:,}) وصل إلى أقل من أو يساوي الحد الآمن ({self.stop_threshold:,}) "
                    f"وتم تعطيل أخذ الضربة القاضية للحفاظ عليها لقلعة أخرى."
                )
                break

            # فحص طاقة اللورد قبل إطلاق الهجمة (الحالة 6)
            lord_stamina = self._get_lord_stamina()
            if lord_stamina < 10:
                self.log.warning(f"🔋 [الحالة 6: نفاذ طاقة اللورد] نفدت طاقة اللورد ({lord_stamina}) أثناء الهجمات — إنهاء مهمة Abra والانتقال للأولويات التالية.")
                break

            # فحص جاهزية الفيلق
            active_marches = await self.get_active_marches_count()

            # اختيار أبطال الحرب وحل البدائل ديناميكياً
            march_heroes = self._resolve_combat_heroes(form_heroes)
            if not march_heroes or active_marches >= max_castle_queues:
                if returning_marches:
                    nearest = returning_marches[0]
                    wait_sec = max(2, int(nearest.finish_time - time.time()))
                    self.log.info(
                        f"⏳ جميع الفيالق أو أبطال الحرب مشغولون حالياً ({active_marches}/{max_castle_queues})، "
                        f"انتظار {wait_sec}ث حتى عودة أقرب فيلق للقلعة وتفريغ قواته..."
                    )
                    await self._wait_for_returning_march(nearest.qid, nearest.finish_time)
                    cleanup_returned_marches()
                    await self._load_heroes()
                    continue
                else:
                    msg = "⚠️ لا يتوفر أي أبطال جاهزون بالقلعة لإرسال المسيرة نحو Abra."
                    self.log.warning(msg)
                    return TaskResult.fail(msg)

            # تجهيز الجيش واستبدال النقص بالجنود المكافئين
            march_army = await self._resolve_combat_army(form_army_dict, march_heroes)
            if not march_army:
                if returning_marches:
                    nearest = returning_marches[0]
                    wait_sec = max(2, int(nearest.finish_time - time.time()))
                    self.log.info(
                        f"⏳ نفدت القوات المتاحة بالقلعة مؤقتاً، "
                        f"انتظار {wait_sec}ث حتى عودة الفيلق السابق بالجنود..."
                    )
                    await self._wait_for_returning_march(nearest.qid, nearest.finish_time)
                    cleanup_returned_marches()
                    await self._load_heroes()
                    continue
                else:
                    msg = "🛑 [الحالة 3: انعدام القوات كلياً] لا تتوفر أي قوات قتالية بالقلعة ولا توجد مسيرات بالخارج تعود لمتابعة الهجوم."
                    self.log.warning(msg)
                    return TaskResult.fail(msg, status="critical_no_army")

            # تجهيز حمولة الهجوم المطابقة لبروتوكول اللعبة
            march_payload = {
                "needSend": False,
                "runePages": form_runes or [1],
                "heros": march_heroes,
                "matrixType": 1,
                "mapId": self._map_id,
                "moveLineType": 1,
                "data": {
                    "data": {},
                    "to": {
                        "x": self.target_x,
                        "y": self.target_y,
                        "id": target_id
                    },
                    "army": march_army
                },
                "pets": form_pets
            }

            self.log.info(
                f"⚔️ [هجمة {attacks_done + 1}/{MAX_DAILY_ATTACKS}] إرسال فيلق نحو Abra عند ({self.target_x}, {self.target_y}) "
                f"| نقاط دم الوحش قبل الضربة: {current_hp:,}..."
            )

            # إرسال الهجوم مع استبدال الأبطال فوراً إذا ظهر كود 9007020
            r_march = None
            qid = ""
            for attempt in range(10):
                r_march = await self.conn.query('1007', '2', march_payload, timeout=6)
                if r_march and str(r_march.get('err', '-1')) == '0':
                    r_data = r_march.get('data') or r_march.get('retData') or {}
                    if isinstance(r_data, dict):
                        q_obj = r_data.get('queue') if isinstance(r_data.get('queue'), dict) else {}
                        qid = str(q_obj.get('id') or r_data.get('queueId') or r_data.get('id') or "")
                    break

                err_code = str(r_march.get('err') if r_march else 'timeout')
                if err_code == '9007020':
                    self._busy_heroes.update(march_heroes)
                    alt_heroes = self._resolve_combat_heroes(form_heroes)
                    if alt_heroes and alt_heroes != march_heroes:
                        self.log.info(f"🔄 تم استبدال الأبطال المنشغلين بأبطال حرب بديلين فوراً ({alt_heroes}) وإعادة إرسال الهجوم...")
                        march_heroes = alt_heroes
                        march_payload["heros"] = march_heroes
                        continue
                    else:
                        if returning_marches:
                            nearest = returning_marches[0]
                            wait_sec = max(2, int(nearest.finish_time - time.time()))
                            self.log.info(f"⏳ أبطال الحرب مشغولون (كود 9007020)، انتظار {wait_sec}ث لعودة فيلق للقلعة...")
                            await self._wait_for_returning_march(nearest.qid, nearest.finish_time)
                            cleanup_returned_marches()
                            await self._load_heroes()
                            continue
                        else:
                            self.log.info(f"⏳ أبطال الحرب جميعهم مشغولون بالمسيرات (كود 9007020)، انتظار وإعادة المحاولة ({attempt + 1}/10)...")
                            await asyncio.sleep(round(random.uniform(13.0, 18.0), 2))
                            await self._load_heroes()
                            continue
                elif err_code in ('8004', '9007004'):
                    # السيرفر يرفض بسبب اكتمال طوابير المسيرات المتاحة للقلعة (QUEUE_FULL)
                    cur_act = await self.get_active_marches_count()
                    observed = max(1, cur_act if cur_act > 0 else len(returning_marches))
                    max_castle_queues = min(max_castle_queues, observed)
                    self.log.info(
                        f"⚠️ طوابير الفيالق ممتلئة بالكامل على السيرفر (كود 8004: ضبط سقف القلعة الفعلي={max_castle_queues})..."
                    )
                    if returning_marches:
                        nearest = returning_marches[0]
                        wait_sec = max(2, int(nearest.finish_time - time.time()))
                        self.log.info(
                            f"⏳ [الحالة 1: انتظار الفيلق العائد] الفيلق السابق في طريق العودة — "
                            f"انتظار {wait_sec}ث حتى دخول القلعة وتفريغ طابور المسيرة..."
                        )
                        await self._wait_for_returning_march(nearest.qid, nearest.finish_time)
                        cleanup_returned_marches()
                        await self._load_heroes()
                        continue
                    else:
                        self.log.info(f"⏳ طوابير الفيالق ممتلئة بالخارج (كود 8004)، انتظار وتحديث الطوابير ({attempt + 1}/10)...")
                        await asyncio.sleep(round(random.uniform(25.0, 35.0), 2))
                        continue
                elif err_code == '8009':
                    if returning_marches:
                        nearest = returning_marches[0]
                        wait_sec = max(2, int(nearest.finish_time - time.time()))
                        self.log.info(f"⏳ نفاد القوات مؤقتاً (كود 8009)، انتظار {wait_sec}ث لعودة الفيلق بالجنود...")
                        await self._wait_for_returning_march(nearest.qid, nearest.finish_time)
                        cleanup_returned_marches()
                        continue
                elif err_code in ('8032', '10002', '10003'):
                    self.log.warning(f"🛑 نفدت طاقة اللورد بالكامل لمتابعة هجمات Abra (كود {err_code}).")
                    return TaskResult.fail("🛑 نفدت طاقة اللورد بالكامل (STAMINA_EMPTY).")
                elif err_code == '16001':
                    wait_sec = round(random.uniform(10.0, 16.0), 2)
                    self.log.warning(
                        f"⏳ [خادم اللعبة مشغول - كود 16001] انتظار {wait_sec} ثانية لفك القفل "
                        f"ثم إعادة إرسال هجمة Abra ({attempt + 1}/10)..."
                    )
                    await asyncio.sleep(wait_sec)
                    continue
                else:
                    self.log.warning(f"⚠️ فشل إرسال هجمة Abra (كود الخطأ: {err_code})")
                    break

            if not r_march or str(r_march.get('err', '-1')) != '0':
                break

            attacks_done += 1
            session_attacks += 1
            self._busy_heroes.update(march_heroes)

            # حساب المسافة وزمن مسيرة الذهاب والعودة بالثواني
            dist = math.hypot(self.target_x - self._castle_x, self.target_y - self._castle_y)
            est_one_way = max(25, int(dist * 1.25))
            r_queue = (r_march.get('retData') or r_march.get('data') or {}).get('queue', {})
            if isinstance(r_queue, dict) and r_queue.get('realTotalTime'):
                est_one_way = int(r_queue['realTotalTime'])

            # 1. انتظار مسيرة الذهاب فقط حتى وصول الفيلق للوحش ووقوع الضربة
            hp_after_strike = await self._wait_for_outbound_hit(qid, one_way_seconds=est_one_way)
            if hp_after_strike is not None:
                current_hp = hp_after_strike

            # تسجيل الفيلق كفيلق عائد بالخلفية
            return_finish = time.time() + est_one_way + 3
            returning_marches.append(ReturningMarch(qid, march_heroes, return_finish))

            # 2. ── فحص الأمان الصارم للضربة القاضية فور وقوع الضربة وقبل إطلاق أي فيلق تالٍ ──
            if not self.killing_blow and current_hp <= self.stop_threshold:
                self.log.info(
                    f"🛑 [أمان الضربة القاضية] تم إيقاف الهجمات فوراً: دم الوحش ({current_hp:,}) "
                    f"وصل إلى أقل من أو يساوي الحد الآمن ({self.stop_threshold:,}). "
                    f"لن يتم إرسال أي فيلق جديد للحفاظ على الضربة الأخيرة لقلعة أخرى!"
                )
                break

            if current_hp <= 0:
                self.log.info("🏆 تم القضاء على الوحش Abra بالكامل!")
                break

            if attacks_done >= MAX_DAILY_ATTACKS:
                self.log.info(f"🛑 تم استهلاك جميع الهجمات المسموح بها اليوم ضد Abra ({attacks_done}/{MAX_DAILY_ATTACKS}).")
                break

            # 3. فحص إمكانية الهجوم المتتابع السريع (Pipeline Marching)
            cleanup_returned_marches()
            active_now = await self.get_active_marches_count()
            has_queue = active_now < max_castle_queues
            can_heroes = bool(self._resolve_combat_heroes(form_heroes))

            # التحقق من توفر قوات كافية بالقلعة لإطلاق مسيرة ثانية بالتوازي
            cur_avail_troops = await self._get_available_troops()
            total_avail = sum(cur_avail_troops.values())
            has_troops = total_avail >= 300

            # مهلة أمان عشوائية بين الضربة والمسيرة التالية لمحاكاة السلوك البشري
            await asyncio.sleep(round(random.uniform(2.2, 3.8), 2))

            if has_queue and can_heroes and has_troops:
                self.log.info(
                    f"🚀 [الهجوم المتتابع السريع] الفيلق السابق بدأ العودة (متبقي {est_one_way}ث)، "
                    f"وتتوفر فيالق شاغرة ({active_now}/{max_castle_queues}) وأبطال وجنود ({total_avail:,}) بالقلعة — إطلاق الهجمة التالية فوراً!"
                )
                # استمرار الدورة فوراً لإطلاق الفيلق التالي دون انتظار عودة السابق!
                continue
            else:
                # إذا كانت القوات بالخارج أو الأبطال مشغولين أو لا تتوفر طوابير إضافية، ننتظر عودة الفيلق
                if returning_marches:
                    nearest = returning_marches[0]
                    wait_sec = max(2, int(nearest.finish_time - time.time()))
                    if not has_queue:
                        self.log.info(
                            f"⏳ [الحالة 1: انتظار عودة الفيلق] طوابير القلعة مشغولة بالكامل ({active_now}/{max_castle_queues})، "
                            f"الانتظار {wait_sec}ث حتى عودة الفيلق السابق لدخول القلعة وتفريغ الطابور..."
                        )
                    elif not has_troops:
                        self.log.info(
                            f"⏳ [الحالة 1: انتظار عودة القوات] جنود القلعة بالكامل في المسيرة السابقة ({total_avail:,} متاح حالياً)، "
                            f"الانتظار {wait_sec}ث حتى عودة الفيلق لدخول القلعة وتفريغ القوات..."
                        )
                    else:
                        self.log.info(
                            f"⏳ [الحالة 1: انتظار الفيالق/الأبطال] الانتظار {wait_sec}ث حتى عودة الفيلق السابق لدخول القلعة وتفريغ القوات والأبطال..."
                        )
                    await self._wait_for_returning_march(nearest.qid, nearest.finish_time)
                    cleanup_returned_marches()
                    await self._load_heroes()

        final_hp, _ = await self.get_monster_hp(self.target_x, self.target_y)
        final_hp_val = final_hp if final_hp is not None else current_hp

        summary_msg = (
            f"✅ [الحالة 5: اكتمال المهمة] تم تنفيذ {session_attacks} هجمة بنجاح ضد Abra "
            f"(إجمالي اليوم: {attacks_done}/{MAX_DAILY_ATTACKS}) | دم الوحش المتبقي: {final_hp_val:,}"
        )
        self.log.info(summary_msg)
        return TaskResult.ok(
            summary_msg,
            status="completed",
            session_attacks=session_attacks,
            total_attacks=attacks_done,
            remaining_hp=final_hp_val
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر للمهمة من سطر الأوامر (مثل باقي المهام)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import json
    import os
    import sys

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    _CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    _PARENT_DIR = os.path.dirname(_CURRENT_DIR)
    for p in [_CURRENT_DIR, _PARENT_DIR, r"e:\osmanli"]:
        if p not in sys.path:
            sys.path.insert(0, p)

    parser = argparse.ArgumentParser(
        description="Empire Abra Boss Task — مهمة الهجوم على وحش الذهب Abra",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للقلعة المستهدفة")
    parser.add_argument("--password", "-p", help="كلمة المرور (اختياري إن كانت الجلسة محفوظة)")
    parser.add_argument("-x", type=int, help="إحداثي X للوحش على الخريطة")
    parser.add_argument("-y", type=int, help="إحداثي Y للوحش على الخريطة")
    parser.add_argument(
        "--killing-blow",
        dest="killing_blow",
        action="store_true",
        default=None,
        help="تفعيل أخذ الضربة القاضية (الهجوم حتى نفاذ الـ 20 هجمة أو موت الوحش)"
    )
    parser.add_argument(
        "--no-killing-blow",
        dest="killing_blow",
        action="store_false",
        help="تعطيل الضربة القاضية (التوقف فور وصول دم الوحش إلى 1,350,000 لحفظ الضربة لقلعة أخرى)"
    )
    parser.add_argument(
        "--formation", "--form", "-f",
        dest="formation",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        help="رقم التشكيلة (1 إلى 4) [افتراضي: 1 أو من إعدادات القلعة]"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="تجاوز فحص اليوم وتشغيل المهمة مباشرة حتى لو لم يكن اليوم إثنين أو أربعاء"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    logging.getLogger("game_conn").setLevel(logging.WARNING)
    logging.getLogger("game_client").setLevel(logging.WARNING)

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
            for em, a in accounts.items():
                if em.lower() == target_email.lower():
                    acc = a
                    target_email = em
                    break

        if not acc:
            print(f"❌ الحساب {target_email} غير موجود في الجلسات!")
            return

        print("═" * 68)
        print(f"🐉 بدء تشغيل مهمة وحش الذهب (Abra Boss) للحساب: {target_email}")
        print("═" * 68)

        target_x = args.x
        target_y = args.y
        killing_blow = args.killing_blow
        formation_id = args.formation

        # محاولة قراءة الإعدادات من قاعدة البيانات إن لم تكن ممررة
        try:
            from core.database import get_castle
            c_db = get_castle(target_email)
            if c_db:
                raw_c = c_db.get("config")
                if isinstance(raw_c, str):
                    try:
                        raw_c = json.loads(raw_c)
                    except Exception:
                        raw_c = {}
                if isinstance(raw_c, dict):
                    abra_c = raw_c.get("abra", {})
                    if target_x is None:
                        target_x = abra_c.get("x")
                    if target_y is None:
                        target_y = abra_c.get("y")
                    if killing_blow is None:
                        killing_blow = bool(abra_c.get("killing_blow", False))
                    if formation_id is None:
                        formation_id = abra_c.get("formation_id") or raw_c.get("march_manager", {}).get("combat", {}).get("formation_id", 1)
        except Exception:
            pass

        if target_x is None or target_y is None or target_x <= 0 or target_y <= 0:
            print("❌ إحداثيات الوحش غير محددة! يرجى تمرير -x و -y (مثال: -x 377 -y 480).")
            return

        if killing_blow is None:
            killing_blow = False

        if formation_id is None:
            formation_id = 1

        print(f"🎯 إحداثيات الوحش: ({target_x}, {target_y})")
        print(f"⚡ الضربة القاضية: {'نعم (حتى تصفير الدم)' if killing_blow else 'لا (التوقف عند 1,350,000 دم)'}")
        print(f"🛡️ رقم التشكيلة  : {formation_id}")
        print(f"🚀 تجاوز فحص اليوم: {'نعم (--force)' if args.force else 'لا'}")
        print("─" * 68)

        conn = GameConnection(acc)
        if not await conn.connect():
            print("❌ فشل الاتصال بخادم اللعبة!")
            return

        for _ in range(15):
            await asyncio.sleep(0.3)
            if len(conn.init_data) > 0 and ("cityCtrl" in conn.init_data or "lordInfoCtrl" in conn.init_data):
                break

        task_cfg = {
            "enabled": True,
            "x": target_x,
            "y": target_y,
            "killing_blow": killing_blow,
            "formation_id": formation_id,
            "force": args.force
        }

        task = AbraTask(conn, task_cfg)
        result = await task.run()

        print("\n" + "═" * 68)
        print(f"📊 النتيجة النهائية: {result.message}")
        print("═" * 68 + "\n")
        await conn.close()

    asyncio.run(_main())
