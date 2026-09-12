import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio
from auto_elf_boss import sdk_login
from game_client import GameConnection, AccountSession

async def main():
    auth = sdk_login("fahed.K140@gmail.com", "mn@123450")
    if not auth.get('success'):
        print("Login failed:", auth)
        return
    acc = AccountSession("fahed.K140@gmail.com", auth['userId'], auth['sessionId'])
    conn = GameConnection(acc)
    if not await conn.connect():
        print("Gate failed")
        return
    for _ in range(10):
        await asyncio.sleep(0.3)
        if "cityCtrl" in conn.init_data:
            break

    # check formation 1
    r_form1 = await conn.query('1005', '7', {"compiletype": 1}, timeout=5)
    print("=== Formation 1 ===")
    print(r_form1)

    # check queues 1007/16
    r_q = await conn.query('1007', '16', {}, timeout=5)
    print("=== Queues (1007/16) ===")
    print(r_q)

    # check city marches
    r_city = await conn.query('1007', '1', {}, timeout=5)
    print("=== Marches (1007/1) ===")
    print(r_city)

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
