import json

with open(r'e:\osmanli\login_all_packets.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find packet with heroCtrl
heroCtrl = data[1]['data']['retdata']['heroCtrl']

print(f"Total heroes in heroCtrl: {len(heroCtrl)}")

hero_list = []
all_skill_ids = set()

for h in heroCtrl:
    hid = h.get('id')
    lv = h.get('lv')
    star = h.get('star')
    skills = h.get('skillList', {})
    awaken = h.get('awakenSkill', {})
    
    skill_info = []
    for slot, sdata in skills.items():
        sid = sdata.get('id')
        slv = sdata.get('lv')
        all_skill_ids.add(sid)
        skill_info.append({'slot': slot, 'id': sid, 'lv': slv})
        
    awaken_info = []
    for slot, adata in awaken.items():
        aid = adata.get('id')
        alv = adata.get('lv')
        all_skill_ids.add(aid)
        awaken_info.append({'slot': slot, 'id': aid, 'lv': alv})
        
    hero_list.append({
        'id': hid,
        'lv': lv,
        'star': star,
        'skills': skill_info,
        'awaken': awaken_info
    })

print(f"Total unique skills found: {len(all_skill_ids)}")
print(f"Hero IDs: {[h['id'] for h in hero_list]}")

with open(r'e:\osmanli\extracted_heroes_and_skills.json', 'w', encoding='utf-8') as out:
    json.dump({'heroes': hero_list, 'skills': list(all_skill_ids)}, out, indent=2)
