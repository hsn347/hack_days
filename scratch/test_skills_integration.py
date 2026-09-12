# -*- coding: utf-8 -*-
"""
test_skills_integration.py — اختبار تكامل مهمة المهارات وتطبيع مدخلات المستخدم
"""
import sys
import os
import asyncio

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from bot_manager import BotManager, DEFAULT_FIREBASE_USER_CONFIG, resolve_target_skills
from core.session_manager import SessionManager

def test_resolve_target_skills():
    print("🧪 1. اختبار دوال تطبيع وتحديد المهارات (Resolver):")

    # Case 1: الكل / all
    res_all1 = resolve_target_skills("all")
    assert res_all1 == ["harvest", "gather", "warehouse"], f"Failed: {res_all1}"
    res_all2 = resolve_target_skills("الكل")
    assert res_all2 == ["harvest", "gather", "warehouse"], f"Failed: {res_all2}"
    print("   ✅ تطبيع 'all' و 'الكل' ➔ جميع المهارات الثلاث.")

    # Case 2: مهارتي الحصاد الوافر والجمع السريع بالعربية
    res_two_ar = resolve_target_skills(["الحصاد الوافر", "الجمع السريع"])
    assert res_two_ar == ["harvest", "gather"], f"Failed: {res_two_ar}"
    print("   ✅ تطبيع ['الحصاد الوافر', 'الجمع السريع'] ➔ ['harvest', 'gather'].")

    # Case 3: مهارتي harvest و gather كنص مفصول بفاصلة
    res_str = resolve_target_skills("harvest,gather")
    assert res_str == ["harvest", "gather"], f"Failed: {res_str}"
    print("   ✅ تطبيع 'harvest,gather' ➔ ['harvest', 'gather'].")

    # Case 4: مهارة واحدة فقط
    res_single = resolve_target_skills("الحصاد الوافر")
    assert res_single == ["harvest"], f"Failed: {res_single}"
    print("   ✅ تطبيع مهارة واحدة 'الحصاد الوافر' ➔ ['harvest'].")

    # Case 5: قاموس اختيارات (Booleans)
    res_dict = resolve_target_skills({"harvest": True, "gather": True, "warehouse": False})
    assert res_dict == ["harvest", "gather"], f"Failed: {res_dict}"
    print("   ✅ تطبيع قاموس {'harvest': True, 'gather': True, 'warehouse': False} ➔ ['harvest', 'gather'].")

def test_config_schema():
    print("\n🧪 2. اختبار مخطط إعدادات Firebase:")
    assert "skills" in DEFAULT_FIREBASE_USER_CONFIG
    sk_cfg = DEFAULT_FIREBASE_USER_CONFIG["skills"]
    assert sk_cfg["enabled"] is True
    assert "target_skills" in sk_cfg
    assert len(sk_cfg["target_skills"]) == 3
    print("   ✅ تم التحقق من قسم skills في DEFAULT_FIREBASE_USER_CONFIG.")

def test_bot_manager_init():
    print("\n🧪 3. اختبار بناء إعدادات BotManager مع خيارات مختلفة:")
    sm = SessionManager()
    accounts = sm.load()
    email = next(iter(accounts.keys()))

    # Case A: Default
    bm1 = BotManager(email)
    assert bm1.config["skills"]["enabled"] is True
    assert len(bm1.config["skills"]["target_skills"]) == 3
    print("   ✅ الحالة الافتراضية: enabled=True, جميع المهارات.")

    # Case B: Custom User Firebase Config (مهارتي الحصاد الوافر والجمع السريع)
    custom_cfg = {
        "skills": {
            "enabled": True,
            "target_skills": ["الحصاد الوافر", "الجمع السريع"]
        }
    }
    bm2 = BotManager(email, config=custom_cfg)
    resolved = resolve_target_skills(bm2.config["skills"])
    assert resolved == ["harvest", "gather"]
    print("   ✅ حالة تخصيص المستخدم: ['الحصاد الوافر', 'الجمع السريع'] ➔ ['harvest', 'gather'].")

    # Case C: Disabled
    disabled_cfg = {
        "skills": {
            "enabled": False,
        }
    }
    bm3 = BotManager(email, config=disabled_cfg)
    assert bm3.config["skills"]["enabled"] is False
    print("   ✅ حالة التعطيل: enabled=False.")

async def test_step_10_skip():
    print("\n🧪 4. اختبار تخطي الخطوة عندما تكون معطلة:")
    sm = SessionManager()
    accounts = sm.load()
    email = next(iter(accounts.keys()))
    bm = BotManager(email, config={"skills": {"enabled": False}})
    res = await bm.step_10_skills_task()
    assert res.get("skipped") is True
    print(f"   ✅ تم التخطي بنجاح: {res['message']}")

if __name__ == "__main__":
    test_resolve_target_skills()
    test_config_schema()
    test_bot_manager_init()
    asyncio.run(test_step_10_skip())
    print("\n🎉 جميع اختبارات التكامل لمهمة المهارات التلقائية نجحت 100%!")
