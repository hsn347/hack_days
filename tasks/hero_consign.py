# -*- coding: utf-8 -*-
"""
أداة رحلات وتكليف الأبطال (Hero Voyage & Consign)
CMD: 3148
  - Subcmd 1: اختيار البطل للترحال (Choose Hero) -> {"cId": int}
  - Subcmd 3: إطلاق الترحال (Voyage Travel) -> {"isItem": 0, "isGuide": false, "amount": 1}
  - Subcmd 4: بدء مهمة تكليف (Start Consign) -> {"index": int, "heroIds": [id1, id2, ...]}
  - Subcmd 5: استلام جائزة مهمة مكتملة (Award Consign) -> {"index": int}
  - Subcmd 7: استلام صندوق الهدايا التراكمي (15 مهمة)
 python hero_consign.py --email sumo-1234@hotmil.com --execute
الحد اليومي: 5 مهام يومياً
"""

import asyncio
import argparse
import json
import os
import random
import re
import sys
import time

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from core.session_manager import SessionManager
from game_client import GameConnection
from tasks.base_task import BaseTask, TaskResult

# -------------------------------------------------------------
# جداول الشروط وقواعد اللعبة (مستخرجة مباشرة من ملفات اللعبة)
# -------------------------------------------------------------

# شروط المهام الـ 15: condition_id -> (spot, [requireIDs])
TASK_CONDITIONS = {
    1:  (3, [50011, 50017, 50023]),
    2:  (3, [50012, 50018, 50024]),
    3:  (3, [50013, 50019, 50025]),
    4:  (3, [50014, 50020, 50026]),
    5:  (3, [50015, 50021, 50027]),
    6:  (3, [50016, 50022, 50028]),
    7:  (4, [50029, 50035, 50041]),
    8:  (4, [50030, 50036, 50042]),
    9:  (4, [50031, 50037, 50043]),
    10: (4, [50032, 50038, 50044]),
    11: (4, [50033, 50039, 50045]),
    12: (4, [50034, 50040, 50046]),
    13: (5, [50047, 50050]),
    14: (5, [50048, 50051]),
    15: (5, [50049, 50052]),
}

# تفاصيل متطلبات الأبطال: requireID -> (heroNum, min_lv, min_star, min_quality, heroType)
# Quality: 3=أزرق, 4=بنفسجي, 5=ذهبي/برتقالي, 6=أحمر
# Type: 1=حرب, 2=تطوير, 3=مساعد, 0=أي نوع
REQUIREMENTS = {
    50011: (1, 0, 0, 0, 2),
    50012: (2, 0, 0, 0, 2),
    50013: (1, 0, 0, 0, 3),
    50014: (2, 0, 0, 0, 3),
    50015: (1, 0, 0, 0, 1),
    50016: (2, 0, 0, 0, 1),
    50017: (2, 0, 0, 3, 0),
    50018: (2, 0, 0, 3, 0),
    50019: (2, 0, 0, 3, 0),
    50020: (2, 0, 0, 3, 0),
    50021: (2, 0, 0, 3, 0),
    50022: (2, 0, 0, 3, 0),
    50023: (2, 0, 1, 0, 0),
    50024: (2, 0, 1, 0, 0),
    50025: (2, 0, 1, 0, 0),
    50026: (2, 0, 1, 0, 0),
    50027: (2, 0, 1, 0, 0),
    50028: (2, 0, 1, 0, 0),
    50029: (2, 0, 0, 0, 2),
    50030: (2, 0, 0, 0, 2),
    50031: (2, 0, 0, 0, 3),
    50032: (2, 0, 0, 0, 3),
    50033: (2, 0, 0, 0, 1),
    50034: (2, 0, 0, 0, 1),
    50035: (3, 0, 0, 4, 0),
    50036: (4, 0, 0, 4, 0),
    50037: (3, 0, 0, 4, 0),
    50038: (4, 0, 0, 4, 0),
    50039: (3, 0, 0, 4, 0),
    50040: (4, 0, 0, 4, 0),
    50041: (3, 0, 2, 0, 0),
    50042: (3, 0, 2, 0, 0),
    50043: (3, 0, 2, 0, 0),
    50044: (3, 0, 2, 0, 0),
    50045: (3, 0, 2, 0, 0),
    50046: (3, 0, 2, 0, 0),
    50047: (5, 0, 0, 5, 0),
    50048: (2, 0, 0, 6, 0),
    50049: (1, 0, 0, 6, 0),
    50050: (5, 0, 3, 0, 0),
    50051: (5, 0, 3, 0, 0),
    50052: (5, 0, 3, 0, 0),
}

QUALITY_NAMES = {3: "أزرق", 4: "بنفسجي", 5: "برتقالي", 6: "أحمر"}
TYPE_NAMES = {1: "حرب", 2: "تطوير", 3: "مساعد"}


