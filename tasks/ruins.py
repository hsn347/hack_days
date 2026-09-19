# -*- coding: utf-8 -*-
"""
tasks/ruins.py — مهمة استكشاف الأطلال (Relics / Ruins Exploration)
═════════════════════════════════════════════════════════════════

تُرسِل مسيرات لاستكشاف الأطلال على الخريطة (Relics Exploration).

البحث:
    • "mapType": 7 , "subType": 0

أمر المسير (1007/2):
    • "moveLineType": 4
    • "matrixType": 1
    • "exploreTime": 900 (15 دقيقة)
    • الحيوانات والرونات والجيش من التشكيلة المحفوظة (1005/7)

الاستخدام:
    python tasks/ruins.py --email "azjfhf48@gmail.com" --minlv 1 --maxlv 30 --marches 2
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
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# ── ملف تاريخ الاستبعاد ──────────────────────────────────────────
HISTORY_FILE = os.path.join(_ROOT_DIR, "exclude_history.json")


# ════════════════════════════════════════════════════════════════════
#  إعدادات افتراضية في رأس الملف (قابلة للتعديل والربط بـ Firebase)
# ════════════════════════════════════════════════════════════════════

DEFAULT_MIN_LV             = 1                # أدنى مستوى للأطلال
DEFAULT_MAX_LV             = 30               # أقصى مستوى للأطلال
DEFAULT_MAX_MARCHES        = 1                # الحد الأقصى للمسيرات (مسيرة واحدة فقط مسموحة للأطلال)
DEFAULT_SEARCH_RANGE       = 100              # نطاق البحث
DEFAULT_FORMATION_ID       = 1                # رقم التشكيلة المفضلة (1..5)
DEFAULT_EXPLORE_TIME       = 900              # مدة الاستكشاف بالثواني (900 = 15 دقيقة)
DEFAULT_TROOPS_COUNT       = 1000             # عدد الجنود الافتراضي



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
#  اختيار أبطال الاستكشاف (Ruins Heroes Selection)
# ════════════════════════════════════════════════════════════════════

def _pick_ruins_heroes(heroes: list, max_count: int = 2, busy: Set[int] = None) -> List[int]:
    """
    يختار أبطال استكشاف متاحين بالقلعة (أولوية لأبطال الجمع/التنمية 5502xxx ثم أبطال الحرب 5501xxx).
    """
    busy = busy or set()
    tier1, tier2 = [], []

    for hero in heroes:
        if not isinstance(hero, dict):
            continue
        hid = hero.get('id')
        if not hid or hid in busy:
            continue
        if hero.get('status', {}).get('state', 0) != 0:
            continue

        hid_str = str(hid)
        lv = int(hero.get('lv', 1))
        star = int(hero.get('star', 1))
        score = lv * 10 + star * 50

        if hid_str.startswith('5502'):
            tier1.append((int(hid), score))
        elif hid_str.startswith('5501') or hid_str.startswith('5503'):
            tier2.append((int(hid), score))

    tier1.sort(key=lambda x: x[1], reverse=True)
    tier2.sort(key=lambda x: x[1], reverse=True)

    chosen = [h[0] for h in tier1] + [h[0] for h in tier2]
    return chosen[:max_count] if max_count else chosen


# ════════════════════════════════════════════════════════════════════
#  اختيار جيش الاستكشاف التلقائي (Ruins Army Selection)
# ════════════════════════════════════════════════════════════════════

def select_ruins_army(available: Dict[int, int], needed_count: int = DEFAULT_TROOPS_COUNT) -> List[Dict[str, int]]:
    """
    اختيار جيش لاستكشاف الأطلال (عربات نقل أو مشاة أو أي قوات متوفرة).
    """
    sorted_troops = sorted(available.items(), key=lambda x: x[1], reverse=True)
    army_list = []
    remaining = needed_count

    for tid, count in sorted_troops:
        if count <= 0:
            continue
        take = min(count, remaining)
        if take > 0:
            army_list.append({"id": tid, "num": take})
            available[tid] -= take
            remaining -= take
            if remaining <= 0:
                break

    return army_list


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

    async def on_start(self):
        for _ in range(20):
            if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
                break
            if self.conn.init_data:
                break
            await asyncio.sleep(0.5)
        await self._load_heroes()

    async def _load_heroes(self):
        """تحميل سجل أبطال القلعة."""
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

    # ── المهمة الرئيسية ───────────────────────────────────────────

    async def run(self) -> TaskResult:
        cfg = self.config
        min_lv          = int(cfg.get('min_lv', DEFAULT_MIN_LV))
        max_lv          = int(cfg.get('max_lv', DEFAULT_MAX_LV))
        max_marches     = int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))
        search_range    = int(cfg.get('search_range', DEFAULT_SEARCH_RANGE))
        formation_id    = int(cfg.get('formation_id', DEFAULT_FORMATION_ID))
        explore_time    = int(cfg.get('explore_time', DEFAULT_EXPLORE_TIME))
        troops_cfg      = int(cfg.get('troops_count', DEFAULT_TROOPS_COUNT))

        self.log.info(f"🏛️ بدء مهمة استكشاف الأطلال (Ruins) | لفل: {min_lv}-{max_lv} | الحد الأقصى للمسيرات: {max_marches}")

        if not self._heroes:
            await self._load_heroes()

        sent_count = 0
        consecutive_errors = 0
        self._busy      = set()
        self._used_army = {}

        for i in range(1, max_marches + 1):
            self.log.info(f"🚀 محاولة إرسال مسيرة الأطلال رقم ({i}/{max_marches})...")
            result_code = await self._send_one_ruins(min_lv, max_lv, search_range, formation_id, explore_time, troops_cfg)

            if result_code == "SUCCESS":
                sent_count += 1
                consecutive_errors = 0
                await asyncio.sleep(5.0)  # حماية من الحظر - تأخير بين المسيرات
            elif result_code in ("QUEUE_FULL", "NO_TARGET", "NO_ARMY"):
                break
            elif result_code == "NO_HEROES":
                return TaskResult.no_heroes()
            elif result_code in ("HERO_BUSY", "TARGET_OCCUPIED"):
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    self.log.warning("⚠️ 3 أخطاء متتالية — توقف مؤقت")
                    break
                continue
            else:
                consecutive_errors += 1
                if consecutive_errors >= 2:
                    break

        self.log.info(f"🏁 إجمالي مسيرات استكشاف الأطلال المُرسَلة: {sent_count}")
        if sent_count > 0:
            return TaskResult.ok(f"✅ تم إرسال {sent_count} مسيرة استكشاف أطلال", sent=sent_count)
        return TaskResult.fail("لم يتم إرسال أي مسيرة استكشاف أطلال", retry_after=120)

    # ── إرسال مسيرة استكشاف واحدة ─────────────────────────────────

    async def _send_one_ruins(self, min_lv: int, max_lv: int, search_range: int, formation_id: int, explore_time: int, troops_cfg: int) -> str:
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. جلب إحداثيات القلعة
        r_castle = await self.conn.query('1006', '25', {"uid": uid_int})
        if not r_castle or not r_castle.get('retData'):
            return "ERROR"
        cx = r_castle['retData'].get('x')
        cy = r_castle['retData'].get('y')

        # 2. البحث عن الأطلال (mapType: 7, subType: 0)
        r_search = await self.conn.query('2011', '3', {
            "mapType": 7,
            "subType": 0,
            "num": 1,
            "y": cy,
            "x": cx,
            "exclude": _get_exclude(self.uid),
            "range": search_range
        })
        if not r_search or not r_search.get('result'):
            self.log.warning(f"⚠️ لا توجد أطلال متاحة في نطاق {search_range}!")
            return "NO_TARGET"

        target    = r_search['result'][0]
        target_id = target.get('id')
        tx, ty    = target.get('x'), target.get('y')
        t_lv      = target.get('level', '?')
        self.log.info(f"🎯 هدف الأطلال: ID={target_id} عند ({tx}, {ty}) لفل={t_lv}")
        _add_exclude(self.uid, target_id)

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

        # 5. استعلام التشكيلة المحفوظة (1005/7)
        form_heroes     = []
        form_pets       = []
        form_rune_pages = []
        form_army_dict  = {}
        r_form = await self.conn.query('1005', '7', {"compiletype": formation_id})
        if r_form and 'data' in r_form:
            form_heroes     = r_form['data'].get('compileHeros', [])
            form_pets       = r_form['data'].get('compilePets', [])
            form_rune_pages = r_form['data'].get('compileRunePages', [1])
            form_army_dict  = r_form['data'].get('compileArmy', {})

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
                self.log.info(f"🎖️ تم اختيار بطلي التشكيلة المحفوظة ({formation_id}): {chosen_heroes}")
            elif len(available_form_heroes) == 1:
                hero1 = available_form_heroes[0]
                self.log.info(f"ℹ️ أحد أبطال التشكيلة متاح ({hero1}) والآخر مشغول — جاري إكمال البطل الثاني بأفضل بطل متاح...")
                extra_busy = set(self._busy) | {hero1}
                filler = _pick_ruins_heroes(self._heroes, max_count=1, busy=extra_busy)
                chosen_heroes = [hero1] + filler
                self.log.info(f"🌾 تشكيلة أبطال الأطلال المكتملة: {chosen_heroes}")

        if not chosen_heroes:
            self.log.info("⚠️ أبطال التشكيلة مشغولون — جاري اختيار أبطال متاحين تلقائياً...")
            chosen_heroes = _pick_ruins_heroes(self._heroes, max_count=2, busy=self._busy)
            if not chosen_heroes:
                self.log.warning("⚠️ لا يوجد أي بطل متاح بالقلعة!")
                return "NO_HEROES"
            self.log.info(f"🌾 الأبطال المختارون تلقائياً: {chosen_heroes}")

        # 7. تكوين جيش المسيرة الذكي (التشكيلة مع الإكمال التلقائي للنقص بالجنود المناسبين)
        army_list = []
        needed_target = troops_cfg or DEFAULT_TROOPS_COUNT

        if form_army_dict:
            # حساب إجمالي القوات المطلوبة في التشكيلة (مع استبعاد فخاخ الجدار 800-899)
            total_form_req = sum(
                int(v) for k, v in form_army_dict.items()
                if str(k).isdigit() and str(v).isdigit() and not (800 <= int(k) < 900)
            )
            # إذا كانت التشكيلة تتجاوز العدد المطلوب للاستكشاف (1000)، نوزعها بنسب متوازنة دقيقة
            scale = 1.0
            if total_form_req > needed_target:
                scale = float(needed_target) / float(total_form_req)

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

        form_troops_count = sum(item['num'] for item in army_list)

        if form_troops_count == 0:
            if formation_id > 0:
                self.log.info(f"⚠️ التشكيلة المحفوظة ({formation_id}) فارغة أو لا تتوفر أي من قواتها بالقلعة — جاري اختيار جيش استكشاف مناسب بالكامل ({needed_target:,} جندي)...")
            army_list = select_ruins_army(available, needed_count=needed_target)
        elif form_troops_count < needed_target:
            deficit = needed_target - form_troops_count
            self.log.info(
                f"ℹ️ جنود التشكيلة ({formation_id}) غير كافيين ({form_troops_count:,}/{needed_target:,} جندي) — "
                f"جاري إكمال النقص ({deficit:,} جندي) تلقائياً بأنسب قوات متاحة..."
            )
            extra_army = select_ruins_army(available, needed_count=deficit)
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
            self.log.warning("⚠️ لا توجد قوات متوفرة بالقلعة لإرسال المسيرة!")
            return "NO_ARMY"

        total_troops = sum(item['num'] for item in army_list)

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

        self.log.info(f"🛡️ تشكيلة الأطلال: {army_list[:2]}... (إجمالي جنود: {total_troops:,}) | حيوان: {pets_list or '{}'}")

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
            return "ERROR"

        err = str(r_attack.get('err', '0'))
        if err == '0':
            self.log.info(f"✅ تم إرسال مسيرة الأطلال بنجاح! → {target_id} | أبطال={chosen_heroes} | جنود={total_troops:,}")
            for hid in chosen_heroes:
                self._busy.add(hid)
            for item in army_list:
                self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
            return "SUCCESS"
        elif err in ('8004', '9007004'):
            self.log.info(f"🛑 اكتملت طوابير المسيرات للقلعة (كود {err})")
            return "QUEUE_FULL"
        elif err == '8037':
            self.log.info(f"🛑 القلعة لديها مسيرة استكشاف أطلال نشطة بالفعل حالياً (كود {err})")
            return "QUEUE_FULL"
        elif err == '8009':
            self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
            return "NO_ARMY"

        elif err == '9007020':
            for hid in chosen_heroes:
                self._busy.add(hid)
            return "HERO_BUSY"
        elif err in ('8062', '8063', '8060', '8035', '8002', '9007062') or (err.isdigit() and 8000 <= int(err) < 8100):
            self.log.warning(f"⚠️ الأطلال {target_id} مشغولة أو سبق استهدافها (كود {err}) — سيتم تجاوزها")
            return "TARGET_OCCUPIED"
        else:
            self.log.error(f"❌ خطأ غير معروف: {err} | الهدف={target_id}")
            return "ERROR"


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Ruins Exploration Bot — استكشاف الأطلال")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--minlv", type=int, default=DEFAULT_MIN_LV, help=f"أدنى لفل للأطلال [افتراضي: {DEFAULT_MIN_LV}]")
    parser.add_argument("--maxlv", type=int, default=DEFAULT_MAX_LV, help=f"أعلى لفل للأطلال [افتراضي: {DEFAULT_MAX_LV}]")
    parser.add_argument("--marches", "-m", type=int, default=DEFAULT_MAX_MARCHES, help=f"الحد الأقصى للمسيرات [افتراضي: {DEFAULT_MAX_MARCHES}]")
    parser.add_argument("--range", type=int, default=DEFAULT_SEARCH_RANGE, help=f"نطاق البحث [افتراضي: {DEFAULT_SEARCH_RANGE}]")
    parser.add_argument("--formation", "-f", type=int, default=DEFAULT_FORMATION_ID, help=f"رقم التشكيلة [افتراضي: {DEFAULT_FORMATION_ID}]")
    parser.add_argument("--time", "-t", type=int, default=DEFAULT_EXPLORE_TIME, help=f"وقت الاستكشاف بالثواني [افتراضي: {DEFAULT_EXPLORE_TIME}]")
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
            "formation_id": args.formation,
            "explore_time": args.time
        }

        task = RuinsTask(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
