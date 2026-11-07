# -*- coding: utf-8 -*-
"""
tasks/alliance.py — مهمة التحالف: التبرع لعلوم التحالف ومساعدة الأعضاء
══════════════════════════════════════════════════════════════════════════════════════

دورة عمل المهمة:
  1. التحقق من عضوية التحالف (تجاوز آمن إذا لم تكن القلعة في تحالف).
  2. تقديم المساعدة لطلبات الأعضاء المتاحة (1012/1 و 1012/2).
  3. استعلام رصيد التبرعات المتاحة وموعد التجديد (1010/81).
  4. الاكتشاف التلقائي للتقنية الموصى بها من قائد التحالف (recommend=True).
  5. تنفيذ التبرعات المجانية بالمتاح حتى 20 مرة (1010/48 | donatetype: 2).
  6. التبرع بالذهب إذا حُدد عدد مرات مخصص من Firebase (donatetype: 1).

الاستخدام كملف مستقل:
    python tasks/alliance.py --email "meik.gaertner2306.MGr@gmail.com"
    python tasks/alliance.py --email "johan2003@yopmail.com" --gold 2
    python tasks/alliance.py --email "sumo-1234@hotmil.com" --gold 3 --sciid 33015
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
#  ثوابت التبرع
# ════════════════════════════════════════════════════════════════════

DONATE_TYPE_GOLD = 1     # التبرع بالذهب
DONATE_TYPE_FREE = 2     # التبرع المجاني بالموارد العادية
DEFAULT_SCI_ID   = 33015 # التقنية الاحتياطية عند عدم وجود توصية
DONATE_DELAY_RANGE = (1.6, 2.9)  # فاصل بشري عشوائي بين طلبات التبرع لمنع رصد البوت


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (AllianceTask)
# ════════════════════════════════════════════════════════════════════

class AllianceTask(BaseTask):
    """
    مهمة التبرع لعلوم التحالف ومساعدة الأعضاء.
    """
    name = "alliance"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    def _find_recommended_science(self) -> Optional[int]:
        """
        يطبع جميع تقنيات التحالف المتاحة للتطوير أولاً للتحقق، 
        ثم يكتشف التقنية الأنسب للتبرع بناءً على (التوصية -> قيد التطوير -> أي تقنية غير مكتملة).
        """
        scilist = None
        for k, v in self.conn.init_data.items():
            if isinstance(v, dict) and 'sciencelist' in v:
                scilist = v['sciencelist'].get('scilist')
                break

        if not scilist or not isinstance(scilist, dict):
            self.log.warning("لم يتم العثور على بيانات علوم التحالف في الحساب.")
            return None

        # ─── كود الفحص والطباعة للعلوم غير المكتملة ───
        incomplete_count = 0
        
        for cat, items in scilist.items():
            if isinstance(items, list):
                for item in items:
                    lv = int(item.get('lv', 0))
                    # طباعة أي تقنية مستواها أقل من 20 (غير مكتملة)
                    if lv < 20:
                        sci_id = int(item.get('id', 0))
                        
                        incomplete_count += 1
                        
        # 1. البحث عن التقنية الموصى بها
        for cat, items in scilist.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get('recommend'):
                        sci_id = int(item.get('id', 0))
                        if sci_id > 0:
                            self.log.info(f"🎯 تم اختيار التقنية الموصى بها للتبرع: ID={sci_id} (المستوى={item.get('lv')})")
                            return sci_id

        # 2. البحث عن تقنية قيد التطوير النشط (point > 0)
        for cat, items in scilist.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get('point', 0) > 0 and int(item.get('lv', 0)) < 20:
                        sci_id = int(item.get('id', 0))
                        if sci_id > 0:
                            self.log.info(f"🔬 لم توجد توصية، تم اختيار تقنية قيد التطوير كبديل: ID={sci_id} (المستوى={item.get('lv')})")
                            return sci_id

        # 3. البحث عن أي تقنية غير مكتملة (كملاذ أخير)
        for cat, items in scilist.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and int(item.get('lv', 0)) < 20:
                        sci_id = int(item.get('id', 0))
                        if sci_id > 0:
                            self.log.info(f"💡 لم توجد توصية أو تطوير نشط، تم اختيار تقنية غير مكتملة كبديل أخير: ID={sci_id} (المستوى={item.get('lv')})")
                            return sci_id

        return None

    async def run(self) -> TaskResult:
        cfg = self.config
        uid = int(self.conn.uid) if self.conn.uid else 0

        # 1. التحقق من عضوية التحالف
        alliance_ctrl = self.conn.init_data.get('allianceCtrl', {})
        alliance_id = 0
        if isinstance(alliance_ctrl, dict) and alliance_ctrl:
            minfo = alliance_ctrl.get('memberinfo', {}).get('minfo', {})
            if isinstance(minfo, dict):
                alliance_id = int(minfo.get('aid', 0))
            if alliance_id == 0:
                alliance_id = int(alliance_ctrl.get('allianceInfo', {}).get('aid', 0))
            if alliance_id == 0 and len(alliance_ctrl) > 5:
                alliance_id = 1

        if alliance_id == 0:
            lord_data = self.conn.init_data.get('lord', {})
            alliance_id = int(lord_data.get('alliance', 0)) if isinstance(lord_data, dict) else 0

        if alliance_id == 0:
            self.log.info("ℹ️ القلعة ليست عضواً في أي تحالف — تم تجاوز التبرع.")
            return TaskResult.ok(
                "القلعة ليست عضواً في تحالف",
                status="no_alliance",
                retry_after=7200
            )

        self.log.debug(f"🏛️ بدء مهمة التحالف (التحالف ID: {alliance_id})")

        alliance_ctrl = self.conn.init_data.get("allianceCtrl", {})
        minfo = alliance_ctrl.get("memberinfo", {}).get("minfo", {}) if isinstance(alliance_ctrl, dict) else {}

        free_available = int(minfo.get("donateCount", 0))
        gold_done      = int(minfo.get("donateGlodCount", 0))
        
        self.log.debug(f"📊 رصيد التبرع الحالي: {free_available}/20 مجاني | تبرعات الذهب: {gold_done}")

        # 4. تحديد التقنية المستهدفة للتبرع
        custom_sciid = cfg.get('sciid')
        target_sciid = int(custom_sciid) if custom_sciid else self._find_recommended_science()

        if not target_sciid or target_sciid <= 0:
            target_sciid = DEFAULT_SCI_ID
            self.log.info(f"ℹ️ استخدام التقنية الافتراضية: ID={target_sciid}")

        total_donated_free = 0
        total_donated_gold = 0
        total_honor_earned = 0
        total_scipoints    = 0

        # 5. تنفيذ التبرعات المجانية بالمتاح (donatetype: 2)
        if free_available > 0:
            self.log.info(f"🚀 جاري تنفيذ {free_available} تبرع مجاني للتقنية #{target_sciid}...")
            for i in range(free_available):
                r_donate = await self.conn.query('1010', '48', {
                    "sciid": target_sciid,
                    "donatetype": DONATE_TYPE_FREE
                }, timeout=8)

                if r_donate and str(r_donate.get('err', '0')) == '0':
                    total_donated_free += 1
                    get_info = r_donate.get('data', {}).get('retdata', {}).get('get', {})
                    total_honor_earned += int(get_info.get('honor', 0))
                    total_scipoints    += int(get_info.get('scipoint', 0))
                else:
                    err_code = str(r_donate.get('err', 'unknown')) if r_donate else 'timeout'
                    self.log.warning(f"⚠️ توقف التبرع المجاني عند المحاولة {i+1} (كود: {err_code})")
                    break

                # تأخير بشري عشوائي يحاكي نقر اليد البشرية الطبيعية
                await asyncio.sleep(round(random.uniform(*DONATE_DELAY_RANGE), 2))

            self.log.info(f"✅ اكتملت التبرعات المجانية")
        else:
            self.log.info("ℹ️ رصيد التبرعات المجانية مستهلك حالياً (0/20) — بانتظار التجديد.")

        # 6. التبرع بالذهب إن حُدد في الإعدادات / Firebase (donatetype: 1 - الحد الأقصى 10)
        target_gold_donations = min(10, max(0, int(cfg.get('gold_donations', 0))))
        if target_gold_donations > 0:
            self.log.info(f"🪙 جاري تنفيذ {target_gold_donations} تبرع بالذهب للتقنية #{target_sciid}...")
            for i in range(target_gold_donations):
                r_gdonate = await self.conn.query('1010', '48', {
                    "sciid": target_sciid,
                    "donatetype": DONATE_TYPE_GOLD
                }, timeout=8)

                if r_gdonate and str(r_gdonate.get('err', '0')) == '0':
                    total_donated_gold += 1
                    get_info = r_gdonate.get('data', {}).get('retdata', {}).get('get', {})
                    total_honor_earned += int(get_info.get('honor', 0))
                    total_scipoints    += int(get_info.get('scipoint', 0))
                else:
                    err_code = str(r_gdonate.get('err', 'unknown')) if r_gdonate else 'timeout'
                    self.log.warning(f"⚠️ توقف التبرع بالذهب عند المحاولة {i+1} (كود: {err_code})")
                    break

                # تأخير بشري عشوائي يحاكي نقر اليد البشرية الطبيعية
                await asyncio.sleep(round(random.uniform(*DONATE_DELAY_RANGE), 2))

            self.log.info(f" اكتمل التبرع بالذهب: {total_donated_gold} تبرع")

        summary_msg = f"تم إنجاز {total_donated_free} تبرع مجاني + {total_donated_gold} تبرع ذهب (شرف +{total_honor_earned:,})"
        return TaskResult.ok(
            summary_msg,
            status="donated",
            free_donated=total_donated_free,
            gold_donated=total_donated_gold,
            honor_earned=total_honor_earned,
            sci_points=total_scipoints,
            sciid=target_sciid,
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Alliance Science Donation Task — مهمة التبرع لعلوم التحالف")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--gold", "-g", type=int, default=0,
                        help="عدد مرات التبرع بالذهب [افتراضي: 0 = بدون تبرع بالذهب]")
    parser.add_argument("--sciid", "-s", type=int, default=None,
                        help="معرف التقنية المخصص للتبرع [افتراضي: اكتشاف التقنية الموصى بها تلقائياً]")
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
            "gold_donations": args.gold,
            "sciid": args.sciid,
        }

        task = AllianceTask(conn, task_cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
