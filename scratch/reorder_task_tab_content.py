# -*- coding: utf-8 -*-
path = r"e:\osmanli\dashboard\src\components\accounts\TaskTabContent.tsx"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

old_block = """            {/* التبرع للتحالف (auto_help) */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '6px 10px', borderRadius: '9px',
              background: (cfg.alliance.auto_help ?? true) ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
              border: (cfg.alliance.auto_help ?? true) ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.07)',
            }}>
              <div>
                <div style={{ color: '#f0fdf4', fontSize: '12px', fontWeight: 600 }}>{t('tasks.allianceDonation')}</div>
              </div>
              <Toggle
                value={cfg.alliance.auto_help ?? true}
                onChange={v => update('alliance', { auto_help: v })}
                size="sm"
              />
            </div>

            {/* استلام وفتح كنز التحالف (open_treasure) */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '6px 10px', borderRadius: '9px',
              background: (cfg.alliance.open_treasure ?? true) ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
              border: (cfg.alliance.open_treasure ?? true) ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.07)',
            }}>
              <div>
                <div style={{ color: '#f0fdf4', fontSize: '12px', fontWeight: 600 }}>{t('tasks.openAllianceTreasure')}</div>
              </div>
              <Toggle
                value={cfg.alliance.open_treasure ?? true}
                onChange={v => update('alliance', { open_treasure: v })}
                size="sm"
              />
            </div>"""

new_block = """            {/* استلام وفتح كنز التحالف (open_treasure) */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '6px 10px', borderRadius: '9px',
              background: (cfg.alliance.open_treasure ?? true) ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
              border: (cfg.alliance.open_treasure ?? true) ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.07)',
            }}>
              <div>
                <div style={{ color: '#f0fdf4', fontSize: '12px', fontWeight: 600 }}>{t('tasks.openAllianceTreasure')}</div>
              </div>
              <Toggle
                value={cfg.alliance.open_treasure ?? true}
                onChange={v => update('alliance', { open_treasure: v })}
                size="sm"
              />
            </div>

            {/* التبرع للتحالف (auto_help) */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '6px 10px', borderRadius: '9px',
              background: (cfg.alliance.auto_help ?? true) ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.03)',
              border: (cfg.alliance.auto_help ?? true) ? '1px solid rgba(34,197,94,0.18)' : '1px solid rgba(255,255,255,0.07)',
            }}>
              <div>
                <div style={{ color: '#f0fdf4', fontSize: '12px', fontWeight: 600 }}>{t('tasks.allianceDonation')}</div>
              </div>
              <Toggle
                value={cfg.alliance.auto_help ?? true}
                onChange={v => update('alliance', { auto_help: v })}
                size="sm"
              />
            </div>"""

if "\r\n" in text:
    old_block_crlf = old_block.replace("\n", "\r\n")
    new_block_crlf = new_block.replace("\n", "\r\n")
else:
    old_block_crlf = old_block
    new_block_crlf = new_block

if old_block_crlf in text:
    text = text.replace(old_block_crlf, new_block_crlf, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("SUCCESS")
elif old_block in text:
    text = text.replace(old_block, new_block, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("SUCCESS_LF")
else:
    print("NOT_FOUND")

