# -*- coding: utf-8 -*-
import asyncio
import json
import os
import sys
from datetime import datetime

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from core.session_manager import SessionManager
from game_client import GameConnection

async def main():
    email = "samartilleli@yopmail.com"
    sm = SessionManager()
    acc = sm.get_or_login(email)
    if not acc:
        print(f"Account not found: {email}")
        return

    conn = GameConnection(acc)
    if not await conn.connect():
        print("Failed to connect")
        return

    print("=== Connected to samartilleli@yopmail.com ===")

    # 1. 1015/1 init
    res = await conn.query("1015", "1", {"version": "1"}, timeout=8.0)
    data = res.get("data", {}) if res else {}

    print(f"Castle Level: {res.get('castleLevel')}, Kid/MapID: {res.get('mapID')}, PID: {res.get('pid')}")

    # numInfo details
    num_info = data.get("numInfo", [])
    print(f"\n--- numInfo entries ({len(num_info)}) ---")
    for idx, ni in enumerate(num_info):
        st = ni.get("setType")
        cover_num = ni.get("coverNum")
        info_dict = ni.get("numInfo", {})
        print(f"[{idx}] setType={st}, coverNum={cover_num}, details={info_dict}")

    # list details
    mlist = data.get("list", [])
    print(f"\n--- data.list entries ({len(mlist)}) ---")
    for i, m in enumerate(mlist):
        mid = m.get("mid")
        m_type = m.get("mailType")
        title = m.get("title")
        sub_title = m.get("subTitle")
        sender = m.get("sender")
        is_view = m.get("isView")
        is_lock = m.get("isLock")
        is_reward = m.get("isReward")
        reward = m.get("reward")
        t_raw = m.get("time")
        t_str = datetime.fromtimestamp(t_raw).strftime("%Y-%m-%d %H:%M:%S") if t_raw else "N/A"
        m_data = m.get("data", {})
        data_summary = list(m_data.keys()) if isinstance(m_data, dict) else str(type(m_data))
        print(f"#{i+1}: mid={mid} | mailType={m_type} | sender={sender} | time={t_str} | isView={is_view} | isLock={is_lock} | isReward={is_reward}")
        print(f"     title={title} | subTitle={sub_title}")
        print(f"     data keys={data_summary}")
        if reward:
            print(f"     reward={reward}")
        if isinstance(m_data, dict):
            # Print brief details of specific data types
            if "scoreInfo" in m_data or "romanSoulInfo" in m_data:
                print(f"     romanSoul: wave={m_data.get('romanSoulInfo', {}).get('wave')}, score={m_data.get('scoreInfo', {}).get('score')}")
            if "monsterInfo" in m_data:
                print(f"     monster: id={m_data.get('monsterInfo', {}).get('id')}, fightResult={m_data.get('fightResult')}")
            if "resourceInfo" in m_data:
                print(f"     resource: id={m_data.get('resourceInfo', {}).get('id')}, resSetType={m_data.get('resourceInfo', {}).get('resSetType')}")

    # 2. Test fetching more or specific setTypes
    print("\n--- Testing queries with various setType values ---")
    for st in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
        r_st = await conn.query("1015", "1", {"setType": st, "version": "1"}, timeout=5.0)
        d_st = r_st.get("data", {}) if r_st else {}
        l_st = d_st.get("list", [])
        print(f"Query 1015/1 setType={st}: err={r_st.get('err') if r_st else 'None'}, returned {len(l_st)} items")

    # 3. What about REQ_VIEW_MAIL_SET (1015/10) followed by 1015/1?
    print("\n--- Testing 1015/10 then 1015/1 ---")
    r10 = await conn.query("1015", "10", {"setType": 7, "version": "1"}, timeout=5.0)
    print(f"1015/10 setType=7 response: {r10}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
