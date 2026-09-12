# -*- coding: utf-8 -*-
"""
tasks/gather.py — مهمة جمع الموارد الذكية (Dynamic Resource Gathering)
═════════════════════════════════════════════════════════════════════
python tasks/gather.py --email "nmrn65794@gmail.com"
تُرسِل مسيرات جمع متتالية مع تحديد البطل والحيوان وتشكيلة الجيش تلقائياً
بدون الحاجة لأي تشكيلة مسبقة محفوظة (تحديد ذاتي كامل).

نظام اختيار الجيش التلقائي:
    1. أولوية 1: عربات النقل والحصار (701..714) من الرتبة الأعلى إلى الأدنى.
    2. أولوية 2: المشاة (401..414).
    3. أولوية 3: الفرسان (501..514).
    4. أولوية 4: الرماة (601..614).
    5. أولوية 5: أي قوات متبقية.

الإعدادات (config):
    res_type    : نوع المورد (1=مزارع, 2=خشب, 3=حجر, 4=حديد) [افتراضي: 4]
    min_lv      : أدنى مستوى للحقل [افتراضي: 5]
    max_lv      : أعلى مستوى للحقل [افتراضي: 6]
    max_marches : الحد الأقصى للمسيرات [افتراضي: 6]
    search_range: نطاق البحث على الخريطة [افتراضي: 100]
    troops_count: عدد الجنود لكل مسيرة (افتراضي: تلقائي حسب حمولة الحقل أو 25,000)
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
    while len(arr) > 15:
        arr.pop(0)
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
#  اختيار أبطال الجمع (هرمية الأولويات)
# ════════════════════════════════════════════════════════════════════

def _pick_gather_heroes(heroes: list, max_count: int = 1, busy: set = None) -> List[int]:
    """
    يختار أفضل أبطال جمع وفق 3 مستويات أولوية:
    1. بطل 5502 + مهارة 5620 (ذهبي)
    2. بطل 5502 بدون مهارة 5620 (فضي)
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

        skills  = hero.get('skillList', {})
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
#  اختيار تشكيلة الجيش تلقائياً (Dynamic Army Selection)
# ════════════════════════════════════════════════════════════════════

def select_gathering_army(available: Dict[int, int], needed_count: int = 25000) -> List[Dict[str, int]]:
    """
    اختيار تشكيلة الجيش تلقائياً لجمع الموارد وفق نظام اللعبة:
    1. أولوية 1: عربات النقل والحصار (701..714) من الرتبة الأعلى إلى الأدنى.
    2. أولوية 2: المشاة (401..414).
    3. أولوية 3: الفرسان (501..514).
    4. أولوية 4: الرماة (601..614).
    5. أولوية 5: أي قوات متبقية.
    """
    carts    = []   # 701..714
    infantry = []   # 401..414
    cavalry  = []   # 501..514
    archers  = []   # 601..614
    others   = []

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

    # ترتيب كل صنف من الرتبة الأعلى إلى الأدنى
    carts.sort(key=lambda x: x[0], reverse=True)
    infantry.sort(key=lambda x: x[0], reverse=True)
    cavalry.sort(key=lambda x: x[0], reverse=True)
    archers.sort(key=lambda x: x[0], reverse=True)

    priority_groups = [carts, infantry, cavalry, archers]

    army_list = []
    remaining_needed = needed_count

    for group in priority_groups:
        for tid, count in group:
            avail = available.get(tid, 0)
            if avail <= 0:
                continue
            take = min(avail, remaining_needed)
            if take > 0:
                army_list.append({"id": tid, "num": take})
                available[tid] -= take
                remaining_needed -= take
                if remaining_needed <= 0:
                    break
        if remaining_needed <= 0:
            break

    return army_list


# ════════════════════════════════════════════════════════════════════
#  اختيار الحيوان الأليف تلقائياً (Dynamic Pet Selection)
# ════════════════════════════════════════════════════════════════════

