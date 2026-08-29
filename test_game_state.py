# -*- coding: utf-8 -*-
"""
test_game_state.py — اختبار الوسيط بدون اتصال فعلي بالمحاكي
═════════════════════════════════════════════════════════════
يختبر: state.py + models.py بشكل معزول
"""
import sys, os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_state.state import GameState
from game_state.models import Hero, March

def test_hero_state():
    print("═"*50)
    print("  اختبار 1: حالة الأبطال")
    print("═"*50)

    st = GameState()

    # محاكاة حزمة init (cmd=1000)
    fake_init = {
        'heroCtrl': [
            {'id': 5502001, 'lv': 90, 'star': 4, 'stage': 2, 'exp': 1000, 'status': {'state': 0}},
            {'id': 5502002, 'lv': 85, 'star': 3, 'stage': 1, 'exp': 500,  'status': {'state': 0}},
            {'id': 5502003, 'lv': 87, 'star': 4, 'stage': 2, 'exp': 800,  'status': {'state': 0}},
        ]
    }
    st.process_init_data(fake_init)

    heroes = st.get_all_heroes()
    assert len(heroes) == 3, f"توقعت 3 أبطال، حصلت على {len(heroes)}"
    print(f"  ✓ تم تحميل {len(heroes)} بطل")

    # كلهم متاحون في البداية
    idle = st.get_idle_heroes()
    assert len(idle) == 3, f"توقعت 3 متاحين، حصلت على {len(idle)}"
    print(f"  ✓ جميع الأبطال متاحون: {len(idle)}")

    assert st.is_hero_available(5502001) == True
    print("  ✓ is_hero_available(5502001) = True")

    # محاكاة NOTIFY_LOCAL_QUEUE_SYNC (بطل 5502003 خرج في مسيرة)
    fake_queue = [{
        'data': {
            'from': {
                'heros': {
                    '10615183': [{'id': 5502003, 'lv': 87}]
                }
            },
            'queueType': 4,
            'status': 1,
            'startTime': 1000000,
            'endTime':   1000350,
            'teamId': 9999,
        },
        'msgType': 1,
        'teamId': 9999,
    }]
    st.process_notify('NOTIFY_LOCAL_QUEUE_SYNC', fake_queue)

    assert st.is_hero_available(5502003) == False, "البطل يجب أن يكون مشغولاً"
    assert st.is_hero_available(5502001) == True,  "البطل يجب أن يكون متاحاً"
    print("  ✓ بطل 5502003 → مشغول بعد QUEUE_SYNC")
    print("  ✓ بطل 5502001 → متاح بعد QUEUE_SYNC")

    idle_after = st.get_idle_heroes()
    busy_after = st.get_busy_heroes()
    assert len(idle_after) == 2
    assert len(busy_after) == 1
    print(f"  ✓ متاح={len(idle_after)}, مشغول={len(busy_after)}")

    # محاكاة عودة البطل (queue فارغة)
    st.process_notify('NOTIFY_LOCAL_QUEUE_SYNC', [])
    assert st.is_hero_available(5502003) == True, "البطل يجب أن يعود متاحاً"
    print("  ✓ بطل 5502003 → عاد متاحاً بعد queue فارغة")

    print("  ✅ اختبار 1 نجح!\n")


