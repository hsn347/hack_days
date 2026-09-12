import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from auto_elf_boss import sdk_login
from game_client import GameConnection, AccountSession
from tasks.elf_boss import ElfBossTask

async def main():
    auth = sdk_login("fahed.K140@gmail.com", "mn@123450")
    acc = AccountSession("fahed.K140@gmail.com", auth['userId'], auth['sessionId'])
    conn = GameConnection(acc)
    await conn.connect()
    for _ in range(10):
        await asyncio.sleep(0.3)
        if "cityCtrl" in conn.init_data:
            break

    task_cfg = {
        "formation_id": 1,
        "boss_type": 10,
        "count": 1,
        "max_march_troops": 200000,
        "delay": 2.0
    }
    task = ElfBossTask(conn, task_cfg)
    await task.on_start()
    res = await task.run()
    print("ElfBossTask run result:", res.message, res.status, res.data)

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