def describe_req(req):
    """وصف مقروء للمتطلب بالعربية"""
    num, min_lv, min_star, min_qual, req_type = req
    parts = [f"{num} أبطال"]
    if min_qual > 0:
        parts.append(f"جودة {QUALITY_NAMES.get(min_qual, str(min_qual))}+")
    if min_star > 0:
        parts.append(f"نجوم {min_star}+")
    if min_lv > 0:
        parts.append(f"مستوى {min_lv}+")
    if req_type > 0:
        parts.append(f"نوع {TYPE_NAMES.get(req_type, str(req_type))}")
    return " | ".join(parts)


# بيانات الأبطال الثابتة (الجودة والنوع) لضمان العمل التام والمستقل على السيرفر دون الاعتماد على ملفات اللوا
STATIC_HEROES_META = {
    5501001: {'quality': 5, 'type': 1}, 5501002: {'quality': 5, 'type': 1}, 5501003: {'quality': 5, 'type': 1},
    5501004: {'quality': 5, 'type': 1}, 5501005: {'quality': 5, 'type': 1}, 5501006: {'quality': 4, 'type': 1},
    5501007: {'quality': 4, 'type': 1}, 5501008: {'quality': 4, 'type': 1}, 5501009: {'quality': 5, 'type': 1},
    5501010: {'quality': 4, 'type': 1}, 5501011: {'quality': 4, 'type': 1}, 5501012: {'quality': 5, 'type': 1},
    5501013: {'quality': 5, 'type': 1}, 5501014: {'quality': 5, 'type': 1}, 5501015: {'quality': 5, 'type': 1},
    5501016: {'quality': 5, 'type': 1}, 5501017: {'quality': 5, 'type': 3}, 5501018: {'quality': 5, 'type': 1},
    5501019: {'quality': 5, 'type': 1}, 5501020: {'quality': 5, 'type': 1}, 5501021: {'quality': 5, 'type': 1},
    5501022: {'quality': 4, 'type': 1}, 5501023: {'quality': 4, 'type': 1}, 5501024: {'quality': 5, 'type': 1},
    5501025: {'quality': 4, 'type': 1}, 5501026: {'quality': 5, 'type': 1}, 5501027: {'quality': 5, 'type': 1},
    5501028: {'quality': 5, 'type': 1}, 5501029: {'quality': 5, 'type': 1}, 5501030: {'quality': 5, 'type': 1},
    5501031: {'quality': 5, 'type': 1}, 5501032: {'quality': 5, 'type': 1}, 5501033: {'quality': 6, 'type': 1},
    5501034: {'quality': 4, 'type': 1}, 5501035: {'quality': 5, 'type': 1}, 5501036: {'quality': 6, 'type': 1},
    5501037: {'quality': 6, 'type': 1}, 5501038: {'quality': 6, 'type': 1}, 5501039: {'quality': 6, 'type': 1},
    5501040: {'quality': 6, 'type': 1}, 5501041: {'quality': 6, 'type': 1}, 5501042: {'quality': 6, 'type': 1},
    5501043: {'quality': 6, 'type': 1},
    5502001: {'quality': 5, 'type': 2}, 5502002: {'quality': 4, 'type': 2}, 5502003: {'quality': 4, 'type': 2},
    5502004: {'quality': 4, 'type': 2}, 5502005: {'quality': 4, 'type': 2}, 5502006: {'quality': 3, 'type': 2},
    5502007: {'quality': 4, 'type': 2}, 5502008: {'quality': 3, 'type': 2}, 5502009: {'quality': 3, 'type': 2},
    5502010: {'quality': 3, 'type': 2}, 5502011: {'quality': 5, 'type': 2}, 5502012: {'quality': 5, 'type': 2},
    5502013: {'quality': 5, 'type': 2},
    5503001: {'quality': 5, 'type': 3}, 5503002: {'quality': 4, 'type': 3}, 5503003: {'quality': 4, 'type': 3},
    5503004: {'quality': 4, 'type': 3}, 5503005: {'quality': 4, 'type': 3}, 5503006: {'quality': 4, 'type': 3},
    5503007: {'quality': 4, 'type': 3}, 5503008: {'quality': 3, 'type': 3}, 5503009: {'quality': 3, 'type': 3},
    5503010: {'quality': 3, 'type': 3}, 5503011: {'quality': 3, 'type': 3}, 5503012: {'quality': 5, 'type': 3},
    5503013: {'quality': 5, 'type': 3}, 5503014: {'quality': 5, 'type': 3}, 5503015: {'quality': 5, 'type': 3},
    5503016: {'quality': 5, 'type': 3}, 5503017: {'quality': 5, 'type': 3}, 5503018: {'quality': 5, 'type': 3},
    5503019: {'quality': 5, 'type': 3}, 5503020: {'quality': 6, 'type': 3}, 5503021: {'quality': 6, 'type': 3},
    5503022: {'quality': 6, 'type': 3}, 5503023: {'quality': 5, 'type': 2}, 5503024: {'quality': 6, 'type': 3},
    5503025: {'quality': 6, 'type': 3}, 5503026: {'quality': 6, 'type': 3}, 5503027: {'quality': 6, 'type': 3},
}


