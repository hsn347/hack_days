# -*- coding: utf-8 -*-
"""
tasks/port.py — مهمة الميناء (Port / Harbor)
══════════════════════════════════════════════

تتحقق من السفن المتاحة في الميناء وتُرسلها.
الإعدادات (config):
    ship_type : نوع السفن [افتراضي: 0 = تلقائي]
"""

from __future__ import annotations

import asyncio
from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


class PortTask(BaseTask):
    """مهمة إرسال سفن الميناء."""
    name = "port"

    async def run(self) -> TaskResult:
        # إرسال طلب استلام جائزة سفينة الميناء مباشرة
        r = await self.conn.query('1033', '2', {})
        if not r or str(r.get('err', '-1')) != '0':
            err_msg = r.get('msg') if r else 'لا يوجد رد'
            return TaskResult.fail(f" تعذر استلام جائزة الميناء: {err_msg}")

        # تحديث بيانات الميناء في الذاكرة الحية فوراً بالعداد والبيانات الجديدة
        new_data = r.get('data')
        if isinstance(new_data, dict):
            self.conn.init_data['timeRewardCtrl'] = new_data

        return TaskResult.ok("تم استلام جائزة سفينة الميناء بنجاح")
