# -*- coding: utf-8 -*-
"""
tasks/shield.py — مهمة الدرع التلقائي ودرع السلام (Peace Shield Task)
══════════════════════════════════════════════════════════════════════════════════════

أنواع الدروع المعتمدة في محرك اللعبة:
  1. 🛡️ درع 8 ساعات:
     - في الحقيبة (مجاني): 300701
     - في المتجر بالذهب: 1000024 (500 ذهب)
  2. 🛡️ درع 24 ساعة (يوم كامل):
     - في الحقيبة (مجاني): 300702
     - في المتجر بالذهب: 1000025 (1000 ذهب)
  3. 🛡️ درع 3 أيام:
     - في الحقيبة (مجاني): 300703
     - في المتجر بالذهب: 1000026 (2500 ذهب)

الاستخدام كملف مستقل:
    python tasks/shield.py --email "meik.gaertner2306.MGr@gmail.com" --duration 8h
    python tasks/shield.py --email "burcudemr@gmail.com" --duration 8h --allow-gold
    python tasks/shield.py --email "meik.gaertner2306.MGr@gmail.com" --duration 3d --allow-gold
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
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  قاموس الدروع وتهيئتها
# ════════════════════════════════════════════════════════════════════

SHIELD_TYPES: Dict[str, Dict[str, Any]] = {
    "8h": {
        "name": "🛡️ درع السلام (8 ساعات)",
        "duration_key": "8h",
        "hours": 8,
        "seconds": 8 * 3600,
        "bag_item_id": 300701,
        "shop_item_id": 1000024,
        "gold_price": 500,
    },
    "24h": {
        "name": "🛡️ درع السلام (24 ساعة / يوم)",
        "duration_key": "24h",
        "hours": 24,
        "seconds": 24 * 3600,
        "bag_item_id": 300702,
        "shop_item_id": 1000025,
        "gold_price": 1000,
    },
    "3d": {
        "name": "🛡️ درع السلام (3 أيام / 72 ساعة)",
        "duration_key": "3d",
        "hours": 72,
        "seconds": 72 * 3600,
        "bag_item_id": 300703,
        "shop_item_id": 1000026,
        "gold_price": 2500,
    },
}

# تطبيع المدخلات المختلفة
DURATION_ALIASES = {
    "8": "8h", "8h": "8h", "8hour": "8h", "8hours": "8h",
    "24": "24h", "24h": "24h", "1d": "24h", "1day": "24h", "day": "24h",
    "72": "3d", "3d": "3d", "3day": "3d", "3days": "3d", "3": "3d",
}


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (ShieldTask)
# ════════════════════════════════════════════════════════════════════

class ShieldTask(BaseTask):
    """
    مهمة تفعيل وتجديد درع السلام التلقائي.
    """
    name = "shield"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    async def run(self) -> TaskResult:
        cfg = self.config
        raw_dur = str(cfg.get('duration', '8h')).lower().strip()
        dur_key = DURATION_ALIASES.get(raw_dur, '8h')
        shield_info = SHIELD_TYPES.get(dur_key, SHIELD_TYPES['8h'])

        allow_gold = bool(cfg.get('allow_gold', False))

        self.log.info(f"🛡️ بدء مهمة الدرع التلقائي [{shield_info['name']}] (الشراء بالذهب: {allow_gold})")

        # 1. فحص مخزون الحقيبة للدروع المجانية (1004/1)
        r_bag = await self.conn.query('1004', '1', {}, timeout=8)
        items = r_bag.get('data', {}).get('itemList', r_bag.get('data', {})) if r_bag else {}

        bag_count = 0
        target_item_id = shield_info["bag_item_id"]

        if isinstance(items, dict):
            for k, v in items.items():
                if isinstance(v, dict):
                    iid = int(v.get('id', v.get('itemID', k)))
                    if iid == target_item_id:
                        bag_count = int(v.get('count', v.get('num', 0)))
                        break
        elif isinstance(items, list):
            for v in items:
                if isinstance(v, dict):
                    iid = int(v.get('id', v.get('itemID', 0)))
                    if iid == target_item_id:
                        bag_count = int(v.get('count', v.get('num', 0)))
                        break

        self.log.info(f"🎒 المخزون المتوفر في الحقيبة من {shield_info['name']}: {bag_count} درع")

        # 2. جلب توقيع العنصر المشفر (item_sign) المطلوب من السيرفر
        item_signs = self.conn.init_data.get('item_sign', {})
        use_sign = item_signs.get(str(target_item_id))
        if not use_sign:
            use_sign = random.randint(1000, 65000)
        else:
            use_sign = int(use_sign)

        # 3. تفعيل الدرع من الحقيبة (مجاناً) إذا كان متوفراً
        if bag_count > 0:
            self.log.info(f"🚀 جاري استخدام 1 من {shield_info['name']} من الحقيبة مجاناً (sign: {use_sign})...")
            payload = {
                "itemID": target_item_id,
                "count": 1,
                "useSign": use_sign
            }

            r_use = await self.conn.query('1004', '2', payload, timeout=8)
            err_code = str(r_use.get('err', '0')) if r_use else '0'

            # إذا نجح التفعيل
            if err_code == '0' or not r_use or err_code == 'Err_None':
                # تحديث التوقيع القادم من السيرفر إن وجد
                next_sign = r_use.get('data', {}).get('sign') if r_use else None
                if next_sign and isinstance(item_signs, dict):
                    item_signs[str(target_item_id)] = next_sign

                success_msg = f"تم تفعيل {shield_info['name']} بنجاح من الحقيبة مجاناً"
                self.log.info(f"✅ {success_msg} 🎉")
                # تعيين التجديد قبل انتهاء الدرع بـ 5 دقائق
                retry_sec = max(300, shield_info["seconds"] - 300)
                return TaskResult.ok(
                    success_msg,
                    status="activated_free",
                    duration=shield_info["duration_key"],
                    method="backpack",
                    retry_after=retry_sec
                )
            else:
                self.log.warning(f"⚠️ فشل استخدام الدرع من الحقيبة (كود: {err_code})")

        # 4. شراء وتفعيل الدرع بالذهب من المتجر (1034/2) إذا كان الشراء مسموحاً
        if allow_gold:
            self.log.info(f"🪙 الدرع المجاني غير متوفر. جاري شراء وتفعيل {shield_info['name']} بالذهب ({shield_info['gold_price']} ذهب)...")
            payload = {
                "shopItemID": shield_info["shop_item_id"],
                "num": 1,
                "use": True,
                "useSign": use_sign
            }

            # إرسال طلب الشراء والاستخدام الفوري (1034/2)
            self.conn.send_nowait('1034', '2', payload)
            await asyncio.sleep(1.5)

            success_msg = f"تم شراء وتفعيل {shield_info['name']} بنجاح بالذهب ({shield_info['gold_price']} ذهب)"
            self.log.info(f"✅ {success_msg} 🎉")

            retry_sec = max(300, shield_info["seconds"] - 300)
            return TaskResult.ok(
                success_msg,
                status="activated_gold",
                duration=shield_info["duration_key"],
                gold_spent=shield_info["gold_price"],
                method="gold_shop",
                retry_after=retry_sec
            )
        else:
            fail_msg = f"لا يوجد {shield_info['name']} مجاني في الحقيبة والشراء بالذهب معطل"
            self.log.warning(f"⚠️ {fail_msg}")
            return TaskResult.fail(
                fail_msg,
                status="no_free_shield",
                retry_after=3600
            )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Peace Shield Task — مهمة الدرع التلقائي ودرع السلام")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--duration", "-d", default="8h", choices=["8h", "24h", "3d", "8", "24", "72"],
                        help="مدة الدرع: 8h (8 ساعات) أو 24h (24 ساعة) أو 3d (3 أيام) [افتراضي: 8h]")
    parser.add_argument("--allow-gold", "-g", action="store_true",
                        help="السماح بالشراء بالذهب في حال عدم توفر الدرع المجاني في الحقيبة")
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
            await asyncio.sleep(1.0)
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "duration": args.duration,
            "allow_gold": args.allow_gold,
        }

        task = ShieldTask(conn, task_cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
