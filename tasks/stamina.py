# -*- coding: utf-8 -*-
"""
tasks/stamina.py — مهمة استخدام جرعات الطاقة وشراء الطاقة بالذهب (Stamina Task)
══════════════════════════════════════════════════════════════════════════════════════

دورة عمل المهمة:
  1. فحص مخزون حقيبة اللاعب لجرعات الطاقة (1004/1):
     - 300401: جرعة طاقة (+10)
     - 300402: جرعة طاقة (+50)
     - 300403: جرعة طاقة (+100)
  2. استخدام الجرعات المجانية المتوفرة بالكامل (1004/2).
  3. شراء الطاقة بالذهب بعدد المرات المحدد في الإعدادات أو Firebase (2060/1).

الاستخدام كملف مستقل:
    python tasks/stamina.py --email "meik.gaertner2306.MGr@gmail.com" --gold 3
    python tasks/stamina.py --email "ossso5030@gmail.com" --gold 3
    python tasks/stamina.py --email "sumo-1234@hotmil.com" --types 300401,300402
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
import time
from typing import Any, Dict, List, Optional

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  قاموس جرعات الطاقة
# ════════════════════════════════════════════════════════════════════

STAMINA_POTIONS: Dict[int, Dict[str, Any]] = {
    300401: {"name": "🧪 جرعة طاقة (+10)",  "value": 10},
    300402: {"name": "🧪 جرعة طاقة (+50)",  "value": 50},
    300403: {"name": "🧪 جرعة طاقة (+100)", "value": 100},
}


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (StaminaTask)
# ════════════════════════════════════════════════════════════════════

class StaminaTask(BaseTask):
    """
    مهمة استهلاك جرعات الطاقة وإدارتها.
    """
    name = "stamina"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    async def run(self) -> TaskResult:
        cfg = self.config
        use_free = cfg.get('use_free', True)
        gold_buys = int(cfg.get('gold_buys', cfg.get('gold', cfg.get('buy_gold_count', 0))))

        self.log.info(f"⚡ بدء مهمة الطاقة (استخدام المجاني: {use_free} | شراء بالذهب: {gold_buys})")

        total_stamina_gained = 0
        used_items_summary   = {}
        gold_buys_done       = 0

        # 1. فحص محتويات الحقيبة لجرعات الطاقة (1004/1)
        r_bag = await self.conn.query('1004', '1', {}, timeout=8)
        items = r_bag.get('data', {}).get('itemList', r_bag.get('data', {})) if r_bag else {}

        bag_potions: Dict[int, int] = {}
        if isinstance(items, dict):
            for k, v in items.items():
                if isinstance(v, dict):
                    iid = int(v.get('id', v.get('itemID', k)))
                    if iid in STAMINA_POTIONS:
                        bag_potions[iid] = int(v.get('count', v.get('num', 0)))
        elif isinstance(items, list):
            for v in items:
                if isinstance(v, dict):
                    iid = int(v.get('id', v.get('itemID', 0)))
                    if iid in STAMINA_POTIONS:
                        bag_potions[iid] = int(v.get('count', v.get('num', 0)))

        self.log.info(f"🎒 المخزون المتوفر في الحقيبة: " +
                      ", ".join([f"{STAMINA_POTIONS[i]['name']}: {bag_potions.get(i, 0)}" for i in STAMINA_POTIONS]))

        # 2. استخدام الجرعات المجانية (1004/2)
        if use_free:
            for item_id, info in STAMINA_POTIONS.items():
                available_count = bag_potions.get(item_id, 0)
                if available_count <= 0:
                    continue

                # الحد الأقصى للاستخدام إذا حُدد في الإعدادات
                cfg_max = cfg.get(f'max_{info["value"]}')
                count_to_use = min(available_count, int(cfg_max)) if cfg_max is not None else available_count

                if count_to_use <= 0:
                    continue

                self.log.info(f"🚀 جاري استخدام {count_to_use} من {info['name']}...")
                payload = {
                    "itemID": item_id,
                    "count": count_to_use
                }

                r_use = await self.conn.query('1004', '2', payload, timeout=8)
                if r_use and str(r_use.get('err', '0')) == '0':
                    stamina_add = count_to_use * info['value']
                    total_stamina_gained += stamina_add
                    used_items_summary[item_id] = count_to_use
                    self.log.info(f"✅ تم استخدام {count_to_use} من {info['name']} بنجاح (+{stamina_add} طاقة) 🎉")
                else:
                    err_code = str(r_use.get('err', 'unknown')) if r_use else 'timeout'
                    self.log.warning(f"⚠️ فشل استخدام {info['name']} (كود السيرفر: {err_code})")

                await asyncio.sleep(1.8)  # فاصل زمني آمن لحماية الحساب

        # 3. شراء الطاقة بالذهب (2060/1) بالتكرار الدقيق بعدد المرات المطلوب
        max_price = int(cfg.get('max_price', cfg.get('price_limit', 0)))
        if gold_buys > 0:
            self.log.info(f"🪙 جاري تنفيذ {gold_buys} عمليات شراء طاقة بالذهب بأمر 2060/1 (الحد الأقصى للسعر: {max_price if max_price > 0 else 'غير محدد'})...")
            for i in range(gold_buys):
                # فحص السعر الحالي قبل إرسال الطلب لحماية الذهب
                bs_now = self.conn.init_data.get('buyStaminaCtrl', {}) if hasattr(self.conn, 'init_data') else {}
                cur_p = int(bs_now.get('price', 0)) if isinstance(bs_now, dict) else 0
                if max_price > 0 and cur_p > max_price:
                    self.log.warning(f"⚠️ توقف شراء الطاقة بالذهب: سعر التبديل الحالي بالقلعة ({cur_p} ذهب) تجاوز الحد الأقصى ({max_price} ذهب).")
                    break

                self.log.info(f"🪙 إرسال طلب الشراء بالذهب #{i+1} من أصل {gold_buys} (السعر الحالي: {cur_p} ذهب)...")
                r_buy = await self.conn.query('2060', '1', {}, timeout=8)
                if r_buy and str(r_buy.get('err', '0')) == '0':
                    gold_buys_done += 1
                    total_stamina_gained += 100
                    if isinstance(r_buy.get('data'), dict) and 'buyStaminaCtrl' in r_buy['data']:
                        self.conn.init_data['buyStaminaCtrl'].update(r_buy['data']['buyStaminaCtrl'])
                    self.log.info(f"✅ تم تنفيذ طلب الشراء بالذهب #{i+1} بنجاح ✅")
                else:
                    err_code = str(r_buy.get('err', 'unknown')) if r_buy else 'timeout'
                    self.log.info(f"ℹ️ رد السيرفر لطلب الشراء #{i+1}: (كود: {err_code})")

                # فاصل زمني آمن بين كل طلب وآخر
                if i < gold_buys - 1:
                    await asyncio.sleep(2.0)

        summary_msg = f"تم استخدام الجرعات المجانية (+{total_stamina_gained} طاقة إجمالية) | شراء ذهب: {gold_buys_done}"
        self.log.info(f"🎉 {summary_msg}")

        return TaskResult.ok(
            summary_msg,
            status="completed",
            stamina_gained=total_stamina_gained,
            used_potions=used_items_summary,
            gold_buys=gold_buys_done,
            retry_after=3600
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Stamina Task — مهمة استخدام جرعات الطاقة وشراء الطاقة بالذهب")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--gold", "-g", type=int, default=0,
                        help="عدد مرات شراء الطاقة بالذهب [افتراضي: 0 = بدون شراء بالذهب]")
    parser.add_argument("--no-free", action="store_true",
                        help="تعطيل استخدام الجرعات المجانية من الحقيبة")
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
            "use_free": not args.no_free,
            "gold": args.gold,
        }

        task = StaminaTask(conn, task_cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
