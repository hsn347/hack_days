# -*- coding: utf-8 -*-
"""
tasks/daily_luxury_gift.py — مهمة جمع الهدية الفاخرة اليومية (Daily Luxury Gift)
══════════════════════════════════════════════════════════════════════════════
البروتوكول:
  CMD: 3094 (CMD_CUMULATE_REWARD)
  SUBCMD: 1 (REQ_GET_CUMULATE_REWARD)
  DATA: {"cumulateType": 1, "times": day}

تعتمد المهمة على فحص بيانات `cumulateRewardData` في `conn.init_data`:
  - `mFinishTimes`: يحدد الحد الأقصى للأيام المكتملة والمتاحة لكل نوع (مثال: {"1": 11, "2": 14}).
  - `mRewardRecords`: يسجل الأيام التي تم استلامها مسبقاً لكل نوع.
تقوم المهمة بحصر كافة الهدايا غير المستلمة (من اليوم 1 وحتى mFinishTimes)
وجمعها جميعاً بالتتابع تلقائياً بدون أي تكلفة ذهب.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

log = logging.getLogger("DailyLuxuryGiftTask")


class DailyLuxuryGiftTask(BaseTask):
    """مهمة فحص وجمع كافة هدايا الهدية الفاخرة اليومية المتاحة تلقائياً."""

    name = "daily_luxury_gift"

    CMD_CUMULATE_REWARD = "3094"
    REQ_GET_CUMULATE_REWARD = "1"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})

    def get_available_gifts(self) -> List[Dict[str, int]]:
        """
        فحص بيانات cumulateRewardData وحصر كافة الهدايا المتاحة غير المستلمة بعد.
        
        Returns:
            قائمة بالقواميس، كل عنصر يحتوي على {"cumulateType": type_id, "times": day}
        """
        init_data = getattr(self.conn, "init_data", {})
        cumu_data = init_data.get("cumulateRewardData", {})
        if not isinstance(cumu_data, dict):
            return []

        finish_times = cumu_data.get("mFinishTimes", {})
        reward_records = cumu_data.get("mRewardRecords", {})

        if not isinstance(finish_times, dict):
            return []

        available_gifts: List[Dict[str, int]] = []

        # فحص كافة الأنواع الموجودة في mFinishTimes
        for c_type_str, max_day in finish_times.items():
            try:
                c_type = int(c_type_str)
                max_d = int(max_day)
            except (ValueError, TypeError):
                continue

            claimed_map = reward_records.get(c_type_str, {}) if isinstance(reward_records, dict) else {}
            if not isinstance(claimed_map, dict):
                claimed_map = {}

            for day in range(1, max_d + 1):
                day_str = str(day)
                # إذا لم يتم استلام هذا اليوم بعد
                if not claimed_map.get(day_str):
                    available_gifts.append({
                        "cumulateType": c_type,
                        "times": day
                    })

        return available_gifts

    def get_status_summary(self) -> Dict[str, Any]:
        """استخراج ملخص حالة الهدية الفاخرة للوحة التحكم والتقارير."""
        init_data = getattr(self.conn, "init_data", {})
        cumu_data = init_data.get("cumulateRewardData", {}) if isinstance(init_data.get("cumulateRewardData"), dict) else {}
        finish_times = cumu_data.get("mFinishTimes", {}) if isinstance(cumu_data.get("mFinishTimes"), dict) else {}
        
        available = self.get_available_gifts()
        daily_max = int(finish_times.get("1", 0))

        return {
            "available_count": len(available),
            "available_gifts": available,
            "daily_max_day": daily_max,
            "has_rewards": len(available) > 0
        }

    async def run(self) -> TaskResult:
        """تنفيذ مهمة جمع الهدية الفاخرة اليومية وجمع كافة الهدايا المتاحة."""
        self.log.info("🎁 بدء مهمة جمع الهدية الفاخرة اليومية (Daily Luxury Gift)...")

        available_gifts = self.get_available_gifts()
        if not available_gifts:
            self.log.info("ℹ️ [الهدية الفاخرة] لا توجد هدايا جديدة جاهزة للاستلام حالياً.")
            return TaskResult(
                success=True,
                message="✅ تم استلام كافة الهدايا الفاخرة المتاحة مسبقاً",
                data={"collected_count": 0}
            )

        self.log.info(f"🎁 تم العثور على {len(available_gifts)} هدية فاخرة جاهزة للاستلام! جاري جمعها...")
        collected = 0
        errors = 0

        for gift in available_gifts:
            c_type = gift["cumulateType"]
            day = gift["times"]
            type_name = "الهدية اليومية" if c_type == 1 else f"المكافأة التراكمية (نوع {c_type})"

            self.log.info(f"📦 استلام {type_name} - اليوم #{day} (3094/1)...")
            await asyncio.sleep(0.3)

            try:
                resp = await self.conn.query(
                    self.CMD_CUMULATE_REWARD,
                    self.REQ_GET_CUMULATE_REWARD,
                    {"cumulateType": c_type, "times": day},
                    timeout=8
                )

                if resp and str(resp.get("err", "-1")) == "0":
                    collected += 1
                    self.log.info(f"✅ تم استلام {type_name} - اليوم #{day} بنجاح!")
                    # تحديث البيانات المخزنة في init_data
                    retdata = resp.get("retdata")
                    if isinstance(retdata, dict):
                        init_data = getattr(self.conn, "init_data", {})
                        cumu_data = init_data.setdefault("cumulateRewardData", {})
                        if "mRewardRecords" in retdata:
                            cumu_data["mRewardRecords"] = retdata["mRewardRecords"]
                        if "mFinishTimes" in retdata:
                            cumu_data["mFinishTimes"] = retdata["mFinishTimes"]
                else:
                    errors += 1
                    err = resp.get("err") if resp else "timeout"
                    self.log.warning(f"⚠️ تعذر استلام {type_name} - اليوم #{day}: {err}")
            except Exception as ex:
                errors += 1
                self.log.error(f"❌ خطأ أثناء استلام الهدية {c_type}/{day}: {ex}")

        msg = f"🎁 تم جمع {collected} من أصل {len(available_gifts)} هدية فاخرة بنجاح!"
        if errors > 0:
            msg += f" (تعذر {errors})"

        self.log.info(f"🎉 {msg}")
        return TaskResult(
            success=True,
            message=msg,
            data={
                "collected_count": collected,
                "total_available": len(available_gifts),
                "errors": errors
            }
        )
