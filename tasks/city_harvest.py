# -*- coding: utf-8 -*-
"""
tasks/city_harvest.py — مهمة حصد وجمع موارد مزارع المدينة الداخلية بالكامل
══════════════════════════════════════════════════════════════════════════════════════
تقوم هذه المهمة بالمرور على جميع مباني الموارد داخل القلعة وجني محاصيلها المتراكمة:
  - 🌾 مزارع القمح (bid: 201)
  - 🪵 مناشر الخشب (bid: 202)
  - ⛏️ مناجم الحديد (bid: 203)
  - 🪙 مناجم الفضة والألماس (bid: 204)

بروتوكول حصد المزرعة:
  - الطلب: cmd: "1001", subcmd: "8", data: {"bid": int(bid), "iid": int(iid)}
  - تبدأ أرقام المزارع (iid) من 0 وتصل إلى 9+ لكل نوع بحسب حجم وتطوير القلعة.

خيارات التشغيل (config):
  - types: أنواع الموارد المستهدفة [افتراضي: "all" أو قائمة محددة: "food,wood,iron,silver"]
  - min_res: الحد الأدنى للموارد المتراكمة في المزرعة للبدء بحصدها [افتراضي: 0]

الاستخدام كملف مستقل (CLI):
  python tasks/city_harvest.py --email "samartilleli@yopmail.com"
  python tasks/city_harvest.py --email "samartilleli@yopmail.com" --types "قمح,حديد"
  python tasks/city_harvest.py --all-accounts
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
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  تعريفات مباني الموارد والرموز
# ════════════════════════════════════════════════════════════════════

RESOURCE_FARMS: Dict[int, Dict[str, Any]] = {
    201: {"name": "🌾 مزارع القمح (Wheat Farm)", "key": "food", "icon": "🌾"},
    202: {"name": "🪵 مناشر الخشب (Sawmill)",    "key": "wood", "icon": "🪵"},
    203: {"name": "⛏️ مناجم الحديد (Iron Mine)",  "key": "iron", "icon": "⛏️"},
    204: {"name": "🪙 مناجم الفضة/الألماس (Silver/Diamond)", "key": "silver", "icon": "🪙"},
}

RES_ALIASES: Dict[str, int] = {
    "food": 201, "wheat": 201, "قمح": 201, "طعام": 201, "القمح": 201, "201": 201,
    "wood": 202, "lumber": 202, "خشب": 202, "الخشب": 202, "منشرة": 202, "202": 202,
    "iron": 203, "حديد": 203, "الحديد": 203, "منجم حديد": 203, "203": 203,
    "silver": 204, "diamond": 204, "steel": 204, "فضة": 204, "الفضة": 204, "ألماس": 204, "الماس": 204, "204": 204,
}


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (CityHarvestTask)
# ════════════════════════════════════════════════════════════════════

class CityHarvestTask(BaseTask):
    """
    مهمة حصد وجني جميع موارد مزارع المدينة الداخلية بالكامل.
    """
    name = "city_harvest"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.target_bids = self._parse_target_bids()
        self.min_res = float(self.config.get("min_res", 0))

    def _parse_target_bids(self) -> List[int]:
        raw = self.config.get("types", self.config.get("type", "all"))
        if not raw or str(raw).strip().lower() in ("all", "الكل", "all_types"):
            return list(RESOURCE_FARMS.keys())

        parts = []
        if isinstance(raw, str):
            parts = [p.strip().lower() for p in raw.replace("،", ",").split(",") if p.strip()]
        elif isinstance(raw, (list, tuple)):
            parts = [str(p).strip().lower() for p in raw if str(p).strip()]

        selected = []
        for p in parts:
            if p in ("all", "الكل"):
                return list(RESOURCE_FARMS.keys())
            bid = RES_ALIASES.get(p)
            if bid and bid not in selected:
                selected.append(bid)

        return selected if selected else list(RESOURCE_FARMS.keys())

    async def get_city_farms(self) -> List[Dict[str, Any]]:
        """استعلام قائمة جميع مباني الموارد الموجودة بالمدينة وحالتها عبر 1001/1."""
        blist = []
        try:
            r = await self.conn.query("1001", "1", {}, timeout=8)
            if r and "data" in r:
                blist = r["data"].get("blist", [])
        except Exception as e:
            self.log.warning(f"⚠️ تعذر الاستعلام المباشر عبر 1001/1: {e}")

        # محاولة قراءة الحزم المحفوظة كاحتياط
        if not blist and "cityCtrl" in self.conn.init_data:
            blist = self.conn.init_data["cityCtrl"].get("blist", [])

        # تصفية مباني الموارد المستهدفة
        farms = []
        for item in blist:
            binfo = item.get("binfo", {}) if isinstance(item, dict) else {}
            bid_raw = binfo.get("bid")
            if bid_raw is None:
                continue
            bid = int(bid_raw)
            if bid in self.target_bids:
                farms.append(binfo)

        # ترتيب المزارع بحسب نوع المورد ثم رقم المزرعة الفرعي (iid)
        farms.sort(key=lambda x: (int(x.get("bid", 0)), int(x.get("iid", 0))))
        return farms

    async def harvest_single_farm(self, bid: int, iid: int) -> bool:
        """إرسال أمر حصد مزرعة فردية محددة عبر 1001/8."""
        payload = {
            "bid": int(bid),
            "iid": int(iid)
        }
        try:
            resp = await self.conn.query("1001", "8", payload, timeout=6)
            return resp is not None and str(resp.get("err", "-1")) == "0"
        except Exception as e:
            self.log.warning(f"⚠️ خطأ أثناء حصد المزرعة {bid}/{iid}: {e}")
            return False

    async def run(self) -> TaskResult:
        self.log.info("🌾 بدء مهمة حصد وجني محاصيل مزارع المدينة الداخلية...")

        farms = await self.get_city_farms()
        if not farms:
            msg = "ℹ️ لم يتم العثور على أي مباني موارد مؤهلة للحصد داخل القلعة."
            self.log.info(msg)
            return TaskResult.ok(msg, harvested_count=0)

        self.log.info(f"📊 إجمالي مباني الموارد المكتشفة في القلعة: {len(farms)} مزرعة/منجم.")

        harvested_by_type: Dict[int, int] = {201: 0, 202: 0, 203: 0, 204: 0}
        total_harvested = 0
        total_skipped_empty = 0

        for farm in farms:
            bid = int(farm.get("bid", 0))
            iid = int(farm.get("iid", 0))
            curres = float(farm.get("curres", 0))
            lv = int(farm.get("lv", 1))
            f_meta = RESOURCE_FARMS.get(bid, {"name": f"مبنى #{bid}", "icon": "📦"})

            # إذا كانت المزرعة شبه فارغة وأقل من الحد الأدنى
            if self.min_res > 0 and curres < self.min_res:
                total_skipped_empty += 1
                continue

            success = await self.harvest_single_farm(bid, iid)
            if success:
                harvested_by_type[bid] = harvested_by_type.get(bid, 0) + 1
                total_harvested += 1
                self.log.info(f"   {f_meta['icon']} تم جني محصول {f_meta['name']} (رقم {iid} | مستوى {lv}) بنجاح! (+{int(curres):,} مورد)")
            else:
                self.log.warning(f"   ⚠️ تعذر جني محصول {f_meta['name']} (رقم {iid})")

            # تأخير قصير جداً لمحاكاة النقر البشري الطبيعي
            await asyncio.sleep(0.25)

        # تجهيز ملخص النتيجة
        summary_parts = []
        for bid, count in harvested_by_type.items():
            if count > 0:
                summary_parts.append(f"{RESOURCE_FARMS[bid]['icon']} {count} {RESOURCE_FARMS[bid]['name'].split(' ')[1]}")

        if total_harvested > 0:
            summary_text = f"✅ تم بنجاح حصد {total_harvested} مزرعة: (" + " | ".join(summary_parts) + ")"
        else:
            summary_text = "ℹ️ جميع المزارع خالية حالياً أو تم حصدها مسبقاً."

        self.log.info(f"🎉 نتيجة حصد المدينة: {summary_text}")

        return TaskResult.ok(
            summary_text,
            total_harvested=total_harvested,
            details=harvested_by_type,
            farms_count=len(farms)
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر من سطر الأوامر (CLI)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(
        description="City Farm Harvest Task — مهمة حصد مزارع موارد المدينة بالكامل"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب المستهدف")
    parser.add_argument(
        "--types", "-t",
        default="all",
        help="أنواع الموارد المستهدفة مفصولة بفاصلة (مثال: 'قمح,خشب' أو 'all') [افتراضي: الكل]"
    )
    parser.add_argument(
        "--min-res", "-m",
        type=float,
        default=0,
        help="الحد الأدنى لكمية الموارد بالمزرعة لبدء جنيها [افتراضي: 0]"
    )
    parser.add_argument("--all-accounts", action="store_true", help="تشغيل المهمة لجميع الحسابات المسجلة")
    args = parser.parse_args()

    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        print("❌ لا توجد حسابات مسجلة في session_cache.json!")
        sys.exit(1)

    async def _run_for_account(acc_email: str, acc_obj: Any):
        print("\n" + "═" * 70)
        print(f"🌾 حصد مزارع الحساب: {acc_email}")
        print("═" * 70)

        conn = GameConnection(acc_obj)
        if not await conn.connect():
            print(f"❌ فشل الاتصال بالحساب {acc_email}!")
            return

        for _ in range(12):
            await asyncio.sleep(0.3)
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "types": args.types,
            "min_res": args.min_res
        }

        task = CityHarvestTask(conn, task_cfg)
        await task.on_start()
        res = await task.run()

        print("─" * 70)
        print(f"{res.message}")
        print("─" * 70 + "\n")

        await conn.close()

    async def _main():
        if args.all_accounts:
            for email, acc in accounts.items():
                if email.startswith("azjfhf"):
                    continue
                await _run_for_account(email, acc)
        else:
            target_email = args.email or next(iter(accounts.keys()))
            acc = accounts.get(target_email)
            if not acc:
                print(f"❌ الحساب {target_email} غير موجود!")
                return
            await _run_for_account(target_email, acc)

    asyncio.run(_main())
