# -*- coding: utf-8 -*-
"""
core/session_manager.py — إدارة جلسات الحسابات
═══════════════════════════════════════════════════

يقرأ ويحفظ ويجدد جلسات الحسابات من session_cache.json
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import threading
import time
from typing import Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from game_client import AccountSession
import onemt_auth

log = logging.getLogger("session_manager")

_ROOT       = os.path.dirname(os.path.dirname(__file__))
CACHE_FILE  = os.path.join(_ROOT, "session_cache.json")
_SESSION_LOCK = threading.Lock()


class SessionManager:
    """يُدير جلسات الحسابات (قراءة / حفظ / تجديد) مع حماية ضد التلف وتداخل العمليات."""

    def __init__(self, cache_path: str = CACHE_FILE):
        self.cache_path = cache_path
        self.backup_path = cache_path + ".bak"
        self._cache: dict = {}

    def _read_raw(self, filepath: str) -> Optional[dict]:
        """محاولة قراءة ملف JSON مع إعادة المحاولة لتجنب التعارض الزمني المؤقت."""
        for attempt in range(3):
            try:
                if not os.path.exists(filepath):
                    return None
                if os.path.getsize(filepath) == 0:
                    time.sleep(0.05)
                    continue
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except (json.JSONDecodeError, PermissionError, OSError) as ex:
                log.debug(f"محاولة قراءة مؤقتة غير مكتملة لـ {filepath} (#{attempt+1}): {ex}")
                time.sleep(0.05)
            except Exception as e:
                log.warning(f"خطأ غير متوقع أثناء قراءة {filepath}: {e}")
                break
        return None

    # ── قراءة الجلسات ─────────────────────────────────────────────

    def load(self) -> Dict[str, AccountSession]:
        """يقرأ ملف الجلسات بأمان ويعيد قاموساً {email: AccountSession}."""
        with _SESSION_LOCK:
            data = self._read_raw(self.cache_path)
            if data is None and os.path.exists(self.backup_path):
                log.warning(f"⚠️ محاولة استعادة الجلسات من النسخة الاحتياطية {self.backup_path}...")
                data = self._read_raw(self.backup_path)

            if data is not None:
                self._cache = data
            elif not os.path.exists(self.cache_path):
                self._cache = {"accounts": {}}
            else:
                # الملف موجود لكن تعذرت قراءته — لا نصفر الذاكرة تجنباً لمسح البيانات
                log.error(f"❌ تعذرت قراءة {self.cache_path} بعد عدة محاولات! سيتم الاحتفاظ بالحالة السابقة.")

            result = {}
            for email, info in self._cache.get('accounts', {}).items():
                if isinstance(info, dict):
                    result[email] = AccountSession(
                        email      = email,
                        user_id    = str(info.get('userId', '')),
                        session_id = str(info.get('sessionId', ''))
                    )
            return result

    def get_all(self) -> List[AccountSession]:
        return list(self.load().values())

    # ── حفظ جلسة جديدة بشكل ذري (Atomic Write) ──────────────────────

    def save_session(self, email: str, user_id: str, session_id: str, source: str = "login"):
        """حفظ جلسة بشكل ذري لمنع تلف الملف وفقدان بيانات الحسابات عند التعارض أو انقطاع الطاقة."""
        with _SESSION_LOCK:
            existing = self._read_raw(self.cache_path)
            if existing is not None:
                self._cache = existing
            elif not os.path.exists(self.cache_path):
                self._cache = {"accounts": {}}
            else:
                # الملف موجود ولكنه قيد القراءة، نحاول النسخة الاحتياطية
                bak = self._read_raw(self.backup_path)
                if bak is not None:
                    self._cache = bak
                elif not self._cache.get("accounts"):
                    self._cache = {"accounts": {}}

            self._cache.setdefault('accounts', {})[email] = {
                "userId":    str(user_id),
                "sessionId": str(session_id),
                "timestamp": time.time(),
                "source":    source
            }

            tmp_path = self.cache_path + f".tmp.{os.getpid()}.{threading.get_ident()}"
            try:
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(self._cache, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                # إنشاء نسخة احتياطية أولاً إذا كان الملف الحالي سليماً
                if os.path.exists(self.cache_path) and os.path.getsize(self.cache_path) > 0:
                    try:
                        shutil.copy2(self.cache_path, self.backup_path)
                    except Exception:
                        pass

                # الاستبدال الذري (Atomic rename)
                os.replace(tmp_path, self.cache_path)
                log.info(f"✅ تم حفظ وتأمين جلسة {email} ذرياً بنجاح.")
            except Exception as e:
                log.error(f"❌ فشل حفظ جلسة {email} في {self.cache_path}: {e}")
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                raise

    # ── تسجيل دخول وحفظ ───────────────────────────────────────────

    def login_and_save(self, email: str, password: str) -> Optional[AccountSession]:
        """تسجيل دخول ببريد وكلمة مرور وحفظ الجلسة."""
        res = onemt_auth.sdk_login(email, password)
        if not res.get('success'):
            log.error(f"❌ فشل تسجيل الدخول لـ {email}: {res.get('error_msg')}")
            return None
        uid = str(res['userId'])
        sid = str(res['sessionId'])
        self.save_session(email, uid, sid, source="sdk_login")
        return AccountSession(email=email, user_id=uid, session_id=sid)