def select_gathering_pet(conn: GameConnection, used_pets: Set[int]) -> List[int]:
    """
    اختيار حيوان أليف متاح للمسيرة من بيانات petCtrl.
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

    # اختيار أعلى حيوان في المستوى
    available_pets.sort(key=lambda x: x[1], reverse=True)
    chosen_pet = available_pets[0][0]
    used_pets.add(chosen_pet)
    return [chosen_pet]


# ════════════════════════════════════════════════════════════════════
#  مهمة الجمع (GatherTask)
# ════════════════════════════════════════════════════════════════════

class GatherTask(BaseTask):
    """
    مهمة جمع الموارد الذكية — ترث من BaseTask.
    """
    name = "gather"

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
        """جلب الأبطال من الاتصال المُهيَّأ أو من سيرفر اللعبة."""
        self._heroes = []
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. من الـ Gate مباشرة (تم استقبالها في init_data)
        if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
            self._heroes = list(self.conn._gate.heroes)
            if self._heroes:
                self.log.info(f"📋 {len(self._heroes)} بطل من init_data")
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
                for _ in range(8):
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

        if self._heroes:
            self.log.info(f"📋 تم العثور على {len(self._heroes)} بطل")
        else:
            self.log.warning("⚠️ لم يتم العثور على أبطال مسجلين في هذا الحساب")

    # ── المهمة الرئيسية ───────────────────────────────────────────

    async def run(self) -> TaskResult:
        """إرسال مسيرات متتالية حتى امتلاء الطوابير."""
        cfg = self.config
        res_type     = int(cfg.get('res_type', 4))
        min_lv       = int(cfg.get('min_lv', 5))
        max_lv       = int(cfg.get('max_lv', 6))
        max_marches  = int(cfg.get('max_marches', 6))
        search_range = int(cfg.get('search_range', 100))
        troops_cfg   = cfg.get('troops_count')

        if not self._heroes:
            await self._load_heroes()

        sent_count = 0
        consecutive_errors = 0
        self._busy      = set()
        self._used_army = {}
        self._used_pets = set()

        for i in range(1, max_marches + 1):
            self.log.info(f"⚔️ محاولة إرسال مسيرة الجمع رقم ({i}/{max_marches})...")
            result_code = await self._send_one_march(res_type, min_lv, max_lv, search_range, troops_cfg)

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

        self.log.info(f"🏁 إجمالي مسيرات الجمع المُرسَلة: {sent_count}")
        if sent_count > 0:
            return TaskResult.ok(f"✅ تم إرسال {sent_count} مسيرة جمع", sent=sent_count)
        return TaskResult.fail("لم يتم إرسال أي مسيرة جمع", retry_after=120)

    # ── إرسال مسيرة واحدة ────────────────────────────────────────

    async def _send_one_march(self, res_type: int, min_lv: int, max_lv: int, search_range: int, troops_cfg: Optional[int] = None) -> str:
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. اختيار البطل تلقائياً
        if not self._heroes:
            await self._load_heroes()
        heroes = _pick_gather_heroes(self._heroes, max_count=1, busy=self._busy)
        if not heroes:
            self.log.warning("⚠️ لا يوجد بطل جمع متاح!")
            return "NO_HEROES"

        chosen_hero = heroes[0]
        self.log.info(f"🌾 البطل المختار تلقائياً: {chosen_hero}")

        # 2. إحداثيات القلعة
        r_castle = await self.conn.query('1006', '25', {"uid": uid_int})
        if not r_castle or not r_castle.get('retData'):
            return "ERROR"
        cx = r_castle['retData'].get('x')
        cy = r_castle['retData'].get('y')

        # 3. البحث عن حقل المورد
        r_search = await self.conn.query('2011', '3', {
            "mapType": 5, "num": 1, "subType": res_type,
            "y": cy, "x": cx,
            "exclude": _get_exclude(self.uid),
            "minLv": min_lv, "maxLv": max_lv, "range": search_range
        })
        if not r_search or not r_search.get('result'):
            self.log.warning("⚠️ لا توجد حقول موارد متاحة في هذا النطاق!")
            return "NO_TARGET"

        target    = r_search['result'][0]
        target_id = target.get('id')
        tx, ty    = target.get('x'), target.get('y')
        self.log.info(f"🎯 الهدف: {target_id} عند ({tx}, {ty})")
        _add_exclude(self.uid, target_id)

        # 4. جلب معرف المملكة (kingdom_id)
        kingdom_id = 0
        if self.conn.kingdom_id:
            try: kingdom_id = int(self.conn.kingdom_id)
            except: pass
        if not kingdom_id:
            r_map = await self.conn.query('1002', '7', {"uid": uid_int})
            if r_map and 'data' in r_map:
                kingdom_id = r_map['data'].get('base', {}).get('partition', 0)

        # 5. استعلام حمولة الحقل الهدف
        cur_res = 0
        r_build = await self.conn.query('1006', '15', {
            "x": tx, "y": ty, "kingdomId": kingdom_id, "id": target_id
        })
        if r_build and 'retData' in r_build:
            cur_res = int(r_build['retData'].get('resource', {}).get('currentSourceNum', 0))

        # حساب عدد الجنود المطلوب بدقة (عربة النقل تحمل ~25 مورد)
        if troops_cfg:
            needed_troops = int(troops_cfg)
        elif cur_res > 0:
            needed_troops = max(15000, cur_res // 25)
        else:
            needed_troops = 25000

        # 6. جلب القوات المتوفرة بالقلعة
        available: Dict[int, int] = {}
        r_army = await self.conn.query('1005', '1', {})
        if r_army and 'data' in r_army:
            for k, v in r_army['data'].get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)

        # خصم القوات المستهلكة في المسيرات السابقة
        for tid, used in self._used_army.items():
            if tid in available:
                available[tid] = max(0, available[tid] - used)

        # 7. تكوين تشكيلة الجيش تلقائياً (عربات أولاً ثم باقي الوحدات)
        army_list = select_gathering_army(available, needed_count=needed_troops)
        if not army_list:
            self.log.warning("⚠️ لا توجد قوات متوفرة بالقلعة لإرسال مسيرة!")
            return "NO_ARMY"

        total_march_troops = sum(item['num'] for item in army_list)

        # 8. اختيار الحيوان الأليف تلقائياً
        pets_list = select_gathering_pet(self.conn, self._used_pets)

        self.log.info(f"🛡️ التشكيلة المختارة تلقائياً: {army_list} (إجمالي جنود: {total_march_troops:,}) | حيوان: {pets_list}")

        # 9. إرسال حزمة المسيرة 1007/2
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
                    "resourceType": 1000 + res_type
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
            self.log.info(f"✅ مسيرة ناجحة! → {target_id} | بطل={chosen_hero} | جنود={total_march_troops:,}")
            self._busy.add(chosen_hero)
            for item in army_list:
                self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
            return "SUCCESS"
        elif err in ('8004', '9007004'):
            self.log.info(f"🛑 اكتملت طوابير المسيرات للقلعة (كود {err})")
            return "QUEUE_FULL"
        elif err == '8009':
            self.log.warning(f"⚠️ نقص في القوات أو الموارد (كود {err})")
            return "NO_ARMY"
        elif err == '9007020':
            self._busy.add(chosen_hero)
            return "HERO_BUSY"
        elif err in ('8062', '8063', '8060', '9007062'):
            self.log.warning(f"⚠️ الهدف {target_id} محجوز/ممتلئ (كود {err}) — سيتم تجاوزه")
            return "TARGET_OCCUPIED"
        else:
            self.log.error(f"❌ خطأ غير معروف: {err} | الهدف={target_id}")
            return "ERROR"


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Gather Bot — جمع الموارد التلقائي الذكي")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--res", "-r", type=int, default=4, help="نوع المورد: 1=مزارع 2=خشب 3=حجر 4=حديد [افتراضي: 4]")
    parser.add_argument("--minlv", type=int, default=5, help="أدنى لفل للحقل [افتراضي: 5]")
    parser.add_argument("--maxlv", type=int, default=6, help="أعلى لفل للحقل [افتراضي: 6]")
    parser.add_argument("--marches", "-m", type=int, default=6, help="الحد الأقصى للمسيرات [افتراضي: 6]")
    parser.add_argument("--range", type=int, default=100, help="نطاق البحث [افتراضي: 100]")
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

        for _ in range(10):
            await asyncio.sleep(2.0)  # حماية من الحظر
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "res_type": args.res,
            "min_lv": args.minlv,
            "max_lv": args.maxlv,
            "max_marches": args.marches,
            "search_range": args.range
        }

        task = GatherTask(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
