# -*- coding: utf-8 -*-
"""
tasks/fountain.py — مهمة النافورة الملكية / بئر الأمنيات (Trevi Fountain Task)
═══════════════════════════════════════════════════════════════════════════════

بروتوكول النافورة الملكية (Trevi Fountain Protocol - CMD 1018):
  - الاستعلام الأولي وحالة النافورة:
    cmd: "1018", subcmd: "1", data: {}
    يرجع عدد المرات المجانية المتاحة اليوم (multipleTimes) وإحصائيات الشراء.
  - طلب الشراء / الأمنية (Wish):
    cmd: "1018", subcmd: "2", data: {"resourceType": resourceType}
    الموارد المدعومة:
      - 1022: القمح (Food) 🌾
      - 1023: الخشب (Wood) 🪵
      - 1006: الحديد (Steel / Iron) ⛏️
      - 1024: الفحم (Safe Iron / Coal) 🪨
      - 1025: الألماس (Diamond / Mithril) 💎

ميزات المهمة:
  1. 🔍 استعلام ذكي وتلقائي عن عدد المرات المجانية المتبقية اليوم (multipleTimes).
  2. 🎁 استهلاك المرات المجانية كاملة تلقائياً وشراء الموارد المحددة بالتناوب الذكي (Round-Robin).
  3. 💰 دعم اختياري وآمن للشراء بالذهب بعد انتهاء المجاني:
     - معطل افتراضياً حمايةً لرصيد اللاعب (--use-gold).
     - تحديد سقف أقصى للذهب المستهلك (--max-gold).
     - تحديد عدد مرات الشراء بالذهب لكل مورد (--gold-times).
  4. 🛡️ نظام أمان متقدم ضد الحظر (Anti-Ban Jitter) بفواصل زمنية عشوائية وطبيعية.
  5. 📊 رصد المضاعفات الحرجة للنافورة (Critical Multipliers 2x, 3x, 5x, 10x!).

الاستخدام كملف مستقل:
    python tasks/fountain.py --email "burcudemr@gmail.com" --check-only
    python tasks/fountain.py --email "burcudemr@gmail.com" --resources food,wood,iron
    python tasks/fountain.py --email "burcudemr@gmail.com" --use-gold --gold-times 2 --max-gold 30
    python tasks/fountain.py --email "king7moe1990@gmail.com" --resources food,wood --use-gold --gold-resources iron:4,diamond:6

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
import random
import time
import argparse
from typing import Any, Dict, List, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection
from core.session_manager import SessionManager


# ════════════════════════════════════════════════════════════════════
#  تعريف الموارد المدعومة في النافورة
# ════════════════════════════════════════════════════════════════════

SUPPORTED_RESOURCES: Dict[str, Dict[str, Any]] = {
    "food": {
        "id": 1022,
        "name": "القمح",
        "icon": "🌾",
        "counter_key": "foodMultipleTimes",
        "pay_counter_key": "payFoodMultipleTimes",
        "aliases": ["food", "wheat", "قمح", "طعام"]
    },
    "wood": {
        "id": 1023,
        "name": "الخشب",
        "icon": "🪵",
        "counter_key": "woodMultipleTimes",
        "pay_counter_key": "payWoodMultipleTimes",
        "aliases": ["wood", "خشب"]
    },
    "iron": {
        "id": 1006,
        "name": "الحديد",
        "icon": "⛏️",
        "counter_key": "ironMultipleTimes",
        "pay_counter_key": "payIronMultipleTimes",
        "aliases": ["iron", "steel", "حديد"]
    },
    "coal": {
        "id": 1024,
        "name": "الفحم",
        "icon": "🪨",
        "counter_key": "mithrilMultipleTimes",
        "pay_counter_key": "payMithrilMultipleTimes",
        "aliases": ["coal", "safe_iron", "فحم"]
    },
    "diamond": {
        "id": 1025,
        "name": "الألماس",
        "icon": "💎",
        "counter_key": "steelMultipleTimes",
        "pay_counter_key": "paySteelMultipleTimes",
        "aliases": ["diamond", "mithril", "الماس", "ألماس"]
    }
}

# مستويات فتح الموارد في القلعة لضمان عدم طلب مورد غير متاح في المزارع
RESOURCE_MIN_CASTLE_LEVEL: Dict[str, int] = {
    "food": 1,
    "wood": 1,
    "iron": 10,
    "coal": 15,
    "diamond": 23,
}

# خريطة المعرفات الرقمية وأسماء الموارد
ID_TO_RESOURCE_KEY: Dict[int, str] = {v["id"]: k for k, v in SUPPORTED_RESOURCES.items()}


def parse_resource_selection(raw: Optional[Any]) -> Tuple[List[str], Dict[str, Optional[int]]]:
    """
    تحليل الموارد المطلوبة من الإعدادات أو سطر الأوامر، مع دعم تحديد الحصص (مثل food:5,wood:3).
    يرجع (قائمة_الموارد, قاموس_الحصص).
    """
    if not raw:
        return list(SUPPORTED_RESOURCES.keys()), {k: None for k in SUPPORTED_RESOURCES}

    tokens: List[str] = []
    if isinstance(raw, str):
        tokens = [t.strip() for t in raw.split(",") if t.strip()]
    elif isinstance(raw, (list, tuple, set)):
        tokens = [str(t).strip() for t in raw if str(t).strip()]

    selected: List[str] = []
    quotas: Dict[str, Optional[int]] = {}

    for token in tokens:
        count_limit: Optional[int] = None
        # دعم صيغ مثل food:5 أو food=5 أو قمح:10
        if ":" in token:
            parts = token.split(":", 1)
            name_part = parts[0].strip().lower()
            try:
                count_limit = int(parts[1].strip())
            except ValueError:
                count_limit = None
        elif "=" in token:
            parts = token.split("=", 1)
            name_part = parts[0].strip().lower()
            try:
                count_limit = int(parts[1].strip())
            except ValueError:
                count_limit = None
        else:
            name_part = token.strip().lower()

        matched_key: Optional[str] = None
        if name_part.isdigit() and int(name_part) in ID_TO_RESOURCE_KEY:
            matched_key = ID_TO_RESOURCE_KEY[int(name_part)]
        else:
            for k, meta in SUPPORTED_RESOURCES.items():
                if name_part == k or name_part in meta["aliases"] or name_part == meta["name"]:
                    matched_key = k
                    break

        if matched_key and matched_key not in selected:
            selected.append(matched_key)
            quotas[matched_key] = count_limit

    if not selected:
        selected = list(SUPPORTED_RESOURCES.keys())
        quotas = {k: None for k in selected}

    return selected, quotas


class FountainTask(BaseTask):
    """
    مهمة النافورة الملكية / بئر الأمنيات (Trevi Fountain).
    """
    name = "fountain"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)

        self.check_only: bool = self.config.get("check_only", False)
        self.allow_gold: bool = bool(self.config.get("allow_gold", False))
        self.gold_times_per_res: int = int(self.config.get("gold_times", 0))

        # 🛡️ قفل صارم: لا يُسمح بالشراء بالذهب إلا إذا كان allow_gold صريحاً وكان gold_times > 0
        raw_use_gold = bool(self.config.get("use_gold", False))
        if self.allow_gold and self.gold_times_per_res > 0 and (raw_use_gold or self.allow_gold):
            self.use_gold = True
        else:
            self.use_gold = False
            self.allow_gold = False
            self.gold_times_per_res = 0

        self.max_gold: int = int(self.config.get("max_gold", 200))

        # تحليل الموارد المستهدفة وحصصها
        self.target_resources, self.target_quotas = parse_resource_selection(self.config.get("resources"))

        # تحليل موارد الشراء بالذهب إذا تم تخصيصها بشكل مستقل
        gold_res_raw = self.config.get("gold_resources")
        if gold_res_raw:
            self.gold_resources, self.gold_quotas = parse_resource_selection(gold_res_raw)
        else:
            self.gold_resources = list(self.target_resources)
            self.gold_quotas = {k: (self.gold_times_per_res if self.gold_times_per_res > 0 else None) for k in self.gold_resources}

        # تصفية الموارد حسب مستوى القلعة لحماية المزارع والحسابات الصغيرة
        self._filter_resources_by_castle_level(self._get_castle_level())

    def _get_castle_level(self) -> int:
        """استخراج مستوى القلعة (bid 101) من بيانات الاتصال أو الإعدادات."""
        cfg_lv = self.config.get("castle_level")
        if cfg_lv:
            try:
                lv = int(cfg_lv)
                if lv > 0:
                    return lv
            except (ValueError, TypeError):
                pass

        try:
            blist = self.conn.init_data.get("cityCtrl", {}).get("blist", [])
            for b in blist:
                binfo = b.get("binfo", {})
                if str(binfo.get("bid", "")) == "101":
                    return int(binfo.get("lv", 1))
        except Exception:
            pass

        try:
            pctrl = self.conn.init_data.get("playerCtrl", {})
            if "level" in pctrl:
                return int(pctrl["level"])
        except Exception:
            pass

        try:
            base = self.conn.init_data.get("lordInfoCtrl", {}).get("base", {})
            if "level" in base:
                return int(base["level"])
        except Exception:
            pass

        return 40

    def _filter_resources_by_castle_level(self, castle_lv: int) -> None:
        """استبعاد الموارد غير المفتوحة لمستوى القلعة لمنع طلبات غير صحيحة أو سحب ذهب غير مقصود."""
        filtered_targets = []
        for r in self.target_resources:
            min_lv = RESOURCE_MIN_CASTLE_LEVEL.get(r, 1)
            if castle_lv >= min_lv:
                filtered_targets.append(r)
            else:
                self.log.info(f"🔒 استبعاد {SUPPORTED_RESOURCES[r]['name']} من المجاني (يتطلب قلعة لفل {min_lv}، الحالي: {castle_lv})")

        if not filtered_targets:
            filtered_targets = ["food", "wood"]

        self.target_resources = filtered_targets

        if self.use_gold:
            filtered_gold = []
            for r in self.gold_resources:
                min_lv = RESOURCE_MIN_CASTLE_LEVEL.get(r, 1)
                if castle_lv >= min_lv:
                    filtered_gold.append(r)
                else:
                    self.log.info(f"🔒 استبعاد {SUPPORTED_RESOURCES[r]['name']} من الشراء بالذهب (يتطلب قلعة لفل {min_lv}، الحالي: {castle_lv})")
            self.gold_resources = filtered_gold

    # ──────────────────────────────────────────────────────────────────
    #  الاستعلام الذكي عن حالة النافورة (1018 / 1)
    # ──────────────────────────────────────────────────────────────────

    async def get_fountain_status(self) -> Optional[Dict[str, Any]]:
        """
        إرسال طلب الاستعلام الأولي 1018 / 1 واستخراج بيانات النافورة.
        """
        self.log.info("🔍 جارٍ الاستعلام عن بيانات النافورة الملكية (CMD 1018 / 1)...")
        try:
            rsp = await self.conn.query("1018", "1", {})
            if not rsp:
                self.log.warning("⚠️ لم يتم استلام رد على استعلام النافورة!")
                return None

            err = str(rsp.get("err", ""))
            if err != "0":
                self.log.error(f"❌ خطأ من السيرفر أثناء استعلام النافورة: {err}")
                return None

            data = rsp.get("data", {})
            free_times = int(data.get("multipleTimes", 0)) + int(data.get("pornMultipleTimes", 0))

            resource_stats = {}
            for key, meta in SUPPORTED_RESOURCES.items():
                total_times = int(data.get(meta["counter_key"], 0))
                pay_times = int(data.get(meta["pay_counter_key"], 0))
                # حساب تكلفة الذهب القادمة إذا نفد المجاني: (payTimes + 1) * 2
                next_gold_cost = (pay_times + 1) * 2

                resource_stats[key] = {
                    "key": key,
                    "id": meta["id"],
                    "name": meta["name"],
                    "icon": meta["icon"],
                    "total_times": total_times,
                    "pay_times": pay_times,
                    "next_gold_cost": next_gold_cost
                }

            return {
                "free_wishes": free_times,
                "raw_data": data,
                "resources": resource_stats
            }

        except Exception as e:
            self.log.error(f"❌ استثناء أثناء الاستعلام عن النافورة: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────
    #  تنفيذ أمنية / شراء مورد واحد (1018 / 2)
    # ──────────────────────────────────────────────────────────────────

    async def _make_wish(self, resource_key: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        إرسال طلب أمنية لمورد محدد (CMD 1018 / 2).
        """
        meta = SUPPORTED_RESOURCES[resource_key]
        payload = {"resourceType": meta["id"]}

        try:
            rsp = await self.conn.query("1018", "2", payload)
            if not rsp:
                return False, {}, "لم يتم استلام رد من السيرفر"

            err = str(rsp.get("err", ""))
            if err == "0":
                data = rsp.get("data", {})
                return True, data, "نجاح"
            elif err == "1002":
                return False, {}, "الذهب غير كافٍ للشراء بالذهب"
            elif err == "1028":
                return False, {}, "المورد غير متاح حالياً"
            else:
                return False, {}, f"كود الخطأ: {err}"

        except Exception as e:
            return False, {}, f"استثناء أثناء إرسال الطلب: {e}"

    # ──────────────────────────────────────────────────────────────────
    #  الحصول على رصيد الذهب الحالي للقلعة
    # ──────────────────────────────────────────────────────────────────

    def _get_current_gold(self) -> int:
        """
        قراءة رصيد الذهب الحالي للحساب من init_data (lordInfoCtrl.base.gold).
        """
        lord_info = self.conn.init_data.get("lordInfoCtrl", {})
        base = lord_info.get("base", {})
        gold = base.get("gold")
        if gold is None:
            pctrl = self.conn.init_data.get("playerCtrl", {})
            status_data = pctrl.get("statusData", {})
            gold = status_data.get("gold") or status_data.get("coin") or 0
        try:
            return int(gold)
        except (ValueError, TypeError):
            return 0

    # ──────────────────────────────────────────────────────────────────
    #  عرض تقرير الاستعلام في الطرفية
    # ──────────────────────────────────────────────────────────────────

    def _print_status_report(self, status: Dict[str, Any]):
        free_wishes = status["free_wishes"]
        resources = status["resources"]
        current_gold = self._get_current_gold()

        print("\n" + "═" * 70)
        print("  ⛲ تقرير النافورة الملكية / بئر الأمنيات (Trevi Fountain Status)")
        print("═" * 70)
        print(f"  🎁 المرات المجانية المتاحة حالياً:  {free_wishes} مرة")
        print(f"  💰 رصيد الذهب الحالي في القلعة:     {current_gold:,} ذهب")
        print("─" * 70)
        print(f"  {'المورد':<16} {'مرات اليوم':<12} {'مرات الذهب':<12} {'تكلفة الذهب القادمة':<16}")
        print("─" * 70)

        # عرض الموارد المحددة في المجاني والذهب
        display_keys = list(dict.fromkeys(self.target_resources + (self.gold_resources if self.use_gold else [])))
        for key in display_keys:
            r = resources[key]
            print(f"  {r['icon']} {r['name']:<12} {r['total_times']:<12} {r['pay_times']:<12} {r['next_gold_cost']} ذهب")

        print("═" * 70 + "\n")

    # ──────────────────────────────────────────────────────────────────
    #  تنفيذ المهمة بالكامل (Main Execution Flow)
    # ──────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """
        تنفيذ الاستعلام والشراء المجاني وشراء الذهب (إذا كان مفعلاً).
        """
        # انتظار وصول بيانات init_data الخاصة بالحساب والذهب ومباني المدينة
        for _ in range(15):
            if ("lordInfoCtrl" in self.conn.init_data or "cityCtrl" in self.conn.init_data) and len(self.conn.init_data) > 10:
                break
            await asyncio.sleep(0.3)

        # إعادة تصفية الموارد بدقة بعد تحميل بيانات المباني والمدينة للتأكد من فتح الموارد
        castle_lv = self._get_castle_level()
        self._filter_resources_by_castle_level(castle_lv)

        status = await self.get_fountain_status()
        if not status:
            return TaskResult.fail("فشل في جلب بيانات النافورة الملكية من السيرفر!")

        self._print_status_report(status)

        if self.check_only:
            return TaskResult.ok(
                f"🔍 تم فحص النافورة بنجاح: {status['free_wishes']} مرة مجانية متاحة",
                free_wishes=status["free_wishes"],
                resources=status["resources"]
            )

        free_wishes_left = status["free_wishes"]
        resources_dict = status["resources"]

        # 🛡️ قاعدة أمان صارمة: إذا لم تكن هناك أمنيات مجانية متاحة، لا يتم عمل المهمة ولا يتم الشراء بالذهب
        if free_wishes_left <= 0:
            msg = "ℹ️ لا توجد مرات مجانية متاحة في نافورة الأمنيات اليوم (تم إنهاء المهمة دون استهلاك ذهب)."
            self.log.info(msg)
            return TaskResult.ok(msg, free_wishes=0, gold_spent=0)

        total_free_done = 0
        total_paid_done = 0
        total_gold_spent = 0
        total_resources_gained: Dict[str, int] = {k: 0 for k in SUPPORTED_RESOURCES}

        # ── المرحلة 1: تنفيذ الأمنيات المجانية بالكامل ──
        if free_wishes_left > 0:
            self.log.info(f"🎁 بدء تنفيذ الأمنيات المجانية ({free_wishes_left} مرة متوفرة)...")
            res_cycle = list(self.target_resources)
            free_done_per_res: Dict[str, int] = {k: 0 for k in self.target_resources}

            while free_wishes_left > 0:
                # تصفية الموارد التي لم تصل لحصتها المحددة بعد
                available_res = [
                    k for k in res_cycle
                    if (self.target_quotas.get(k) is None or free_done_per_res[k] < self.target_quotas[k])
                ]
                if not available_res:
                    self.log.info("🎯 تم الوصول للحصص المطلوبة لجميع الموارد المحددة في الأمنيات المجانية.")
                    break

                cur_res_key = available_res[total_free_done % len(available_res)]
                cur_meta = SUPPORTED_RESOURCES[cur_res_key]

                # فاصل أمان ضد الحظر
                if total_free_done > 0:
                    jitter = round(random.uniform(1.6, 2.9), 2)
                    self.log.info(f"🛡️ انتظار أمان بشري: {jitter} ثانية...")
                    await asyncio.sleep(jitter)

                # قراءة رصيد الذهب قبل إرسال الطلب المجاني
                gold_before_wish = self._get_current_gold()

                self.log.info(f"👉 طلب مجاني: {cur_meta['icon']} {cur_meta['name']} (المتبقي: {free_wishes_left})...")
                ok, data, err_msg = await self._make_wish(cur_res_key)

                if not ok:
                    self.log.warning(f"❌ فشل تنفيذ الأمنية المجانية لـ {cur_meta['name']}: {err_msg}")
                    break

                # 🛡️ حراسة فورية صارمة لرصيد الذهب: إذا كان الشراء بالذهب معطلاً، نتحقق أن رصيد الذهب لم ينقص إطلاقاً
                if not self.use_gold:
                    gold_after_wish = self._get_current_gold()
                    if gold_after_wish < gold_before_wish:
                        spent_gold = gold_before_wish - gold_after_wish
                        self.log.critical(
                            f"🚨 طوارئ! تم رصد نقص {spent_gold} ذهب أثناء طلب أمنية مجانية لـ {cur_meta['name']} والشراء بالذهب معطل! إيقاف المهمة فوراً."
                        )
                        return TaskResult.fail(
                            f"🚨 إيقاف طارئ: خصم غير مصرح به للذهب ({spent_gold} ذهب) أثناء طلب مجاني لـ {cur_meta['name']}. تم إيقاف المهمة فوراً."
                        )

                # قراءة النتيجة
                add_res = int(data.get("addResource", 0))
                multiplier = int(data.get("must", 1))
                free_wishes_left = int(data.get("multipleTimes", 0)) + int(data.get("pornMultipleTimes", 0))

                total_free_done += 1
                free_done_per_res[cur_res_key] += 1
                total_resources_gained[cur_res_key] += add_res

                mult_str = f"🔥 (مضاعف {multiplier}x!)" if multiplier > 1 else ""
                print(f"  ✅ [مجاني] {cur_meta['icon']} {cur_meta['name']}: +{add_res:,} مورد {mult_str} | المتبقي المجاني: {free_wishes_left}")

            self.log.info(f"🏁 انتهت المرات المجانية. تم تنفيذ {total_free_done} أمنية مجانية.")
        else:
            self.log.info("ℹ️ لا توجد مرات مجانية متاحة اليوم.")

        # ── المرحلة 2: الشراء بالذهب (إذا تم تفعيله من قبل المستخدم بشكل صريح ومؤكد) ──
        if self.use_gold and self.allow_gold and self.gold_times_per_res > 0:
            self.log.info(f"💰 بدء الشراء بالذهب (أقصى ذهب: {self.max_gold})...")
            current_gold = self._get_current_gold()

            # متابعة الشراء لكل مورد مطلوب
            for res_key in self.gold_resources:
                res_meta = SUPPORTED_RESOURCES[res_key]
                paid_done_for_res = 0
                res_limit = self.gold_quotas.get(res_key)
                if res_limit is None:
                    res_limit = self.gold_times_per_res if self.gold_times_per_res > 0 else 0

                if res_limit <= 0:
                    continue

                while paid_done_for_res < res_limit:
                    # الاستعلام عن التكلفة القادمة
                    cur_pay_times = resources_dict[res_key]["pay_times"]
                    next_cost = (cur_pay_times + 1) * 2

                    # التحقق من سقف الذهب الإجمالي
                    if total_gold_spent + next_cost > self.max_gold:
                        self.log.warning(f"🛑 تم الوصول للحد الأقصى للذهب المسموح بصرفه ({self.max_gold} ذهب)!")
                        break

                    # التحقق من رصيد الذهب المتوفر
                    if current_gold < next_cost:
                        self.log.warning(f"🛑 رصيد الذهب غير كافٍ ({current_gold} < {next_cost})!")
                        break

                    # فاصل أمان ضد الحظر
                    jitter = round(random.uniform(1.8, 3.2), 2)
                    self.log.info(f"🛡️ انتظار أمان بشري: {jitter} ثانية...")
                    await asyncio.sleep(jitter)

                    self.log.info(f"👉 طلب بالذهب: {res_meta['icon']} {res_meta['name']} (التكلفة: {next_cost} ذهب)...")
                    ok, data, err_msg = await self._make_wish(res_key)

                    if not ok:
                        self.log.warning(f"❌ فشل الشراء بالذهب لـ {res_meta['name']}: {err_msg}")
                        break

                    add_res = int(data.get("addResource", 0))
                    multiplier = int(data.get("must", 1))

                    # تحديث العدادات
                    resources_dict[res_key]["pay_times"] += 1
                    paid_done_for_res += 1
                    total_paid_done += 1
                    total_gold_spent += next_cost
                    current_gold -= next_cost
                    total_resources_gained[res_key] += add_res

                    mult_str = f"🔥 (مضاعف {multiplier}x!)" if multiplier > 1 else ""
                    print(f"  💎 [بالذهب] {res_meta['icon']} {res_meta['name']}: +{add_res:,} مورد {mult_str} | التكلفة: {next_cost} ذهب (المصروف: {total_gold_spent}/{self.max_gold})")

        # ── تقرير الملخص النهائي ──
        summary_lines = [
            f"🎯 تم تنفيذ {total_free_done} أمنية مجانية",
        ]
        if total_paid_done > 0:
            summary_lines.append(f"{total_paid_done} أمنية بالذهب (مصروف: {total_gold_spent} ذهب)")

        gained_parts = []
        all_active_keys = list(dict.fromkeys(self.target_resources + (self.gold_resources if self.use_gold else [])))
        for k in all_active_keys:
            g = total_resources_gained.get(k, 0)
            if g > 0:
                gained_parts.append(f"{SUPPORTED_RESOURCES[k]['icon']} {SUPPORTED_RESOURCES[k]['name']}: +{g:,}")

        summary_msg = " | ".join(summary_lines)
        if gained_parts:
            summary_msg += "\n  📊 الموارد المكتسبة: " + " | ".join(gained_parts)

        return TaskResult.ok(
            summary_msg,
            free_done=total_free_done,
            paid_done=total_paid_done,
            gold_spent=total_gold_spent,
            gained=total_resources_gained
        )


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول كملف مستقل (CLI Runner)
# ════════════════════════════════════════════════════════════════════

async def _cli_main():
    parser = argparse.ArgumentParser(description="مهمة النافورة الملكية / بئر الأمنيات (Trevi Fountain Task)")
    parser.add_argument("--email", type=str, help="البريد الإلكتروني للحساب")
    parser.add_argument("--check-only", action="store_true", help="استعلام فقط وعرض حالة النافورة دون تنفيذ أمنيات")
    parser.add_argument("--resources", type=str, default=None, help="الموارد المطلوبة (مثلاً food,wood,iron أو food:5,wood:5)")
    parser.add_argument("--use-gold", action="store_true", help="السماح بالشراء بالذهب بعد انتهاء المجاني")
    parser.add_argument("--gold-resources", type=str, default=None, help="الموارد المخصصة للشراء بالذهب (مثلاً food:2,iron:1)")
    parser.add_argument("--gold-times", type=int, default=0, help="عدد مرات الشراء بالذهب لكل مورد (افتراضي: 0)")
    parser.add_argument("--max-gold", type=int, default=200, help="الحد الأقصى لإجمالي الذهب المسموح بصرفه (افتراضي: 200)")
    args = parser.parse_args()

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

    print(f"📡 جارٍ الاتصال بالحساب: {target_email}...")
    conn = GameConnection(acc)
    if not await conn.connect():
        print("❌ فشل الاتصال بالسيرفر!")
        return

    config = {
        "check_only": args.check_only,
        "resources": args.resources,
        "use_gold": args.use_gold,
        "gold_resources": args.gold_resources,
        "gold_times": args.gold_times,
        "max_gold": args.max_gold
    }

    task = FountainTask(conn, config)
    res = await task.run()

    print(f"\n📊 النتيجة النهائية:\n  {res.message}\n")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(_cli_main())
