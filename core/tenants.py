# -*- coding: utf-8 -*-
"""
core/tenants.py — سجل إعدادات التجار والنطاقات المتعددة (Backend Tenant Registry)
═════════════════════════════════════════════════════════════════════════════════
هذا الملف يحدد قائمة التجار والدومينات المعتمدة وحسابات المشرفين الخاصة بهم.
"""

from typing import List, Dict, Any, Optional

DEFAULT_TENANT: Dict[str, Any] = {
    "id": "main",
    "domains": ["localhost", "127.0.0.1", "ibrabot.com", "187.7.79.122", "ibraabot.online", "www.ibraabot.online"],
    "brand_name": "IBRA BOT",
    "default_language": "ar",
    "admin_email": "ibraboths@gmail.com",
    "primary_color": "#10b981",
    "logo_url": "/logo.png?v=2",
}

MERCHANTS_CONFIG: List[Dict[str, Any]] = [
    {
        "id": "nurjan",
        "domains": ["nurjanbot.online", "www.nurjanbot.online"],
        "brand_name": "Nurjan bot",
        "default_language": "tr",
        "admin_email": "nurjan12ddsw2@gmail.com",
        "primary_color": "#d49835",
        "logo_url": "/nurjan_logo.jpeg",
        "tagline": "",
    },
    # ── يمكنك نسخ وإضافة أي تاجر أو دومين جديد هنا بكل بساطة ──
    # {
    #     "id": "vipbot",
    #     "domains": ["vipbot.net", "www.vipbot.net"],
    #     "brand_name": "VIP BOT",
    #     "admin_email": "vip_admin@gmail.com",
    #     "primary_color": "#8b5cf6",
    #     "tagline": "أقوى بوت للمعارك والتحالفات",
    # },
]


def clean_domain(domain: str) -> str:
    """تنظيف النطاق من www أو المسافات أو المنافذ"""
    if not domain:
        return ""
    d = domain.strip().lower()
    if ":" in d:
        d = d.split(":")[0]
    if d.startswith("www."):
        d = d[4:]
    return d


def get_all_merchants() -> List[Dict[str, Any]]:
    """إرجاع قائمة بجميع التجار المعتمدين"""
    return MERCHANTS_CONFIG


def get_tenant_by_domain(domain: str) -> Dict[str, Any]:
    """العثور على إعدادات التاجر بناءً على اسم الدومين"""
    c_domain = clean_domain(domain)
    for m in MERCHANTS_CONFIG:
        for d in m.get("domains", []):
            if clean_domain(d) == c_domain:
                return m
    return DEFAULT_TENANT


def get_tenant_by_admin_email(email: str) -> Optional[Dict[str, Any]]:
    """التحقق مما إذا كان البريد تابعاً لمشرف أحد التجار (وليس المشرف الأعلى)"""
    if not email:
        return None
    clean_mail = email.strip().lower()
    if clean_mail == DEFAULT_TENANT["admin_email"]:
        return None  # هذا هو المشرف الأعلى
    for m in MERCHANTS_CONFIG:
        if m.get("admin_email", "").strip().lower() == clean_mail:
            return m
    return None


def is_merchant_admin(email: str) -> bool:
    """هل هذا المستخدم هو مشرف لأحد نطاقات التجار؟"""
    return get_tenant_by_admin_email(email) is not None


def is_super_admin(user_or_email: Any) -> bool:
    """هل هذا المستخدم هو المشرف الأعلى الوحيد (ibraboths@gmail.com)؟"""
    if not user_or_email:
        return False
    if isinstance(user_or_email, dict):
        email = str(user_or_email.get("email", "")).strip().lower()
    else:
        email = str(user_or_email).strip().lower()
    return email == DEFAULT_TENANT["admin_email"].strip().lower()


def is_user_allowed_for_tenant_domain(user_dict: Optional[Dict[str, Any]], domain: str) -> bool:
    """
    التحقق الصارم من أن المستخدم ينتمي لهذا الدومين ولا ينتمي لدومين تاجر آخر أو للنظام الرئيسي بشكل غير مصرح به.
    """
    if not user_dict:
        return False

    c_domain = clean_domain(domain)
    target_tenant = get_tenant_by_domain(c_domain)
    target_tenant_id = target_tenant.get("id", "main")

    email = str(user_dict.get("email", "")).strip().lower()
    user_tenant_domain = clean_domain(str(user_dict.get("tenant_domain", "")))

    # 1. إذا كان الدومين المطلوب تابعاً لتاجر معين (مثل nurjanbot.online)
    if target_tenant_id != "main":
        # مشرف التاجر مصرح له حصراً بالدخول لنظامه
        if email == target_tenant.get("admin_email", "").strip().lower():
            return True

        # المشرف الأعلى وحسابات التجار الآخرين غير مصرح لهم بنظام هذا التاجر
        if email == DEFAULT_TENANT["admin_email"].strip().lower():
            return False
        for m in MERCHANTS_CONFIG:
            if m.get("id") != target_tenant_id and m.get("admin_email", "").strip().lower() == email:
                return False

        # دومينات هذا التاجر
        allowed_domains = [clean_domain(d) for d in target_tenant.get("domains", [])]
        allowed_domains.append(target_tenant_id)

        # حسابات المستخدمين التابعين لهذا التاجر يجب أن تكون مسجلة تحت هذا الدومين حصراً
        if not user_tenant_domain:
            return False  # حساب النظام الرئيسي ممنوع من دخول نظام التاجر

        return user_tenant_domain in allowed_domains

    # 2. إذا كان الدومين المطلوب هو النظام الرئيسي (main / ibrabot.com / localhost)
    if target_tenant_id == "main":
        # المشرف الأعلى مصرح له
        if email == DEFAULT_TENANT["admin_email"].strip().lower():
            return True

        # أي مشرف تاجر ممنوع من الدخول كحساب عادي في النظام الرئيسي
        if is_merchant_admin(email):
            return False

        # أي مستخدم مسجل تحت دومين تاجر ممنوع من الدخول في النظام الرئيسي
        all_merchant_domains = []
        for m in MERCHANTS_CONFIG:
            all_merchant_domains.extend([clean_domain(d) for d in m.get("domains", [])])
            all_merchant_domains.append(m.get("id", ""))

        if user_tenant_domain and user_tenant_domain in all_merchant_domains:
            return False

        return True

    return False


