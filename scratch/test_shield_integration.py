# -*- coding: utf-8 -*-
"""
test_shield_integration.py — اختبار تكامل مهمة درع السلام في BotManager
"""
import sys
import os
import asyncio

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from bot_manager import BotManager, DEFAULT_FIREBASE_USER_CONFIG
from core.session_manager import SessionManager

def test_config_schema():
    print("🧪 1. اختبار مخطط الإعدادات الافتراضي:")
    assert "shield" in DEFAULT_FIREBASE_USER_CONFIG, "shield not in DEFAULT_FIREBASE_USER_CONFIG"
    shield_cfg = DEFAULT_FIREBASE_USER_CONFIG["shield"]
    assert shield_cfg["enabled"] is True
    assert shield_cfg["duration"] == "8h"
    assert shield_cfg["allow_gold"] is False
    print("   ✅ تم التحقق من قيم ومفاتيح مهمة الدرع في DEFAULT_FIREBASE_USER_CONFIG بنجاح.")

def test_bot_manager_init():
    print("\n🧪 2. اختبار بناء إعدادات BotManager مع خيارات مختلفة:")
    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        print("   ⚠️ لا توجد حسابات مسجلة")
        return

    email = next(iter(accounts.keys()))

    # Case A: Default
    bm1 = BotManager(email)
    assert bm1.config["shield"]["enabled"] is True
    assert bm1.config["shield"]["duration"] == "8h"
    assert bm1.config["shield"]["allow_gold"] is False
    print("   ✅ الحالة الافتراضية: duration=8h, allow_gold=False, enabled=True")

    # Case B: Custom User Firebase Config
    custom_cfg = {
        "shield": {
            "enabled": True,
            "duration": "24h",
            "allow_gold": True,
        }
    }
    bm2 = BotManager(email, config=custom_cfg)
    assert bm2.config["shield"]["duration"] == "24h"
    assert bm2.config["shield"]["allow_gold"] is True
    print("   ✅ حالة تخصيص المستخدم: duration=24h, allow_gold=True")

    # Case C: Disabled
    disabled_cfg = {
        "shield": {
            "enabled": False,
            "duration": "3d",
        }
    }
    bm3 = BotManager(email, config=disabled_cfg)
    assert bm3.config["shield"]["enabled"] is False
    assert bm3.config["shield"]["duration"] == "3d"
    print("   ✅ حالة التعطيل: enabled=False, duration=3d")

async def test_step_8_skip():
    print("\n🧪 3. اختبار تخطي الخطوة عندما تكون معطلة:")
    sm = SessionManager()
    accounts = sm.load()
    email = next(iter(accounts.keys()))
    bm = BotManager(email, config={"shield": {"enabled": False}})
    res = await bm.step_8_shield_task()
    assert res.get("skipped") is True
    print(f"   ✅ تم التخطي بنجاح: {res['message']}")

if __name__ == "__main__":
    test_config_schema()
    test_bot_manager_init()
    asyncio.run(test_step_8_skip())
    print("\n🎉 جميع اختبارات التكامل لمهمة درع السلام نجحت 100%!")
