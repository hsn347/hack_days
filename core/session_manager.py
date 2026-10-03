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

    def remove_session(self, email: str):
        """حذف جلسة حساب معينة بأمان وذرياً عند حذف القلعة."""
        if not email:
            return
        clean_target = email.strip().lower()
        with _SESSION_LOCK:
            existing = self._read_raw(self.cache_path)
            if existing is None:
                return
            accounts = existing.get("accounts", {})
            matched = [k for k in accounts if k.strip().lower() == clean_target]
            if not matched:
                return
            for k in matched:
                accounts.pop(k, None)
            existing["accounts"] = accounts

            tmp_path = self.cache_path + f".tmp.{os.getpid()}.{threading.get_ident()}"
            try:
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.cache_path)
                log.info(f"🗑️ تم حذف جلسة {clean_target} من {self.cache_path}")
            except Exception as e:
                log.warning(f"⚠️ فشل حذف جلسة {clean_target} من {self.cache_path}: {e}")
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

    # ── تسجيل دخول وحفظ ───────────────────────────────────────────

    _LAST_AUTH_ERRORS: Dict[str, str] = {}

    @classmethod
    def get_last_error(cls, email: str) -> Optional[str]:
        return cls._LAST_AUTH_ERRORS.get(email.strip().lower())

    def login_and_save(self, email: str, password: str) -> Optional[AccountSession]:
        """تسجيل دخول ببريد وكلمة مرور وحفظ الجلسة مع تصنيف دقيق للأخطاء."""
        clean_email = email.strip().lower()
        res = onemt_auth.sdk_login(email, password)
        if not res.get('success'):
            err_code = str(res.get('error_code', ''))
            raw_err  = str(res.get('error_msg', ''))
            
            if err_code == 'BUSINESS_ACCOUNT_PASSWORD_LIMIT' or 'كلمة السر خاطئة' in raw_err:
                msg = "❌ كلمة المرور غير صحيحة (تأكد من كتابتها بدقة)"
            elif err_code == 'BUSINESS_ACCOUNT_FORBIDDEN' or 'إيقاف فاعلية الحساب' in raw_err:
                msg = "🛑 تم إيقاف الحساب لمدة ساعة من اللعبة بسبب تكرار كلمة المرور 5 مرات"
            elif err_code in ('INVALID_USER', 'USER_NOT_EXIST', 'ACCOUNT_NOT_EXIST') or 'غير موجود' in raw_err:
                msg = "❌ البريد الإلكتروني غير مسجل أو غير صحيح"
            elif raw_err:
                msg = f"❌ فشل تسجيل الدخول: {raw_err}"
            else:
                msg = "❌ خطأ في البريد أو كلمة المرور"

            self._LAST_AUTH_ERRORS[clean_email] = msg
            log.error(f"❌ فشل تسجيل الدخول لـ {email}: {msg}")
            return None

        # نجاح تسجيل الدخول — مسح أي خطأ سابق
        self._LAST_AUTH_ERRORS.pop(clean_email, None)
        uid = str(res['userId'])
        sid = str(res['sessionId'])
        self.save_session(email, uid, sid, source="sdk_login")
        return AccountSession(email=email, user_id=uid, session_id=sid)

    def _fetch_password_from_db(self, castle_id: Optional[str] = None, email: Optional[str] = None) -> Optional[str]:
        """استرجاع كلمة المرور المحفوظة للقلعة من قاعدة البيانات المحلية SQLite."""
        try:
            from core.database import get_castle_password, get_castle
            if castle_id:
                pwd = get_castle_password(castle_id)
                if pwd:
                    return pwd
            if email:
                c = get_castle(email)
                if c and c.get("password"):
                    return str(c["password"]).strip()
        except Exception as e:
            log.debug(f"تعذر جلب كلمة المرور من SQLite: {e}")
        return None

    def get_or_login(
        self,
        email: str,
        password: Optional[str] = None,
        user_id: Optional[str] = None,
        castle_id: Optional[str] = None
    ) -> Optional[AccountSession]:
        """
        1. البحث في session_cache.json أولاً.
        2. إذا لم تكن موجودة، يتم جلب كلمة المرور (سواء الممررة أو من SQLite).
        3. تسجيل الدخول وحفظ الجلسة في session_cache.json تلقائياً ثم إعادتها.
        """
        clean_email = email.strip().lower()
        # 1. البحث في الكاش أولاً
        sessions = self.load()
        if email in sessions:
            return sessions[email]

        # 2. غير موجودة في الكاش — جلب كلمة المرور من SQLite
        pwd = password
        if not pwd:
            pwd = self._fetch_password_from_db(castle_id=castle_id, email=email)

        # 3. تسجيل الدخول وحفظ الجلسة في الكاش
        if pwd:
            log.info(f"🔑 [{email}] لم يتم العثور على الجلسة في الكاش — جاري تسجيل الدخول وحفظها في session_cache.json تلقائياً...")
            return self.login_and_save(email, pwd)

        msg = "❌ لا توجد كلمة مرور مسجلة للقلعة لتسجيل الدخول"
        self._LAST_AUTH_ERRORS[clean_email] = msg
        log.warning(f"⚠️ [{email}] {msg}")
        return None

    def refresh_session(
        self,
        email: str,
        password: Optional[str] = None,
        user_id: Optional[str] = None,
        castle_id: Optional[str] = None
    ) -> Optional[AccountSession]:
        """تجديد إجباري للجلسة بكلمة المرور وتحديث session_cache.json."""
        clean_email = email.strip().lower()
        pwd = password
        if not pwd:
            pwd = self._fetch_password_from_db(castle_id=castle_id, email=email)

        if pwd:
            log.info(f"🔄 [{email}] تجديد الجلسة بكلمة المرور وتحديث session_cache.json...")
            return self.login_and_save(email, pwd)

        msg = "❌ لا توجد كلمة مرور مسجلة لتجديد الجلسة"
        self._LAST_AUTH_ERRORS[clean_email] = msg
        return None


def get_last_auth_error(email: str) -> Optional[str]:
    """دالة مساعدة عامة لاستخراج آخر خطأ مصادقة للحساب."""
    return SessionManager.get_last_error(email)