def load_heroes_meta():
    """تحميل بيانات الأبطال الثابتة (الجودة والنوع) مع دعم ملفات اللوا إن وُجدت محلياً"""
    meta = dict(STATIC_HEROES_META)
    path = os.path.join(_ROOT_DIR, 'lua_src', 'src', 'src', 'app', 'localtb', 'config_client', 'heroinfodes.lua')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            pattern = re.compile(r'\[(\d+)\]\s*=\s*\{([^}]+)\}')
            for match in pattern.finditer(content):
                hid = int(match.group(1))
                body = match.group(2)
                q_m = re.search(r'heroQuality\s*=\s*(\d+)', body)
                t_m = re.search(r'heroType\s*=\s*(\d+)', body)
                meta[hid] = {
                    'quality': int(q_m.group(1)) if q_m else 0,
                    'type': int(t_m.group(1)) if t_m else 0
                }
        except Exception:
            pass
    return meta


HEROES_META = load_heroes_meta()


def get_task_duration(task_id: int) -> int:
    """حساب مدة المهمة بالثواني بناءً على معرف المهمة بدقة 100%"""
    tid = int(task_id)
    if tid >= 440000:
        return 21600
    elif tid >= 430000:
        return 18000
    return 14400


def hero_satisfies_req(hero, req):
    """التحقق مما إذا كان بطل معين يستوفي شرطاً محدداً"""
    num, min_lv, min_star, min_qual, req_type = req
    if min_lv > 0 and hero['lv'] < min_lv:
        return False
    if min_star > 0 and hero['star'] < min_star:
        return False
    if min_qual > 0 and hero['quality'] < min_qual:
        return False
    if req_type > 0 and hero['type'] != req_type:
        return False
    return True


def solve_task(available_heroes, cond_id):
    """
    اختيار أصغر فريق أبطال يستوفي جميع شروط المهمة المحددة (بحد أقصى spot).
    نفس منطق العميل الأصلي: نفضل الأبطال الأقل رتبة لحفظ الأبطال الأقوياء.
    """
    if cond_id not in TASK_CONDITIONS:
        return None

    spot, rids = TASK_CONDITIONS[cond_id]
    reqs = [REQUIREMENTS[r] for r in rids if r in REQUIREMENTS]
    if not reqs:
        return None

    # تصفية الأبطال المرشحين (الذين يحققون شرطاً واحداً على الأقل)
    candidates = []
    for h in available_heroes:
        mask = [hero_satisfies_req(h, r) for r in reqs]
        if any(mask):
            candidates.append((h, mask))

    # ترتيب تصاعدي حسب الجودة والنجوم والمستوى لاستهلاك الأقل قيمة أولاً
    candidates.sort(key=lambda x: (x[0]['quality'], x[0]['star'], x[0]['lv']))

    n_reqs = len(reqs)
    targets = [r[0] for r in reqs]
    best_team = None

    def backtrack(idx, team, counts):
        nonlocal best_team
        if all(counts[i] >= targets[i] for i in range(n_reqs)):
            best_team = list(team)
            return True
        if len(team) >= spot or idx >= len(candidates):
            return False

        remaining_slots = spot - len(team)
        deficits = [max(0, targets[i] - counts[i]) for i in range(n_reqs)]
        if max(deficits) > remaining_slots:
            return False

        hero, mask = candidates[idx]
        new_counts = [counts[i] + (1 if mask[i] else 0) for i in range(n_reqs)]
        team.append(hero['id'])
        if backtrack(idx + 1, team, new_counts):
            return True
        team.pop()

        if backtrack(idx + 1, team, counts):
            return True
        return False

    backtrack(0, [], [0] * n_reqs)
    return best_team


