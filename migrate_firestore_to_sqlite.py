# -*- coding: utf-8 -*-
"""
migrate_firestore_to_sqlite.py — ترحيل البيانات من Firestore إلى SQLite
════════════════════════════════════════════════════════════════════════
يُشغَّل مرة واحدة فقط لسحب جميع بيانات المستخدمين والقلاع من Firestore
وحفظها في SQLite (castles.db) مع نسخة احتياطية JSON كاملة.
"""

import json
import os
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

DUMPS_DIR = os.path.join(_ROOT, "dumps")
os.makedirs(DUMPS_DIR, exist_ok=True)


def migrate():
    """سحب جميع البيانات من Firestore وحفظها في SQLite."""
    print("=" * 60)
    print("🔄 بدء ترحيل البيانات من Firestore إلى SQLite...")
    print("=" * 60)

    # 1. تهيئة Firebase
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_fs

        sak = os.path.join(_ROOT, "firebase_service_account.json")
        if not os.path.exists(sak):
            print(f"❌ ملف Service Account غير موجود: {sak}")
            return False

        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(credentials.Certificate(sak))

        db = fb_fs.client()
        print("✅ تم الاتصال بـ Firebase بنجاح")
    except Exception as e:
        print(f"❌ فشل الاتصال بـ Firebase: {e}")
        print("⚠️  سيتم الاعتماد على البيانات المحلية الموجودة في SQLite")
        return False

    # 2. سحب جميع المستخدمين
    all_data = {"users": {}, "migrated_at": datetime.now(timezone.utc).isoformat()}
    user_count = 0
    castle_count = 0

    try:
        users_stream = db.collection("users").stream()
        for u_snap in users_stream:
            uid = u_snap.id
            u_data = u_snap.to_dict() or {}
            all_data["users"][uid] = {
                "profile": u_data,
                "castles": {}
            }
            user_count += 1

            # 3. سحب قلاع كل مستخدم
            try:
                castles_stream = u_snap.reference.collection("castles").stream()
                for c_snap in castles_stream:
                    cid = c_snap.id
                    c_data = c_snap.to_dict() or {}
                    all_data["users"][uid]["castles"][cid] = c_data
                    castle_count += 1
            except Exception as ce:
                print(f"  ⚠️ تعذر قراءة قلاع المستخدم {uid}: {ce}")

            print(f"  📦 المستخدم #{user_count}: {u_data.get('email', uid)} — {len(all_data['users'][uid]['castles'])} قلعة")

    except Exception as e:
        print(f"❌ خطأ أثناء قراءة المستخدمين: {e}")
        if user_count == 0:
            return False

    print(f"\n📊 تم سحب: {user_count} مستخدم و {castle_count} قلعة من Firestore")

    # 4. حفظ نسخة JSON احتياطية
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(DUMPS_DIR, f"firestore_backup_{timestamp}.json")
    try:
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"💾 تم حفظ النسخة الاحتياطية: {backup_path}")
    except Exception as e:
        print(f"⚠️ تعذر حفظ النسخة الاحتياطية: {e}")

    # 5. كتابة البيانات في SQLite
    try:
        from core.database import (
            init_db, create_or_update_user, save_castle,
            upsert_castle_conn_state, upsert_castle_resources
        )
        init_db()

        migrated_users = 0
        migrated_castles = 0

        for uid, user_entry in all_data["users"].items():
            profile = user_entry["profile"]
            sub = profile.get("subscription", {})

            try:
                create_or_update_user(
                    uid=uid,
                    email=str(profile.get("email", "")).strip().lower(),
                    username=str(profile.get("username", "")),
                    phone=str(profile.get("phone", "")),
                    role=str(profile.get("role", "user")),
                    is_banned=bool(profile.get("is_banned", False)),
                    created_at=str(profile.get("created_at", "")),
                    plan_id=str(sub.get("plan_id", "free")),
                    plan_name=str(sub.get("plan_name", "مجاني")),
                    subscription_status=str(sub.get("status", "active")),
                    subscription_started_at=str(sub.get("started_at", "")),
                    subscription_expires_at=str(sub.get("expires_at", "")),
                    max_castles_allowed=int(sub.get("max_castles_allowed", 1)),
                    current_castles_count=int(sub.get("current_castles_count", 0)),
                    pending_castles_count=int(sub.get("pending_castles_count", 0)),
                )
                migrated_users += 1
            except Exception as ue:
                print(f"  ⚠️ تعذر ترحيل المستخدم {uid}: {ue}")

            for cid, c_data in user_entry.get("castles", {}).items():
                try:
                    email = str(c_data.get("email", "")).strip().lower()
                    password = str(c_data.get("password", ""))
                    config = c_data.get("config", {})
                    is_active = c_data.get("is_active", True)
                    created_at = str(c_data.get("created_at", ""))
                    castle_info = c_data.get("castle_info", {})
                    resources = c_data.get("resources", {})
                    bot_status = c_data.get("bot_status", {})

                    save_castle(
                        user_id=uid,
                        castle_id=cid,
                        email=email,
                        password=password,
                        config=json.dumps(config, ensure_ascii=False) if isinstance(config, dict) else str(config),
                        is_active=1 if is_active else 0,
                        created_at=created_at,
                    )

                    # تحديث معلومات القلعة والموارد
                    upsert_castle_resources(
                        email=email,
                        resources=resources,
                        castle_info=castle_info,
                        user_id=uid,
                        castle_id=cid,
                    )

                    # تحديث حالة البوت
                    conn_state = bot_status.get("conn_state", bot_status.get("state", "idle"))
                    msg = bot_status.get("last_run_message", "")
                    upsert_castle_conn_state(
                        email=email,
                        conn_state="idle",  # دائماً idle عند الترحيل
                        message="تم الترحيل بنجاح — جاهز للتشغيل",
                        user_id=uid,
                        castle_id=cid,
                    )

                    migrated_castles += 1
                except Exception as ce:
                    print(f"  ⚠️ تعذر ترحيل القلعة {cid}: {ce}")

        print(f"\n{'=' * 60}")
        print(f"✅ تم الترحيل بنجاح!")
        print(f"   👤 المستخدمين: {migrated_users}/{user_count}")
        print(f"   🏰 القلاع: {migrated_castles}/{castle_count}")
        print(f"   💾 النسخة الاحتياطية: {backup_path}")
        print(f"{'=' * 60}")
        return True

    except ImportError as ie:
        print(f"❌ خطأ استيراد: {ie}")
        print("   تأكد من تحديث core/database.py أولاً بالدوال الجديدة")
        return False
    except Exception as e:
        print(f"❌ خطأ أثناء الكتابة في SQLite: {e}")
        return False


if __name__ == "__main__":
    migrate()
