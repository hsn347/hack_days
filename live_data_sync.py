"""
live_data_sync.py — تشغيل الوسيط كسكربت مستقل
════════════════════════════════════════════════
يشغّل game_state middleware ويبقيه حياً حتى Ctrl+C.
البيانات تتحدث في game_data_captured.json تلقائياً.
"""
import sys, time, argparse
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from game_state import game, start_sync, wait_ready, stop_sync, is_running


def main():
    p = argparse.ArgumentParser(description="مزامنة بيانات اللعبة اللحظية")
    p.add_argument('--verbose', '-v', action='store_true', help='طباعة تفاصيل كل الحزم')
    p.add_argument('--timeout', '-t', type=int, default=60, help='مهلة اكتشاف الجلسة (ثانية)')
    args = p.parse_args()

    print("\n" + "═"*60)
    print("  ⚡ Game State Middleware — مزامنة لحظية")
    print("  📁 game_data_captured.json")
    print("  🛑 Ctrl+C للإيقاف")
    print("═"*60)

    # تشغيل الوسيط في الخلفية
    start_sync(verbose=args.verbose, background=True, tap_timeout=args.timeout)

    # انتظار اكتمال البيانات الأولية
    print("\n  [*] انتظار اكتمال البيانات الأولية...")
    if not wait_ready(timeout=args.timeout + 20):
        print("  [✗] لم تكتمل البيانات — تأكد من فتح اللعبة والضغط على الشاشة")
        return

    # طباعة الحالة الأولية
    print()
    game.print_status()
    print()
    game.print_heroes()
    print()
    print("  ✅ الوسيط يعمل — البيانات تتحدث لحظياً\n")

    # حلقة المراقبة
    try:
        last = time.time()
        while True:
            time.sleep(5)
            if time.time() - last >= 60:
                last = time.time()
                ts = datetime.now().strftime('%H:%M:%S')
                s = game.get_summary()
                idle = s['heroes_idle']
                busy = s['heroes_busy']
                pkts = s['packets']
                print(f"  [{ts}] 💓 أبطال متاح={idle} مشغول={busy} | حزم={pkts}")
    except KeyboardInterrupt:
        print("\n  [*] إيقاف الوسيط...")
        stop_sync()
        print("  [✓] تم الإيقاف وحفظ البيانات.")


if __name__ == '__main__':
    main()
