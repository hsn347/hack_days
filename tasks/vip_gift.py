# -*- coding: utf-8 -*-
"""
tasks/vip_gift.py — مهمة جمع صندوق الـ VIP اليومي المجاني (VIP Daily Free Gift)
══════════════════════════════════════════════════════════════════════════════
البروتوكول:
  CMD: 1082 (CMD_VIP_MODULE)
  SUBCMD: 1 (REQ_BUY_VIP_DAILY_GIFT)

شروط الأمان والمجانية:
  - فحص بيانات `vipCtrl` في `conn.init_data`:
    - إذا كان `dailyGiftFlag == true`: الصندوق مستلم اليوم مسبقاً، تخرج المهمة فوراً دون إرسال أي طلب.
    - إذا كان `dailyGiftFlag == false`: الصندوق المجاني متاح للاستلام، يتم إرسال طلب 1082/1.
  - لا تستهلك أي ذهب نهائياً.
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

log = logging.getLogger("VipGiftTask")


class VipGiftTask(BaseTask):
    """مهمة فحص واستلام صندوق الـ VIP اليومي المجاني تلقائياً وبأمان تام."""

    name = "vip_gift"

    CMD_VIP_MODULE = "1082"
    REQ_BUY_VIP_DAILY_GIFT = "1"

    ERR_ALREADY_GOT = "44001"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})

    def get_vip_status(self) -> Dict[str, Any]:
        """
        استخراج حالة الـ VIP وصندوق الهدايا اليومي من init_data.
        
        Returns:
            قاموس يحتوي على:
              - free_available (bool): هل الصندوق المجاني متاح اليوم
              - vip_lv (int): مستوى الـ VIP الحالي
              - vip_point (int): نقاط الـ VIP الحالية
              - daily_claimed (bool): هل تم استلام الصندوق اليوم
              - claim_time (int): توقيت آخر استلام
        """
        init_data = getattr(self.conn, "init_data", {})
        vip_data = init_data.get("vipCtrl", {})
        if not isinstance(vip_data, dict):
            vip_data = {}

        daily_flag = bool(vip_data.get("dailyGiftFlag", False))
        vip_lv = int(vip_data.get("vipLv", 0))
        vip_point = int(vip_data.get("vipPoint", 0))
        claim_time = int(vip_data.get("claimDailyGiftTime", 0))

        # في كود اللعبة: dailyGiftFlag == true تعني تم الاستلام اليوم مسبقاً
        free_available = not daily_flag

        return {
            "free_available": free_available,
            "daily_claimed": daily_flag,
            "vip_lv": vip_lv,
            "vip_point": vip_point,
            "claim_time": claim_time,
            "vip_data": vip_data
        }

    async def run(self) -> TaskResult:
        """تنفيذ فحص واستلام صندوق الـ VIP المجاني."""
        self.log.info("👑 بدء فحص مهمة صندوق الـ VIP اليومي (VIP Daily Gift)...")

        status = self.get_vip_status()
        vip_lv = status["vip_lv"]

        # 1. التحقق من توفر الصندوق المجاني
        if not status["free_available"]:
            self.log.info(f"ℹ️ [صندوق VIP] الصندوق المجاني مستلم اليوم مسبقاً (VIP مستوى {vip_lv}). إنهاء المهمة بأمان.")
            return TaskResult(
                success=True,
                message=f"✅ تم استلام صندوق الـ VIP المجاني اليوم مسبقاً (VIP مستوى {vip_lv})",
                data={"free_available": False, "claimed": False, "vip_lv": vip_lv}
            )

        # 2. إرسال طلب استلام الصندوق المجاني
        self.log.info(f"🎁 [صندوق VIP] صندوق الـ VIP المجاني جاهز للاستلام فوراً (VIP {vip_lv})! جاري الإرسال (1082/1)...")
        try:
            resp = await self.conn.query(self.CMD_VIP_MODULE, self.REQ_BUY_VIP_DAILY_GIFT, timeout=8)
        except Exception as ex:
            self.log.error(f"❌ خطأ أثناء إرسال طلب صندوق VIP: {ex}")
            return TaskResult(success=False, message=f"خطأ اتصال أثناء استلام صندوق VIP: {ex}")

        err = str(resp.get("err", "-1")) if resp else "timeout"

        if err == "0":
            self.log.info(f"🎉 [صندوق VIP] ✅ تم استلام صندوق الـ VIP المجاني بنجاح! (VIP مستوى {vip_lv})")
            # تحديث حالة vipCtrl في init_data
            init_data = getattr(self.conn, "init_data", {})
            if "vipCtrl" in init_data and isinstance(init_data["vipCtrl"], dict):
                init_data["vipCtrl"]["dailyGiftFlag"] = True
                if resp and isinstance(resp.get("data"), dict):
                    init_data["vipCtrl"].update(resp["data"])

            return TaskResult(
                success=True,
                message=f"🎉 تم استلام صندوق الـ VIP المجاني بنجاح! (VIP مستوى {vip_lv})",
                data={"free_available": False, "claimed": True, "vip_lv": vip_lv}
            )

        elif err == self.ERR_ALREADY_GOT:
            self.log.info(f"ℹ️ [صندوق VIP] الصندوق مستلم مسبقاً من السيرفر (كود {err}).")
            init_data = getattr(self.conn, "init_data", {})
            if "vipCtrl" in init_data and isinstance(init_data["vipCtrl"], dict):
                init_data["vipCtrl"]["dailyGiftFlag"] = True

            return TaskResult(
                success=True,
                message=f"✅ تم استلام صندوق الـ VIP المجاني اليوم مسبقاً",
                data={"free_available": False, "claimed": False, "vip_lv": vip_lv}
            )

        else:
            self.log.warning(f"⚠️ [صندوق VIP] تعذر استلام الصندوق، كود الخطأ: {err}")
            return TaskResult(
                success=False,
                message=f"تعذر استلام صندوق الـ VIP (كود {err})",
                data={"err": err}
            )
