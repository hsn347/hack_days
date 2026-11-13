# -*- coding: utf-8 -*-
"""
core/proxy_manager.py — مدير بروكسيات SOCKS5 الذكي
══════════════════════════════════════════════════════════════════════════════════════
- دعم البروكسيات السكنية المدفوعة (Static Residential) كخيار أساسي ومعتمد.
- دعم البروكسيات المجانية (Free Datacenter) كخيار احتياطي (Fallback).
- كاش محلي دائم لكل فئة (Permanent Caches): استهلاك صفر API أثناء التشغيل اليومي.
- حظر التسريب الصارم (Strict Anti-Leak): لا يسمح بالاتصال المباشر إطلاقاً عند تفعيل أي نمط بروكسي.
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

# ملفات الكاش المنفصلة
_RESIDENTIAL_CACHE_FILE = os.path.join(_DIR, "static_residential_proxies.json")
_FREE_CACHE_FILE = os.path.join(_DIR, "webshare_free_proxies.json")
_CACHE_FILE = os.path.join(_DIR, "webshare_proxies.json")
_USER_BINDINGS_FILE = os.path.join(_DIR, "user_proxy_bindings.json")
_DB_PATH = os.path.join(_ROOT, "database", "castles.db")

# الذاكرة الحية لمجموعات البروكسيات
_residential_proxies: List[Dict[str, Any]] = []
_free_proxies: List[Dict[str, Any]] = []
_proxies: List[Dict[str, Any]] = []  # توافق عكسي للباقة النشطة

# قواميس الارتباطات لكل فئة: {"residential": {...}, "free": {...}}
_user_bindings: Dict[str, Dict[str, str]] = {"residential": {}, "free": {}}
_castle_bindings: Dict[str, Dict[str, str]] = {"residential": {}, "free": {}}

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
    """
    استرجاع نمط الاتصال:
      - 'residential': بروكسيات سكنية ثابتة مدفوعة (Static Residential - أساسي افتراضي)
      - 'free': بروكسيات مجانية (Free Datacenter - احتياطي)
      - 'direct': IP السيرفر المباشر
    """
    try:
        from core.database import get_system_setting
        val = get_system_setting("network_mode", default="residential")
        if val in ("direct", "free", "residential"):
            return val
        if val == "socks5":
            return "residential"
    except Exception:
        pass
    return "residential" if _proxy_enabled else "direct"


def set_network_mode(mode: str) -> str:
    """تحديد نمط الاتصال وحفظه في قاعدة البيانات وتحميل الباقة المطلوبة."""
    global _proxy_enabled
    target = str(mode or "").strip().lower()
    if target not in ("direct", "free", "residential"):
        if target == "socks5":
            target = "residential"
        else:
            target = "residential"

    try:
        from core.database import set_system_setting
        set_system_setting("network_mode", target)
    except Exception as e:
        log.warning(f"[ProxyMgr] فشل حفظ نمط الشبكة في قاعدة البيانات: {e}")

    _proxy_enabled = (target != "direct")

    # إعادة تحميل الباقة النشطة فوراً
    with _manager_lock:
        _ensure_loaded(force=False)
        _sync_active_proxies_legacy()

    if target == "direct":
        log.warning("[ProxyMgr] 🌐 تم تفعيل نمط الاتصال المباشر (Direct Server IP) — البروكسيات معطلة.")
    elif target == "free":
        log.info("[ProxyMgr] 🛡️ تم تفعيل نمط البروكسيات المجانية الاحتياطية (Free Datacenter).")
    else:
        log.info("[ProxyMgr] 🌟 تم تفعيل نمط البروكسيات السكنية المدفوعة المعتمدة (Static Residential).")
    return target


def is_proxy_enabled() -> bool:
    return get_network_mode() in ("residential", "free", "socks5")


def disable_proxy():
    set_network_mode("direct")


def enable_proxy():
    set_network_mode("residential")


def _fetch_from_api() -> List[Dict[str, Any]]:
    """جلب قائمة البروكسيات السكنية من Webshare API."""
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


def _load_pool(pool_name: str) -> List[Dict[str, Any]]:
    """قراءة البروكسيات المخزنة لفئة محددة ('residential' أو 'free')."""
    if pool_name == "free":
        targets = [_FREE_CACHE_FILE, _CACHE_FILE]
    else:
        targets = [_RESIDENTIAL_CACHE_FILE, _CACHE_FILE]

    for target in targets:
        if os.path.exists(target):
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    proxies = data.get("proxies", [])
                    if proxies:
                        return proxies
            except Exception as e:
                log.debug(f"[ProxyMgr] تعذرت قراءة الكاش ({target}): {e}")
    return []


def _save_pool(pool_name: str, proxies: List[Dict[str, Any]]):
    """حفظ قائمة البروكسيات لفئة محددة في ملف الكاش المخصص لها."""
    target = _FREE_CACHE_FILE if pool_name == "free" else _RESIDENTIAL_CACHE_FILE
    try:
        payload = {
            "saved_at": time.time(),
            "count": len(proxies),
            "type": "free_datacenter" if pool_name == "free" else "static_residential",
            "proxies": proxies
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"[ProxyMgr] فشل حفظ كاش البروكسي ({pool_name}): {e}")


def _load_bindings():
    """تحميل ارتباطات القلاع والمستخدمين مع دعم العزل بين المدفوع والمجاني."""
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
                if "residential" in data and isinstance(data["residential"], dict):
                    _user_bindings["residential"] = data["residential"].get("users", {}) or {}
                    _castle_bindings["residential"] = data["residential"].get("castles", {}) or {}
                    _user_bindings["free"] = data.get("free", {}).get("users", {}) or {}
                    _castle_bindings["free"] = data.get("free", {}).get("castles", {}) or {}
                else:
                    # ترحيل البيانات السابقة: وضعها في المجاني وتفريغ السكني لبدء توزيع نقي
                    old_users = data.get("users", {}) or {}
                    old_castles = data.get("castles", {}) or {}
                    _user_bindings["free"] = dict(old_users)
                    _castle_bindings["free"] = dict(old_castles)
                    _user_bindings["residential"] = {}
                    _castle_bindings["residential"] = {}
        except Exception as e:
            log.warning(f"[ProxyMgr] فشل قراءة ملف الارتباطات: {e}")


def _save_bindings():
    """حفظ ارتباطات القلاع والمستخدمين بشكل معزول وآمن."""
    try:
        mode = get_network_mode()
        pool_key = "free" if mode == "free" else "residential"
        payload = {
            "residential": {
                "users": _user_bindings.get("residential", {}),
                "castles": _castle_bindings.get("residential", {}),
            },
            "free": {
                "users": _user_bindings.get("free", {}),
                "castles": _castle_bindings.get("free", {}),
            },
            # توافق عكسي للبرامج التي تقرأ المفاتيح العامة
            "users": _user_bindings.get(pool_key, {}),
            "castles": _castle_bindings.get(pool_key, {}),
            "active_mode": mode,
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
    """التأكد من تحميل كلا الكاشين (السكني المدفوع والمجاني الاحتياطي)."""
    global _residential_proxies, _free_proxies

    # 1. تحميل البروكسيات السكنية المدفوعة
    if force or not _residential_proxies:
        cached_res = _load_pool("residential")
        if cached_res and not force:
            _residential_proxies = cached_res
        else:
            api_res = _fetch_from_api()
            if api_res:
                _residential_proxies = api_res
                _save_pool("residential", api_res)
            elif cached_res:
                _residential_proxies = cached_res

    # 2. تحميل البروكسيات المجانية الاحتياطية
    if force or not _free_proxies:
        _free_proxies = _load_pool("free")


def get_active_proxies() -> List[Dict[str, Any]]:
    """استرجاع قائمة البروكسيات النشطة بحسب النمط المختار مع العودة للبديل إن لزم."""
    _ensure_loaded()
    mode = get_network_mode()
    if mode == "free":
        if _free_proxies:
            return _free_proxies
        return _residential_proxies
    else:  # residential (الأساسي)
        if _residential_proxies:
            return _residential_proxies
        return _free_proxies


def _sync_active_proxies_legacy():
    """مزامنة القائمة العامة _proxies للتوافق مع أي استدعاءات قديمة."""
    global _proxies
    _proxies = get_active_proxies()


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
    """
    تخصيص بروكسي دائم ومستقر يعتمد فهرس البروكسي (proxy_index) المسجل في قاعدة البيانات
    مع توحيد قلاع نفس المستخدم والتوزيع المتوازن، لضمان عدم تغير موقع القلعة حتى عند تجديد البروكسيات.
    """
    if not is_proxy_enabled():
        return None

    clean_email = (account_key or "").strip().lower()
    if not clean_email:
        return None

    with _manager_lock:
        active_proxies = get_active_proxies()
        if not active_proxies:
            log.error("[ProxyMgr] 🛑 لا توجد أي بروكسيات متاحة في الباقة النشطة!")
            return None

        total_proxies = len(active_proxies)
        _load_bindings()
        mode = get_network_mode()
        pool_key = "free" if mode == "free" else "residential"

        c_bindings = _castle_bindings.setdefault(pool_key, {})
        u_bindings = _user_bindings.setdefault(pool_key, {})

        effective_user_id = user_id or _resolve_user_id_for_email(clean_email)

        # ── 1. فحص قاعدة البيانات: هل القلعة تمتلك proxy_index محفوظ مسبقاً؟ ──
        db_proxy_idx: Optional[int] = None
        try:
            from core.database import get_castle_proxy_index
            db_proxy_idx = get_castle_proxy_index(clean_email)
        except Exception as e:
            log.debug(f"[ProxyMgr] تعذرت قراءة proxy_index من قاعدة البيانات: {e}")

        if db_proxy_idx is not None and db_proxy_idx >= 0:
            safe_idx = db_proxy_idx % total_proxies
            selected_url = _format_proxy_url(active_proxies[safe_idx])
            if selected_url:
                c_bindings[clean_email] = selected_url
                if effective_user_id:
                    u_bindings[effective_user_id] = selected_url
                return selected_url

        # ── 2. فحص قلاع نفس المستخدم في قاعدة البيانات: توحيد البروكسي لقلاع نفس المستخدم ──
        if effective_user_id:
            try:
                from core.database import get_user_proxy_index, set_castle_proxy_index
                user_proxy_idx = get_user_proxy_index(effective_user_id)
                if user_proxy_idx is not None and user_proxy_idx >= 0:
                    safe_idx = user_proxy_idx % total_proxies
                    selected_url = _format_proxy_url(active_proxies[safe_idx])
                    if selected_url:
                        set_castle_proxy_index(clean_email, safe_idx)
                        c_bindings[clean_email] = selected_url
                        u_bindings[effective_user_id] = selected_url
                        _save_bindings()
                        log.info(f"[ProxyMgr] 🔗 [قاعدة البيانات] تم ضم القلعة {clean_email} لبروكسي المستخدم {effective_user_id} المشترك (فهرس: {safe_idx}).")
                        return selected_url
            except Exception as e:
                log.debug(f"[ProxyMgr] تعذر استعلام proxy_index للمستخدم: {e}")

        # ── 3. التوافق العكسي: فحص الارتباط المسجل مسبقاً في ملف الـ JSON إن وجد وترقيته لقاعدة البيانات ──
        proxy_urls = [_format_proxy_url(p) for p in active_proxies]
        valid_urls = {u for u in proxy_urls if u}

        if clean_email in c_bindings and c_bindings[clean_email] in valid_urls:
            bound_url = c_bindings[clean_email]
            try:
                matched_idx = proxy_urls.index(bound_url)
                from core.database import set_castle_proxy_index
                set_castle_proxy_index(clean_email, matched_idx)
            except Exception:
                pass
            return bound_url

        # ── 4. تخصيص جديد ذكي: اختيار الفهرس الأقل حمولة وحفظه نهائياً في قاعدة البيانات ──
        counts: Dict[int, int] = {i: 0 for i in range(total_proxies)}
        try:
            from core.database import get_all_castle_proxy_counts
            counts = get_all_castle_proxy_counts(total_proxies)
        except Exception:
            for bound_url in c_bindings.values():
                for i, u in enumerate(proxy_urls):
                    if u == bound_url:
                        counts[i] = counts.get(i, 0) + 1

        least_loaded_idx = min(range(total_proxies), key=lambda i: counts.get(i, 0))
        selected_url = _format_proxy_url(active_proxies[least_loaded_idx])
        if not selected_url:
            return None

        try:
            from core.database import set_castle_proxy_index
            set_castle_proxy_index(clean_email, least_loaded_idx)
        except Exception as e:
            log.warning(f"[ProxyMgr] تعذر حفظ proxy_index للقلعة ({clean_email}): {e}")

        c_bindings[clean_email] = selected_url
        if effective_user_id:
            u_bindings[effective_user_id] = selected_url

        _save_bindings()
        new_count = counts.get(least_loaded_idx, 0) + 1
        log.info(f"[ProxyMgr] ⚖️ [توزيع DB] ربط القلعة {clean_email} بالبروكسي رقم [{least_loaded_idx}] (الحمولة: {new_count} قلعة).")
        return selected_url


def get_proxy_ip_for_email(email: str) -> str:
    """استرجاع عنوان الـ IP المخصص للقلعة في الباقة النشطة (أو IP السيرفر إذا كان النمط مباشر)."""
    if not is_proxy_enabled():
        return get_server_public_ip()
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return ""
    with _manager_lock:
        # فحص قاعدة البيانات أولاً
        try:
            from core.database import get_castle_proxy_index
            db_idx = get_castle_proxy_index(clean_email)
            if db_idx is not None and db_idx >= 0:
                active = get_active_proxies()
                if active:
                    p = active[db_idx % len(active)]
                    ip = p.get("proxy_address", "")
                    if ip:
                        return ip
        except Exception:
            pass

        _load_bindings()
        mode = get_network_mode()
        pool_key = "free" if mode == "free" else "residential"
        url = _castle_bindings.get(pool_key, {}).get(clean_email, "")
        if not url:
            other_key = "residential" if pool_key == "free" else "free"
            url = _castle_bindings.get(other_key, {}).get(clean_email, "")
        if not url:
            return ""
        try:
            return url.split("@")[-1].split(":")[0]
        except Exception:
            return ""


def remove_castle_proxy(email: str) -> bool:
    """إزالة ارتباط البروكسي للقلعة المحذوفة من كلا الباقتين وقاعدة البيانات."""
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return False
    with _manager_lock:
        try:
            from core.database import set_castle_proxy_index
            set_castle_proxy_index(clean_email, -1)
        except Exception:
            pass
        _load_bindings()
        changed = False
        for pool in ("residential", "free"):
            if clean_email in _castle_bindings.get(pool, {}):
                del _castle_bindings[pool][clean_email]
                changed = True
        if changed:
            _save_bindings()
            log.info(f"[ProxyMgr] 🗑️ تم حذف ارتباط البروكسي للقلعة: {clean_email}")
            return True
    return False


def set_castle_proxy(email: str, proxy_url: str) -> None:
    """ربط قلعة ببروكسي محدد في الباقة النشطة وتحديث الارتباطات."""
    clean_email = (email or "").strip().lower()
    with _manager_lock:
        _load_bindings()
        mode = get_network_mode()
        pool_key = "free" if mode == "free" else "residential"
        _castle_bindings.setdefault(pool_key, {})[clean_email] = proxy_url
        _save_bindings()


def get_castle_proxy(email: str) -> Optional[str]:
    """استرجاع رابط البروكسي المرتبط بالقلعة في الباقة النشطة."""
    clean_email = (email or "").strip().lower()
    with _manager_lock:
        _load_bindings()
        mode = get_network_mode()
        pool_key = "free" if mode == "free" else "residential"
        return _castle_bindings.get(pool_key, {}).get(clean_email)


def remove_user_proxy_bindings(user_id: str, castle_emails: Optional[List[str]] = None) -> None:
    """إزالة ارتباطات البروكسي لمستخدم وجميع قلاعه المحذوفة من كلا الباقتين."""
    clean_uid = (user_id or "").strip()
    with _manager_lock:
        _load_bindings()
        changed = False
        for pool in ("residential", "free"):
            u_b = _user_bindings.get(pool, {})
            c_b = _castle_bindings.get(pool, {})
            if clean_uid and clean_uid in u_b:
                del u_b[clean_uid]
                changed = True
            if castle_emails:
                for em in castle_emails:
                    clean_em = (em or "").strip().lower()
                    if clean_em in c_b:
                        del c_b[clean_em]
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
    """إعادة جلب وتحديث قائمة البروكسيات السكنية من Webshare API."""
    with _manager_lock:
        _ensure_loaded(force=True)
        _sync_active_proxies_legacy()
        active = get_active_proxies()
        return len(active)


def proxy_status() -> Dict[str, Any]:
    """تقرير شفاف يُظهر تفاصيل الـ IPs والقلاع المربوطة وفق قاعدة البيانات لعرضها في صفحة AdminProxies.tsx."""
    with _manager_lock:
        _ensure_loaded()
        _load_bindings()
        _sync_active_proxies_legacy()

        mode = get_network_mode()
        pool_key = "free" if mode == "free" else "residential"
        active_proxies = get_active_proxies()
        total_p = len(active_proxies)
        c_bindings = _castle_bindings.get(pool_key, {})
        u_bindings = _user_bindings.get(pool_key, {})

        # جلب قلاع قاعدة البيانات وتصنيفها حسب فهرس البروكسي (proxy_index)
        db_castle_map: Dict[int, List[str]] = {}
        try:
            if os.path.exists(_DB_PATH):
                conn = sqlite3.connect(_DB_PATH, timeout=2.0)
                cur = conn.cursor()
                cur.execute("SELECT lower(email), proxy_index FROM castle_states WHERE proxy_index >= 0")
                for em_row, idx_row in cur.fetchall():
                    if em_row and idx_row is not None and total_p > 0:
                        safe_i = int(idx_row) % total_p
                        db_castle_map.setdefault(safe_i, []).append(em_row)
                conn.close()
        except Exception:
            pass

        proxies_list = []
        for idx, p in enumerate(active_proxies):
            url = _format_proxy_url(p)
            if url:
                host = p.get("proxy_address", "")
                port = p.get("socks5_port") or p.get("port")
                assigned = [em for em, u in c_bindings.items() if u == url]
                for db_em in db_castle_map.get(idx, []):
                    if db_em not in assigned:
                        assigned.append(db_em)
                users = [uid for uid, u in u_bindings.items() if u == url]
                proxies_list.append({
                    "ip": host,
                    "port": port,
                    "country": p.get("country_code", "??"),
                    "city": p.get("city_name", ""),
                    "asn": p.get("asn_name", ""),
                    "type": pool_key,
                    "assigned_castles": assigned,
                    "assigned_users": users,
                    "full_url": url
                })

        all_bound_castles = set(c_bindings.keys())
        for ems in db_castle_map.values():
            all_bound_castles.update(ems)

        return {
            "enabled": is_proxy_enabled(),
            "network_mode": mode,
            "server_ip": get_server_public_ip(),
            "total_proxies": len(active_proxies),
            "residential_count": len(_residential_proxies),
            "free_count": len(_free_proxies),
            "active_pool_name": "سكنية مدفوعة (Static Residential)" if mode == "residential" else ("مجانية (Free Datacenter)" if mode == "free" else "IP السيرفر المباشر"),
            "total_bound_castles": len(all_bound_castles),
            "total_bound_users": len(u_bindings),
            "proxies_list": proxies_list
        }

