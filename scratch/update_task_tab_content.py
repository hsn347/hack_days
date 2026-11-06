# -*- coding: utf-8 -*-
import os

path = r"e:\osmanli\dashboard\src\components\accounts\TaskTabContent.tsx"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

anchor = "onChange={v => update('alliance', { auto_help: v })}\r\n                size=\"sm\"\r\n              />\r\n            </div>"
if anchor not in text:
    anchor = "onChange={v => update('alliance', { auto_help: v })}\n                size=\"sm\"\n              />\n            </div>"

addition = """

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

if "\r\n" in text:
    addition = addition.replace("\n", "\r\n")

if anchor in text:
    new_text = text.replace(anchor, anchor + addition, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print("SUCCESS")
else:
    print("ANCHOR_NOT_FOUND")

