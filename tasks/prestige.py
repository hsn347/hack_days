# -*- coding: utf-8 -*-
"""
tasks/prestige.py — مهمة مهام الهيبة اليومية داخل المدينة (Daily City Prestige Quests)
══════════════════════════════════════════════════════════════════════════════════════════
تُنفّذ هذه المهمة مهام الهيبة اليومية (مهام المجد) الخاصة بداخل القلعة حصراً:
  1. متجر المهربين (Smuggler Store / Traveling Merchant - CMD 1024):
     - الشراء بالموارد العادية فقط (قمح، خشب، حديد، فضة).
     - استبعاد الذهب والعملات الخاصة نهائياً وممنوع إنفاق أي ذهب.
  2. طاحونة الماء (Watermill - CMD 1001/9, 1010):
     - تفعيل كافة مباني الموارد ومسموح الشراء من متجر التحالف.
  3. تدريب وتجنيد الجيوش (Troop Training - CMD 1005):
     - تدريب 250 وحدة من كل نوع على مستوى 1 (مشاة، فرسان، رماة، عربات).
  4. حصن الحرب وتدريب الفخاخ (Fortress Traps - CMD 1005):
     - تدريب الفخاخ بالحد الأقصى المتاح تلقائياً.
  5. تبديل القمح بوسام الحرب (War Badge Exchange - CMD 1067/2):
     - استبدال القمح بوسام الحرب مرة واحدة يومياً لإكمال مهمة المجد (#4112024).

ملاحظة هامة:
مهام المسيرات الخارجية لمهام الهيبة:
  - قتل غزاة الهيبة (Prestige Invaders)
  - الهجوم على معقل الهيبة (Prestige Stronghold)
  - جمع موارد الهيبة بحمولة 25k (Prestige Gather)
تم نقلها بالكامل لتُدار مركزياً وذكياً ضمن أولويات منسق الفيالق الموحد (March Manager).
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from tasks.watermill import WatermillTask
from tasks.train import TrainTask
from tasks.fortress import FortressTask
from game_client import GameConnection

# ── الموارد والسلع المسموح الشراء بها في متجر المهربين ──────────────
ALLOWED_SMUGGLER_CURRENCIES: Dict[int, Dict[str, str]] = {
    1002: {"name": "قمح", "icon": "🌾"},
    1003: {"name": "خشب", "icon": "🪵"},
    1004: {"name": "حديد", "icon": "⛏️"},
    1005: {"name": "فضة/ألماس", "icon": "💎"}
}
DISALLOWED_CURRENCIES: Set[int] = {1001, 1006}  # الذهب والعملات الخاصة - ممنوع نهائياً

# ── معرفات مهام الهيبة اليومية لداخل القلعة (meritoriousTaskCtrl) ───
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    "smuggler": 4112022,        # متجر المهربين / التاجر المتجول (10 مشتريات)
    "watermill": 4112027,       # تعزيز إنتاج حقول الموارد (الساقية - مرة واحدة)
    "badge_exchange": 4112024,  # تبديل الموارد بوسام الحرب (مرة واحدة)
    "fortress": 4112014,        # تصنيع الفخاخ في حصن الحرب (250 وحدة)
    "train_infantry": 4112010,  # تدريب المشاة (250 وحدة)
    "train_cavalry": 4112011,   # تدريب الخيالة (250 وحدة)
    "train_archers": 4112012,   # تدريب الرماة (250 وحدة)
    "train_chariots": 4112013,  # تدريب العربات (250 وحدة)
}

# أسماء وتسميات مهام الهيبة للعرض والتقارير
PRESTIGE_QUEST_NAMES: Dict[str, str] = {
    "smuggler": "متجر المهربين (10 مشتريات بالموارد)",
    "watermill": "تعزيز إنتاج حقول الموارد (الساقية)",
    "badge_exchange": "تبديل القمح بوسام الحرب (مرة واحدة)",
    "fortress": "تصنيع فخاخ حصن الحرب (250 وحدة)",
    "train_infantry": "تدريب المشاة (250 وحدة)",
    "train_cavalry": "تدريب الخيالة (250 وحدة)",
    "train_archers": "تدريب الرماة (250 وحدة)",
    "train_chariots": "تدريب العربات (250 وحدة)",
}

# أسماء أنواع القوات والفخاخ بالعربية لسجلات البوت
TRAIN_TYPE_NAMES_AR: Dict[str, str] = {
    "infantry": "مشاة",
    "cavalry": "خيالة",
    "archers": "رماة",
    "chariots": "عربات",
    "traps": "فخاخ",
}

# ── أسماء وتسميات المهام الفرعية لمهام الهيبة داخل القلعة ───────────
PRESTIGE_SUBTASKS_ALL: List[str] = [
    "smuggler",
    "watermill",
    "train",
    "fortress",
    "badge_exchange",
]

PRESTIGE_SUBTASK_ALIASES: Dict[str, str] = {
    # 1. متجر المهربين
    "smuggler": "smuggler", "المهربين": "smuggler", "متجر": "smuggler", "متجر المهربين": "smuggler", "shop": "smuggler",
    # 2. الساقية
    "watermill": "watermill", "الساقية": "watermill", "ساقية": "watermill", "طاحونة": "watermill",
    # 3. تدريب الجنود
    "train": "train", "تدريب": "train", "الجنود": "train", "تدريب الجنود": "train", "troops": "train",
    # 4. حصن الحرب
    "fortress": "fortress", "حصن": "fortress", "الحصن": "fortress", "فخاخ": "fortress", "حصن الحرب": "fortress", "traps": "fortress",
    # 5. تبديل وسام الحرب
    "badge_exchange": "badge_exchange", "badge": "badge_exchange", "war_badge": "badge_exchange",
    "وسام": "badge_exchange", "وسام الحرب": "badge_exchange", "تبديل الوسام": "badge_exchange",
    "تبديل": "badge_exchange", "exchange": "badge_exchange",
}


# ════════════════════════════════════════════════════════════════════
#  كلاس مهمة مهام الهيبة (PrestigeTask)
# ════════════════════════════════════════════════════════════════════

class PrestigeTask(BaseTask):
    """
    مهمة مهام الهيبة اليومية داخل القلعة:
      1. متجر المهربين: الشراء بالموارد العادية فقط بدون أي ذهب.
      2. الساقية: تفعيل مباني الموارد الأربعة.
      3. تدريب الجنود: تدريب 250 جندي مستوى 1 من كل ثكنة.
      4. حصن الحرب: تدريب فخاخ الحصن.
    """
    name = "prestige"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        # عدد المشتريات المستهدفة من متجر المهربين (10 مرات لمهام الهيبة)
        self.target_smuggler_buys = int(self.config.get("smuggler_buys", self.config.get("target_buys", 10)))
        self.max_gold_refresh = int(self.config.get("max_gold_refresh", 20))
        self.subtasks_config = self.config.get("subtasks", {})

    def get_merit_level(self) -> int:
        """جلب مستوى الهيبة / الجدارة من الذاكرة الحية (meritoriousTaskCtrl.meritLv)."""
        try:
            init = getattr(self.conn, 'init_data', {}) or {}
            return int(init.get('meritoriousTaskCtrl', {}).get('meritLv', 0))
        except Exception:
            return 0

    def is_subtask_enabled(self, subtask_name: str) -> bool:
        """
        فحص ما إذا كانت مهمة فرعية محددة من مهام الهيبة مفعلة من المستخدم.
        يدعم تمرير القيمة كـ dict أو list أو str أو أعلام فردية.
        """
        key = PRESTIGE_SUBTASK_ALIASES.get(subtask_name.strip().lower(), subtask_name.strip().lower())

        # 1. إذا تم تمرير subtasks كقاموس (dict)
        if isinstance(self.subtasks_config, dict) and self.subtasks_config:
            for k, v in self.subtasks_config.items():
                alias_k = PRESTIGE_SUBTASK_ALIASES.get(str(k).strip().lower(), str(k).strip().lower())
                if alias_k == key:
                    return bool(v)

        # 2. إذا تم تمرير subtasks كقائمة (list / tuple / set)
        elif isinstance(self.subtasks_config, (list, tuple, set)):
            norm_set = {PRESTIGE_SUBTASK_ALIASES.get(str(x).strip().lower(), str(x).strip().lower()) for x in self.subtasks_config}
            if "all" in norm_set or "الكل" in norm_set:
                return True
            return key in norm_set

        # 3. إذا تم تمرير subtasks كنص مفصول بفواصل (comma-separated string)
        elif isinstance(self.subtasks_config, str):
            val = self.subtasks_config.strip().lower()
            if val in ("all", "الكل", "*", ""):
                return True
            tokens = {PRESTIGE_SUBTASK_ALIASES.get(t.strip(), t.strip()) for t in val.split(",") if t.strip()}
            return key in tokens

        # 4. فحص مباشر من جذر إعدادات المهمة
        cfg_key = f"enable_{key}"
        if cfg_key in self.config:
            return bool(self.config[cfg_key])
        if key in self.config and isinstance(self.config[key], bool):
            return self.config[key]

        return True

    async def on_start(self):
        """انتظار بيانات القلعة ومهام الهيبة عند بدء المهمة."""
        for _ in range(30):
            has_city = "cityCtrl" in self.conn.init_data
            has_merit = "meritoriousTaskCtrl" in self.conn.init_data
            if has_city and has_merit:
                break
            await asyncio.sleep(0.3)

    async def _refresh_merit_data(self) -> bool:
        """تجديد بيانات مهام الهيبة من السيرفر مباشرة عبر BaseTask."""
        return await self.refresh_prestige_data(force=True)

    def get_quest_info(self, quest_key_or_id: str | int) -> Dict[str, Any]:
        """
        جلب بيانات وإحصائيات مهمة معينة من meritoriousTaskCtrl في ذاكرة اللعبة.
        """
        if isinstance(quest_key_or_id, int):
            qid = quest_key_or_id
        else:
            norm_key = str(quest_key_or_id).strip().lower()
            qid = PRESTIGE_QUEST_IDS.get(norm_key, 0)

        merit_ctrl = self.conn.init_data.get("meritoriousTaskCtrl", {})
        if not isinstance(merit_ctrl, dict):
            return {"found": False, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

        # 1. فحص taskData (القاموس الرئيسي لمهام الهيبة اليومية)
        task_data = merit_ctrl.get("taskData", {})
        if isinstance(task_data, dict) and str(qid) in task_data:
            t_obj = task_data[str(qid)]
            if isinstance(t_obj, dict):
                c_num = int(t_obj.get("cNum", t_obj.get("c_num", 0)))
                l_num = int(t_obj.get("lNum", t_obj.get("l_num", 0)))
                status = int(t_obj.get("status", 0))
                is_done = (status == 4) or (l_num > 0 and c_num >= l_num)
                remaining = max(0, l_num - c_num) if l_num > 0 else 0
                return {
                    "found": True,
                    "task_id": qid,
                    "c_num": c_num,
                    "l_num": l_num,
                    "is_done": is_done,
                    "remaining": remaining,
                }

        # 2. فحص قائمة tasks القديمة إن وُجدت
        tasks = merit_ctrl.get("tasks", [])
        if isinstance(tasks, dict):
            tasks = list(tasks.values())

        for task_obj in tasks:
            if not isinstance(task_obj, dict):
                continue
            t_id = task_obj.get("taskId") or task_obj.get("id")
            if t_id and int(t_id) == qid:
                c_num = int(task_obj.get("c_num", task_obj.get("cNum", 0)))
                l_num = int(task_obj.get("l_num", task_obj.get("lNum", 0)))
                is_finish = int(task_obj.get("is_finish", task_obj.get("isFinish", 0)))
                is_done = (is_finish == 1) or (l_num > 0 and c_num >= l_num)
                remaining = max(0, l_num - c_num) if l_num > 0 else 0
                return {
                    "found": True,
                    "task_id": qid,
                    "c_num": c_num,
                    "l_num": l_num,
                    "is_done": is_done,
                    "remaining": remaining,
                }

        # 3. فحص daily_task (قاموس العدادات اليومية)
        daily_task = merit_ctrl.get("daily_task", {})
        if isinstance(daily_task, dict) and str(qid) in daily_task:
            c_val = int(daily_task[str(qid)])
            return {
                "found": True,
                "task_id": qid,
                "c_num": c_val,
                "l_num": 1,
                "is_done": c_val >= 1,
                "remaining": 0 if c_val >= 1 else 1,
            }

        return {"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

    def query_prestige_summary(self, keys: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """فحص حالة مهام الهيبة الداخلية."""
        target_keys = keys or ["smuggler"]
        summary = {}
        for key in target_keys:
            summary[key] = self.get_quest_info(key)
        return summary

    def log_prestige_overview(self, quests_status: Dict[str, Dict[str, Any]]):
        """طباعة ملخص حالة مهام الهيبة الداخلية في سجل البوت (مستوى DEBUG)."""
        self.log.debug("📊 ───【 فحص حالة مهام الهيبة اليومية (الاستعلام المسبق من السيرفر) 】───")
        for key, info in quests_status.items():
            name = PRESTIGE_QUEST_NAMES.get(key, key)
            if not info.get("found"):
                st_label = "❓ غير معثور عليها"
            elif info.get("is_done"):
                st_label = f"✨ مكتملة تماماً ({info['c_num']:,}/{info['l_num']:,})"
            else:
                c = info['c_num']
                l = info['l_num']
                rem = info['remaining']
                st_label = f"⏳ قيد الإنجاز ({c:,}/{l:,} — متبقي {rem:,})"
            self.log.debug(f"   • {name:<35}: {st_label}")

    def _get_castle_resources(self) -> Dict[int, float]:
        """استخراج رصيد موارد القلعة الحالية."""
        city_ctrl = self.conn.init_data.get("cityCtrl", {})
        reslist = city_ctrl.get("reslist", {}) if isinstance(city_ctrl, dict) else {}
        resources = {}
        for resid in (1002, 1003, 1004, 1005):
            try:
                resources[resid] = float(reslist.get(str(resid), 0))
            except Exception:
                resources[resid] = 0.0
        return resources

    # ════════════════════════════════════════════════════════════════
    #  الجزء 1: متجر المهربين (Smuggler Store)
    # ════════════════════════════════════════════════════════════════

    async def run_smuggler_store(self) -> Dict[str, Any]:
        """
        تنفيذ عمليات الشراء من متجر المهربين / التاجر المتجول حتى إتمام عمليات الشراء المطلوبة بالموارد:
          - فحص مسبق: إذا كانت المهمة مكتملة بالفعل في meritoriousTaskCtrl يتم تخطيها فوراً.
          - شراء البضائع بالموارد العادية حصراً (1002=قمح, 1003=خشب, 1004=حديد, 1005=فضة/ألماس).
          - استبعاد أي سلعة تباع بالذهب (1001, 1006) منعاً باتاً.
        """
        q_info = self.get_quest_info("smuggler")
        if q_info["is_done"]:
            self.log.info(
                f"✨ [استعلام مسبق] مهمة متجر المهربين مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}) "
                f"— يتم تخطي الخطوة 1 بالكامل لتوفير الموارد!"
            )
            return {
                "success": True,
                "skipped": True,
                "purchased_count": 0,
                "items": [],
                "message": f"مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']})"
            }

        needed_buys = self.target_smuggler_buys
        if q_info["found"] and q_info["remaining"] > 0:
            needed_buys = min(self.target_smuggler_buys, q_info["remaining"])
            self.log.info(f"🎯 [استعلام مسبق] تقدم المتجر الحالي: {q_info['c_num']}/{q_info['l_num']} — المطلوب إنجازه: {needed_buys} مشتريات فقط")

        self.log.info(f"🛒 ───【 الخطوة 1: متجر المهربين (المطلوب: {needed_buys} عمليات شراء بالموارد) 】───")
        store_res = {"success": True, "skipped": False, "purchased_count": 0, "items": []}

        # الاستعلام الأولي عن المتجر (1024/1)
        resp = await self.conn.query("1024", "1", {}, timeout=6)
        if not resp or str(resp.get("err", "0")) != "0":
            self.log.warning("⚠️ تعذر استلام بيانات متجر المهربين (1024/1)")
            store_res["success"] = False
            return store_res

        store_data = resp.get("data", {})
        if not store_data.get("isOpen", True):
            self.log.info("🚪 كشك متجر المهربين غير متاح حالياً بالقلعة.")
            return store_res

        shop_items: List[Dict[str, Any]] = list(store_data.get("shopItemArray", []))
        refresh_gold = int(store_data.get("refreshGold", 0))
        resources = self._get_castle_resources()
        purchased_items: List[Dict[str, Any]] = []
        total_refreshes = 0
        consecutive_errors = 0
        max_refreshes = 30

        def _has_buyable_item(items: List[Dict[str, Any]]) -> bool:
            """فحص هل توجد أي سلعة معروضة حالياً يمكن شراؤها بالموارد العادية ورصيدها متوفر."""
            for itm in items:
                if not isinstance(itm, dict):
                    continue
                sid = itm.get("shopItemID")
                pt = itm.get("pricetype")
                pr = float(itm.get("price", 0))
                ib = itm.get("isBuy", 0)
                if ib == 1 or not sid:
                    continue
                if pt in ALLOWED_SMUGGLER_CURRENCIES and pt not in DISALLOWED_CURRENCIES:
                    if resources.get(pt, 0) >= pr:
                        return True
            return False

        while len(purchased_items) < needed_buys:
            if not getattr(self.conn, "is_connected", True):
                self.log.warning("⚠️ انقطع الاتصال بالسيرفر أثناء الشراء من المتجر!")
                break

            purchased_in_this_pass = False

            # فحص وشراء السلع المعروضة مع الشراء الفوري المتتالي لأي سلعة بديلة تنزل بالموارد
            for idx in range(len(shop_items)):
                if len(purchased_items) >= needed_buys:
                    break

                # حلقة الشراء المتتالي في نفس الخانة طالما تنزل سلع بديلة بالموارد
                while len(purchased_items) < needed_buys:
                    if idx >= len(shop_items):
                        break
                    itm = shop_items[idx]
                    if not isinstance(itm, dict):
                        break
                    shop_id = itm.get("shopItemID")
                    ptype = itm.get("pricetype")
                    price = float(itm.get("price", 0))
                    is_buy = itm.get("isBuy", 0)

                    if is_buy == 1 or not shop_id:
                        break

                    # استبعاد الذهب والعملات الخاصة نهائياً
                    if ptype in DISALLOWED_CURRENCIES or ptype not in ALLOWED_SMUGGLER_CURRENCIES:
                        break

                    curr_info = ALLOWED_SMUGGLER_CURRENCIES[ptype]
                    curr_name = curr_info["name"]
                    curr_icon = curr_info["icon"]
                    avail_bal = resources.get(ptype, 0)

                    if avail_bal < price:
                        break

                    # محاكاة بشرية سريعة قبل الشراء
                    await asyncio.sleep(round(random.uniform(1.2, 2.2), 2))

                    buy_resp = await self.conn.query("1024", "3", {"shopItemID": int(shop_id)}, timeout=6)
                    if buy_resp and str(buy_resp.get("err", "0")) == "0":
                        consecutive_errors = 0
                        resources[ptype] = max(0, resources[ptype] - price)
                        purchased_items.append({"shop_id": shop_id, "currency": curr_name, "price": price})
                        self.log.info(
                            f"✅ [متجر المهربين ({len(purchased_items)}/{needed_buys})] "
                            f"تم شراء سلعة #{shop_id}! {curr_icon} السعر: {int(price):,} {curr_name}"
                        )
                        purchased_in_this_pass = True

                        # استبدال السلعة المشتراة بالسلعة البديلة الجديدة فوراً في نفس الخانة ومتابعة فحصها
                        new_item = buy_resp.get("data", {}).get("newShopItem")
                        if new_item and isinstance(new_item, dict):
                            shop_items[idx] = new_item
                            self.log.debug(f"🔄 نزلت سلعة بديلة في الخانة #{idx} (shopItemID: {new_item.get('shopItemID')})")
                        else:
                            shop_items[idx] = {}
                            break
                    else:
                        consecutive_errors += 1
                        err_c = buy_resp.get("err") if buy_resp else "timeout"
                        self.log.warning(f"⚠️ تعذر شراء السلعة #{shop_id} (كود: {err_c})")
                        if consecutive_errors >= 3:
                            break
                        break

            if len(purchased_items) >= needed_buys:
                break

            # تأكيد انتهاء سلع الموارد: إذا تم الشراء في هذه الجولة ولا زالت توجد سلع بالموارد، نكرر الفحص
            if purchased_in_this_pass and _has_buyable_item(shop_items):
                continue

            # إذا لم تعد هناك أي سلعة معروضة أو بديلة بالموارد، نلجأ للتحديث المجاني فقط
            if refresh_gold == 0 and total_refreshes < max_refreshes:
                total_refreshes += 1
                self.log.info(f"🔄 [متجر المهربين] تحديث المتجر مجاناً (التحديث #{total_refreshes})...")
                await asyncio.sleep(round(random.uniform(1.5, 2.5), 2))

                ref_resp = await self.conn.query("1024", "2", {}, timeout=6)
                if ref_resp and str(ref_resp.get("err", "0")) == "0":
                    ref_data = ref_resp.get("data", {})
                    shop_items = list(ref_data.get("shopItemArray", []))
                    refresh_gold = int(ref_data.get("refreshGold", 0))
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= 2:
                        break
            else:
                if refresh_gold > 0:
                    self.log.info(f"🛑 [متجر المهربين] التحديث القادم يتطلب {refresh_gold} ذهب — توقف تام لحماية الذهب!")
                break

        store_res["purchased_count"] = len(purchased_items)
        store_res["items"] = purchased_items
        self.log.info(f"🏁 تم إنجاز خطوة متجر المهربين بنجاح (إجمالي المشتريات بالموارد: {len(purchased_items)}/{needed_buys}).")
        return store_res

    # ════════════════════════════════════════════════════════════════
    #  الجزء 2: الساقية — تفعيل جميع مباني إنتاج الموارد
    # ════════════════════════════════════════════════════════════════

    async def run_watermill_step(self) -> Dict[str, Any]:
        """
        تشغيل مهمة الساقية لتفعيل جميع مباني الموارد (مزارع، مناشر، مناجم) لمهام الهيبة:
          - فحص مسبق: إذا كانت مهمة الهيبة مكتملة بالفعل (4112027) يتم تخطيها فوراً لحفظ نقاط التحالف.
          - مسموح بالشراء من متجر التحالف بالكامل لضمان التفعيل عند الحاجة.
        """
        q_info = self.get_quest_info("watermill")
        if q_info["is_done"]:
            self.log.info(
                f"✨ [استعلام مسبق] مهمة تعزيز إنتاج الموارد (الساقية) في الهيبة مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}) "
                f"— يتم تخطي خطوة الهيبة لتوفير نقاط شرف التحالف!"
            )
            return {
                "success": True,
                "skipped": True,
                "activated": 0,
                "message": f"مكتملة مسبقاً في الهيبة ({q_info['c_num']}/{q_info['l_num']})"
            }

        self.log.info("💧 ───【 الخطوة 2: الساقية — تفعيل جميع مباني إنتاج الموارد لمهام الهيبة 】───")
        try:
            wm_cfg = {
                "types": "all",
                "allow_shop_buy": True,
                "auto_buy": True,
                "allow_alliance_shop": True,
            }
            watermill_task = WatermillTask(self.conn, wm_cfg)
            await watermill_task.on_start()
            res = await watermill_task.run()
            self.log.info(f"🏁 اكتملت مهمة الساقية: {res.message if res else 'تم التنفيذ'}")
            return {
                "success": bool(res and res.success),
                "message": res.message if res else "No response",
                "activated": res.data.get("activated", 0) if (res and res.data) else 0,
            }
        except Exception as e:
            self.log.warning(f"⚠️ خطأ في مهمة الساقية: {e}")
            return {"success": False, "message": str(e), "activated": 0}

    # ════════════════════════════════════════════════════════════════
    #  الجزء 3: تدريب الجنود وتصنيع الفخاخ (Train Troops & Traps - 250 وحدة)
    # ════════════════════════════════════════════════════════════════

    def get_prestige_train_status(self) -> Dict[str, Any]:
        """
        فحص حالة مهام تدريب الجنود والفخاخ الخمسة في الهيبة من الذاكرة الحية (RAM / Zero-Request):
          - #4112010: المشاة (250 وحدة)
          - #4112011: الخيالة (250 وحدة)
          - #4112012: الرماة (250 وحدة)
          - #4112013: العربات (250 وحدة - مفتوحة عند لفل هيبة 5)
          - #4112014: الفخاخ / حصن الحرب (250 وحدة - مفتوحة عند لفل هيبة 5)
        ترجع قاموساً يحدد ما إذا كانت جميع المهام مكتملة وقائمة الأنواع المحتاجة للتدريب.
        """
        TRAIN_QUEST_IDS = {
            "infantry": 4112010,
            "cavalry":  4112011,
            "archers":  4112012,
            "chariots": 4112013,
            "traps":    4112014,
        }
        merit = self.conn.init_data.get("meritoriousTaskCtrl", {})
        task_data = merit.get("taskData", {}) if isinstance(merit, dict) else {}
        daily_task = merit.get("daily_task", {}) if isinstance(merit, dict) else {}

        needed_types: List[str] = []
        completed_types: List[str] = []
        details: Dict[str, Any] = {}

        for t_type, qid in TRAIN_QUEST_IDS.items():
            # إذا عطل المستخدم حصن الحرب صراحة من المهام الفرعية
            if t_type == "traps" and not self.is_subtask_enabled("fortress"):
                continue

            qid_str = str(qid)
            q_obj = task_data.get(qid_str)

            # إذا كانت المهمة غير موجودة في taskData (مثلاً مقفلة حسب مستوى الهيبة)
            if not q_obj or not isinstance(q_obj, dict):
                if qid_str in daily_task:
                    c_num = int(daily_task[qid_str])
                    if c_num >= 250:
                        completed_types.append(t_type)
                    else:
                        needed_types.append(t_type)
                continue

            c_num = int(q_obj.get("cNum", q_obj.get("c_num", 0)))
            l_num = int(q_obj.get("lNum", q_obj.get("l_num", 250)))
            status = int(q_obj.get("status", 0))

            details[t_type] = {"c_num": c_num, "l_num": l_num, "status": status}

            # حالة 4: مكتملة وجاهزة للاستلام، حالة 1: تم استلامها، أو العدد المنجز وصل للمستهدف
            if status in (1, 4) or (l_num > 0 and c_num >= l_num):
                completed_types.append(t_type)
            else:
                needed_types.append(t_type)

        all_done = (len(needed_types) == 0 and len(completed_types) > 0)
        return {
            "all_done": all_done,
            "needed_types": needed_types,
            "completed_types": completed_types,
            "details": details
        }

    def get_busy_training_barracks(self) -> Set[str]:
        """
        فحص المنشآت التي تجري فيها عملية تدريب فعلياً حالياً من queueCtrl بالذاكرة الحية (RAM / Zero-Request).
        ترجع مجموعة بأسماء الأنواع المشغولة ('infantry', 'cavalry', 'archers', 'chariots', 'traps').
        """
        BID_TO_TYPE = {
            "118": "infantry",  # ثكنة المشاة
            "116": "cavalry",   # ثكنة الفرسان / الخيالة
            "117": "archers",   # ثكنة الرماة
            "119": "chariots",  # مصنع العربات
            "120": "traps",     # حصن الحرب / الفخاخ
        }
        QTYPE_TO_TYPE = {
            "1206": "infantry",
            "1204": "cavalry",
            "1205": "archers",
            "1203": "chariots",
            "1207": "traps",    # طابور حصن الحرب
        }
        now_ts = int(time.time())
        queue_ctrl = self.conn.init_data.get("queueCtrl", {})
        busy_types: Set[str] = set()

        if isinstance(queue_ctrl, dict):
            for qkey, qdata in queue_ctrl.items():
                if not isinstance(qdata, dict):
                    continue
                qtype_str = str(qdata.get("qtype") or qdata.get("queuetype") or qkey)
                bid_str = str(qdata.get("data", {}).get("bid", ""))

                t_type = BID_TO_TYPE.get(bid_str) or QTYPE_TO_TYPE.get(qtype_str)
                if t_type:
                    start_t = int(qdata.get("starttime", 0))
                    total_t = int(qdata.get("totaltime", 0))
                    # المنشأة مشغولة إذا كان وقت الانتهاء لم يحل بعد
                    if start_t + total_t > now_ts:
                        busy_types.add(t_type)

        return busy_types

    async def run_train_step(self) -> Dict[str, Any]:
        """
        تدريب الجنود وتصنيع الفخاخ لمهام الهيبة مع الفحص المسبق الذكي (Zero-Request):
          1. فحص اكتمال مهام تدريب الجنود والفخاخ في الهيبة مسبقاً (4112010 - 4112014) لتوفير الموارد.
          2. فحص طوابير التدريب الجارية في الثكنات وحصن الحرب من queueCtrl وتجنب المشغولة.
          3. تدريب الجنود الشاغرين (250 مستوى 1) وتصنيع فخاخ الحصن (250 وحدة) للهيبة فقط.
        """
        # 1. فحص اكتمال مهام تدريب الجنود والفخاخ بالهيبة في الذاكرة الحية
        t_status = self.get_prestige_train_status()
        if t_status["all_done"]:
            c_cnt = len(t_status["completed_types"])
            self.log.info(
                f"✨ [استعلام مسبق] جميع مهام تدريب الجنود والفخاخ في الهيبة مكتملة مسبقاً ({c_cnt} مهام) "
                f"— يتم تخطي الخطوة 3 بالكامل لحفظ الموارد!"
            )
            return {
                "success": True,
                "skipped": True,
                "already_done": True,
                "trained": [],
                "trained_count": 0,
                "busy": [],
                "busy_count": 0,
                "message": f"مهام تدريب الجنود والفخاخ بالهيبة مكتملة مسبقاً ({c_cnt} مهام)"
            }

        needed_types = t_status["needed_types"] or ["infantry", "cavalry", "archers", "chariots", "traps"]
        done_names = ", ".join(TRAIN_TYPE_NAMES_AR.get(t, t) for t in t_status["completed_types"]) if t_status["completed_types"] else "لا يوجد"
        needed_names = ", ".join(TRAIN_TYPE_NAMES_AR.get(t, t) for t in needed_types)
        self.log.info(f"📋 حالة مهام تدريب الهيبة: مكتمل [{done_names}] | متبقي بحاجة لتدريب [{needed_names}]")

        # 2. فحص طوابير التدريب الجارية حالياً في الذاكرة الحية (الثكنات وحصن الحرب)
        busy_types = self.get_busy_training_barracks()
        available_types = [t for t in needed_types if t not in busy_types]

        if not available_types:
            busy_str = ", ".join(TRAIN_TYPE_NAMES_AR.get(t, t) for t in busy_types) if busy_types else "الكل"
            self.log.info(
                f"⏳ [طوابير مشغولة] جميع المنشآت المطلوبة قيد التدريب حالياً ({busy_str}) "
                f"— يتم التخطي لتفادي التعارض مع التدريب الجاري."
            )
            return {
                "success": True,
                "skipped": True,
                "busy": True,
                "trained": [],
                "trained_count": 0,
                "busy_count": len(busy_types),
                "message": f"المنشآت المطلوبة مشغولة بالتدريب حالياً ({busy_str})"
            }

        avail_str = ", ".join(TRAIN_TYPE_NAMES_AR.get(t, t) for t in available_types)
        self.log.info(f"⚔️ ───【 الخطوة 3: تدريب الجنود وتصنيع الفخاخ للهيبة (المطلوب والشاغر: {avail_str}) 】───")

        troop_types = [t for t in available_types if t != "traps"]
        train_traps = "traps" in available_types

        trained_all: List[str] = []
        busy_all: List[str] = list(busy_types)
        success_all = True
        messages: List[str] = []

        # 1. تدريب الجنود في الثكنات (مشاة، خيالة، رماة، عربات)
        if troop_types:
            try:
                train_cfg = {
                    "types": troop_types,  # تدريب الأنواع الشاغرة والمطلوبة فقط
                    "level": 1,            # مستوى 1 لجميع الأنواع
                    "count": 250,          # 250 وحدة لكل نوع
                }
                train_task = TrainTask(self.conn, train_cfg)
                await train_task.on_start()
                res = await train_task.run()
                self.log.info(f"🏁 اكتمل تدريب الجنود: {res.message if res else 'تم التنفيذ'}")
                data = res.data if (res and res.data) else {}
                trained_troops = data.get("trained", [])
                busy_troops = data.get("busy", [])
                trained_all.extend(trained_troops)
                busy_all.extend(busy_troops)
                if res and res.success:
                    messages.append(res.message or "تم تدريب الجنود")
                else:
                    success_all = False
                    messages.append(res.message if res else "فشل تدريب الجنود")
            except Exception as e:
                self.log.warning(f"⚠️ خطأ في مهمة تدريب الجنود: {e}")
                messages.append(str(e))
                success_all = False

        # 2. تصنيع الفخاخ في حصن الحرب (250 وحدة)
        if train_traps:
            if troop_types:
                await asyncio.sleep(round(random.uniform(1.2, 2.0), 2))
            try:
                self.log.info("🏰 بدء تصنيع فخاخ حصن الحرب لمهام الهيبة (250 فخ)...")
                fortress_cfg = {
                    "type": "auto",   # الفئة التلقائية المتاحة
                    "level": 1,       # مستوى 1 لتوفير الموارد
                    "count": 250,     # 250 فخ لإنجاز مهمة الهيبة
                }
                fortress_task = FortressTask(self.conn, fortress_cfg)
                await fortress_task.on_start()
                res_f = await fortress_task.run()
                self.log.info(f"🏁 اكتمل تصنيع الفخاخ: {res_f.message if res_f else 'تم التنفيذ'}")
                if res_f and res_f.success:
                    trained_all.append("traps")
                    messages.append(res_f.message or "تم تصنيع الفخاخ")
                else:
                    if res_f and res_f.status == "busy":
                        busy_all.append("traps")
                    messages.append(res_f.message if res_f else "فشل تصنيع الفخاخ")
            except Exception as e:
                self.log.warning(f"⚠️ خطأ في مهمة تصنيع الفخاخ: {e}")
                messages.append(str(e))

        return {
            "success": success_all,
            "message": " | ".join(messages) if messages else "تم التنفيذ",
            "trained": trained_all,
            "trained_count": len(trained_all),
            "busy": list(set(busy_all)),
            "busy_count": len(set(busy_all)),
        }

    # ════════════════════════════════════════════════════════════════
    #  الجزء 4: حصن الحرب — تدريب الفخاخ تلقائياً
    # ════════════════════════════════════════════════════════════════

    async def run_fortress_step(self) -> Dict[str, Any]:
        """
        تدريب فخاخ حصن الحرب بالحد الأقصى التلقائي (auto).
        """
        self.log.info("🏰 ───【 الخطوة 4: حصن الحرب — تدريب الفخاخ تلقائياً 】───")
        try:
            fortress_cfg = {
                "type": "auto",   # تدريب جميع أنواع الفخاخ المتاحة تلقائياً
                "count": "max",   # الحد الأقصى المتاح تلقائياً
            }
            fortress_task = FortressTask(self.conn, fortress_cfg)
            await fortress_task.on_start()
            res = await fortress_task.run()
            self.log.info(f"🏁 اكتملت مهمة حصن الحرب: {res.message if res else 'تم التنفيذ'}")
            return {
                "success": bool(res and res.success),
                "message": res.message if res else "No response",
            }
        except Exception as e:
            self.log.warning(f"⚠️ خطأ في مهمة حصن الحرب: {e}")
            return {"success": False, "message": str(e)}

    # ════════════════════════════════════════════════════════════════
    #  الجزء 5: تبديل القمح بوسام الحرب (War Badge Exchange)
    # ════════════════════════════════════════════════════════════════

    async def run_badge_exchange_step(self) -> Dict[str, Any]:
        """
        تبديل القمح بوسام الحرب (CMD 1067/2) مرة واحدة يومياً لإنجاز مهمة الهيبة #4112024:
          - قاعدة التكلفة الصارمة: التبديل مسموح فقط إذا كانت تكلفة القمح 300,000 أو أقل.
            (السحبة الأولى = 300,000 قمح، بينما السحبات التالية تكلف 600,000+ قمح وتتجاوز الحد المسموح).
          - إذا كانت المهمة مكتملة مسبقاً اليوم (is_done أو curExchangeNum >= 1) يتم التخطي فوراً لتوفير الموارد.
          - إذا كان رصيد القمح بالقلعة أقل من 300,000 يتم التخطي فوراً.
        """
        MAX_WHEAT_COST = 300000

        merit_lv = self.get_merit_level()
        if merit_lv < 5:
            self.log.info(f"👾 [غزاة الهيبة] تم التخطي: نظام الهيبة غير مفتوح للقلعة بعد (meritLv = {merit_lv}).")
            return {"status": "skipped", "reason": "merit_level_too_low", "merit_level": merit_lv}

        q_info = self.get_quest_info("badge_exchange")
        if q_info["is_done"]:
            self.log.info(
                f"✨ [استعلام مسبق] مهمة تبديل القمح بوسام الحرب مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}) "
                f"— يتم التخطي لتوفير الموارد!"
            )
            return {
                "success": True,
                "skipped": True,
                "exchanged": 0,
                "message": f"مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']})"
            }

        # فحص إضافي عبر CMD 1067 / subcmd 1 و badgeExchangeCtrl
        cur_num = 0
        try:
            r1 = await self.conn.query("1067", "1", {}, timeout=5)
            if r1 and str(r1.get("err", "0")) == "0":
                cur_num = int(r1.get("curExchangeNum", 0))
        except Exception as e:
            self.log.debug(f"استعلام 1067/1 لم يكتمل: {e}")

        if cur_num == 0:
            bctrl = self.conn.init_data.get("badgeExchangeCtrl", {})
            if isinstance(bctrl, dict):
                cur_num = int(bctrl.get("curExchangeNum", 0))

        # التحقق من أن تكلفة التبديل لا تتجاوز 300,000 (التبديل الأول فقط = 300k، ما بعده يتجاوز 300k)
        if cur_num >= 1:
            self.log.info(
                f"🛑 [تبديل وسام الحرب] تكلفة التبديل القادمة تتجاوز الحد الأقصى 300,000 قمح "
                f"(عدد التباديل السابقة اليوم: {cur_num} — التكلفة > 300,000) — تم التخطي لحماية الموارد!"
            )
            return {
                "success": True,
                "skipped": True,
                "exchanged": 0,
                "message": f"تكلفة التبديل تتجاوز 300,000 قمح (curExchangeNum={cur_num})"
            }

        # فحص رصيد القمح المتاح بالقلعة
        resources = self._get_castle_resources()
        wheat_bal = resources.get(1002, 0)
        if wheat_bal < MAX_WHEAT_COST:
            self.log.info(
                f"🛑 [تبديل وسام الحرب] رصيد القمح بالقلعة غير كافٍ ({int(wheat_bal):,} < {MAX_WHEAT_COST:,}) "
                f"— تم إلغاء التبديل لحماية مخزون القلعة!"
            )
            return {
                "success": False,
                "skipped": True,
                "exchanged": 0,
                "message": f"رصيد القمح غير كافٍ ({int(wheat_bal):,} < {MAX_WHEAT_COST:,})"
            }

        self.log.info(f"🎖️ ───【 الخطوة 5: تبديل القمح بوسام الحرب (التكلفة: {MAX_WHEAT_COST:,} قمح) 】───")

        payload = {
            "nType": 1002,        # القمح
            "exchangeNum": 1,     # مرة واحدة
            "badgeType": 1        # وسام الحرب
        }

        resp = await self.conn.query("1067", "2", payload, timeout=8)
        if resp and str(resp.get("err", "0")) == "0":
            self.log.info("✅ [مهام الهيبة] تم تبديل 300,000 قمح بوسام الحرب بنجاح! 🎖️ (المورد: القمح #1002 | العدد: 1)")

            # تحديث الكاش المحلي
            merit = self.conn.init_data.setdefault("meritoriousTaskCtrl", {})
            task_data = merit.setdefault("taskData", {})
            t24 = task_data.setdefault("4112024", {"id": 4112024, "lNum": 1})
            t24["cNum"] = 1
            t24["status"] = 4
            daily = merit.setdefault("daily_task", {})
            daily["4112024"] = 1

            bctrl = self.conn.init_data.setdefault("badgeExchangeCtrl", {})
            bctrl["curExchangeNum"] = cur_num + 1

            return {
                "success": True,
                "skipped": False,
                "exchanged": 1,
                "message": "تم التبديل بنجاح (300,000 قمح)"
            }
        else:
            err_code = resp.get("err", "unknown") if resp else "timeout"
            self.log.warning(f"⚠️ [مهام الهيبة] تعذر تبديل القمح بوسام الحرب (كود: {err_code})")
            return {
                "success": False,
                "skipped": False,
                "exchanged": 0,
                "error": err_code,
                "message": f"فشل التبديل: {err_code}"
            }

    # ════════════════════════════════════════════════════════════════
    #  الجزء 6: فحص مهام الهيبة اليومية (Meritorious Quests Status)
    # ════════════════════════════════════════════════════════════════

    async def report_prestige_status(self):
        """عرض ملخص نقاط الهيبة ومستوى المجد والمهام اليومية الجاهزة."""
        merit = self.conn.init_data.get("meritoriousTaskCtrl", {})
        if not merit:
            return

        merit_lv = merit.get("meritLv", 0)
        merit_exp = merit.get("meritExp", 0)
        daily_point = merit.get("dailyPoint", 0)
        task_data = merit.get("taskData", {})

        ready_count = sum(1 for t in task_data.values() if t.get("status") == 4)
        in_progress_count = sum(1 for t in task_data.values() if t.get("status") == 2)

        self.log.info("🎖️ ───【 ملخص بيانات الهيبة والمجد 】───")
        self.log.info(f"   • مستوى الهيبة/المجد: {merit_lv} | نقاط المجد: {merit_exp:,}")
        self.log.info(f"   • نقاط النشاط اليومي الحالية: {daily_point} نقطة")
        self.log.info(f"   • المهام المكتملة الجاهزة للاستلام: {ready_count} مهمة | قيد الإنجاز: {in_progress_count}")

    # ════════════════════════════════════════════════════════════════
    #  دورة العمل الرئيسية للمهمة (run)
    # ════════════════════════════════════════════════════════════════

    async def run(self) -> TaskResult:
        """تنفيذ دورة مهام الهيبة اليومية داخل القلعة حصراً."""
        print("\n" + "═" * 70)
        print("  🎖️ بدء مهمة مهام الهيبة اليومية (داخل القلعة حصراً)")
        print(f"  • متجر المهربين: الشراء بالموارد العادية حصراً (المستهدف: {self.target_smuggler_buys} عمليات شراء)")
        print(f"  • الساقية: تفعيل جميع مباني الموارد مع السماح بالشراء من متجر التحالف")
        print(f"  • تدريب الجنود والفخاخ: 250 وحدة من كل نوع على مستوى 1 (مشاة، خيالة، أسهم، عربات، فخاخ)")
        print(f"  • حصن الحرب: تدريب الفخاخ الإضافية تلقائياً")
        print(f"  • وسام الحرب: تبديل القمح بوسام الحرب (مرة واحدة يومياً)")
        print("  ℹ️ مهام الهيبة المعتمدة داخل المدينة: متجر المهربين، الساقية، تدريب الجنود والفخاخ، حصن الحرب، وسام الحرب.")
        print("═" * 70 + "\n")

        # 0. تجديد بيانات مهام الهيبة من السيرفر للحصول على أحدث حالة
        self.log.info("🔄 [تجديد البيانات] جاري استعلام السيرفر لأحدث حالة مهام الهيبة...")
        await self._refresh_merit_data()

        # 0.1 الاستعلام المسبق وفحص حالة مهام الهيبة من السيرفر (المهام الداخلية)
        quests_status = self.query_prestige_summary(["smuggler", "watermill", "fortress", "badge_exchange"])
        self.log_prestige_overview(quests_status)

        # 1. متجر المهربين
        if self.is_subtask_enabled("smuggler"):
            smuggler_res = await self.run_smuggler_store()
            await asyncio.sleep(round(random.uniform(2.5, 4.0), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة متجر المهربين معطلة بناءً على اختيار المستخدم.")
            smuggler_res = {"success": True, "skipped": True, "user_disabled": True, "purchased_count": 0}

        # 2. الساقية — تفعيل جميع مباني إنتاج الموارد
        if self.is_subtask_enabled("watermill"):
            watermill_res = await self.run_watermill_step()
            await asyncio.sleep(round(random.uniform(2.0, 3.5), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة الساقية معطلة بناءً على اختيار المستخدم.")
            watermill_res = {"success": True, "skipped": True, "user_disabled": True, "activated": 0}

        # 3. تدريب الجنود وتصنيع الفخاخ — 250 من كل نوع على مستوى 1
        if self.is_subtask_enabled("train"):
            train_res = await self.run_train_step()
            await asyncio.sleep(round(random.uniform(2.0, 3.5), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة تدريب الجنود والفخاخ معطلة بناءً على اختيار المستخدم.")
            train_res = {"success": True, "skipped": True, "user_disabled": True, "trained_count": 0}

        # 4. حصن الحرب — تدريب الفخاخ تلقائياً
        if self.is_subtask_enabled("fortress"):
            # إذا تم تصنيع الفخاخ بالفعل في خطوة التدريب المشتركة أو اكتملت المهمة مسبقاً
            if "traps" in train_res.get("trained", []) or self.get_quest_info(4112014)["is_done"]:
                self.log.info("✨ [استعلام مسبق] فخاخ حصن الحرب تم تصنيعها بالفعل في خطوة التدريب — يتم التخطي لتوفير الموارد.")
                fortress_res = {"success": True, "skipped": True, "already_done": True}
            else:
                fortress_res = await self.run_fortress_step()
                await asyncio.sleep(round(random.uniform(1.5, 2.5), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة حصن الحرب معطلة بناءً على اختيار المستخدم.")
            fortress_res = {"success": True, "skipped": True, "user_disabled": True}

        # 5. تبديل القمح بوسام الحرب (تُفعّل تلقائياً عند تفعيل مهمة الهيبة)
        if self.is_subtask_enabled("badge_exchange"):
            badge_res = await self.run_badge_exchange_step()
            await asyncio.sleep(round(random.uniform(1.2, 2.0), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة تبديل القمح بوسام الحرب معطلة بناءً على اختيار المستخدم.")
            badge_res = {"success": True, "skipped": True, "user_disabled": True, "exchanged": 0}

        # 6. عرض تقرير حالة الهيبة
        await self.report_prestige_status()

        total_bought = smuggler_res.get("purchased_count", 0)
        watermill_activated = watermill_res.get("activated", 0)
        train_trained = train_res.get("trained_count", 0)
        smuggler_skipped = bool(smuggler_res.get("skipped"))
        watermill_skipped = bool(watermill_res.get("skipped"))
        badge_exchanged = badge_res.get("exchanged", 0)
        badge_skipped = bool(badge_res.get("skipped"))

        executed_parts = []
        skipped_parts = []

        if smuggler_res.get("user_disabled"):
            skipped_parts.append("متجر المهربين (معطل)")
        elif smuggler_skipped:
            skipped_parts.append("متجر المهربين ✨")
        else:
            executed_parts.append(f"متجر المهربين ({total_bought}/{self.target_smuggler_buys})")

        if watermill_res.get("user_disabled"):
            skipped_parts.append("الساقية (معطل)")
        elif watermill_skipped:
            skipped_parts.append("الساقية ✨")
        else:
            executed_parts.append(f"الساقية ({watermill_activated} مبنى)")

        if train_res.get("user_disabled"):
            skipped_parts.append("تدريب الجنود والفخاخ (معطل)")
        elif train_res.get("skipped"):
            if train_res.get("already_done"):
                skipped_parts.append("تدريب الجنود والفخاخ ✨")
            elif train_res.get("busy"):
                skipped_parts.append("تدريب الجنود والفخاخ ⏳")
            else:
                skipped_parts.append("تدريب الجنود والفخاخ (تخطي)")
        else:
            executed_parts.append(f"تدريب الجنود والفخاخ ({train_trained} أنواع)")

        if fortress_res.get("user_disabled"):
            skipped_parts.append("حصن الحرب (معطل)")
        elif fortress_res.get("skipped"):
            skipped_parts.append("حصن الحرب ✨")
        else:
            executed_parts.append(f"حصن الحرب ({'✅' if fortress_res.get('success') else '⚠️'})")

        if badge_res.get("user_disabled"):
            skipped_parts.append("تبديل وسام الحرب (معطل)")
        elif badge_skipped:
            skipped_parts.append("تبديل وسام الحرب ✨")
        elif badge_exchanged > 0:
            executed_parts.append("تبديل وسام الحرب 🎖️")

        summary_txt = ""
        if executed_parts:
            summary_txt += f"المنفذ: [{', '.join(executed_parts)}]"
        if skipped_parts:
            if summary_txt:
                summary_txt += " | "
            summary_txt += f"المتخطي: [{', '.join(skipped_parts)}]"

        msg = f"✅ اكتملت دورة مهام الهيبة الداخلية! {summary_txt}"
        self.log.info(msg)
        return TaskResult.ok(
            msg,
            smuggler_buys=total_bought,
            smuggler_skipped=smuggler_skipped,
            watermill_activated=watermill_activated,
            watermill_skipped=watermill_skipped,
            train_trained=train_trained,
            fortress_ok=fortress_res.get("success", False),
            badge_exchanged=badge_exchanged,
            badge_skipped=badge_skipped,
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر لسطر الأوامر (Standalone CLI)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(description="Prestige Quests Task — مهمة مهام الهيبة اليومية داخل القلعة")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--password", "-p", help="كلمة المرور للحساب للتسجيل المباشر إن لم يكن في الكاش")
    parser.add_argument("--buys", "-b", type=int, default=10, help="عدد المشتريات المستهدفة من متجر المهربين [افتراضي: 10]")
    parser.add_argument(
        "--subtasks",
        default="all",
        help="المهام الفرعية المطلوب تشغيلها مفصولة بفاصلة (smuggler,watermill,train,fortress أو all) [افتراضي: all]"
    )

    args = parser.parse_args()

    async def _main():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة في session_cache.json")
            return

        target_email = args.email.strip() if args.email else None
        if not target_email:
            target_email = next(iter(accounts.keys()))
            print(f"ℹ️ لم يتم تحديد بريد، سيتم استخدام الحساب الأول: {target_email}")

        account = accounts.get(target_email)
        if not account:
            for em, acc in accounts.items():
                if em.lower() == target_email.lower():
                    account = acc
                    break

        if not account:
            print(f"❌ لم يتم العثور على الحساب: {target_email}")
            return

        conn = GameConnection(account)
        print(f"🔌 جاري الاتصال بحساب {target_email}...")
        if not await conn.connect():
            print("❌ فشل الاتصال بالسيرفر!")
            return

        for _ in range(30):
            await asyncio.sleep(0.5)
            if "cityCtrl" in conn.init_data and "meritoriousTaskCtrl" in conn.init_data:
                break

        cfg = {
            "smuggler_buys": args.buys,
            "subtasks": args.subtasks,
        }

        task = PrestigeTask(conn, cfg)
        await task.on_start()
        result = await task.run()

        print("\n" + "═" * 60)
        print(f"📊 النتيجة النهائية: {'✅ نجاح' if result.success else '❌ فشل'}")
        print(f"💬 الرسالة: {result.message}")
        print("═" * 60)

        await conn.close()

    asyncio.run(_main())
