
"""
tasks/stronghold.py — مهمة الهجوم على المعقل / الملجأ (Stronghold Attack)
═══════════════════════════════════════════════════════════════════════

الاستخدام:
    python tasks/stronghold.py --email "jzarco.all@gmail.com" --minlv 15 --maxlv 30 --marches 2
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
from tasks.monster import get_monster_recommended_power, calculate_smart_combat_troops
from tasks.exclude_manager import get_manager as _get_exclude_manager
from tasks.march_capacity import get_castle_march_capacity, enforce_safe_march_troops, record_learned_march_capacity


# ════════════════════════════════════════════════════════════════════
#  إعدادات افتراضية في رأس الملف (قابلة للتعديل والربط بـ Firebase)
# ════════════════════════════════════════════════════════════════════

DEFAULT_MIN_LV             = 1                # أدنى مستوى للمعقل
DEFAULT_MAX_LV             = 35               # أقصى مستوى للمعقل
DEFAULT_MAX_MARCHES        = 2                # الحد الأقصى للمسيرات
DEFAULT_SEARCH_RANGE       = 100              # نطاق البحث
DEFAULT_FORMATION_ID       = 1                # رقم التشكيلة المفضلة (1..5) [0 = تلقائي ذكي بدون تشكيلة ثابتة]
DEFAULT_TROOPS_COUNT       = 30000            # عدد الجنود الافتراضي / المناسب للمسيرة

# ════════════════════════════════════════════════════════════════════
#  مهمة الهجوم على المعقل (StrongholdTask)
# ════════════════════════════════════════════════════════════════════

class StrongholdTask(BaseTask):

    name = "stronghold"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self._heroes    : list     = []
        self._busy      : Set[int] = set()
        self._used_army : Dict[int, int] = {}
        self._used_pets : Set[int] = set()
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

    # ── المهمة الرئيسية ───────────────────────────────────────────

    async def run(self) -> TaskResult:
        cfg = self.config
        min_lv          = int(cfg.get('min_lv', DEFAULT_MIN_LV))
        max_lv          = int(cfg.get('max_lv', DEFAULT_MAX_LV))
        max_marches     = int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))
        search_range    = int(cfg.get('search_range', DEFAULT_SEARCH_RANGE))
        formation_id    = int(cfg.get('formation_id', DEFAULT_FORMATION_ID))
        troops_cfg      = int(cfg.get('troops_count', DEFAULT_TROOPS_COUNT))

        self.log.info(f"🏰 [المعقل] بدء الهجوم (لفل: {min_lv}-{max_lv} | المطلوب: {max_marches})")

        if not self._heroes:
            await self._load_heroes()

        sent_count = 0
        consecutive_errors = 0
        self._busy      = set(cfg.get('busy_heroes', cfg.get('busy', [])))
        self._used_army = {}
        self._used_pets = set()

        wait_for_queue = bool(cfg.get('wait_for_queue', cfg.get('wait_queue', False)))
        wait_interval  = float(cfg.get('wait_interval', 15.0))
        max_wait_cycles = int(cfg.get('max_wait_cycles', 40))
        wait_cycles = 0
        cmd_opting_retries = 0
        last_result = None

        while sent_count < max_marches:
            current_target_idx = sent_count + 1
            self.log.debug(f"🚀 محاولة إرسال مسيرة المعقل رقم ({current_target_idx}/{max_marches})...")
            result_code = await self._send_one_stronghold(min_lv, max_lv, search_range, formation_id, troops_cfg)
            last_result = result_code

            if result_code == "SUCCESS":
                sent_count += 1
                consecutive_errors = 0
                cmd_opting_retries = 0
                wait_cycles = 0
                if sent_count < max_marches:
                    spacing = round(random.uniform(4.5, 7.5), 2)
                    self.log.debug(f"🛡️ انتظار {spacing} ثانية قبل مسيرة المعقل التالية...")
                    await asyncio.sleep(spacing)
            elif result_code == "QUEUE_FULL":
                if not wait_for_queue or wait_cycles >= max_wait_cycles:
                    self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل.")
                    break

                cur_act = await self.get_active_marches_count()
                max_q = max(getattr(self, '_max_castle_queues', 0), max(1, cur_act))
                self._max_castle_queues = max_q

                queue_freed = False
                while wait_for_queue and wait_cycles < max_wait_cycles:
                    wait_cycles += 1
                    self.log.info(
                        f"⏳ [طوابير ممتلئة ({cur_act}/{max_q}) - دورة {wait_cycles}/{max_wait_cycles}] "
                        f"جميع الفيالق مشغولة بالخارج — الانتظار {wait_interval:.0f} ثانية لتفريغ فيلق للمعقل..."
                    )
                    await asyncio.sleep(wait_interval)

                    cur_act = await self.get_active_marches_count()
                    self.log.info(f"🔍 [فحص الفيالق] الفيالق النشطة بالخارج حالياً: {cur_act}/{max_q}")
                    if cur_act < max_q:
                        self.log.info(
                            f"✅ [توفر فيلق شاغر] عاد أحد الفيالق إلى القلعة بنجاح ({cur_act}/{max_q}) "
                            f"— استئناف هجوم المعقل الآن!"
                        )
                        queue_freed = True
                        break
                    else:
                        self.log.info(
                            f"⏳ [الفيالق لا تزال ممتلئة ({cur_act}/{max_q})] "
                            f"لم يعد أي فيلق بعد — مواصلة الانتظار {wait_interval:.0f} ثانية أخرى دون إرسال محاولات فاشلة..."
                        )

                if queue_freed:
                    self._busy.clear()
                    self._used_army.clear()
                    await self._load_heroes()
                    continue
                else:
                    self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل بعد استنفاد دورات الانتظار.")
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
            elif result_code == "STAMINA_EMPTY":
                self.log.warning("🛑 نفدت طاقة اللورد بالكامل — إيقاف محاولات الهجوم على المعقل.")
                break
            elif result_code in ("CMD_OPTING", "16001", "CMD_OPTING_FAILED"):
                cmd_opting_retries += 1
                if cmd_opting_retries <= 2:
                    wait_time = round(random.uniform(10.0, 16.0), 2)
                    self.log.warning(
                        f"⏳ [خادم اللعبة مشغول - كود 16001] انتظار {wait_time} ثانية لفك القفل "
                        f"ثم إعادة تجهيز مسيرة المعقل نظيفاً من البداية (محاولة {cmd_opting_retries}/2)..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    self.log.warning("🏁 استمر انشغال خادم اللعبة (كود 16001) بعد المحاولات — إيقاف الدورة مؤقتاً.")
                    break
            elif result_code in ("NO_TARGET", "TARGET_OCCUPIED"):
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    self.log.warning("⚠️ 3 محاولات بحث متتالية دون جدوى — إنهاء المهمة.")
                    break
                await asyncio.sleep(round(random.uniform(1.8, 3.2), 2))
                continue
            else:
                consecutive_errors += 1
                if consecutive_errors >= 2:
                    break
                await asyncio.sleep(round(random.uniform(1.8, 3.2), 2))

        self.log.info(f"🏁 [المعقل] تم إرسال {sent_count}/{max_marches} مسيرة بنجاح")
        if sent_count > 0:
            return TaskResult.ok(
                f"✅ تم إرسال {sent_count} مسيرة هجوم على المعقل",
                sent=sent_count,
                queue_full=(last_result == "QUEUE_FULL"),
                stop_reason=last_result
            )
        if last_result == "QUEUE_FULL":
            return TaskResult.fail("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل (كود 8004: QUEUE_FULL)", queue_full=True, stop_reason="QUEUE_FULL")
        if last_result == "STAMINA_EMPTY":
            return TaskResult.fail("🛑 نفدت طاقة اللورد بالكامل", stop_reason="STAMINA_EMPTY")
        return TaskResult.fail("لم يتم إرسال أي مسيرة هجوم على المعقل", retry_after=120)

    # ── إرسال مسيرة معقل واحدة ────────────────────────────────────

    async def _send_one_stronghold(self, min_lv: int, max_lv: int, search_range: int, formation_id: int, troops_cfg: int) -> str:
        # 1. جلب إحداثيات القلعة عبر الدالة المركزية في BaseTask (Zero-Request)
        cx, cy = await self.get_castle_coords()
        if not cx or not cy:
            self.log.warning("⚠️ تعذر تحديد إحداثيات القلعة للهجوم على المعقل!")
            return "ERROR"

        # 2. جلب معرف المملكة عبر الدالة المركزية في BaseTask (Zero-Request)
        kingdom_id = await self.get_kingdom_id()


        # 3. البحث عن المعاقل (mapType: 26, subType: 0)
        exclude_map = await self._exclude_mgr.get_exclude_map(self.uid, kingdom_id=kingdom_id)
        search_payload = {
            "mapType": 26,
            "subType": 0,
            "num": 5,
            "y": cy,
            "x": cx,
            "exclude": exclude_map,
            "range": search_range,
        }
        if min_lv and max_lv:
            search_payload["minLv"] = min_lv
            search_payload["maxLv"] = max_lv

        r_search = await self.conn.query('2011', '3', search_payload)
        raw_candidates = r_search.get('result', []) if r_search else []
        candidates = [c for c in raw_candidates if str(c.get('id', '')) not in exclude_map]
        if not candidates:
            self.log.warning(f"⚠️ لا توجد معاقل متاحة في نطاق {search_range}!")
            return "NO_TARGET"

        # 4. جلب القوات المتوفرة وغير المشغولة بالقلعة عبر الدالة المركزية في BaseTask (Zero-Request)
        available = await self.get_available_troops()

        # 5. جلب بيانات التشكيلة المحفوظة عبر الدالة المركزية في BaseTask (Zero-Request)
        form_heroes, form_pets, form_rune_pages, form_army_dict = await self.get_formation(formation_id)


        # 6. اختيار وفحص أبطال المسيرة عبر الدالة المركزية (فحص التشكيلة أو استبدالهم بأبطال هجوم وقتال)
        chosen_heroes = await self.get_combat_heroes(form_heroes=form_heroes, max_count=2, exclude_busy=self._busy)
        if not chosen_heroes:
            self.log.warning("⚠️ لا يوجد أي بطل متاح بالقلعة نهائياً!")
            return "NO_HEROES"
        self.log.debug(f"⚔️ أبطال المسيرة المعتمدون: {chosen_heroes}")

        # 7. تجهيز جيش المسيرة بدقة وفق التشكيلة المحددة دون أي زيادة فوقها
        max_safe_capacity = get_castle_march_capacity(self.conn, chosen_heroes=chosen_heroes)
        try:
            army_list = await self.get_march_army(
                form_army_dict=form_army_dict,
                formation_id=formation_id,
                available_troops=available,
                fallback_count=troops_cfg,
                max_capacity=max_safe_capacity
            )
        except RuntimeError as e:
            self.log.warning(f"🛑 {e}")
            return "WEAK_ARMY"

        if not army_list:
            self.log.warning("⚠️ لا توجد قوات متوفرة بالقلعة لإرسال المسيرة!")
            return "NO_ARMY"

        total_troops = sum(item['num'] for item in army_list)
        self.log.info(f"⚔️ [جيش المسيرة] تم تجهيز {total_troops:,} جندي وفق التشكيلة بدقة دون أي زيادة.")

        # 8. اختيار الحيوان الأليف والرونات
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
            pets_list = await self.select_combat_pet()

        rune_pages_list = self.get_rune_pages(form_rune_pages)

        self.log.debug(f"🛡️ تشكيلة المعقل: إجمالي جنود: {total_troops:,}")

        # 9. محاولة إرسال مسيرة المعقل على أهداف القائمة تباعاً
        for target in candidates:
            target_id = target.get('id')
            tx, ty    = target.get('x'), target.get('y')
            t_lv      = target.get('level', '?')
            self.log.debug(f"🎯 محاولة استهداف معقل: ID={target_id} عند ({tx}, {ty}) لفل={t_lv}")
            # حجز مؤقت في الذاكرة فقط — لن يُثبت في الملف إلا بعد نجاح الهجوم
            await self._exclude_mgr.reserve(self.uid, target_id, kingdom_id=kingdom_id)

            attack_payload = {
                "needSend": False,
                "runePages": rune_pages_list,
                "heros": chosen_heroes,
                "matrixType": 1,
                "mapId": int(kingdom_id),
                "moveLineType": 3,               # 3 = مسار الهجوم على المعقل
                "data": {
                    "data": {
                        "judianState": 1         # 1 = حالة المعقل (judianState)
                    },
                    "to": {
                        "y": int(ty),
                        "x": int(tx),
                        "id": str(target_id)
                    },
                    "army": army_list
                },
                "pets": pets_list
            }

            r_attack = await self.conn.query('1007', '2', attack_payload)
            if not r_attack:
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                continue

            err = str(r_attack.get('err', '0'))
            if err == '0':
                self.log.info(f"✅ [المعقل] إرسال مسيرة بنجاح إلى معقل لفل {t_lv} عند ({tx}, {ty}) | جنود: {total_troops:,}")
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
            elif err == '8009':
                self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "NO_ARMY"
            elif err in ('8032', '10002', '10003'):
                self.log.warning(f"🛑 نفدت طاقة اللورد بالكامل (كود {err})")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "STAMINA_EMPTY"
            elif err == '9007020':
                for hid in chosen_heroes:
                    self._busy.add(hid)
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "HERO_BUSY"
            elif err == '8035':
                current_total = sum(item['num'] for item in army_list)
                if current_total > 400:
                    reduced_troops = max(300, int(current_total * 0.85))
                    record_learned_march_capacity(self.conn, reduced_troops)
                    self.log.warning(f"⚠️ خطأ 8035 (تجاوز سعة مسيرة اللورد) | إعادة المحاولة فوراً بضبط القوات ({reduced_troops:,} جندي)...")
                    army_list = enforce_safe_march_troops(army_list, reduced_troops)
                    total_troops = sum(itm['num'] for itm in army_list)
                    attack_payload['data']['army'] = army_list
                    r_retry = await self.conn.query('1007', '2', attack_payload)
                    if r_retry and str(r_retry.get('err', '0')) == '0':
                        self.log.info(f"✅ تم إرسال مسيرة المعقل بنجاح بعد ضبط القوات! → {target_id} (لفل {t_lv}) | أبطال={chosen_heroes} | جنود={total_troops:,}")
                        await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                        for hid in chosen_heroes:
                            self._busy.add(hid)
                        for item in army_list:
                            self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                        return "SUCCESS"
                # تنبيه: خطأ 8035 هو خطأ سعة مسيرة وليس انشغال معقل — لا نستبعد المعقل من قاعدة البيانات
                self.log.warning(f"⚠️ خطأ 8035 في المعقل {target_id} | تحرير الهدف وتعديل سقف السعة دون حظر المعقل...")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                continue
            elif err == '16001':
                self.log.warning(
                    f"   ⚠️ خادم اللعبة مشغول بعملية سابقة (كود 16001: Err_CMD_OPTING) — "
                    f"تحرير المعقل {target_id} لإعادة تجهيز المسيرة نظيفاً من البداية..."
                )
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "CMD_OPTING"
            elif err in ('8062', '8063', '8060', '8013', '8002', '8026', '8003', '9007062') or (err.isdigit() and 8000 <= int(err) < 8100 and err not in ('8004', '8009', '8032')):
                self.log.warning(f"⚠️ المعقل {target_id} غير متاح أو مشغول بمعركة أخرى (كود {err}) — فحص معقل بديل فوراً...")
                # المعقل مشغول فعلاً — نثبت الاستبعاد
                await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                continue
            else:
                self.log.error(f"❌ خطأ غير معروف: {err} | الهدف={target_id}")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "ERROR"

        return "TARGET_OCCUPIED"

# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Stronghold Attack Bot — الهجوم على المعقل / الملجأ")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--minlv", type=int, default=DEFAULT_MIN_LV, help=f"أدنى لفل للمعقل [افتراضي: {DEFAULT_MIN_LV}]")
    parser.add_argument("--maxlv", type=int, default=DEFAULT_MAX_LV, help=f"أعلى لفل للمعقل [افتراضي: {DEFAULT_MAX_LV}]")
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
            "min_lv": args.minlv,
            "max_lv": args.maxlv,
            "max_marches": args.marches,
            "search_range": args.range,
            "formation_id": args.formation
        }

        task = StrongholdTask(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
