# -*- coding: utf-8 -*-
"""
test_stamina_integration.py — اختبار تكامل مهمة الطاقة في BotManager
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
    print("🧪 1. اختبار مخطط الإعدادات الافتراضي لمهمة الطاقة:")
    assert "stamina" in DEFAULT_FIREBASE_USER_CONFIG, "stamina not in DEFAULT_FIREBASE_USER_CONFIG"
    stamina_cfg = DEFAULT_FIREBASE_USER_CONFIG["stamina"]
    assert stamina_cfg["enabled"] is True
    assert stamina_cfg["gold_buys"] == 0
    print("   ✅ تم التحقق من قيم ومفاتيح مهمة الطاقة في DEFAULT_FIREBASE_USER_CONFIG بنجاح.")

def test_bot_manager_init():
    print("\n🧪 2. اختبار بناء إعدادات BotManager مع خيارات الطاقة:")
    sm = SessionManager()
    accounts = sm.load()
    email = next(iter(accounts.keys()))

    # Case A: Default
    bm1 = BotManager(email)
    assert bm1.config["stamina"]["enabled"] is True
    assert bm1.config["stamina"]["gold_buys"] == 0
    print("   ✅ الحالة الافتراضية: enabled=True, gold_buys=0 (مجاني فقط)")

    # Case B: Custom User Firebase Config
    custom_cfg = {
        "stamina": {
            "enabled": True,
            "gold_buys": 3,
        }
    }
    bm2 = BotManager(email, config=custom_cfg)
    assert bm2.config["stamina"]["gold_buys"] == 3
    print("   ✅ حالة تخصيص المستخدم: enabled=True, gold_buys=3")

    # Case C: Disabled
    disabled_cfg = {
        "stamina": {
            "enabled": False,
        }
    }
    bm3 = BotManager(email, config=disabled_cfg)
    assert bm3.config["stamina"]["enabled"] is False
    print("   ✅ حالة التعطيل: enabled=False")

async def test_step_9_skip():
    print("\n🧪 3. اختبار تخطي الخطوة عندما تكون معطلة:")
    sm = SessionManager()
    accounts = sm.load()
    email = next(iter(accounts.keys()))
    bm = BotManager(email, config={"stamina": {"enabled": False}})
    res = await bm.step_9_stamina_task()
    assert res.get("skipped") is True
    print(f"   ✅ تم التخطي بنجاح: {res['message']}")

if __name__ == "__main__":
    test_config_schema()
    test_bot_manager_init()
    asyncio.run(test_step_9_skip())
    print("\n🎉 جميع اختبارات التكامل لمهمة الطاقة نجحت 100%!")
