import json, sys
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\Computer Home\.gemini\antigravity-ide\brain\801b092d-99bc-4b80-bea3-7bd0e962e35e\.system_generated\logs\transcript.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f):
        d = json.loads(line)
        c = d.get('content', '')
        t = d.get('type')
        if any(x in c for x in ['57', '45', '30']) and t in ['USER_INPUT', 'ASK_QUESTION', 'PLANNER_RESPONSE']:
            if 'USER' in t or 'ASK' in t:
                print(f"--- Line {idx} [{t}] ---")
                print(c[:300])
