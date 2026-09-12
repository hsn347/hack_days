# -*- coding: utf-8 -*-
"""
config.py — الإعدادات المركزية للبوت (Firebase-ready)
═══════════════════════════════════════════════════════

الإعدادات الافتراضية لكل مهمة.
عند تفعيل Firebase، ستُستبدَل هذه القيم بما يأتي من Firebase.

الاستخدام:
    from config import DEFAULT_TASK_CONFIG, get_account_config
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional


# ════════════════════════════════════════════════════════════════════
#  الإعدادات الافتراضية للمهام
# ════════════════════════════════════════════════════════════════════

DEFAULT_TASK_CONFIG: Dict[str, Dict[str, Any]] = {
    "gather": {
        "enabled":      True,
        "res_type":     4,       # 1=مزارع 2=خشب 3=حجر 4=حديد/ذهب
        "min_lv":       5,
        "max_lv":       6,
        "max_marches":  6,
        "search_range": 100,
        "interval":     1800,    # ثانية (30 دقيقة)
    },
    "port": {
        "enabled":  True,
        "interval": 86400,       # يوم كامل
    },
    "alliance": {
        "enabled":  True,
        "interval": 3600,        # ساعة
    },
    "train": {
        "enabled":  False,       # معطل افتراضياً
        "unit_id":  711,         # عربات (Cart)
        "unit_num": 1000,
        "interval": 7200,        # ساعتان
    },
    "transport": {
        "enabled":          False,       # نقل وإمداد الموارد (تفعيل عند الحاجة)
        "target_x":         487,         # إحداثي X للقلعة الهدف
        "target_y":         290,         # إحداثي Y للقلعة الهدف
        "resource_ids":     [1002],      # 1002=قمح, 1003=خشب, 1004=حديد, 1005=ألماس
        "amount_per_march": 50000,       # حمولة الفيلق الواحد
        "max_marches":      6,           # عدد فيالق النقل المتتالية
        "interval":         3600,        # التكرار كل ساعة
    },
    "monster": {
        "enabled":          False,       # الهجوم على الغزاة والمتمردين
        "monster_type":     "rebels",    # "rebels" (متمردين: 35) أو "invaders" (غزاة: 6)
        "min_lv":           1,
        "max_lv":           30,
        "max_marches":      6,
        "search_range":     50,
        "formation_id":     1,           # رقم التشكيلة المفضلة (1..5)
        "interval":         1800,        # التكرار كل 30 دقيقة
    },
    "ruins": {
        "enabled":          False,       # استكشاف الأطلال (Relics Exploration)
        "min_lv":           1,
        "max_lv":           30,
        "max_marches":      1,           # مسيرة واحدة فقط كحد أقصى مسموح به في اللعبة للأطلال
        "search_range":     100,
        "formation_id":     1,           # رقم التشكيلة المفضلة (1..5)
        "explore_time":     900,         # مدة الاستكشاف (15 دقيقة)
        "interval":         1800,        # التكرار كل 30 دقيقة
    },
    "stronghold": {
        "enabled":          False,       # الهجوم على المعاقل / الملاجئ (Stronghold Attack)
        "min_lv":           1,
        "max_lv":           35,
        "max_marches":      6,
        "search_range":     100,
        "formation_id":     1,           # رقم التشكيلة المفضلة (1..5)
        "interval":         1800,        # التكرار كل 30 دقيقة
    },
    "gold_gather": {
        "enabled":          False,       # جمع الذهب وموارد التحالف (Gold & Alliance Gathering)
        "sub_type":         1,           # 1=ذهب (1001), 2=قمح, 3=خشب, 4=حديد, 5=ألماس
        "min_lv":           1,
        "max_lv":           6,
        "max_marches":      6,
        "search_range":     50,
        "formation_id":     1,           # رقم التشكيلة المفضلة (1..5)
        "alliance_x":       None,        # إحداثي X للتحالف (أو None للقلعة)
        "alliance_y":       None,        # إحداثي Y للتحالف (أو None للقلعة)
        "interval":         1800,        # التكرار كل 30 دقيقة
    },
}








# ════════════════════════════════════════════════════════════════════
#  إعدادات الحسابات (يمكن تخصيص كل حساب)
# ════════════════════════════════════════════════════════════════════

# مثال: إذا أردت تخصيص حساب معين، أضفه هنا.
# إذا لم يكن الحساب هنا، سيُستخدم DEFAULT_TASK_CONFIG
ACCOUNT_OVERRIDES: Dict[str, Dict] = {
    # "user@gmail.com": {
    #     "offset": 120,           # تأخير 120 ثانية قبل بدء مهام هذا الحساب
    #     "tasks": {
    #         "gather": {"res_type": 2, "max_marches": 3},
    #         "train":  {"enabled": True, "unit_num": 500}
    #     }
    # }
}


# ════════════════════════════════════════════════════════════════════
#  إعدادات البوت العامة
# ════════════════════════════════════════════════════════════════════

BOT_CONFIG = {
    "log_level":          "INFO",
    "reconnect_interval": 60,     # ثواني قبل إعادة الاتصال عند الانقطاع
    "default_offset":     0,      # الـ offset الافتراضي بين الحسابات
    "offset_step":        30,     # تزداد كل حساب بـ 30 ثانية تلقائياً
}


# ════════════════════════════════════════════════════════════════════
#  دالة جلب إعدادات حساب + مهمة مدمجة
# ════════════════════════════════════════════════════════════════════

def get_account_config(email: str) -> Dict[str, Any]:
    """
    يعيد إعدادات الحساب الكاملة.
    إذا لم يكن الحساب في ACCOUNT_OVERRIDES → يستخدم القيم الافتراضية.
    """
    override = ACCOUNT_OVERRIDES.get(email, {})
    tasks    = {}
    for task_name, defaults in DEFAULT_TASK_CONFIG.items():
        task_override = override.get('tasks', {}).get(task_name, {})
        tasks[task_name] = {**defaults, **task_override}

    return {
        "email":  email,
        "offset": override.get('offset', 0),
        "tasks":  tasks,
    }


def get_enabled_tasks(email: str) -> List[str]:
    """يعيد قائمة أسماء المهام المُفعَّلة لهذا الحساب."""
    cfg = get_account_config(email)
    return [name for name, tcfg in cfg['tasks'].items() if tcfg.get('enabled')]
