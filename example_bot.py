# -*- coding: utf-8 -*-
"""
example_bot.py — مثال عملي لاستخدام Game State Middleware في البوت
════════════════════════════════════════════════════════════════════
يوضح كيفية استخدام الوسيط لقراءة البيانات في أي سكربت بوت.
"""
import sys, time
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ══════════════════════════════════════════════════
#  الاستيراد — سطر واحد فقط
# ══════════════════════════════════════════════════
from game_state import game, start_sync, wait_ready, stop_sync


def run_bot():
    print("═"*55)
    print("  🤖 مثال بوت — Game State Middleware")
    print("═"*55)

    # 1) تشغيل الوسيط في الخلفية (مرة واحدة فقط)
    print("\n  [1/3] تشغيل الوسيط...")
    start_sync(verbose=False)  # background=True افتراضياً

    # 2) انتظار اكتمال البيانات الأولية
    print("  [2/3] انتظار البيانات (اضغط على شاشة اللعبة)...")
    if not wait_ready(timeout=90):
        print("  [✗] فشل جلب البيانات!")
        return

    print("  [3/3] البيانات جاهزة!\n")

    # ════════════════════════════════════════════
    #  من هنا كود البوت العادي — بدون أي تعقيد
    # ════════════════════════════════════════════

    # طباعة معلومات الحساب
    player = game.get_player()
    print(f"  👤 اللاعب: {player.name} (uid={player.uid})")
    print(f"  🏰 مستوى القلعة: {player.castle_lv}")
    print()

    # طباعة جدول الأبطال
    game.print_heroes()
    print()

    # مثال: حلقة بوت بسيطة
    print("  ─── حلقة البوت ───")
    for cycle in range(1, 4):
        print(f"\n  [دورة {cycle}]")

        # جلب الأبطال المتاحين
        idle_heroes = game.get_idle_heroes()
        print(f"  • أبطال متاحون: {len(idle_heroes)}")
        for h in idle_heroes:
            print(f"    → {h}")

        # جلب أفضل بطل متاح
        best = game.get_best_idle_hero()
        if best:
            print(f"  • أفضل بطل: {best}")
        else:
            print("  • لا يوجد بطل متاح حالياً")

        # المسيرات النشطة
        marches = game.get_active_marches()
        if marches:
            print(f"  • مسيرات نشطة: {len(marches)}")
            for m in marches:
                print(f"    → {m}")
        else:
            print("  • لا توجد مسيرات نشطة")

        # فحص بطل محدد
        hero_id = 5502002
        if game.is_hero_available(hero_id):
            print(f"  • البطل {hero_id} متاح ✅")
        else:
            h = game.get_hero(hero_id)
            print(f"  • البطل {hero_id} مشغول ❌")

        print("  ⏳ انتظار 10 ثوانٍ...")
        time.sleep(10)

    # إيقاف الوسيط عند الانتهاء
    stop_sync()
    print("\n  ✅ انتهى البوت.")


if __name__ == '__main__':
    run_bot()
