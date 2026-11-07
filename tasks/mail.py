# -*- coding: utf-8 -*-
"""
tasks/mail.py — مهمة جمع البريد وحذف الرسائل (Mail Collect & Delete Task)
════════════════════════════════════════════════════════════════════════
المراحل:
  1. استعلام البريد (CMD 1015 / SUB 1 - REQ_INIT_MAILDATA) للتبويبات المحددة (افتراضياً: setType = 4).
  2. استخراج معرفات الرسائل (midArray) غير المقفلة (isLock == 0).
  3. إذا لم توجد رسائل -> إنهاء المهمة وتخطيها فوراً.
  4. أمر الجمع التلقائي للجوائز والمكافآت (CMD 1015 / SUB 18 - REQ_GET_EXTRA_OF_MAILS):
       cmd: "1015", subcmd: "18", data: {"version": "1", "midArray": [...], "setType": setType}
  5. انتظار 3 ثوانٍ محاكاةً للإيقاع الطبيعي وحمايةً من الحظر.
  6. أمر حذف الرسائل بعد الجمع (CMD 1015 / SUB 4 - REQ_REMOVE_MAIL):
       cmd: "1015", subcmd: "4", data: {"version": "1", "midArray": [...], "setType": setType}
"""

from __future__ import annotations

import sys
import os
import asyncio
import logging
import random
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


