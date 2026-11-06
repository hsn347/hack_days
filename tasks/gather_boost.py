# -*- coding: utf-8 -*-
"""
tasks/gather_boost.py — مهمة مكافأة الجمع (Gather Speed Boost Task)
════════════════════════════════════════════════════════════════════
تفعيل مكافأة زيادة سرعة جمع الموارد بنسبة 50% للقلعة:
  - مكافأة الجمع الصغيرة (itemID: 400101, buffID: 5008, مدتها 8 ساعات)
  - مكافأة الجمع الكبيرة (itemID: 400102, buffID: 5009, مدتها 24 ساعة)

المنطق وقواعد التشغيل:
  1. فحص التعزيزات النشطة (buffCtrl / CMD 1019/1):
     - إذا كانت هناك مكافأة جمع مفعلة سلفاً (صغيرة أو كبيرة ولم تنتهِ مدتها)،
       يتم تخطي المهمة ككل فوراً مع إظهار الوقت المتبقي.
  2. فحص الحقيبة (CMD 1004/1):
     - الأولوية للمكافأة الصغيرة (400101). إذا وُجدت، يتم تفعيلها عبر 1004/2.
     - إذا لم تتوفر الصغيرة، يتم فحص المكافأة الكبيرة (400102). إذا وُجدت، يتم تفعيلها.
     - إذا لم تتوفر أي منهما، يتم تخطي المهمة بسلام (no_items).

الاستخدام كملف مستقل:
    python tasks/gather_boost.py --email "king7moe1990@gmail.com"
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
import argparse
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  ثوابت أدوات وتعزيزات مكافأة الجمع
# ════════════════════════════════════════════════════════════════════

ITEM_SMALL_BOOST = 400101   # مكافأة الجمع الصغيرة (8 ساعات)
ITEM_LARGE_BOOST = 400102   # مكافأة الجمع الكبيرة (24 ساعة)

BUFF_SMALL_BOOST = 5008     # معرّف تعزيز الصغيرة في السيرفر (effectType = 17)
BUFF_LARGE_BOOST = 5009     # معرّف تعزيز الكبيرة في السيرفر (effectType = 17)

DURATION_SMALL_SEC = 8 * 3600    # 28,800 ثانية
DURATION_LARGE_SEC = 24 * 3600   # 86,400 ثانية

BOOST_CONFIGS: Dict[int, Dict[str, Any]] = {
    ITEM_SMALL_BOOST: {
        "item_id": ITEM_SMALL_BOOST,
        "buff_id": BUFF_SMALL_BOOST,
        "name": "مكافأة الجمع الصغيرة",
        "duration_sec": DURATION_SMALL_SEC,
        "duration_str": "8 ساعات",
    },
    ITEM_LARGE_BOOST: {
        "item_id": ITEM_LARGE_BOOST,
        "buff_id": BUFF_LARGE_BOOST,
        "name": "مكافأة الجمع الكبيرة",
        "duration_sec": DURATION_LARGE_SEC,
        "duration_str": "24 ساعة",
    }
}

BUFF_TO_ITEM: Dict[int, int] = {
    BUFF_SMALL_BOOST: ITEM_SMALL_BOOST,
    BUFF_LARGE_BOOST: ITEM_LARGE_BOOST,
}


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (GatherBoostTask)
# ════════════════════════════════════════════════════════════════════

class GatherBoostTask(BaseTask):
    """
    مهمة فحص وتفعيل مكافأة سرعة الجمع (Gather Boost Task).
    """

    name = "gather_boost"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.log = logging.getLogger(f"GatherBoostTask[{getattr(conn, 'email', 'Unknown')}]")

    async def check_active_boost(self) -> Tuple[bool, Optional[Dict[str, Any]], int]:
        """
        التحقق مما إذا كانت هناك مكافأة جمع نشطة حالياً.
        1. تفحص مؤقت الجلسة الداخلي.
        2. تستعلم السيرفر عبر 1019/1 لتحديث التعزيزات الحية.
        3. تفحص قائمة buffCtrl في init_data.

        Returns:
            (is_active: bool, buff_info: Optional[dict], remaining_seconds: int)
        """
        now = int(time.time())

        # 1. فحص مؤقت الجلسة الداخلي المسجل مسبقاً (إن وجد)
        session_expire = getattr(self.conn, 'gather_boost_expire_ts', 0)
        if session_expire > now + 30:
            rem = session_expire - now
            return True, {"source": "session_cache", "expire_ts": session_expire}, rem

        # 2. استعلام السيرفر لتحديث قائمة التعزيزات النشطة (1019/1 - REQ_INIT_BUFFDATA)
        try:
            r_buff = await self.conn.query('1019', '1', {}, timeout=6)
            if r_buff and str(r_buff.get('err', '0')) == '0':
                data = r_buff.get('data')
                if isinstance(data, list):
                    self.conn.init_data['buffCtrl'] = data
                elif isinstance(data, dict) and 'buffCtrl' in data:
                    self.conn.init_data['buffCtrl'] = data['buffCtrl']
        except Exception as e:
            self.log.debug(f"استعلام 1019/1 لتحديث التعزيزات: {e}")

        # 3. فحص مصفوفة التعزيزات (buffCtrl) في بيانات القلعة
        init_data = getattr(self.conn, 'init_data', {}) or {}
        buff_ctrl = init_data.get('buffCtrl', [])

        if isinstance(buff_ctrl, list):
            for b in buff_ctrl:
                if not isinstance(b, dict):
                    continue
                b_id = b.get('id')
                if b_id in BUFF_TO_ITEM:
                    item_id = BUFF_TO_ITEM[b_id]
                    b_cfg = BOOST_CONFIGS[item_id]
                    begin_time = int(b.get('beginTime', 0))
                    duration = b_cfg['duration_sec']
                    end_time = int(b.get('endTime', 0)) or (begin_time + duration if begin_time > 0 else 0)

                    if end_time > now:
                        rem = end_time - now
                        self.conn.gather_boost_expire_ts = end_time
                        return True, {
                            "buff_id": b_id,
                            "item_id": item_id,
                            "name": b_cfg['name'],
                            "duration_str": b_cfg['duration_str'],
                            "begin_time": begin_time,
                            "end_time": end_time
                        }, rem

        return False, None, 0

    async def get_bag_boost_items(self) -> Dict[int, int]:
        """
        استعلام الحقيبة 1004/1 واستخراج رصيد مكافآت الجمع المتوفرة.
        يعيد قاموس {item_id: count}.
        """
        counts = {ITEM_SMALL_BOOST: 0, ITEM_LARGE_BOOST: 0}
        try:
            r_bag = await self.conn.query('1004', '1', {}, timeout=8)
            if not r_bag or str(r_bag.get('err', '0')) != '0':
                self.log.warning(f"⚠️ فشل استعلام الحقيبة 1004/1: {r_bag.get('err') if r_bag else 'timeout'}")
                return counts

            data = r_bag.get('data', {})
            # معالجة القاموس سواء كان data مباشرة أو داخل itemList
            items_dict = data.get('itemList', data) if isinstance(data, dict) else {}

            if isinstance(items_dict, dict):
                for k, v in items_dict.items():
                    iid = None
                    cnt = 0
                    if isinstance(v, dict):
                        iid = int(v.get('id', v.get('itemID', k)))
                        cnt = int(v.get('count', v.get('num', 0)))
                    elif str(v).isdigit():
                        try:
                            iid = int(k)
                            cnt = int(v)
                        except Exception:
                            pass

                    if iid in counts:
                        counts[iid] = max(counts[iid], cnt)

            elif isinstance(items_dict, list):
                for v in items_dict:
                    if isinstance(v, dict):
                        iid = int(v.get('id', v.get('itemID', 0)))
                        cnt = int(v.get('count', v.get('num', 0)))
                        if iid in counts:
                            counts[iid] = max(counts[iid], cnt)

        except Exception as e:
            self.log.warning(f"⚠️ خطأ أثناء قراءة الحقيبة 1004/1: {e}")

        return counts

    async def run(self) -> TaskResult:
        """
        تنفيذ منطق مهمة مكافأة الجمع:
        1. فحص إذا كانت هناك مكافأة جمع مفعلة -> تخطي المهمة ككل.
        2. إذا لم يكن هناك شيء مفعل -> فحص الحقيبة.
        3. الأولوية للصغيرة (400101) أولاً، ثم الكبيرة (400102).
        4. إذا لم يتوفر أي منهما -> تخطي المهمة.
        """
        cfg = self.config or {}
        if not bool(cfg.get('enabled', True)):
            return TaskResult.ok("⏭️ تم تخطي مهمة مكافأة الجمع (معطلة من الإعدادات)", skipped=True)

        self.log.info("🌾 بدء فحص مهمة مكافأة الجمع (Gather Speed Boost)...")

        # ── الخطوة 1: فحص ما إذا كانت هناك مكافأة جمع نشطة حالياً ──
        is_active, active_info, remaining_sec = await self.check_active_boost()
        if is_active:
            hours = remaining_sec // 3600
            mins = (remaining_sec % 3600) // 60
            buff_name = (active_info or {}).get('name', 'مكافأة جمع')
            msg = f"⏭️ تم تخطي مهمة مكافأة الجمع: {buff_name} نشطة بالفعل (متبقي: {hours} س و {mins} د)."
            self.log.info(msg)
            return TaskResult.ok(
                msg,
                skipped=True,
                already_active=True,
                remaining_seconds=remaining_sec,
                retry_after=max(60, remaining_sec),
                active_info=active_info
            )

        self.log.info("🔍 لا توجد مكافأة جمع نشطة حالياً — جاري فحص محتويات الحقيبة...")

        # ── الخطوة 2: فحص الحقيبة واستخراج المكافآت المتوفرة ──
        bag_counts = await self.get_bag_boost_items()
        small_count = bag_counts.get(ITEM_SMALL_BOOST, 0)
        large_count = bag_counts.get(ITEM_LARGE_BOOST, 0)

        self.log.info(
            f"🎒 المخزون المتوفر بالحقيبة: مكافأة الجمع الصغيرة: {small_count} | مكافأة الجمع الكبيرة: {large_count}"
        )

        # ── الخطوة 3: تحديد العنصر المستهدف وفق الأولوية (الصغيرة أولاً ثم الكبيرة) ──
        target_item_id: Optional[int] = None
        if small_count > 0:
            target_item_id = ITEM_SMALL_BOOST
        elif large_count > 0:
            target_item_id = ITEM_LARGE_BOOST
        else:
            msg = "⏭️ تم تخطي مهمة مكافأة الجمع: لا تتوفر أي مكافأة جمع (صغيرة أو كبيرة) في الحقيبة."
            self.log.info(msg)
            return TaskResult.ok(msg, skipped=True, no_items=True)

        target_cfg = BOOST_CONFIGS[target_item_id]
        item_name = target_cfg['name']
        dur_str = target_cfg['duration_str']
        dur_sec = target_cfg['duration_sec']
        buff_id = target_cfg['buff_id']

        # ── الخطوة 4: إرسال طلب التفعيل 1004/2 ──
        self.log.info(f"🚀 جاري تفعيل {item_name} (مدة: {dur_str}) عبر الأمر 1004/2...")
        payload = {
            "itemID": target_item_id,
            "count": 1
        }

        r_use = await self.conn.query('1004', '2', payload, timeout=8)
        if r_use and str(r_use.get('err', '0')) == '0':
            now = int(time.time())
            self.conn.gather_boost_expire_ts = now + dur_sec

            # تحديث قائمة التعزيزات داخلياً في init_data
            if hasattr(self.conn, 'init_data') and isinstance(self.conn.init_data, dict):
                buff_list = self.conn.init_data.setdefault('buffCtrl', [])
                if isinstance(buff_list, list):
                    self.conn.init_data['buffCtrl'] = [
                        b for b in buff_list if isinstance(b, dict) and b.get('id') not in (BUFF_SMALL_BOOST, BUFF_LARGE_BOOST)
                    ]
                    self.conn.init_data['buffCtrl'].append({
                        "id": buff_id,
                        "beginTime": now
                    })

            msg = f"✅ تم تفعيل {item_name} بنجاح (+50% سرعة جمع لمدة {dur_str}) 🎉"
            self.log.info(msg)
            return TaskResult.ok(
                msg,
                activated_item=target_item_id,
                item_name=item_name,
                buff_id=buff_id,
                duration_sec=dur_sec,
                remaining_seconds=dur_sec,
                retry_after=dur_sec
            )
        else:
            err_code = str(r_use.get('err', 'unknown')) if r_use else 'timeout'
            msg = f"⚠️ فشل تفعيل {item_name} (كود السيرفر: {err_code})"
            self.log.warning(msg)
            return TaskResult.fail(msg, err_code=err_code, target_item=target_item_id)


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول للتشغيل المستقل (Standalone CLI)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(description="Empire Gather Boost Task — مهمة مكافأة الجمع")
    parser.add_argument("--email", type=str, default=None, help="البريد الإلكتروني للحساب")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

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

        # انتظار تحميل بيانات التهيئة
        for _ in range(12):
            await asyncio.sleep(1.0)
            if len(conn.init_data) > 0:
                break

        task = GatherBoostTask(conn, {"enabled": True})
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
