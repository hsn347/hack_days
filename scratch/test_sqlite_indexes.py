# -*- coding: utf-8 -*-
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "castles.db")

def check_indexes():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c = conn.cursor()

    tables = ['castle_states', 'users']
    for table in tables:
        print(f"=== Table: {table} ===")
        c.execute(f"PRAGMA index_list('{table}')")
        indexes = c.fetchall()
        for idx in indexes:
            idx_name = idx[1]
            print(f"  Index: {idx_name}, Unique: {idx[2]}, Origin: {idx[3]}, Partial: {idx[4]}")
            c.execute(f"PRAGMA index_info('{idx_name}')")
            info = c.fetchall()
            print(f"    Info: {info}")

        c.execute(f"SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='{table}'")
        sqls = c.fetchall()
        for name, sql in sqls:
            print(f"    SQL for {name}: {sql}")

    conn.close()

if __name__ == '__main__':
    check_indexes()