class HeroConsignTask(BaseTask):
    """
    مهمة رحلات وتكليف الأبطال (Hero Voyage & Consign - CMD 3148):
      1. رحلات الأبطال (Voyage Travel - SUB 3):
         - التحقق من اختيار بطل للترحال (SUB 1) إن لم يكن محدداً.
         - تنفيذ رحلات الترحال المتبقية (حتى 10 يومياً) بفاصل زمني ثانيتين.
      2. استلام جوائز مهام التكليف المنجزة (Award Consign - SUB 5):
         - استعلام وفحص المهام المنتهية واستلام جوائزها بفاصل زمني ثانيتين.
         - إذا لم توجد جوائز، يتم المتابعة مباشرة إلى تكليف الأبطال.
      3. تكليف الأبطال (Hero Consign - SUB 4):
         - فحص المتبقي من الحد اليومي (5 مهام يومياً).
         - حل المهام المتاحة ومطابقتها بأبطال الحساب بذكاء وتوفير الأبطال النادرين.
         - إرسال المهام بفاصل ثانيتين حتى استنفاد الحد اليومي.
         - استلام صندوق الهدايا التراكمي (SUB 7) عند وصول العداد التراكمي إلى 15 مهمة.
    """
    name = "hero_consign"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config or {})

    async def run(self) -> TaskResult:
        if not bool(self.config.get("enabled", True)):
            return TaskResult.ok("⏭️ تم تخطي مهمة رحلات وتكليف الأبطال (معطلة في الإعدادات)")

        # انتظار تحميل حزم التهيئة الأولية
        for _ in range(12):
            if 'heroVoyageAgCtrl' in self.conn.init_data and 'heroCtrl' in self.conn.init_data:
                break
            await asyncio.sleep(0.5)

        voyage = self.conn.init_data.get('heroVoyageAgCtrl', {})
        if not voyage:
            msg = "لم يتم العثور على بيانات تكليف الأبطال (heroVoyageAgCtrl) في حزم التهيئة."
            self.log.warning(msg)
            return TaskResult.fail(msg)

        raw_heroes = self.conn.init_data.get('heroCtrl', [])
        player_hero_ids = [h.get('id') for h in raw_heroes if isinstance(h, dict)]

        # ── المرحلة الأولى: رحلات الأبطال (Hero Voyage / Travel) ──
        cur_travel_hero = voyage.get('heroId', 0)
        if not cur_travel_hero or cur_travel_hero == 0:
            target_hero_id = 5502011 if 5502011 in player_hero_ids else (player_hero_ids[0] if player_hero_ids else 5502011)
            self.log.info(f"[*] لم يتم تحديد بطل للترحال، جاري اختيار البطل {target_hero_id}...")
            r_choose = await self.conn.query("3148", "1", {"cId": target_hero_id}, timeout=8.0)
            if r_choose and str(r_choose.get('err', '')) in ('0', 'None', ''):
                cur_travel_hero = target_hero_id
                voyage['heroId'] = target_hero_id
                self.log.info(f"    ✓ تم اختيار البطل {target_hero_id} للترحال بنجاح.")
                await asyncio.sleep(random.uniform(1.5, 2.5))
            else:
                err_c = r_choose.get('err', 'Unknown') if r_choose else 'Timeout'
                self.log.warning(f"    ✗ فشل اختيار البطل للترحال: {err_c}")

        voyage_count = voyage.get('voyageCount', {})
        used_physical = int(voyage_count.get("1", 0)) if isinstance(voyage_count, dict) else 0
        max_physical_travels = 10
        remaining_travels = max(0, max_physical_travels - used_physical)

        completed_travels = 0
        if remaining_travels > 0 and cur_travel_hero:
            self.log.info(f"🚀 بدء تنفيذ رحلات الأبطال المتبقية ({remaining_travels} رحلات)...")
            while remaining_travels > 0:
                r_travel = await self.conn.query("3148", "3", {
                    "isItem": 0,
                    "isGuide": False,
                    "amount": 1
                }, timeout=8.0)

                if r_travel and str(r_travel.get('err', '')) in ('0', 'None', ''):
                    completed_travels += 1
                    remaining_travels -= 1
                    v_data = r_travel.get('data', {})
                    if 'voyageCount' in v_data:
                        voyage['voyageCount'] = v_data['voyageCount']
                    self.log.info(f"    ✓ تم تنفيذ رحلة الترحال #{completed_travels} بنجاح.")
                else:
                    err_t = r_travel.get('err', 'Unknown') if r_travel else 'Timeout'
                    self.log.warning(f"    ✗ توقف الترحال: {err_t}")
                    break

                await asyncio.sleep(random.uniform(1.6, 2.8))
        else:
            self.log.info(f"ℹ️ رحلات الأبطال (الترحال): مكتملة مسبقاً ({used_physical}/10).")

        # ── المرحلة الثانية: استلام جوائز مهام التكليف المنجزة (Award Consign) ──
        consign_tasks = voyage.get('consignTasks', [])
        now_ts = int(time.time())

        ready_to_claim = []
        for idx_0, t in enumerate(consign_tasks):
            idx_1 = idx_0 + 1
            status = t.get('status', 1)
            start_time = t.get('startTime', 0)
            tid = t.get('id', 0)
            duration = get_task_duration(tid)

            if status == 3 or (status == 2 and start_time > 0 and now_ts >= (start_time + duration)):
                ready_to_claim.append((idx_1, t))

        claimed_count = 0
        if ready_to_claim:
            self.log.info(f"🎁 تم العثور على {len(ready_to_claim)} جوائز مهام منجزة جاهزة للاستلام...")
            for idx_1, t in ready_to_claim:
                resp = await self.conn.query("3148", "5", {"index": idx_1}, timeout=8.0)
                if resp and str(resp.get('err', '')) in ('0', 'None', ''):
                    claimed_count += 1
                    self.log.info(f"    ✓ تم استلام جائزة الخانة #{idx_1} بنجاح.")
                    r_data = resp.get('data', {})
                    if 'consignTasks' in r_data:
                        consign_tasks = r_data['consignTasks']
                        voyage['consignTasks'] = consign_tasks
                    if 'consignNum' in r_data:
                        voyage['consignNum'] = r_data['consignNum']
                else:
                    err_c = resp.get('err', 'Unknown') if resp else 'Timeout'
                    self.log.warning(f"    ✗ تعذر استلام جائزة الخانة #{idx_1}: {err_c}")

                await asyncio.sleep(random.uniform(1.5, 2.7))

            voyage = self.conn.init_data.get('heroVoyageAgCtrl', voyage)
            consign_tasks = voyage.get('consignTasks', consign_tasks)
        else:
            self.log.info("ℹ️ لا توجد صناديق/جوائز مهام منجزة جاهزة للاستلام حالياً. المتابعة إلى تكليف الأبطال...")

        # ── المرحلة الثالثة: تكليف الأبطال (Hero Consign) ──
        consign_count = voyage.get('consignCount', 0)
        daily_limit = 5
        remaining = max(0, daily_limit - consign_count)

        busy_hero_ids = set()
        for t in consign_tasks:
            if t.get('status') == 2:
                heros = t.get('heros')
                if isinstance(heros, list):
                    busy_hero_ids.update(heros)
                elif isinstance(heros, dict):
                    busy_hero_ids.update(heros.values())

        available_heroes = []
        for h in raw_heroes:
            hid = h.get('id')
            if hid in busy_hero_ids:
                continue
            meta = HEROES_META.get(hid, {})
            available_heroes.append({
                'id': hid,
                'lv': int(h.get('lv', 1)),
                'star': int(h.get('star', 1)),
                'quality': meta.get('quality', 0),
                'type': meta.get('type', 0),
            })

        executed_count = 0
        if remaining > 0:
            solvable_tasks = []
            for idx_0, t in enumerate(consign_tasks):
                idx_1 = idx_0 + 1
                cid = t.get('condition')
                status = t.get('status', 1)
                if status == 1:
                    sol = solve_task(available_heroes, cid)
                    if sol:
                        solvable_tasks.append((idx_1, t, sol))

            if solvable_tasks:
                self.log.info(f"🚀 بدء تنفيذ مهام التكليف المتاحة (المتبقي: {remaining})...")
                for idx_1, t, _ in solvable_tasks:
                    if remaining <= 0:
                        break
                    cid = t.get('condition')
                    sol = solve_task(available_heroes, cid)
                    if not sol:
                        continue

                    resp = await self.conn.query("3148", "4", {
                        "index": idx_1,
                        "heroIds": sol
                    }, timeout=8.0)

                    if resp and str(resp.get('err', '')) in ('0', 'None', ''):
                        executed_count += 1
                        remaining -= 1
                        self.log.info(f"    ✓ تم بدء مهمة التكليف #{idx_1} بنجاح بالأبطال {sol}")
                        used_set = set(sol)
                        available_heroes = [h for h in available_heroes if h['id'] not in used_set]
                    else:
                        err_msg = resp.get('err', 'Unknown') if resp else 'No response'
                        self.log.warning(f"    ✗ فشل تنفيذ المهمة #{idx_1}: {err_msg}")
                        break

                    await asyncio.sleep(random.uniform(1.6, 2.9))
            else:
                self.log.info("ℹ️ لا توجد مهام تكليف جاهزة تتوفر شروطها مع الأبطال المتاحين حالياً.")
        else:
            self.log.info(f"ℹ️ استنفد الحد اليومي لمهام التكليف ({consign_count}/{daily_limit}).")

        # فحص صندوق الهدايا التراكمي
        gift_claimed = False
        consign_num = voyage.get('consignNum', 0)
        if (consign_num // 15) > 0:
            self.log.info(f"🎁 استلام صندوق الهدايا التراكمي ({consign_num}/15)...")
            r_gift = await self.conn.query("3148", "7", {}, timeout=6.0)
            if r_gift and str(r_gift.get('err', '')) in ('0', 'None', ''):
                gift_claimed = True
                self.log.info("    ✓ تم استلام صندوق الهدايا التراكمي بنجاح.")

        msg = (
            f"🧭 اكتملت رحلات وتكليف الأبطال: "
            f"رحلات ترحال: {completed_travels} | جوائز مستلمة: {claimed_count} | مهام تكليف: {executed_count}"
        )
        return TaskResult.ok(
            msg,
            travels=completed_travels,
            claimed_rewards=claimed_count,
            dispatched_tasks=executed_count,
            gift_claimed=gift_claimed
        )


async def run_hero_consign(email: str, execute: bool = False):
    """تنفيذ الاستعلام أو تشغيل مهام تكليف الأبطال لحساب محدد"""
    sm = SessionManager()
    acc = sm.get_or_login(email)
    if not acc:
        print(f"[!] الحساب غير موجود أو فشل تسجيل الدخول: {email}")
        return

    conn = GameConnection(acc)
    print(f"[*] جاري الاتصال باللعبة للحساب: {email}...")
    if not await conn.connect():
        print("[!] فشل الاتصال بخادم اللعبة.")
        return

    # انتظار تحميل حزم التهيئة الأولية (بما فيها heroVoyageAgCtrl و heroCtrl)
    for _ in range(12):
        await asyncio.sleep(0.5)
        if 'heroVoyageAgCtrl' in conn.init_data and 'heroCtrl' in conn.init_data:
            break

    voyage = conn.init_data.get('heroVoyageAgCtrl', {})
    if not voyage:
        print("[!] لم يتم العثور على بيانات تكليف الأبطال (heroVoyageAgCtrl).")
        await conn.close()
        return

    raw_heroes = conn.init_data.get('heroCtrl', [])
    player_hero_ids = [h.get('id') for h in raw_heroes if isinstance(h, dict)]

    # =============================================================
    #  المرحلة الأولى: رحلات الأبطال (Hero Voyage / Travel)
    # =============================================================
    print("\n" + "=" * 60)
    print(f"  🧭 رحلات الأبطال (Hero Voyage) — {email}")
    print("=" * 60)

    cur_travel_hero = voyage.get('heroId', 0)

    # 1. الاستعلام عن البطل المختار واختيار بطل إذا لم يكن هناك بطل مختار
    if not cur_travel_hero or cur_travel_hero == 0:
        target_hero_id = 5502011 if 5502011 in player_hero_ids else (player_hero_ids[0] if player_hero_ids else 5502011)
        if execute:
            print(f"[*] لم يتم تحديد بطل للترحال، جاري اختيار البطل {target_hero_id}...")
            r_choose = await conn.query("3148", "1", {"cId": target_hero_id}, timeout=8.0)
            if r_choose and str(r_choose.get('err', '')) in ('0', 'None', ''):
                cur_travel_hero = target_hero_id
                voyage['heroId'] = target_hero_id
                print(f"    ✓ تم اختيار البطل {target_hero_id} بنجاح.")
                await asyncio.sleep(2.0)
            else:
                err_c = r_choose.get('err', 'Unknown') if r_choose else 'Timeout'
                print(f"    ✗ فشل اختيار البطل: {err_c}")
        else:
            print(f"  • البطل المختار للترحال: لا يوجد (سيتم اختيار {target_hero_id} تلقائياً عند التنفيذ)")
    else:
        print(f"  • البطل المختار للترحال: {cur_travel_hero}")

    # 2. الاستعلام عن عدد المرات المسموحة للترحال
    voyage_count = voyage.get('voyageCount', {})
    used_physical = int(voyage_count.get("1", 0)) if isinstance(voyage_count, dict) else 0
    max_physical_travels = 10
    remaining_travels = max(0, max_physical_travels - used_physical)

    print(f"  • الترحال المنفذ اليوم : {used_physical} من {max_physical_travels}")
    print(f"  • المتبقي للترحال     : {remaining_travels} رحلات")
    print("=" * 60)

    # 3. تنفيذ الترحالات إن طُلب ذلك
    if execute and remaining_travels > 0 and cur_travel_hero:
        print(f"\n🚀 بدء تنفيذ رحلات الأبطال المتبقية ({remaining_travels} رحلات)...")
        completed_travels = 0
        while remaining_travels > 0:
            print(f"[*] جاري إطلاق رحلة ترحال #{completed_travels + 1} (المتبقي: {remaining_travels})...")
            r_travel = await conn.query("3148", "3", {
                "isItem": 0,
                "isGuide": False,
                "amount": 1
            }, timeout=8.0)

            if r_travel and str(r_travel.get('err', '')) in ('0', 'None', ''):
                completed_travels += 1
                remaining_travels -= 1
                v_data = r_travel.get('data', {})
                if 'voyageCount' in v_data:
                    voyage['voyageCount'] = v_data['voyageCount']
                print(f"    ✓ تم تنفيذ رحلة الترحال بنجاح.")
            else:
                err_t = r_travel.get('err', 'Unknown') if r_travel else 'Timeout'
                print(f"    ✗ توقف الترحال: {err_t}")
                break

            # فترة زمنية ثانيتين بين كل ترحال
            await asyncio.sleep(2.0)

        print(f"[✓] اكتملت مرحلة الترحال (تم تنفيذ {completed_travels} رحلات). الانتقال إلى تكليف الأبطال...")
    elif remaining_travels <= 0:
        print("\n[!] استنفدت جميع رحلات الترحال لليوم (10/10). الانتقال إلى تكليف الأبطال...")
    else:
        print("\n💡 وضع الاستعلام فقط للترحال. للتنفيذ أضف الخيار: --execute")

    # =============================================================
    #  المرحلة الثانية: استلام جوائز مهام التكليف المنجزة (Award Consign)
    # =============================================================
    print("\n" + "=" * 60)
    print(f"  🎁 جوائز مهام التكليف المنجزة — {email}")
    print("=" * 60)

    consign_tasks = voyage.get('consignTasks', [])
    now_ts = int(time.time())

    # 1. الاستعلام عن المهام الجاهزة للاستلام
    ready_to_claim = []
    for idx_0, t in enumerate(consign_tasks):
        idx_1 = idx_0 + 1
        status = t.get('status', 1)
        start_time = t.get('startTime', 0)
        tid = t.get('id', 0)
        duration = get_task_duration(tid)

        # المهمة جاهزة إذا كانت status == 3 أو انتهت مدتها الزمنية
        if status == 3 or (status == 2 and start_time > 0 and now_ts >= (start_time + duration)):
            ready_to_claim.append((idx_1, t))

    if not ready_to_claim:
        print("  • لا توجد صناديق/جوائز مهام منجزة جاهزة للاستلام حالياً.")
        print("  • المتابعة مباشرة إلى تكليف الأبطال...")
    else:
        print(f"  • تم العثور على {len(ready_to_claim)} مهام منجزة جاهزة للاستلام:")
        for idx_1, t in ready_to_claim:
            print(f"    - خانة #{idx_1} (Task ID {t.get('id')})")

        if execute:
            print(f"\n🚀 بدء استلام جوائز المهام المنجزة ({len(ready_to_claim)} مهام)...")
            claimed_count = 0
            for idx_1, t in ready_to_claim:
                print(f"[*] جاري استلام جائزة الخانة #{idx_1} (Task ID {t.get('id')})...")
                resp = await conn.query("3148", "5", {"index": idx_1}, timeout=8.0)
                if resp and str(resp.get('err', '')) in ('0', 'None', ''):
                    print(f"    ✓ تم استلام الجائزة بنجاح.")
                    claimed_count += 1
                    r_data = resp.get('data', {})
                    if 'consignTasks' in r_data:
                        consign_tasks = r_data['consignTasks']
                        voyage['consignTasks'] = consign_tasks
                    if 'consignNum' in r_data:
                        voyage['consignNum'] = r_data['consignNum']
                else:
                    err_c = resp.get('err', 'Unknown') if resp else 'Timeout'
                    print(f"    ✗ تعذر استلام الجائزة: {err_c}")

                # فاصل زمني ثانيتين بين كل استلام
                await asyncio.sleep(2.0)

            print(f"[✓] تم الانتهاء من استلام الجوائز ({claimed_count} مستلمة). المتابعة إلى تكليف الأبطال...")
            # تحديث قائمة المهام وبيانات التكليف بعد الاستلام
            await asyncio.sleep(0.5)
            voyage = conn.init_data.get('heroVoyageAgCtrl', voyage)
            consign_tasks = voyage.get('consignTasks', consign_tasks)
        else:
            print("\n💡 وضع الاستعلام فقط. لاستلام الجوائز تلقائياً أضف الخيار: --execute")

    # =============================================================
    #  المرحلة الثالثة: تكليف الأبطال (Hero Consign)
    # =============================================================
    # 1. الاستعلام عن عدد المرات المسموحة
    consign_count = voyage.get('consignCount', 0)
    daily_limit = 5
    remaining = max(0, daily_limit - consign_count)
    consign_num = voyage.get('consignNum', 0)

    print("\n" + "=" * 60)
    print(f"  📜 تكليف الأبطال (Hero Consign) — {email}")
    print("=" * 60)
    print(f"  • المنفذ اليوم       : {consign_count} من {daily_limit}")
    print(f"  • المتبقي المسموح به : {remaining} تنفيذات")
    print(f"  • العداد التراكمي    : {consign_num} / 15 (صندوق الهدايا)")
    print("=" * 60)

    # تجهيز الأبطال وتحديد الأبطال المشغولين
    busy_hero_ids = set()
    for t in consign_tasks:
        if t.get('status') == 2:  # قيد التنفيذ
            heros = t.get('heros')
            if isinstance(heros, list):
                busy_hero_ids.update(heros)
            elif isinstance(heros, dict):
                busy_hero_ids.update(heros.values())

    raw_heroes = conn.init_data.get('heroCtrl', [])
    available_heroes = []
    for h in raw_heroes:
        hid = h.get('id')
        if hid in busy_hero_ids:
            continue
        meta = HEROES_META.get(hid, {})
        available_heroes.append({
            'id': hid,
            'lv': int(h.get('lv', 1)),
            'star': int(h.get('star', 1)),
            'quality': meta.get('quality', 0),
            'type': meta.get('type', 0),
        })

    print(f"[*] إجمالي أبطال اللاعب: {len(raw_heroes)} | الأبطال المتاحون حالياً: {len(available_heroes)}")

    # 3. استعراض المهام المتوفرة
    print("\n📋 قائمة المهام وحالة التوفر:")
    solvable_tasks = []

    for idx_0, t in enumerate(consign_tasks):
        idx_1 = idx_0 + 1
        tid = t.get('id')
        cid = t.get('condition')
        status = t.get('status', 1)

        status_text = {
            1: "جاهزة (Ready)",
            2: "قيد التنفيذ (Running)",
            3: "مكتملة بانتظار الاستلام (Award)",
            4: "منتهية (Finished)"
        }.get(status, str(status))

        # جلب الشروط بصيغة نصية
        cond_desc = []
        if cid in TASK_CONDITIONS:
            spot, rids = TASK_CONDITIONS[cid]
            for r in rids:
                if r in REQUIREMENTS:
                    cond_desc.append(describe_req(REQUIREMENTS[r]))

        solution = None
        if status == 1:
            solution = solve_task(available_heroes, cid)
            if solution:
                solvable_tasks.append((idx_1, t, solution))

        sol_str = f"نعم ✓ (الأبطال: {solution})" if solution else ("لا ✗" if status == 1 else "-")
        print(f"  [{idx_1:02d}] مهمة {tid} | شروط: {', '.join(cond_desc)} | الحالة: {status_text} | إمكانية التنفيذ: {sol_str}")

    # 4. التنفيذ إذا طُلب ذلك
    if execute:
        if remaining <= 0:
            print("\n[!] لا توجد مرات متبقية للتنفيذ اليوم (5/5 مكتملة).")
        elif not solvable_tasks:
            print("\n[!] لا توجد مهام جاهزة تتوفر شروطها مع أبطالك الحاليين.")
        else:
            print(f"\n🚀 بدء تنفيذ المهام المتاحة حتى استهلاك المرات المتبقية ({remaining})...")
            executed_count = 0

            for idx_1, t, _ in solvable_tasks:
                if remaining <= 0:
                    break

                cid = t.get('condition')
                # إعادة حل المهمة مع الأبطال المتبقين فعلياً بعد كل مهمة
                sol = solve_task(available_heroes, cid)
                if not sol:
                    continue

                print(f"\n[*] جاري إرسال المهمة #{idx_1} (Task ID {t.get('id')}) بالأبطال: {sol}...")
                resp = await conn.query("3148", "4", {
                    "index": idx_1,
                    "heroIds": sol
                }, timeout=8.0)

                is_success = bool(resp and str(resp.get('err', '')) in ('0', 'None', ''))

                if is_success:
                    print(f"    ✓ تم بدء المهمة بنجاح!")
                    executed_count += 1
                    remaining -= 1
                    # إزالة الأبطال المستخدمين من القائمة المتاحة
                    used_set = set(sol)
                    available_heroes = [h for h in available_heroes if h['id'] not in used_set]
                else:
                    err_msg = resp.get('err', 'Unknown') if resp else 'No response'
                    print(f"    ✗ فشل تنفيذ المهمة: {err_msg}")
                    break

                # فترة زمنية ثانيتين بين كل تنفيذ مهمة
                await asyncio.sleep(2.0)

            print(f"\n[✓] تم الانتهاء. إجمالي المهام التي تم إطلاقها: {executed_count}")
    else:
        print("\n💡 وضع الاستعلام فقط. لتنفيذ المهام المتوفرة تلقائياً أضف الخيار: --execute")

    # فحص صندوق الهدايا
    gift_count = consign_num // 15
    if gift_count > 0 and execute:
        print(f"\n🎁 يتوفر صندوق هدايا تراكمي ({consign_num}/15)! جاري الاستلام...")
        await conn.query("3148", "7", {}, timeout=6.0)

    await conn.close()
    print("\n[+] تم إغلاق الاتصال.")


def main():
    parser = argparse.ArgumentParser(description="تكليف الأبطال (Hero Consign)")
    parser.add_argument("--email", type=str, default="", help="البريد الإلكتروني للحساب")
    parser.add_argument("--execute", action="store_true", help="تنفيذ المهام المتوفرة حتى انتهاء المرات المسموحة")
    args = parser.parse_args()

    email = args.email
    if not email:
        # اختيار أول حساب مسجل في session_cache
        cache_path = os.path.join(_ROOT_DIR, 'database', 'session_cache.json')
        if not os.path.exists(cache_path):
            cache_path = os.path.join(_ROOT_DIR, 'session_cache.json')
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                accounts = list(cache_data.get('accounts', {}).keys())
                # نفضل الحسابات المعروفة الشغالة
                for acc in accounts:
                    if acc in ['hmzawyha44@gmail.com', 'daysofempire2024@gmail.com', 'samartilleli@yopmail.com']:
                        email = acc
                        break
                if not email and accounts:
                    email = accounts[0]
            except Exception:
                pass

    if not email:
        print("[!] يرجى تحديد البريد الإلكتروني للحساب عبر --email")
        return

    asyncio.run(run_hero_consign(email, execute=args.execute))


if __name__ == '__main__':
    main()
