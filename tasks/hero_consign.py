# -*- coding: utf-8 -*-
"""
أداة رحلات وتكليف الأبطال (Hero Voyage & Consign)
CMD: 3148
  - Subcmd 1: اختيار البطل للترحال (Choose Hero) -> {"cId": int}
  - Subcmd 3: إطلاق الترحال (Voyage Travel) -> {"isItem": 0, "isGuide": false, "amount": 1}
  - Subcmd 4: بدء مهمة تكليف (Start Consign) -> {"index": int, "heroIds": [id1, id2, ...]}
  - Subcmd 5: استلام جائزة مهمة مكتملة (Award Consign) -> {"index": int}
  - Subcmd 7: استلام صندوق الهدايا التراكمي (15 مهمة)
 python tasks/hero_consign.py --email burcudemr@gmail.com --execute
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
from typing import Any, Dict, List, Optional, Tuple

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


def get_task_quality(task_id: int) -> int:
    """
    تعيد رتبة أولوية المهمة بناءً على معرّفها (taskID) من سورس كود اللعبة:
      quality=4 → برتقالي (أولوية 4 — الأعلى)
      quality=3 → بنفسجي  (أولوية 3)
      quality=2 → أزرق    (أولوية 2)
      غير معروف → أولوية 1 (الأدنى — احتياط لأي لون مستقبلي)
    المصدر: hero_consign_task.lua — config_server
    """
    tid = int(task_id)
    if tid >= 440000:
        return 4  # 🟠 برتقالي
    elif tid >= 430000:
        return 3  # 🟣 بنفسجي
    elif tid >= 420000:
        return 2  # 🔵 أزرق
    return 1      # ❓ لون غير معروف — أدنى أولوية احتياطاً


def _is_resp_ok(resp: Any) -> bool:
    """التحقق الآمن من نجاح استجابة السيرفر وتفادي أخطاء ردود القوائم."""
    return isinstance(resp, dict) and str(resp.get('err', '')) in ('0', 'None', '')


def _get_resp_err(resp: Any) -> str:
    """استخراج كود الخطأ بأمان تام دون افتراض أن الرد قاموس دائماً."""
    if isinstance(resp, dict):
        return str(resp.get('err', 'Unknown'))
    return str(resp) if resp is not None else 'Timeout'


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

        raw_voyage = self.conn.init_data.get('heroVoyageAgCtrl', {}) if self.conn else {}
        if isinstance(raw_voyage, list):
            voyage = raw_voyage[0] if (raw_voyage and isinstance(raw_voyage[0], dict)) else {}
        elif isinstance(raw_voyage, dict):
            voyage = raw_voyage
        else:
            voyage = {}

        if not voyage or not isinstance(voyage, dict):
            msg = "لم يتم العثور على بيانات تكليف الأبطال (heroVoyageAgCtrl) في حزم التهيئة."
            self.log.warning(msg)
            return TaskResult.fail(msg)

        raw_heroes = self.conn.init_data.get('heroCtrl', []) if self.conn else []
        player_hero_ids = [h.get('id') for h in raw_heroes if isinstance(h, dict) and h.get('id')]

        # ── المرحلة الأولى: رحلات الأبطال (Hero Voyage / Travel) ──
        cur_travel_hero = voyage.get('heroId', 0) if isinstance(voyage, dict) else 0
        if not cur_travel_hero or cur_travel_hero == 0:
            target_hero_id = 5502011 if 5502011 in player_hero_ids else (player_hero_ids[0] if player_hero_ids else 5502011)
            self.log.info(f"[*] لم يتم تحديد بطل للترحال، جاري اختيار البطل {target_hero_id}...")
            r_choose = await self.conn.query("3148", "1", {"cId": target_hero_id}, timeout=8.0)
            if _is_resp_ok(r_choose):
                cur_travel_hero = target_hero_id
                voyage['heroId'] = target_hero_id
                self.log.info(f"    ✓ تم اختيار البطل {target_hero_id} للترحال بنجاح.")
                await asyncio.sleep(random.uniform(1.5, 2.5))
            else:
                err_c = _get_resp_err(r_choose)
                self.log.warning(f"    ✗ فشل اختيار البطل للترحال: {err_c}")

        voyage_count = voyage.get('voyageCount', {}) if isinstance(voyage, dict) else {}
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

                if _is_resp_ok(r_travel):
                    completed_travels += 1
                    remaining_travels -= 1
                    v_data = r_travel.get('data', {}) if isinstance(r_travel, dict) else {}
                    if isinstance(v_data, dict) and 'voyageCount' in v_data:
                        voyage['voyageCount'] = v_data['voyageCount']
                    self.log.info(f"    ✓ تم تنفيذ رحلة الترحال #{completed_travels} بنجاح.")
                else:
                    err_t = _get_resp_err(r_travel)
                    self.log.warning(f"    ✗ توقف الترحال: {err_t}")
                    break

                await asyncio.sleep(random.uniform(1.6, 2.8))
        else:
            self.log.debug(f"ℹ️ رحلات الأبطال (الترحال): مكتملة مسبقاً ({used_physical}/10).")

        # ── المرحلة الثانية: استلام جوائز مهام التكليف المنجزة (Award Consign) ──
        raw_consign_tasks = voyage.get('consignTasks', []) if isinstance(voyage, dict) else []
        if isinstance(raw_consign_tasks, dict):
            consign_tasks = [v for v in raw_consign_tasks.values() if isinstance(v, dict)]
        elif isinstance(raw_consign_tasks, list):
            consign_tasks = [t for t in raw_consign_tasks if isinstance(t, dict)]
        else:
            consign_tasks = []

        now_ts = int(time.time())

        ready_to_claim = []
        for idx_0, t in enumerate(consign_tasks):
            if not isinstance(t, dict):
                continue
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
                if _is_resp_ok(resp):
                    claimed_count += 1
                    self.log.info(f"    ✓ تم استلام جائزة الخانة #{idx_1} بنجاح.")
                    r_data = resp.get('data', {}) if isinstance(resp, dict) else {}
                    if isinstance(r_data, dict):
                        if 'consignTasks' in r_data:
                            fresh_tasks = r_data['consignTasks']
                            if isinstance(fresh_tasks, dict):
                                consign_tasks = [v for v in fresh_tasks.values() if isinstance(v, dict)]
                            elif isinstance(fresh_tasks, list):
                                consign_tasks = [x for x in fresh_tasks if isinstance(x, dict)]
                            voyage['consignTasks'] = consign_tasks
                        if 'consignNum' in r_data:
                            voyage['consignNum'] = r_data['consignNum']
                else:
                    err_c = _get_resp_err(resp)
                    self.log.warning(f"    ✗ تعذر استلام جائزة الخانة #{idx_1}: {err_c}")

                await asyncio.sleep(random.uniform(1.5, 2.7))

            fresh_voyage = self.conn.init_data.get('heroVoyageAgCtrl', voyage) if self.conn else voyage
            if isinstance(fresh_voyage, list):
                voyage = fresh_voyage[0] if (fresh_voyage and isinstance(fresh_voyage[0], dict)) else voyage
            elif isinstance(fresh_voyage, dict):
                voyage = fresh_voyage
            raw_consign_tasks = voyage.get('consignTasks', consign_tasks) if isinstance(voyage, dict) else consign_tasks
            if isinstance(raw_consign_tasks, dict):
                consign_tasks = [v for v in raw_consign_tasks.values() if isinstance(v, dict)]
            elif isinstance(raw_consign_tasks, list):
                consign_tasks = [x for x in raw_consign_tasks if isinstance(x, dict)]
        else:
            self.log.debug("ℹ️ لا توجد صناديق/جوائز مهام منجزة جاهزة للاستلام حالياً. المتابعة إلى تكليف الأبطال...")

        # ── المرحلة الثالثة: تكليف الأبطال (Hero Consign) ──
        consign_count = int(voyage.get('consignCount', 0) or 0) if isinstance(voyage, dict) else 0
        daily_limit = 5
        remaining = max(0, daily_limit - consign_count)

        busy_hero_ids = set()
        for t in consign_tasks:
            if not isinstance(t, dict):
                continue
            if t.get('status') == 2:
                heros = t.get('heros')
                if isinstance(heros, list):
                    busy_hero_ids.update([int(x) for x in heros if str(x).isdigit()])
                elif isinstance(heros, dict):
                    busy_hero_ids.update([int(x) for x in heros.values() if str(x).isdigit()])

        available_heroes = []
        for h in raw_heroes:
            if not isinstance(h, dict):
                continue
            hid = h.get('id')
            if not hid or hid in busy_hero_ids:
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
                if not isinstance(t, dict):
                    continue
                idx_1 = idx_0 + 1
                cid = t.get('condition')
                status = t.get('status', 1)
                if status == 1:
                    sol = solve_task(available_heroes, cid)
                    if sol:
                        solvable_tasks.append((idx_1, t, sol))

            # ترتيب المهام تنازلياً حسب لون الرتبة: 🟠 برتقالي → 🟣 بنفسجي → 🔵 أزرق → ❓ غير معروف
            solvable_tasks.sort(
                key=lambda x: get_task_quality(x[1].get('id', 0) if isinstance(x[1], dict) else 0),
                reverse=True
            )

            if solvable_tasks:
                self.log.info(f"🚀 بدء تنفيذ مهام التكليف المتاحة (المتبقي: {remaining})...")
                for idx_1, t, _ in solvable_tasks:
                    if remaining <= 0:
                        break
                    if not isinstance(t, dict):
                        continue
                    cid = t.get('condition')
                    sol = solve_task(available_heroes, cid)
                    if not sol:
                        continue

                    resp = await self.conn.query("3148", "4", {
                        "index": idx_1,
                        "heroIds": sol
                    }, timeout=8.0)

                    if _is_resp_ok(resp):
                        executed_count += 1
                        remaining -= 1
                        self.log.info(f"    ✓ تم بدء مهمة التكليف #{idx_1} بنجاح بالأبطال {sol}")
                        used_set = set(sol)
                        available_heroes = [h for h in available_heroes if h['id'] not in used_set]
                    else:
                        err_msg = _get_resp_err(resp)
                        self.log.warning(f"    ✗ فشل تنفيذ المهمة #{idx_1}: {err_msg}")
                        break

                    await asyncio.sleep(random.uniform(1.6, 2.9))
            else:
                self.log.info("ℹ️ لا توجد مهام تكليف جاهزة تتوفر شروطها مع الأبطال المتاحين حالياً.")
        else:
            self.log.info(f"ℹ️ استنفد الحد اليومي لمهام التكليف ({consign_count}/{daily_limit}).")

        # فحص صندوق الهدايا التراكمي
        gift_claimed = False
        consign_num = int(voyage.get('consignNum', 0) or 0) if isinstance(voyage, dict) else 0
        if (consign_num // 15) > 0:
            self.log.info(f"🎁 استلام صندوق الهدايا التراكمي ({consign_num}/15)...")
            r_gift = await self.conn.query("3148", "7", {}, timeout=6.0)
            if _is_resp_ok(r_gift):
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


async def _run_cli(email: str) -> None:
    """تشغيل HeroConsignTask مباشرة من CLI — نفس منطق البوت العام بالضبط."""
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

    result = await HeroConsignTask(conn, {"enabled": True}).run()
    print(f"\n[✓] النتيجة: {result.message}")
    await conn.close()


def main():
    parser = argparse.ArgumentParser(description="تكليف الأبطال — CLI (يستخدم نفس منطق البوت العام)")
    parser.add_argument("--email", required=True, help="البريد الإلكتروني للحساب")
    # --execute محتفظ به للتوافق مع الأوامر القديمة (لا تأثير، المهمة تُنفَّذ دائماً)
    parser.add_argument("--execute", action="store_true", help="(افتراضي) تنفيذ المهمة")
    args = parser.parse_args()
    asyncio.run(_run_cli(args.email))


if __name__ == '__main__':
    main()

