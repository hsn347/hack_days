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

    def is_shield_active(self, shield_info: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, int]:
        """
        التحقق الشامل مما إذا كان هناك درع سلام نشط حالياً لحماية القلعة.

        المعايير المعتمدة وفق بروتوكول ومحرك اللعبة:
          1. مؤقت الجلسة النشط (shield_expire_ts): إذا تم تفعيل درع مسبقاً في هذه الجلسة وما زال وقته سارياً.
          2. مؤشر الأمان في الخريطة (kingdomMapCtrl.isSafe): يرسله خادم اللعبة عند تسجيل الدخول (1000/1)
             ويحدد بشكل قاطع ما إذا كانت القلعة تحت الحماية (True) أو مكشوفة (False).
          3. مصفوفة التعزيزات (buffCtrl): فحص معرّف درع السلام (id: 5001) ووقت بدئه (beginTime).

        Returns:
            (is_active: bool, reason_str: str, remaining_seconds: int)
        """
        now = time.time()

        # 1. فحص مؤقت الجلسة الداخلي
        expire_ts = getattr(self.conn, 'shield_expire_ts', 0)
        if expire_ts > now + 60:
            rem = int(expire_ts - now)
            hours = rem // 3600
            mins = (rem % 3600) // 60
            return True, f"درع سلام نشط ومسجل في الجلسة (متبقي: {hours} س و {mins} د)", rem
        elif expire_ts > 0 and expire_ts <= now:
            self.conn.shield_expire_ts = 0

        # 2. فحص بيانات التهيئة القادمة من السيرفر (init_data)
        init_data = getattr(self.conn, 'init_data', {}) or {}
        km = init_data.get('kingdomMapCtrl', {})
        is_safe = km.get('isSafe') if isinstance(km, dict) else False

        # 3. فحص قائمة التعزيزات النشطة (buffCtrl) للبحث عن معرّف درع السلام (5001)
        buff_ctrl = init_data.get('buffCtrl', [])
        shield_buff = None
        if isinstance(buff_ctrl, list):
            for b in buff_ctrl:
                if isinstance(b, dict) and b.get('id') == 5001:
                    shield_buff = b
                    break

        shield_duration_sec = (shield_info or {}).get("seconds", 8 * 3600)

        # إذا كانت القلعة محمية في الخريطة أو يوجد تعزيز الدرع 5001
        if is_safe or shield_buff:
            rem = 0
            if shield_buff:
                b_begin = int(shield_buff.get('beginTime', 0))
                if b_begin > 0:
                    elapsed = int(now) - b_begin
                    if elapsed < shield_duration_sec:
                        rem = shield_duration_sec - elapsed
                    else:
                        # إذا كان elapsed أكبر من مدة الدرع المستهدف ولكن السيرفر ما زال يبلغ أن isSafe=True
                        # فهذا يعني أن المستخدم كان قد فعّل درعاً أطول (مثلاً 24 ساعة أو 3 أيام)
                        rem = max(3600, 24 * 3600 - elapsed)

            if rem > 0:
                self.conn.shield_expire_ts = now + rem
                hours = rem // 3600
                mins = (rem % 3600) // 60
                time_str = f" (متبقي تقريبياً: {hours} س و {mins} د)" if hours > 0 or mins > 0 else ""
                return True, f"القلعة محمية بالفعل بدرع سلام نشط (isSafe=True){time_str}", rem
            else:
                default_rem = 3600
                self.conn.shield_expire_ts = now + default_rem
                return True, "القلعة محمية بالفعل بدرع سلام نشط وفق بيانات السيرفر (isSafe=True)", default_rem

        return False, "لا يوجد درع سلام نشط (القلعة مكشوفة)", 0

    def _record_shield_activation(self, shield_info: Dict[str, Any]):
        """تسجيل تفعيل الدرع بنجاح في كائن الاتصال وبيانات التهيئة لتفادي إعادة التفعيل."""
        now = time.time()
        self.conn.shield_expire_ts = now + shield_info["seconds"]
        if hasattr(self.conn, 'init_data') and isinstance(self.conn.init_data, dict):
            km = self.conn.init_data.setdefault("kingdomMapCtrl", {})
            if isinstance(km, dict):
                km["isSafe"] = True
            buff_list = self.conn.init_data.setdefault("buffCtrl", [])
            if isinstance(buff_list, list):
                self.conn.init_data["buffCtrl"] = [b for b in buff_list if isinstance(b, dict) and b.get("id") != 5001]
                self.conn.init_data["buffCtrl"].append({
                    "id": 5001,
                    "beginTime": int(now)
                })

    async def run(self) -> TaskResult:
        cfg = self.config
        raw_dur = str(cfg.get('duration', '8h')).lower().strip()
        dur_key = DURATION_ALIASES.get(raw_dur, '8h')
        shield_info = SHIELD_TYPES.get(dur_key, SHIELD_TYPES['8h'])

        allow_gold = bool(cfg.get('allow_gold', False))

        self.log.info(f"🛡️ بدء مهمة الدرع التلقائي [{shield_info['name']}] (الشراء بالذهب: {allow_gold})")

        # 0. التحقق الاستباقي: هل القلعة محمية بالفعل بدرع سلام نشط؟
        is_active, reason, remaining_sec = self.is_shield_active(shield_info)
        if is_active:
            self.log.info(f"🛡️ {reason} — تم إنهاء المهمة بنجاح لتوفير الدروع وعدم إهدارها.")
            retry_sec = max(300, remaining_sec - 300) if remaining_sec > 300 else 3600
            return TaskResult.ok(
                f"🛡️ القلعة محمية بالفعل بدرع سلام نشط: {reason}",
                status="already_active",
                shield_active=True,
                remaining_seconds=remaining_sec,
                retry_after=retry_sec
            )

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

                # تسجيل الدرع وتحديث مؤقت الحماية في الجلسة وبيانات التهيئة
                self._record_shield_activation(shield_info)

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

            # تسجيل الدرع وتحديث مؤقت الحماية في الجلسة وبيانات التهيئة
            self._record_shield_activation(shield_info)

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