def test_march_tracking():
    print("═"*50)
    print("  اختبار 2: تتبع المسيرات")
    print("═"*50)

    import time
    st = GameState()

    fake_init = {
        'heroCtrl': [
            {'id': 5501001, 'lv': 60, 'star': 3, 'stage': 1, 'exp': 0, 'status': {'state': 0}},
        ]
    }
    st.process_init_data(fake_init)

    now = int(time.time())
    fake_queue = [{
        'data': {
            'from': {'heros': {'123': [{'id': 5501001, 'lv': 60}]}},
            'queueType': 4,
            'status': 1,
            'startTime': now,
            'endTime': now + 300,  # 5 دقائق
            'teamId': 1111,
            'to': {'x': 200, 'y': 300, 'type': 5},
        },
        'teamId': 1111,
    }]
    st.process_notify('NOTIFY_LOCAL_QUEUE_SYNC', fake_queue)

    marches = st.get_active_marches()
    assert len(marches) == 1, f"توقعت مسيرة واحدة، حصلت على {len(marches)}"
    m = marches[0]
    assert 5501001 in m.hero_ids
    assert m.remaining_seconds > 0
    print(f"  ✓ مسيرة نشطة: {m}")
    print(f"  ✓ الوقت المتبقي: {m.remaining_seconds} ثانية")
    print("  ✅ اختبار 2 نجح!\n")


def test_concurrency():
    print("═"*50)
    print("  اختبار 3: التزامن (Threading)")
    print("═"*50)

    import threading
    st = GameState()
    fake_init = {
        'heroCtrl': [{'id': i, 'lv': 50, 'star': 2, 'stage': 0, 'exp': 0, 'status': {'state': 0}}
                     for i in range(5500000, 5500020)]
    }
    st.process_init_data(fake_init)

    errors = []

    def reader():
        for _ in range(500):
            heroes = st.get_idle_heroes()
            busy   = st.get_busy_heroes()
            if len(heroes) + len(busy) != 20:
                errors.append(f"عدد خاطئ: {len(heroes)+len(busy)}")

    def writer():
        for i in range(50):
            q = [{'data': {'from': {'heros': {'u': [{'id': 5500000+i}]}}}, 'teamId': i}]
            st.process_notify('NOTIFY_LOCAL_QUEUE_SYNC', q)

    threads = [threading.Thread(target=reader) for _ in range(4)]
    threads += [threading.Thread(target=writer) for _ in range(2)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert not errors, f"أخطاء تزامن: {errors}"
    print(f"  ✓ لا أخطاء تزامن بعد {6} خيوط متوازية")
    print("  ✅ اختبار 3 نجح!\n")


def test_hero_api():
    print("═"*50)
    print("  اختبار 4: واجهة game API")
    print("═"*50)

    from game_state import game
    from game_state.state import GameState

    # حقن بيانات تجريبية في الـ state المركزي
    import game_state as gs
    fake = {
        'heroCtrl': [
            {'id': 5502001, 'lv': 95, 'star': 5, 'stage': 3, 'exp': 9999, 'status': {'state': 0}},
            {'id': 5502002, 'lv': 70, 'star': 3, 'stage': 1, 'exp': 100,  'status': {'state': 1}},
        ]
    }
    gs._state.process_init_data(fake)
    gs._state.init_done = True

    assert game.is_hero_available(5502001) == True
    assert game.is_hero_available(5502002) == False
    print("  ✓ game.is_hero_available() يعمل صح")

    best = game.get_best_idle_hero()
    assert best is not None and best.id == 5502001
    print(f"  ✓ game.get_best_idle_hero() = {best}")

    idle = game.get_idle_heroes()
    assert len(idle) == 1
    print(f"  ✓ game.get_idle_heroes() = {len(idle)} بطل")

    summary = game.get_summary()
    assert summary['heroes_total'] == 2
    assert summary['heroes_idle'] == 1
    assert summary['heroes_busy'] == 1
    print(f"  ✓ game.get_summary() صحيح")

    print("  ✅ اختبار 4 نجح!\n")


if __name__ == '__main__':
    print("\n" + "═"*50)
    print("  🧪 اختبار Game State Middleware")
    print("═"*50 + "\n")

    try:
        test_hero_state()
        test_march_tracking()
        test_concurrency()
        test_hero_api()

        print("═"*50)
        print("  🎉 جميع الاختبارات نجحت!")
        print("═"*50)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n  ❌ فشل الاختبار: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n  ❌ خطأ: {e}")
        traceback.print_exc()
        sys.exit(1)
