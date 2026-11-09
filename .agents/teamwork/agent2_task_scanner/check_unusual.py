import json

with open(r"e:\osmanli\.agents\teamwork\agent2_task_scanner\scan_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Let's inspect all controller references in detail
with open(r"e:\osmanli\.agents\teamwork\agent2_task_scanner\deep_scan.py", "r", encoding="utf-8") as f:
    pass

# We can re-scan and get the exact line snippets for each controller
import re, glob, os

all_files = glob.glob(r"e:\osmanli\tasks\*.py") + [r"e:\osmanli\bot_manager.py", r"e:\osmanli\game_client.py"]

ctrl_details = {}

for fpath in all_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        for lno, line in enumerate(f, 1):
            for ctrl in data["controllers"]:
                if ctrl in line and any(k in line for k in ["init_data", "init", "conn", "retdata", "data"]):
                    ctrl_details.setdefault(ctrl, []).append((fname, lno, line.strip()))

# Print details for controllers with < 10 references or unusual names
print("=== DETAILED INSPECTION FOR UNUSUAL CONTROLLERS ===")
unusual = [c for c in data["controllers"] if c in [
    "lord", "reslist", "saferes", "cumulateRewardData", "item_sign", "itemShop",
    "loginDataInitCtrl", "godBeastCtrl", "allianceTreasureCtrl", "heroEquipAgCtrl",
    "equipmentCtrl", "shopItemBuyTimesMgr", "badgeExchangeCtrl", "activityShowCtrl",
    "heroTacticalHallAgCtrl", "heroTacticalHallCtrl", "troyTreasureAgCtrl",
    "savingsBankAgCtrl", "playerCtrl", "exchangeStoreAgCtrl", "fieldShopCtrl",
    "runeForgeAgCtrl", "heroVoyageAgCtrl", "pyramidCtrl", "salesRoomAgCtrl",
    "buyStaminaCtrl"
]]

for c in sorted(unusual):
    print(f"\n--- {c} ---")
    for fname, lno, line in ctrl_details.get(c, [])[:5]:
        print(f"  {fname}:{lno} -> {line}")
