# -*- coding: utf-8 -*-
"""
tasks/port.py — مهمة الميناء (Port / Harbor)
══════════════════════════════════════════════

تتحقق من السفن المتاحة في الميناء وتستلم جوائزها وتحدّث الذاكرة الحية.
"""

from __future__ import annotations

import asyncio
import time
from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


class PortTask(BaseTask):
    """مهمة سفن الميناء واستلام جوائزها وتحديث الذاكرة الحية."""
    name = "port"

    async def run(self) -> TaskResult:
        # قراءة بيانات الميناء من الذاكرة الحية فقط (Zero-Request Mode دون إرسال أي استعلام شبكي)
        tr = self.conn.init_data.get('timeRewardCtrl', {})
        tr_data = tr.get('data', tr) if isinstance(tr, dict) else {}

        # 1. فحص استنفاد جميع سفن اليوم
        if tr_data.get('isAllReceive') == 1:
            self.log.info("⏭️ تم استلام جميع سفن الميناء المتاحة لهذا اليوم بالكامل.")
            return TaskResult.ok("تم استلام جميع سفن الميناء لهذا اليوم")

        # 2. فحص حالة جاهزية الجائزة من الذاكرة الحية (2 = جاهزة للاستلام فوراً):
        is_receive = tr_data.get('isReceive')
        if is_receive != 2:
            self.log.info("⏳ سفينة الميناء لا تزال في طريقها إلى الرصيف (لم تصل بعد).")
            return TaskResult.ok("سفينة الميناء في الطريق (لم تصل بعد)")

        # 3. فحص طابور الميناء (1227) في الذاكرة الحية إن وُجد
        queue_ctrl = self.conn.init_data.get('queueCtrl', {})
        port_q = queue_ctrl.get('1227') or queue_ctrl.get(1227)
        if isinstance(port_q, dict):
            end_t = float(port_q.get('endTime') or port_q.get('endtime') or 0)
            now_ts = time.time()
            if end_t > now_ts:
                rem = int(end_t - now_ts)
                self.log.info(f"⏳ سفينة الميناء لا تزال في طريقها (متبقي {rem} ثانية).")
                return TaskResult.ok("سفينة الميناء في الطريق")

        # 4. محاولة استلام جائزة السفينة عبر (1033/2) فقط عند الجاهزية
        self.log.info("🚀 بدء استلام جوائز سفن الميناء التجارية...")
        r = await self.conn.query('1033', '2', {})
        if not r:
            self.log.warning("⚠️ تعذر استلام جائزة الميناء: لا يوجد رد من السيرفر")
            return TaskResult.fail("تعذر استلام جائزة الميناء: لا يوجد رد")

        err = str(r.get('err', '0'))
        if err == '0':
            # نجاح تام وتحديث الذاكرة الحية بالبيانات الواردة
            new_data = r.get('data')
            if isinstance(new_data, dict):
                if 'data' in new_data and isinstance(new_data['data'], dict):
                    self.conn.init_data['timeRewardCtrl'] = new_data
                else:
                    self.conn.init_data['timeRewardCtrl'] = {'data': new_data}
            self.log.info("🎉 تم استلام جائزة سفينة الميناء بنجاح!")
            return TaskResult.ok("تم استلام جائزة سفينة الميناء بنجاح")

        elif err == '17001':  # Err_RECEIVED_REWARD
            # تم الاستلام مسبقاً ➔ تحديث الذاكرة الحية فوراً لمنع أي تكرار
            tr = self.conn.init_data.setdefault('timeRewardCtrl', {})
            if isinstance(tr, dict):
                tr_d = tr.setdefault('data', {})
                if isinstance(tr_d, dict):
                    tr_d['isReceive'] = 1
            self.log.info("ℹ️ تم استلام جائزة سفينة الميناء مسبقاً (السفينة في الطريق حالياً).")
            return TaskResult.ok("تم استلام جائزة الميناء مسبقاً")

        elif err == '17002':  # Err_ALL_RECEIVED_TODAY
            # اكتملت سفن اليوم ➔ تحديث الذاكرة الحية
            tr = self.conn.init_data.setdefault('timeRewardCtrl', {})
            if isinstance(tr, dict):
                tr_d = tr.setdefault('data', {})
                if isinstance(tr_d, dict):
                    tr_d['isAllReceive'] = 1
            self.log.info("ℹ️ اكتمل استلام كافة سفن الميناء المتاحة لليوم.")
            return TaskResult.ok("اكتملت جميع سفن اليوم")

        else:
            err_msg = r.get('msg') or f"كود: {err}"
            self.log.warning(f"⚠️ تعذر استلام جائزة الميناء: {err_msg}")
            return TaskResult.fail(f"تعذر استلام جائزة الميناء: {err_msg}")