class MailTask(BaseTask):
    """
    مهمة جمع وحذف بريد القلعة التلقائي:
    - فحص الرسائل في التبويبات المحددة (تقارير الموارد والمعارك setType=4 افتراضياً)
    - جمع مكافآت وجوائز البريد دفعة واحدة (1015/18)
    - انتظار 3 ثوانٍ
    - حذف الرسائل غير المقفلة بعد الجمع (1015/4)
    - التخطي التلقائي إذا كان البريد فارغاً
    """
    name = "mail"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})
        raw_set_types = self.config.get("set_types") or self.config.get("setTypes") or [4]
        if isinstance(raw_set_types, (int, str)):
            self.set_types: List[int] = [int(raw_set_types)]
        elif isinstance(raw_set_types, list):
            self.set_types: List[int] = [int(x) for x in raw_set_types if str(x).isdigit()]
        else:
            self.set_types: List[int] = [4]
        if not self.set_types:
            self.set_types = [4]

        self.delete_after_collect: bool = bool(self.config.get("delete_after_collect", True))
        self.wait_seconds: float = float(self.config.get("wait_seconds", 3.0))

    async def run(self) -> TaskResult:
        if not self.is_connected:
            return TaskResult.fail("الاتصال بالسيرفر مقطوع")

        self.log.debug(f"📬 بدء مهمة فحص وجمع بريد القلعة (التبويبات: {self.set_types})...")

        # تهيئة جلسة البريد مع السيرفر أولاً كما في ملفات اللعبة (mailCtrl:REQ_INIT_MAILDATA)
        try:
            await self.conn.query("1015", "1", {"version": "1"}, timeout=6.0)
        except Exception as e:
            self.log.debug(f"تهيئة جلسة البريد 1015/1: {e}")

        total_collected = 0
        total_deleted = 0
        all_processed_mids: List[int] = []

        for set_type in self.set_types:
            if self.is_stopped():
                break

            loop_iteration = 0
            max_loops = 6   # سقف أمان للدورة الواحدة (300 رسالة كحد أقصى) لتفادي سيل الطلبات المكثف
            seen_mids = set()

            while loop_iteration < max_loops:
                if self.is_stopped():
                    break
                loop_iteration += 1

                # 1. استعلام قائمة رسائل التبويب عبر 1015 / 19 (REQ_GET_MORE_LIST) كما في مصادر اللعبة (mailCtrl.lua)
                try:
                    r_list = await self.conn.query("1015", "19", {
                        "setType": int(set_type),
                        "key": "key",
                        "num": 50,
                        "version": "1"
                    }, timeout=8.0)
                except Exception as e:
                    self.log.warning(f"⚠️ تعذر استعلام البريد للتبويب {set_type}: {e}")
                    break

                if not r_list or r_list.get("err") != "0":
                    err_code = r_list.get("err") if r_list else "timeout"
                    self.log.debug(f"استعلام بريد التبويب {set_type} أعاد كود: {err_code}")
                    break

                mail_list = r_list.get("data", {}).get("list", [])
                if not isinstance(mail_list, list) or not mail_list:
                    self.log.debug(f"📭 انتهت جميع رسائل التبويب {set_type} واكتمل تنظيف الصندوق بالكامل.")
                    break

                # تصفية الرسائل غير المقفلة (isLock == 0) والتي لم يسبق معالجتها في هذه الدورة
                unlocked_mids: List[int] = []
                for m in mail_list:
                    if not isinstance(m, dict):
                        continue
                    mid = m.get("mid")
                    is_lock = int(m.get("isLock", 0))
                    if mid is not None and is_lock == 0:
                        try:
                            m_int = int(mid)
                            if m_int not in seen_mids:
                                unlocked_mids.append(m_int)
                        except (ValueError, TypeError):
                            pass

                if not unlocked_mids:
                    self.log.debug(f"📭 لا توجد رسائل جديدة غير مقفلة في التبويب {set_type} (تم الانتهاء).")
                    break

                self.log.info(f"📬 [دفعة #{loop_iteration}] تم العثور على {len(unlocked_mids)} رسالة غير مقفلة في التبويب {set_type}...")

                # تقسيم القائمة إلى دفعات لتجنب ضخامة الحزمة على السيرفر (أقصى دفعة: 50 رسالة)
                chunk_size = 50
                for i in range(0, len(unlocked_mids), chunk_size):
                    if self.is_stopped():
                        break

                    batch_mids = unlocked_mids[i:i + chunk_size]
                    for m_id in batch_mids:
                        seen_mids.add(m_id)

                    # 2. أمر جمع الجوائز والمكافآت (1015 / 18)
                    self.log.info(f"🎁 إرسال أمر جمع مكافآت {len(batch_mids)} رسالة (1015/18)...")
                    try:
                        r_collect = await self.conn.query("1015", "18", {
                            "version": "1",
                            "midArray": batch_mids,
                            "setType": int(set_type)
                        }, timeout=6.0)

                        if r_collect and r_collect.get("err") in ("0", "6"):
                            # كود 0: نجاح الجمع | كود 6: مجمعة مسبقاً أو لا توجد مرفقات
                            total_collected += len(batch_mids)
                            all_processed_mids.extend(batch_mids)
                        else:
                            err = r_collect.get("err") if r_collect else "timeout"
                            self.log.warning(f"⚠️ رد أمر جمع المكافآت (كود {err})")
                    except Exception as e:
                        self.log.warning(f"⚠️ خطأ أثناء إرسال أمر جمع المكافآت 1015/18: {e}")

                    # 3. مهلة الانتظار بين الجمع والحذف (محاكاة طبيعية للبشر ضد الحظر)
                    if self.delete_after_collect:
                        wait_time = round(random.uniform(2.2, 3.8), 2)
                        self.log.info(f"⏳ انتظار {wait_time} ثوانٍ قبل تنفيذ أمر حذف الرسائل المجمعة...")
                        await asyncio.sleep(wait_time)

                        # 4. أمر حذف الرسائل بعد الجمع (1015 / 4)
                        self.log.info(f"🗑️ إرسال أمر حذف {len(batch_mids)} رسالة بعد الجمع (1015/4)...")
                        try:
                            r_delete = await self.conn.query("1015", "4", {
                                "version": "1",
                                "midArray": batch_mids,
                                "setType": int(set_type)
                            }, timeout=6.0)

                            if r_delete and r_delete.get("err") in ("0", "6"):
                                total_deleted += len(batch_mids)
                            else:
                                err_del = r_delete.get("err") if r_delete else "timeout"
                                self.log.debug(f"رد أمر الحذف 1015/4: كود {err_del}")
                        except Exception as e:
                            self.log.warning(f"⚠️ خطأ أثناء حذف الرسائل 1015/4: {e}")

                # استراحة طبيعية عشوائية قبل تكرار الاستعلام للتحقق إن بقيت رسائل أخرى
                await asyncio.sleep(round(random.uniform(1.4, 2.6), 2))

        if not all_processed_mids:
            return TaskResult.ok("📭 صندوق البريد فارغ، لا توجد رسائل للمعالجة.")

        return TaskResult.ok(
            f"✅ تم جمع وحذف كافة رسائل البريد بنجاح ({len(all_processed_mids)} رسالة)",
            total_processed=len(all_processed_mids),
            total_collected=total_collected,
            total_deleted=total_deleted
        )


if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(description="تشغيل مهمة جمع وحذف البريد تجريبياً")
    parser.add_argument("--email", required=True, help="البريد الإلكتروني للقلعة")
    parser.add_argument("--set-type", type=int, default=4, help="رقم التبويب (افتراضي: 4)")
    args = parser.parse_args()

    async def _test():
        sm = SessionManager()
        acc = sm.get_or_login(args.email)
        if not acc:
            print("❌ الحساب غير موجود في الكاش!")
            return
        conn = GameConnection(acc)
        if not await conn.connect():
            print("❌ فشل الاتصال!")
            return
        task = MailTask(conn, {"set_types": [args.set_type], "delete_after_collect": True, "wait_seconds": 3.0})
        res = await task.run()
        print(f"النتيجة: {res.message}")
        await conn.close()

    asyncio.run(_test())
