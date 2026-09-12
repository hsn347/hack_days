# -*- coding: utf-8 -*-
"""
tasks/material_workshop.py — مهمة ورشة المواد وإنتاج خامات العتاد تلقائياً
══════════════════════════════════════════════════════════════════════════════════════

بروتوكول ورشة المواد (Material Workshop / Equipment Materials):
  - الأمر: cmd: "3129", subcmd: "4"
  - البيانات: {"mid": material_id}

الخامات المتاحة:
  1. 🦷 الناب (Fang):   690402
  2. 🦊 الفرو (Fur):    690102
  3. ⛓️ المعدن (Metal): 690202
  4. 🪵 الفحم (Coal):   690302

سعة الإنتاج:
  - الحد الأقصى للمسار هو 5 عناصر (1 قيد التصنيع المباشر + 4 في قائمة الانتظار).
  - البوت يملأ كافة المسارات الفارغة بالكامل مع تحقيق التوازن التام بين الخامات المختارة من المستخدم.

الاستخدام كملف مستقل:
    python tasks/material_workshop.py --email "johan2003@yopmail.com" --materials all
    python tasks/material_workshop.py --email "burcudemr@gmail.com" --materials "ناب,فرو"
    python tasks/material_workshop.py --email "zzoro8290@gmail.com" -m "fang,metal,coal"
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
from collections import Counter
from typing import Any, Dict, List, Optional, Union

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# ════════════════════════════════════════════════════════════════════
#  تعريف خامات ورشة المواد
# ════════════════════════════════════════════════════════════════════

MATERIALS_MAP: Dict[int, Dict[str, Any]] = {
    690402: {"id": 690402, "key": "fang",  "name_ar": "الناب",  "name_en": "Fang",  "icon": "🦷"},
    690102: {"id": 690102, "key": "fur",   "name_ar": "الفرو",  "name_en": "Fur",   "icon": "🦊"},
    690202: {"id": 690202, "key": "metal", "name_ar": "المعدن", "name_en": "Metal", "icon": "⛓️"},
    690302: {"id": 690302, "key": "coal",  "name_ar": "الفحم",  "name_en": "Coal",  "icon": "🪵"},
}

MATERIAL_NAME_ALIASES: Dict[str, int] = {
    # Fang
    "fang": 690402, "tooth": 690402, "الناب": 690402, "ناب": 690402, "690402": 690402,
    # Fur
    "fur": 690102, "pelt": 690102, "الفرو": 690102, "فرو": 690102, "690102": 690102,
    # Metal
    "metal": 690202, "iron": 690202, "ore": 690202, "المعدن": 690202, "معدن": 690202, "حديد": 690202, "690202": 690202,
    # Coal
    "coal": 690302, "charcoal": 690302, "الفحم": 690302, "فحم": 690302, "690302": 690302,
}

MAX_TOTAL_CAPACITY = 5  # 1 نشط + 4 انتظار
QUEUE_TYPE_WORKSHOP = "1256"


def parse_materials_choice(raw_input: Union[str, List[Any], None]) -> List[int]:
    """تحويل مدخلات المستخدم إلى قائمة معرفات الخامات المختارة."""
    if not raw_input or raw_input == "all" or raw_input == "الكل":
        return list(MATERIALS_MAP.keys())

    if isinstance(raw_input, str):
        # فصل الفواصل أو المسافات
        parts = [p.strip().lower() for p in raw_input.replace("،", ",").split(",") if p.strip()]
    elif isinstance(raw_input, (list, tuple)):
        parts = [str(p).strip().lower() for p in raw_input if str(p).strip()]
    else:
        return list(MATERIALS_MAP.keys())

    selected_ids: List[int] = []
    for part in parts:
        if part in ("all", "الكل", "all_materials"):
            return list(MATERIALS_MAP.keys())
        if part in MATERIAL_NAME_ALIASES:
            mid = MATERIAL_NAME_ALIASES[part]
            if mid not in selected_ids:
                selected_ids.append(mid)

    return selected_ids if selected_ids else list(MATERIALS_MAP.keys())


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (MaterialWorkshopTask)
# ════════════════════════════════════════════════════════════════════

class MaterialWorkshopTask(BaseTask):
    """
    مهمة إنتاج خامات عتاد الأبطال في ورشة المواد بملء المسارات الـ 5 بالكامل وموازنة الخامات.
    """
    name = "material_workshop"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        raw_mat = self.config.get("materials", "all")
        self.selected_mids = parse_materials_choice(raw_mat)

    async def run(self) -> TaskResult:
        self.log.info("🔨 بدء مهمة ورشة المواد (إنتاج خامات العتاد)...")

        now_ts = int(time.time())

        # 1. قراءة حالة مسار الإنتاج الحالي
        queue_ctrl = self.conn.init_data.get('queueCtrl', {})
        he_ag_ctrl = self.conn.init_data.get('heroEquipAgCtrl', {})

        active_item_info = queue_ctrl.get(QUEUE_TYPE_WORKSHOP, {}) if isinstance(queue_ctrl, dict) else {}
        waiting_queues: List[int] = he_ag_ctrl.get('queues', []) if isinstance(he_ag_ctrl, dict) else []

        if not isinstance(waiting_queues, list):
            waiting_queues = []

        # فحص العنصر النشط قيد التصنيع الآن
        has_active_production = False
        active_end_time = 0
        active_mid = 0

        if active_item_info:
            active_data = active_item_info.get('data', {})
            active_end_time = int(active_data.get('endTime', 0))
            active_mid = int(active_data.get('mid', 0))
            if active_end_time > now_ts:
                has_active_production = True

        occupied_count = (1 if has_active_production else 0) + len(waiting_queues)
        free_slots = max(0, MAX_TOTAL_CAPACITY - occupied_count)

        self.log.info(f"📊 حالة مسار الورشة: {occupied_count}/{MAX_TOTAL_CAPACITY} ممتلئ | الفراغات المتاحة: {free_slots}")
        if has_active_production:
            m_info = MATERIALS_MAP.get(active_mid, {"name_ar": f"خامة #{active_mid}", "icon": "📦"})
            remaining_s = active_end_time - now_ts
            self.log.info(f"⏳ قيد التصنيع حالياً: {m_info['icon']} {m_info['name_ar']} (متبقي: {remaining_s // 60} دقيقة)")

        if waiting_queues:
            waiting_names = [f"{MATERIALS_MAP.get(m, {}).get('icon', '')} {MATERIALS_MAP.get(m, {}).get('name_ar', str(m))}" for m in waiting_queues]
            self.log.info(f"📋 قائمة الانتظار ({len(waiting_queues)}): {', '.join(waiting_names)}")

        # عرض الخامات المختارة للإنتاج
        chosen_names = [f"{MATERIALS_MAP[m]['icon']} {MATERIALS_MAP[m]['name_ar']}" for m in self.selected_mids if m in MATERIALS_MAP]
        self.log.info(f"🎯 الخامات المحددة للإنتاج: {', '.join(chosen_names)}")

        # 2. إذا كانت كافة المسارات ممتلئة بالكامل
        if free_slots <= 0:
            retry_seconds = max(60, active_end_time - now_ts) if active_end_time > now_ts else 3600
            msg = f"مسار ورشة المواد ممتلئ بالكامل ({occupied_count}/{MAX_TOTAL_CAPACITY}). سينتهي أقرب عنصر بعد {retry_seconds // 60} دقيقة."
            self.log.info(f"ℹ️ {msg}")
            return TaskResult.ok(
                msg,
                status="queue_full",
                retry_after=retry_seconds,
                data={
                    "occupied_slots": occupied_count,
                    "waiting_queues": waiting_queues,
                    "active_mid": active_mid,
                    "active_end_time": active_end_time,
                }
            )

        # 3. ملء الفراغات المتاحة بالتوازن بين الخامات المختارة
        # نحسب تكرار كل خامة في المسار الحالي لتحديد الأقل إنتاجاً وموازنته
        current_counts = Counter()
        if has_active_production and active_mid in self.selected_mids:
            current_counts[active_mid] += 1
        for m in waiting_queues:
            if m in self.selected_mids:
                current_counts[m] += 1

        queued_actions: List[Dict[str, Any]] = []

        for slot_idx in range(free_slots):
            # اختيار الخامة الأقل تواجداً في المسار من بين المختارة لضمان الموازنة التامة
            best_mid = min(self.selected_mids, key=lambda mid: current_counts[mid])
            m_info = MATERIALS_MAP.get(best_mid, {"name_ar": str(best_mid), "icon": "📦"})

            self.log.info(f"➕ [فتحة {slot_idx + 1}/{free_slots}] جاري إضافة {m_info['icon']} {m_info['name_ar']} إلى خط الإنتاج...")

            payload = {"mid": best_mid}
            resp = await self.conn.query("3129", "4", payload, timeout=8)

            if resp and str(resp.get("err", "0")) == "0":
                self.log.info(f"✅ تم وضع {m_info['icon']} {m_info['name_ar']} في خط الإنتاج بنجاح!")
                current_counts[best_mid] += 1
                queued_actions.append({
                    "mid": best_mid,
                    "name": m_info["name_ar"],
                    "icon": m_info["icon"]
                })
            elif resp and resp.get("err") == "Err_HERO_EQUIP_MAX_QUEUE":
                self.log.warning("⚠️ اكتمل الحد الأقصى للمسار بالكامل في السيرفر.")
                break
            else:
                err_code = resp.get("err", "unknown") if resp else "timeout"
                self.log.warning(f"⚠️ تعذر وضع {m_info['name_ar']} (خطأ: {err_code})")
                break

            # فاصل زمني بسيط بين الطلبات
            await asyncio.sleep(1.5)

        # 4. حساب وقت المراجعة القادمة
        total_now = occupied_count + len(queued_actions)
        retry_seconds = max(60, active_end_time - now_ts) if active_end_time > now_ts else 21600

        msg = f"تم ملء ورشة المواد بإضافة {len(queued_actions)} عناصر جديدة (المسار الآن: {total_now}/{MAX_TOTAL_CAPACITY})."
        self.log.info(f"🎉 {msg}")

        return TaskResult.ok(
            msg,
            status="produced",
            retry_after=retry_seconds,
            data={
                "added_materials": queued_actions,
                "total_occupied": total_now,
                "selected_mids": self.selected_mids,
                "retry_after": retry_seconds
            }
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Material Workshop Task — مهمة ورشة المواد وإنتاج خامات العتاد")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--materials", "-m", default="all", help="الخامات المطلوبة مفصولة بفواصل (مثل: ناب,فرو أو fang,metal أو all)")
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

        cfg = {"materials": args.materials}
        task = MaterialWorkshopTask(conn, cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
