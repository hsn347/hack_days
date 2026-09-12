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
import sys
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


class SessionManager:
    """يُدير جلسات الحسابات (قراءة / حفظ / تجديد)."""

    def __init__(self, cache_path: str = CACHE_FILE):
        self.cache_path = cache_path
        self._cache: dict = {}

    # ── قراءة الجلسات ─────────────────────────────────────────────

    def load(self) -> Dict[str, AccountSession]:
        """يقرأ ملف الجلسات ويعيد قاموساً {email: AccountSession}."""
        if not os.path.exists(self.cache_path):
            return {}
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                self._cache = json.load(f)
        except Exception as e:
            log.error(f"خطأ في قراءة session_cache: {e}")
            return {}

        result = {}
        for email, info in self._cache.get('accounts', {}).items():
            result[email] = AccountSession(
                email      = email,
                user_id    = info.get('userId', ''),
                session_id = info.get('sessionId', '')
            )
        log.info(f"📋 تم تحميل {len(result)} حساب من session_cache.json")
        return result

    def get_all(self) -> List[AccountSession]:
        return list(self.load().values())

    # ── حفظ جلسة جديدة ────────────────────────────────────────────

    def save_session(self, email: str, user_id: str, session_id: str, source: str = "login"):
        if not os.path.exists(self.cache_path):
            self._cache = {"accounts": {}}
        else:
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {"accounts": {}}

        self._cache.setdefault('accounts', {})[email] = {
            "userId":    user_id,
            "sessionId": session_id,
            "timestamp": time.time(),
            "source":    source
        }
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(self._cache, f, indent=2, ensure_ascii=False)
        log.info(f"✅ تم حفظ جلسة {email}")

    # ── تسجيل دخول وحفظ ───────────────────────────────────────────

    def login_and_save(self, email: str, password: str) -> Optional[AccountSession]:
        """تسجيل دخول ببريد وكلمة مرور وحفظ الجلسة."""
        res = onemt_auth.sdk_login(email, password)
        if not res.get('success'):
            log.error(f"❌ فشل تسجيل الدخول لـ {email}: {res.get('error_msg')}")
            return None
        uid = res['userId']
        sid = res['sessionId']
        self.save_session(email, uid, sid, source="sdk_login")
        return AccountSession(email=email, user_id=uid, session_id=sid)
