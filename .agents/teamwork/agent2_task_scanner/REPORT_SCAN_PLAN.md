# Technical Report: Bot Task Audit & Controller Whitelist Architecture Plan

## 1. Objective & Diagnosis
To achieve zero memory bloat, prevent memory leaks, and ensure 100% reliable bot loop execution, we are auditing all bot tasks in `e:\osmanli\tasks\`, `e:\osmanli\bot_manager.py`, and `e:\osmanli\game_client.py`.
The server transmits numerous controllers during login, regular updates, and async notifications. Unrestricted retention causes memory bloat and unstructured dictionary mutations. Conversely, dropping essential controllers would break bot automation tasks.

## 2. Methodology & Actions
1. **File Inventory**: Catalog every task file in `tasks/` and core modules (`game_client.py`, `bot_manager.py`, `task_context.py`).
2. **Access Pattern Analysis**: Scan for all occurrences of:
   - `init_data` access (`.init_data.get(...)`, `['...']`, `init_data[...]`)
   - `send_command`, `call`, and protocol command IDs.
3. **Whitelist Construction**:
   - `ALLOWED_CONTROLLERS`: Comprehensive set of controllers required by any task, UI, or core subsystem.
   - `DROPPED_CONTROLLERS`: Noise, high-frequency chat, system broadcast, and unreferenced tracking controllers.
4. **Critical Startup Gate & Fallback Queries**:
   - `CRITICAL_STARTUP_CONTROLLERS`: Controllers that must be fully loaded before task pipelines start.
   - Fallback command mapping for each critical controller.
5. **Decoupling & Safety Verification**: Verify GEMINI.md Rule 7 (Elf task decoupled from march manager) and confirm zero regressions.

## 3. Planned Commands & Inspection
- Directory listing and text scanning across `tasks/` and root python files.
- Deliver final specification in `CONTROLLER_WHITELIST_SPEC.md`.
