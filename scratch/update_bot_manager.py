# -*- coding: utf-8 -*-
with open('bot_manager.py', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Update DEFAULT_FIREBASE_USER_CONFIG
target1 = """    # 🏦 19. مهمة دار الادخار وبنك التوفير (Savings Bank)
    "savings_bank": {
        "enabled": False,            # تفعيل/تعطيل استثمار الذهب وسحب الأرباح في دار الادخار تلقائياً
        "days": 7,                   # خطة الاستثمار والمدة المختارة بالأيام
    },"""

replacement1 = """    # 🏦 19. مهمة دار الادخار وبنك التوفير (Savings Bank)
    "savings_bank": {
        "enabled": False,            # تفعيل/تعطيل استثمار الذهب وسحب الأرباح في دار الادخار تلقائياً
        "days": 7,                   # خطة الاستثمار والمدة المختارة بالأيام
        "deposit": 2000,             # مبلغ الذهب المراد إيداعه (100 - 6000)
    },"""

if target1 not in c:
    target1_lf = target1.replace('\r\n', '\n')
    c_lf = c.replace('\r\n', '\n')
    assert target1_lf in c_lf, "target1 not found"
    c = c_lf.replace(target1_lf, replacement1.replace('\r\n', '\n'), 1)
else:
    c = c.replace(target1, replacement1, 1)

# 2. Update step_19_savings_bank_task
target2 = """        raw_days = sb_cfg.get("days", DEFAULT_SAVINGS_DAYS)
        target_days = parse_savings_days(raw_days)

        plan_info = SAVINGS_PLANS.get(target_days, SAVINGS_PLANS[DEFAULT_SAVINGS_DAYS])
        log.info(f"🏦 بدء مهمة دار الادخار (فحص الأرباح وإيداع الذهب بخطة: {plan_info['name']})...")

        task = SavingsBankTask(self.conn, {"days": target_days})"""

replacement2 = """        raw_days = sb_cfg.get("days", DEFAULT_SAVINGS_DAYS)
        target_days = parse_savings_days(raw_days)

        raw_deposit = sb_cfg.get("deposit")
        try:
            deposit_val = int(raw_deposit) if raw_deposit is not None else 2000
            deposit_val = max(100, min(6000, deposit_val))
        except (ValueError, TypeError):
            deposit_val = 2000

        plan_info = SAVINGS_PLANS.get(target_days, SAVINGS_PLANS[DEFAULT_SAVINGS_DAYS])
        log.info(f"🏦 بدء مهمة دار الادخار (فحص الأرباح وإيداع الذهب بخطة: {plan_info['name']} بمبلغ: {deposit_val:,} ذهب)...")

        task = SavingsBankTask(self.conn, {"days": target_days, "deposit": deposit_val})"""

if target2 not in c:
    target2_lf = target2.replace('\r\n', '\n')
    c_lf = c.replace('\r\n', '\n')
    assert target2_lf in c_lf, "target2 not found"
    c = c_lf.replace(target2_lf, replacement2.replace('\r\n', '\n'), 1)
else:
    c = c.replace(target2, replacement2, 1)

with open('bot_manager.py', 'w', encoding='utf-8') as f:
    f.write(c)

print("SUCCESS")

