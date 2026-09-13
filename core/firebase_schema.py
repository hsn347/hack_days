# -*- coding: utf-8 -*-
"""
core/firebase_schema.py — مخطط ونماذج بيانات Firebase Firestore للبوت ولوحة التحكم
═════════════════════════════════════════════════════════════════════════════════════════
يوفر هذا الملف:
  1. دوال إنشاء مستندات المستخدم والاشتراكات والقلاع بالقيم الافتراضية.
  2. التحقق من صلاحية الاشتراك ونفاذه (Subscription Validity & Expiry).
  3. فحص الحد الأقصى لعدد القلاع المسموح بها حسب باقة المستخدم (Castles Quota).
  4. استخراج وتجهيز قاموس config المتوافق مباشرة مع BotManager.
  5. بناء قواميس تحديث الموارد الحية وحالة البوت لحفظها في Firestore.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from bot_manager import DEFAULT_FIREBASE_USER_CONFIG


# ════════════════════════════════════════════════════════════════════
# 💳 خطط وباقات الاشتراكات الافتراضية (Subscription Plans Catalog)
# ════════════════════════════════════════════════════════════════════

DEFAULT_SUBSCRIPTION_PLANS: Dict[str, Dict[str, Any]] = {
    "basic": {
        "plan_id": "basic",
        "plan_name": "الباقة الأساسية (Basic)",
        "max_castles_allowed": 1,
        "default_duration_days": 30,
        "description": "تشغيل قلعة واحدة مع كافة المهام الأساسية",
    },
    "pro": {
        "plan_id": "pro",
        "plan_name": "باقة المحترفين (Pro)",
        "max_castles_allowed": 3,
        "default_duration_days": 30,
        "description": "تشغيل حتى 3 قلاع مع سرعة تنفيذ وأولويات متقدمة",
    },
    "vip_pro": {
        "plan_id": "vip_pro",
        "plan_name": "باقة كبار الشخصيات (VIP Plan)",
        "max_castles_allowed": 5,
        "default_duration_days": 30,
        "description": "تشغيل حتى 5 قلاع مع دعم كامل لمنسق الفيالق الذكي",
    },
    "unlimited": {
        "plan_id": "unlimited",
        "plan_name": "الباقة غير المحدودة (Enterprise)",
        "max_castles_allowed": 15,
        "default_duration_days": 30,
        "description": "تشغيل حتى 15 قلعة للتحالفات والمزارع الضخمة",
    },
}


# ════════════════════════════════════════════════════════════════════
# 🏭 مصانع إنشاء المستندات (Document Factories)
# ════════════════════════════════════════════════════════════════════

def create_user_document(
    uid: str,
    username: str,
    email: str,
    phone: str = "",
    plan_id: str = "vip_pro",
    duration_days: int = 30,
    role: str = "user"
) -> Dict[str, Any]:
    """إنشاء مستند مستخدم جديد متضمناً تفاصيل الاشتراك وصلاحيته."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=duration_days)

    plan_info = DEFAULT_SUBSCRIPTION_PLANS.get(plan_id, DEFAULT_SUBSCRIPTION_PLANS["vip_pro"])

    return {
        "uid": uid,
        "username": username,
        "email": email,
        "phone": phone,
        "role": role,
        "created_at": now.isoformat(),
        "is_banned": False,
        "subscription": {
            "plan_id": plan_id,
            "plan_name": plan_info["plan_name"],
            "status": "active",
            "started_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "days_remaining": duration_days,
            "max_castles_allowed": plan_info["max_castles_allowed"],
            "current_castles_count": 0,
        }
    }


