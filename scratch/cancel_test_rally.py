import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from auto_elf_boss import sdk_login
from game_client import GameConnection, AccountSession

async def main():
    auth = sdk_login("fahed.K140@gmail.com", "mn@123450")
    acc = AccountSession("fahed.K140@gmail.com", auth['userId'], auth['sessionId'])
    conn = GameConnection(acc)
    await conn.connect()
    for _ in range(10):
        await asyncio.sleep(0.3)
        if "cityCtrl" in conn.init_data:
            break

    r_q = await conn.query('1007', '16', {}, timeout=5)
    print("Queues 1007/16:", r_q)

    # If there is a rally, let's cancel/disband it so we don't leave troops hanging!
    # Or recall it
    if r_q and r_q.get('data'):
        for q in r_q['data']:
            qid = q.get('queueId') or q.get('id')
            print("Active queue:", qid, q.get('moveLineType'), q.get('status'))
            # cmd 1007, subcmd 4 is cancel rally / disband mass
            # or 1007/3 is recall
            r_cancel = await conn.query('1007', '4', {"queueId": qid}, timeout=4)
            print(f"Cancel rally {qid} (1007/4):", r_cancel)

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
