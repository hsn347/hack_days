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
        self.log.info("🚢 فحص الميناء...")

        # استعلام قائمة السفن المتاحة
        r = await self.conn.query('1033', '2', {})
        if not r or 'data' not in r:
            return TaskResult.fail("❌ فشل استعلام الميناء", retry_after=300)

        ships = r['data'].get('shipList', [])
        if not ships:
            self.log.info("🚢 لا توجد سفن متاحة حالياً")
            return TaskResult.ok("لا توجد سفن", ships=0)

        sent = 0
        for ship in ships:
            ship_id = ship.get('id')
            if not ship_id:
                continue
            if ship.get('status', 0) != 0:  # 0 = متاح للإرسال
                continue
            r_send = await self.conn.query('1033', '3', {"shipId": ship_id})
            if r_send and str(r_send.get('err', '0')) == '0':
                self.log.info(f"✅ تم إرسال السفينة {ship_id}")
                sent += 1
            await asyncio.sleep(2.0)  # حماية من الحظر

        return TaskResult.ok(f"✅ تم إرسال {sent} سفينة", sent=sent)
