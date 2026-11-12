# -*- coding: utf-8 -*-
"""
test_check_target.py — أداة بسيطة لتجربة check_target_busy_or_marched بشكل منفصل
═══════════════════════════════════════════════════════════════════════════════

أمثلة التشغيل:
  1) تمرير المعاملات عبر سطر الأوامر:
     python test_check_target.py -e "shook124@gmail.com" --id "380-269-5-1-3205" --tx 380 --ty 269
     python test_check_target.py  --target-id "391-270-5-1-3205" --tx 391 --ty 270
     python test_check_target.py -e "user@gmail.com" --id "512-512-5-1" -x 512 -y 512 -k 251
     python test_check_target.py --id "400-400-26-0" -x 400 -y 400 --stronghold --spy

  2) تشغيل تفاعلي (يطلب منك إدخال المعاملات يدوياً):
     python test_check_target.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.session_manager import SessionManager
from game_client import GameConnection
from tasks.base_task import BaseTask, TaskResult


class _TargetCheckTask(BaseTask):
    """كلاس خفيف يرث من BaseTask فقط لاستدعاء check_target_busy_or_marched."""
    name = "test_check_target"

    async def run(self) -> TaskResult:
        return TaskResult.ok()


def _prompt_missing_params(args: argparse.Namespace) -> tuple[str, int, int, int, bool]:
    """استكمال أي معاملات ناقصة تفاعلياً إذا لم تُمرر عبر سطر الأوامر."""
    asked_interactive = False

    target_id = args.target_id
    if not target_id:
        target_id = input("أدخل target_id (مثل 512-512-5-1): ").strip()
        asked_interactive = True

    tx = args.tx
    if tx is None:
        tx = int(input("أدخل tx (إحداثي X): ").strip())
        asked_interactive = True

    ty = args.ty
    if ty is None:
        ty = int(input("أدخل ty (إحداثي Y): ").strip())
        asked_interactive = True

    kingdom_id = args.kingdom_id
    is_stronghold = args.is_stronghold
    if asked_interactive:
        if kingdom_id == 0:
            raw_kid = input("أدخل kingdom_id (اتركه فارغاً لاستخدام مملكة الحساب): ").strip()
            if raw_kid:
                kingdom_id = int(raw_kid)
        if not is_stronghold:
            raw_sh = input("هل الهدف معقل is_stronghold؟ (y/N): ").strip().lower()
            is_stronghold = raw_sh in ("y", "yes", "1", "true", "نعم")

    return target_id, tx, ty, kingdom_id, is_stronghold


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="تجربة الدالة check_target_busy_or_marched بشكل منفصل"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب (افتراضي: أول حساب مسجل)")
    parser.add_argument("--target-id", "--id", "-i", dest="target_id", help="معرف الهدف target_id")
    parser.add_argument("--tx", "-x", type=int, help="إحداثي X للهدف")
    parser.add_argument("--ty", "-y", type=int, help="إحداثي Y للهدف")
    parser.add_argument(
        "--kingdom-id", "-k",
        type=int,
        default=0,
        help="رقم المملكة (افتراضي: 0 ليتم جلبه من اتصال الحساب)"
    )
    parser.add_argument(
        "--stronghold", "--is-stronghold",
        dest="is_stronghold",
        action="store_true",
        help="تحديد الهدف كمعقل (is_stronghold=True)"
    )
    parser.add_argument("--spy", action="store_true", help="تفعيل طباعة حزم الشبكة (spy_mode)")
    parser.add_argument("--debug", action="store_true", help="عرض سجلات DEBUG التفصيلية")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    target_id, tx, ty, kingdom_id, is_stronghold = _prompt_missing_params(args)

    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        print("❌ لا توجد حسابات مسجلة في session_cache.json!")
        return

    target_email = args.email.strip().lower() if args.email else next(iter(accounts.keys()))
    acc = accounts.get(target_email)
    if not acc:
        print(f"❌ الحساب {target_email} غير موجود في session_cache.json!")
        return

    conn = GameConnection(acc)
    if args.spy:
        conn.spy_mode = True

    print(f"🔌 جاري الاتصال بالحساب: {target_email} ...")
    if not await conn.connect():
        print("❌ فشل الاتصال بالسيرفر!")
        return

    try:
        for _ in range(10):
            await asyncio.sleep(0.5)
            if len(conn.init_data) > 0:
                break

        print(
            f"🔍 استدعاء check_target_busy_or_marched("
            f"target_id={target_id!r}, tx={tx}, ty={ty}, "
            f"kingdom_id={kingdom_id}, is_stronghold={is_stronghold}) "
            f"[uid={conn.uid}, conn.kingdom_id={conn.kingdom_id}]"
        )

        task = _TargetCheckTask(conn)
        is_busy, reason, node_data = await task.check_target_busy_or_marched(
            target_id=target_id,
            tx=tx,
            ty=ty,
            kingdom_id=kingdom_id,
            is_stronghold=is_stronghold,
        )

        print("\n════════════════════════════════════════════")
        print(f"is_busy   : {is_busy}")
        print(f"reason    : {reason or '(فارغ — الهدف متاح)'}")
        print("node_data :")
        print(json.dumps(node_data, ensure_ascii=False, indent=2, default=str))
        print("════════════════════════════════════════════\n")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())