def create_castle_document(
    castle_id: str,
    email: str,
    lord_name: str = "لورد الإمبراطورية",
    castle_name: str = "القلعة الملكية",
    server_id: int = 1,
    coordinates: Optional[Dict[str, int]] = None,
    castle_level: int = 1,
    lord_power: int = 0,
    vip_level: int = 0,
    alliance_name: str = "",
    custom_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """إنشاء مستند قلعة جديدة متضمناً معلوماتها العامة والموارد والمخطط الكامل للمهام."""
    now = datetime.now(timezone.utc).isoformat()
    coords = coordinates or {"x": 0, "y": 0}

    # دمج التكوين المخصص فوق DEFAULT_FIREBASE_USER_CONFIG
    merged_config = copy.deepcopy(DEFAULT_FIREBASE_USER_CONFIG)
    if custom_config:
        for k, v in custom_config.items():
            if isinstance(v, dict) and k in merged_config and isinstance(merged_config[k], dict):
                merged_config[k].update(v)
            else:
                merged_config[k] = v

    return {
        "castle_id": castle_id,
        "email": email,
        "is_active": True,
        "created_at": now,
        "castle_info": {
            "lord_name": lord_name,
            "castle_name": castle_name,
            "server_id": server_id,
            "castle_level": castle_level,
            "lord_power": lord_power,
            "vip_level": vip_level,
            "alliance_name": alliance_name,
            "coordinates": coords,
        },
        "resources": {
            "food": 0,
            "wood": 0,
            "iron": 0,
            "diamond": 0,
            "gold": 0,
            "stamina": 120,
            "last_updated": now,
        },
        "bot_status": {
            "state": "idle",
            "last_run_time": None,
            "next_run_time": None,
            "last_run_message": "جاهز للتشغيل",
            "active_marches": 0,
            "max_marches": 6,
            "last_error": None,
        },
        "config": merged_config,
    }


# ════════════════════════════════════════════════════════════════════
# 🔍 دوال التحقق من الاشتراكات وحصص القلاع (Validation Helpers)
# ════════════════════════════════════════════════════════════════════

def check_user_subscription(user_doc: Dict[str, Any]) -> Tuple[bool, str]:
    """
    التحقق من صلاحية اشتراك المستخدم:
      - هل الحساب محظور؟
      - هل الاشتراك في حالة active؟
      - هل تاريخ الصلاحية لم ينتهِ بعد؟
    """
    if not user_doc:
        return False, "المستخدم غير موجود"

    if user_doc.get("is_banned"):
        return False, "الحساب محظور من قبل الإدارة"

    sub = user_doc.get("subscription", {})
    status = sub.get("status", "expired")
    if status != "active":
        return False, f"الاشتراك غير مفعل (الحالة: {status})"

    expires_at_raw = sub.get("expires_at")
    if expires_at_raw:
        try:
            # معالجة تواريخ ISO
            expires_at = datetime.fromisoformat(str(expires_at_raw).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if now > expires_at:
                return False, f"انتهت صلاحية الاشتراك بتاريخ: {expires_at.strftime('%Y-%m-%d %H:%M')}"
        except Exception as e:
            return False, f"صيغة تاريخ انتهاء الاشتراك غير صالحة: {e}"

    return True, "الاشتراك نشط وصالح"


def can_user_add_castle(user_doc: Dict[str, Any], current_count: Optional[int] = None) -> Tuple[bool, int, int]:
    """
    فحص ما إذا كان المستخدم يملك سعة لإضافة قلعة جديدة وفق باقته:
    يعيد: (مسموح_أم_لا, عدد_القلاع_الحالي, الحد_الأقصى_المسموح)
    """
    sub = user_doc.get("subscription", {})
    max_allowed = int(sub.get("max_castles_allowed", 1))

    if current_count is None:
        curr = int(sub.get("current_castles_count", 0))
    else:
        curr = int(current_count)

    allowed = (curr < max_allowed)
    return allowed, curr, max_allowed


def extract_castle_bot_config(castle_doc: Dict[str, Any]) -> Dict[str, Any]:
    """استخراج قاموس config لقلعة محددة مع دمجه بالقيم الافتراضية للتأكد من اكتمال كافة الحقول."""
    merged = copy.deepcopy(DEFAULT_FIREBASE_USER_CONFIG)
    user_cfg = castle_doc.get("config", {})

    for task_name, task_params in user_cfg.items():
        if isinstance(task_params, dict) and task_name in merged and isinstance(merged[task_name], dict):
            merged[task_name].update(task_params)
        else:
            merged[task_name] = task_params

    return merged


def build_resources_update(
    food: int = 0,
    wood: int = 0,
    iron: int = 0,
    diamond: int = 0,
    gold: int = 0,
    stamina: int = 120,
    state: str = "idle",
    last_message: str = "",
    active_marches: int = 0,
    max_marches: int = 6,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """تجهيز قاموس التحديث الجزئي لحفظ الموارد وحالة البوت في Firestore."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "resources.food": food,
        "resources.wood": wood,
        "resources.iron": iron,
        "resources.diamond": diamond,
        "resources.gold": gold,
        "resources.stamina": stamina,
        "resources.last_updated": now,
        "bot_status.state": state,
        "bot_status.last_run_time": now,
        "bot_status.last_run_message": last_message,
        "bot_status.active_marches": active_marches,
        "bot_status.max_marches": max_marches,
        "bot_status.last_error": error,
    }
