# -*- coding: utf-8 -*-
import sqlite3
import json

db_path = r"e:\osmanli\database\castles.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT castle_id, config FROM castle_states WHERE config IS NOT NULL AND config != ''")
rows = cur.fetchall()

updated_count = 0
for cid, cfg_str in rows:
    try:
        cfg = json.loads(cfg_str)
        if isinstance(cfg, dict):
            alliance_cfg = cfg.setdefault("alliance", {"enabled": True, "gold_donations": 0})
            if isinstance(alliance_cfg, dict):
                if "open_treasure" not in alliance_cfg:
                    alliance_cfg["open_treasure"] = True
                    cur.execute(
                        "UPDATE castle_states SET config = ? WHERE castle_id = ?",
                        (json.dumps(cfg, ensure_ascii=False), cid)
                    )
                    updated_count += 1
    except Exception as e:
        print(f"Error for castle {cid}: {e}")

conn.commit()
conn.close()
print(f"UPDATED_RECORDS: {updated_count} / {len(rows)}")

