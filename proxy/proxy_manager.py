# -*- coding: utf-8 -*-
"""
core/proxy_manager.py — مدير بروكسيات SOCKS5 مع كاش دائم ونظام منع التسريب الصارم
══════════════════════════════════════════════════════════════════════════════════════
- كاش محلي دائم (Permanent Cache): صفر استهلاك لـ Webshare API أثناء التشغيل اليومي.
- حظر التسريب الصارم (Strict Anti-Leak): لا يسمح بالاتصال المباشر إطلاقاً عند تفعيل البروكسي.
- توحيد IP قلاع نفس المستخدم (User-Centric Grouping) لتبدو كشبكة منزلية طبيعية.
- توزيع متوازن ومتساوٍ للحمولة (Least-Loaded Balancing) على جميع الـ IPs.
- دعم الفحص المباشر للبروكسي من لوحة التحكم (Live Proxy Health Test).
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sqlite3
import threading
import time
import urllib.request
from typing import Any, Dict, List, Optional

log = logging.getLogger("proxy_manager")

WEBSHARE_API_KEY = os.environ.get("WEBSHARE_API_KEY", "2jvvi0xryjubgg224ub15mrk7sdb1y9g5zp7x5mw")
WEBSHARE_API_URL = "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=100"

_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_DIR)
_CACHE_FILE = os.path.join(_DIR, "webshare_proxies.json")
_USER_BINDINGS_FILE = os.path.join(_DIR, "user_proxy_bindings.json")
_DB_PATH = os.path.join(_ROOT, "database", "castles.db")

_proxies: List[Dict[str, Any]] = []
_user_bindings: Dict[str, str] = {}    # {user_key: proxy_url}
_castle_bindings: Dict[str, str] = {}  # {email: proxy_url}
_manager_lock = threading.Lock()
_lock = _manager_lock
_proxy_enabled: bool = True
_cached_server_ip: Optional[str] = None


def get_server_public_ip() -> str:
    """استرجاع IP السيرفر الحقيقي العام وتخزينه في الذاكرة لتجنب أي تأخير."""
    global _cached_server_ip
    if _cached_server_ip:
        return _cached_server_ip
    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "EmpireBot/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            _cached_server_ip = resp.read().decode("utf-8").strip()
    except Exception:
        _cached_server_ip = "187.7.79.122"
    return _cached_server_ip or "187.7.79.122"


def get_network_mode() -> str:
    """استرجاع نمط الاتصال: 'socks5' (افتراضي) أو 'direct' (IP السيرفر المباشر)."""
    try:
        from core.database import get_system_setting
        val = get_system_setting("network_mode", default="socks5")
        if val in ("direct", "socks5"):
            return val
    except Exception:
        pass
    return "socks5" if _proxy_enabled else "direct"


def set_network_mode(mode: str) -> str:
    """تحديد نمط الاتصال وحفظه في قاعدة البيانات."""
    global _proxy_enabled
    target = "direct" if mode == "direct" else "socks5"
    try:
        from core.database import set_system_setting
        set_system_setting("network_mode", target)
    except Exception as e:
        log.warning(f"[ProxyMgr] فشل حفظ نمط الشبكة في قاعدة البيانات: {e}")

    _proxy_enabled = (target == "socks5")
    if target == "direct":
        log.warning("[ProxyMgr] 🌐 تم تفعيل نمط الاتصال المباشر (Direct Server IP) — البروكسيات معطلة.")
    else:
        log.info("[ProxyMgr] 🛡️ تم تفعيل نمط البروكسيات (SOCKS5 Proxies).")
    return target


def is_proxy_enabled() -> bool:
    return get_network_mode() == "socks5"


def disable_proxy():
    set_network_mode("direct")


def enable_proxy():
    set_network_mode("socks5")


def _fetch_from_api() -> List[Dict[str, Any]]:
    if not WEBSHARE_API_KEY:
        log.warning("[ProxyMgr] لم يتم تعيين مفتاح Webshare API!")
        return []

    try:
        req = urllib.request.Request(
            WEBSHARE_API_URL,
            headers={
                "Authorization": f"Token {WEBSHARE_API_KEY}",
                "User-Agent": "EmpireBot-ProxyManager/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            log.info(f"[ProxyMgr] ✓ تم جلب {len(results)} بروكسي بنجاح من Webshare API")
            return results
    except Exception as e:
        log.warning(f"[ProxyMgr] فشل الاتصال بـ Webshare API: {e}")
        return []


def _load_cache() -> List[Dict[str, Any]]:
    try:
        target = _CACHE_FILE
        if not os.path.exists(target):
            fallback = os.path.join(_ROOT, "webshare_proxies.json")
            if os.path.exists(fallback):
                target = fallback
        if os.path.exists(target):
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                proxies = data.get("proxies", [])
                if proxies:
                    return proxies
    except Exception as e:
        log.debug(f"[ProxyMgr] تعذرت قراءة الكاش المحلي: {e}")
    return []


def _save_cache(proxies: List[Dict[str, Any]]):
    try:
        payload = {
            "saved_at": time.time(),
            "count": len(proxies),
            "proxies": proxies
        }
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"[ProxyMgr] فشل حفظ كاش البروكسي: {e}")


def _load_bindings():
    global _user_bindings, _castle_bindings
    target = _USER_BINDINGS_FILE
    if not os.path.exists(target):
        fallback = os.path.join(_ROOT, "user_proxy_bindings.json")
        if os.path.exists(fallback):
            target = fallback
    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                _user_bindings = data.get("users", {})
                _castle_bindings = data.get("castles", {})
        except Exception as e:
            log.warning(f"[ProxyMgr] فشل قراءة ملف الارتباطات: {e}")


def _save_bindings():
    try:
        payload = {
            "users": _user_bindings,
            "castles": _castle_bindings,
            "updated_at": time.time()
        }
        with open(_USER_BINDINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"[ProxyMgr] فشل حفظ الارتباطات: {e}")


def _format_proxy_url(item: Dict[str, Any]) -> Optional[str]:
    host = item.get("proxy_address", "")
    port = item.get("socks5_port") or item.get("port", 0)
    user = item.get("username", "")
    pwd  = item.get("password", "")
    if not host or not port:
        return None
    if user and pwd:
        return f"socks5://{user}:{pwd}@{host}:{port}"
    return f"socks5://{host}:{port}"


def _ensure_loaded(force: bool = False):
    global _proxies
    if not force and _proxies:
        return

    if not force:
        cached = _load_cache()
        if cached:
            _proxies = cached
            return

    fresh = _fetch_from_api()
    if fresh:
        _proxies = fresh
        _save_cache(fresh)
    else:
        _proxies = _load_cache() or []
        if not _proxies:
            log.error("[ProxyMgr] لا توجد أي بروكسيات متاحة!")


def _resolve_user_id_for_email(email: str) -> Optional[str]:
    clean_email = (email or "").strip().lower()
    if not clean_email or not os.path.exists(_DB_PATH):
        return None

    try:
        conn = sqlite3.connect(_DB_PATH, timeout=3.0)
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM castle_states WHERE lower(email) = ? LIMIT 1", (clean_email,))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip()
    except Exception:
        pass
    return None


def get_proxy_for_account(account_key: str, user_id: Optional[str] = None) -> Optional[str]:
    """تخصيص بروكسي دائم مع توحيد قلاع نفس المستخدم والتوزيع المتوازن للأقل حملاً."""
    if not is_proxy_enabled():
        return None

    clean_email = (account_key or "").strip().lower()
    if not clean_email:
        return None

    with _manager_lock:
        _ensure_loaded()
        if not _proxies:
            return None

        _load_bindings()

        # 1. إذا كانت القلعة مرتبطة مسبقاً
        if clean_email in _castle_bindings:
            return _castle_bindings[clean_email]

        # 2. استعلام صاحب القلعة
        effective_user_id = user_id or _resolve_user_id_for_email(clean_email)

        # 3. توحيد قلاع نفس المستخدم
        if effective_user_id and effective_user_id in _user_bindings:
            user_proxy = _user_bindings[effective_user_id]
            _castle_bindings[clean_email] = user_proxy
            _save_bindings()
            log.info(f"[ProxyMgr] 🔗 تم ضم القلعة {clean_email} لبروكسي المستخدم {effective_user_id} المشترك.")
            return user_proxy

        # 4. توزيع متوازن للمستخدم الجديد على البروكسي الأقل حملاً
        proxy_urls = []
        counts: Dict[str, int] = {}
        for p in _proxies:
            url = _format_proxy_url(p)
            if url:
                proxy_urls.append(url)
                counts[url] = 0

        if not proxy_urls:
            return None

        for bound_url in _castle_bindings.values():
            if bound_url in counts:
                counts[bound_url] += 1

        least_loaded_proxy = min(proxy_urls, key=lambda u: counts.get(u, 0))

        _castle_bindings[clean_email] = least_loaded_proxy
        if effective_user_id:
            _user_bindings[effective_user_id] = least_loaded_proxy

        _save_bindings()
        new_count = counts.get(least_loaded_proxy, 0) + 1
        log.info(f"[ProxyMgr] ⚖️ [توزيع متوازن] ربط القلعة {clean_email} (مستخدم: {effective_user_id or 'فردي'}) بالبروكسي (الحمولة: {new_count} قلعة).")
        return least_loaded_proxy


def get_proxy_ip_for_email(email: str) -> str:
    """استرجاع عنوان الـ IP المخصص للقلعة (أو IP السيرفر إذا كان النمط مباشر)."""
    if not is_proxy_enabled():
        return get_server_public_ip()
    clean_email = (email or "").strip().lower()
    with _manager_lock:
        _load_bindings()
        url = _castle_bindings.get(clean_email, "")
        if not url:
            return ""
        try:
            return url.split("@")[-1].split(":")[0]
        except Exception:
            return ""


def remove_castle_proxy(email: str) -> bool:
    """إزالة ارتباط البروكسي للقلعة المحذوفة وتحديث ملف الإعدادات الدائم."""
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return False
    with _manager_lock:
        if not _castle_bindings:
            _load_bindings()
        if clean_email in _castle_bindings:
            del _castle_bindings[clean_email]
            _save_bindings()
            log.info(f"[ProxyMgr] 🗑️ تم حذف ارتباط البروكسي للقلعة: {clean_email}")
            return True
        else:
            _load_bindings()
            if clean_email in _castle_bindings:
                del _castle_bindings[clean_email]
                _save_bindings()
                log.info(f"[ProxyMgr] 🗑️ تم حذف ارتباط البروكسي للقلعة: {clean_email}")
                return True
    return False


def set_castle_proxy(email: str, proxy_url: str) -> None:
    """ربط قلعة ببروكسي محدد وتحديث الارتباطات."""
    clean_email = (email or "").strip().lower()
    with _manager_lock:
        _castle_bindings[clean_email] = proxy_url


def get_castle_proxy(email: str) -> Optional[str]:
    """استرجاع رابط البروكسي المرتبط بالقلعة."""
    clean_email = (email or "").strip().lower()
    with _manager_lock:
        return _castle_bindings.get(clean_email)


def remove_user_proxy_bindings(user_id: str, castle_emails: Optional[List[str]] = None) -> None:
    """إزالة ارتباطات البروكسي لمستخدم وجميع قلاعه المحذوفة وحفظ التغييرات."""
    clean_uid = (user_id or "").strip()
    with _manager_lock:
        if not _user_bindings and not _castle_bindings:
            _load_bindings()
        changed = False
        if clean_uid and clean_uid in _user_bindings:
            del _user_bindings[clean_uid]
            changed = True
        if castle_emails:
            for em in castle_emails:
                clean_em = (em or "").strip().lower()
                if clean_em in _castle_bindings:
                    del _castle_bindings[clean_em]
                    changed = True
        if changed:
            _save_bindings()
            log.info(f"[ProxyMgr] 🗑️ تم حذف ارتباطات البروكسي للمستخدم {clean_uid}")


async def test_single_proxy(proxy_url: str) -> Dict[str, Any]:
    """فحص نفق SOCKS5 لعنوان معين وحساب الـ Ping والتأكد من نجاح الاتصال."""
    if not proxy_url:
        return {"ok": False, "msg": "عنوان البروكسي فارغ"}

    t0 = time.time()
    try:
        from python_socks.async_.asyncio import Proxy
        import asyncio
        proxy = Proxy.from_url(proxy_url)
        # محاولة فتح اتصال نفق باتجاه سيرفر الدخول للعبة
        sock = await asyncio.wait_for(
            proxy.connect(dest_host="119.8.212.255", dest_port=10000),
            timeout=8
        )
        sock.close()
        ping_ms = int((time.time() - t0) * 1000)
        return {"ok": True, "ping": ping_ms, "msg": "متصل ومؤمن بنجاح"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def reload_proxies() -> int:
    with _manager_lock:
        _ensure_loaded(force=True)
        return len(_proxies)


def proxy_status() -> Dict[str, Any]:
    """تقرير شفاف يُظهر تفاصيل الـ IPs والقلاع المربوطة لعرضها في صفحة AdminProxies.tsx."""
    with _manager_lock:
        _ensure_loaded()
        _load_bindings()

        proxies_list = []
        for p in _proxies:
            url = _format_proxy_url(p)
            if url:
                host = p.get("proxy_address", "")
                port = p.get("socks5_port") or p.get("port")
                assigned = [em for em, u in _castle_bindings.items() if u == url]
                users = [uid for uid, u in _user_bindings.items() if u == url]
                proxies_list.append({
                    "ip": host,
                    "port": port,
                    "country": p.get("country_code", "??"),
                    "assigned_castles": assigned,
                    "assigned_users": users,
                    "full_url": url
                })

        return {
            "enabled": is_proxy_enabled(),
            "network_mode": get_network_mode(),
            "server_ip": get_server_public_ip(),
            "total_proxies": len(_proxies),
            "total_bound_castles": len(_castle_bindings),
            "total_bound_users": len(_user_bindings),
            "proxies_list": proxies_list
        }
