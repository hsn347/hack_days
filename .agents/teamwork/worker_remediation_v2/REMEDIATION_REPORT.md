# Technical Remediation Report: Live Memory Remediation (v2)

**Author**: Worker: Live Memory Remediation Engineer (v2)  
**Date**: 2026-11-09T14:19:00Z  
**Target File**: `core/live_memory.py`  
**Compliance**: GEMINI.md Rules 4, 5, 6, 7  

---

## 1. Diagnosis & Rationale (تشخيص السبب ولماذا هذا الإجراء مطلوب)

The independent Victory Auditor (`victory_auditor/handoff.md`) identified two distinct failures during independent test suite execution:

### 1.1 Failure in `tests/test_agent14_city_resource_qa.py`
- **Error**:
  ```
  FAIL: test_adversarial_open_charge_queue_missing_starttime (tests.test_agent14_city_resource_qa.TestCityResourceDeltaQA.test_adversarial_open_charge_queue_missing_starttime)
  AssertionError: 'starttime' unexpectedly found in {'totaltime': 172800, 'lefttime': 86400, 'starttime': 1794233406} : starttime is missing from openChargeQueue payload
  ```
- **Root Cause**: In `core/live_memory.py:646-653`, the notification handler `_handle_notify_city` for `openChargeQueue` was previously modified to inject a fallback `starttime = int(time.time())` whenever `starttime` was missing or `<= 0`. However, in the canonical Lua protocol (`cityCtrl.lua:1037-1056`), `openChargeQueue` simply stores the table payload received from the server without inventing a `starttime` timestamp. Furthermore, `test_adversarial_open_charge_queue_missing_starttime` explicitly tests that when `starttime` is absent in the payload, `cityCtrl["queue"]["1201"]` must not contain an invented `starttime`.
- **Requirement**: Only populate `charge_info["starttime"]` if `"starttime"` is explicitly present in the `openChargeQueue` item and is not `None`.

### 1.2 Failure in `tests/test_live_conn_agent11.py`
- **Error**:
  ```
  FAIL: test_06_real_session_cache_live_auth_attempt (tests.test_live_conn_agent11.TestLiveConnectionAndInitVerification.test_06_real_session_cache_live_auth_attempt)
  AssertionError: 'local_queues' not found in frozenset({...}) : Non-whitelisted controller leaked in live connection: local_queues
  ```
- **Root Cause**: In `core/live_memory.py:998`, the memory engine stores the synthesized local march queues into `self.init_data`:
  ```python
  if self.local_queues_map:
      self.init_data["local_queues"] = list(self.local_queues_map.values())
  ```
  However, `"local_queues"` was omitted from `ALLOWED_CONTROLLERS` in `core/live_memory.py:51-102`. When `test_live_conn_agent11.py` connects to the real live server using a session from `session_cache.json`, it asserts that every controller/key stored in `init_data` exists in `ALLOWED_CONTROLLERS`. Because `"local_queues"` was absent from the whitelist, the isolation assertion failed.
- **Requirement**: Add `"local_queues"` to `ALLOWED_CONTROLLERS` under the Internal State Keys section in `core/live_memory.py`. This brings the catalog count from 42 to 43, which is explicitly supported by `test_allowed_controllers_exact_catalog` (`self.assertIn(len(ALLOWED_CONTROLLERS), (42, 43))`).

---

## 2. Remediation Logic & Applied Steps (المنطق والخطوات التي سيتم تطبيقها)

1. **Step 1 — Whitelist Update**:
   - In `core/live_memory.py`, locate `ALLOWED_CONTROLLERS` (lines 98-102).
   - Add `"local_queues"` to the frozenset under `# --- Aliases & Internal State Keys ---`.
   - Update the comment from `(3)` to `(4)` and total from `42` to `43`.

2. **Step 2 — `openChargeQueue` Handling**:
   - In `core/live_memory.py`, locate `_handle_notify_city` around line 643.
   - Replace the unconditional injection of `starttime = int(time.time())` with a conditional assignment:
     ```python
     # 6. Second (charge) build queue
     if "openChargeQueue" in delta and isinstance(delta["openChargeQueue"], dict):
         charge_info = copy.deepcopy(delta["openChargeQueue"])
         if "starttime" in delta["openChargeQueue"] and delta["openChargeQueue"]["starttime"] is not None:
             try:
                 charge_info["starttime"] = int(float(delta["openChargeQueue"]["starttime"]))
             except (ValueError, TypeError):
                 pass

         city_ctrl.setdefault("queue", {})["1201"] = charge_info
         charge_info_q = copy.deepcopy(charge_info)
         charge_info_q["qtype"] = "1201"
         queue_ctrl = self.init_data.setdefault("queueCtrl", {})
         if isinstance(queue_ctrl, dict):
             queue_ctrl["1201"] = charge_info_q
     ```
   - If `"starttime"` was NOT in `delta["openChargeQueue"]`, `charge_info` will not have `"starttime"`.
   - If `"starttime"` WAS in `delta["openChargeQueue"]` and was valid, `charge_info["starttime"]` is parsed cleanly as an integer.

3. **Step 3 — Direct Tool Editing**:
   - Use `edit_file` exclusively for modifying `core/live_memory.py` (Rule 6).
   - Never use python scripts or temporary file replacers.

4. **Step 4 — Verification**:
   - Execute all 9 test suites locally (Rule 4: no deployment).
   - Ensure 100% pass rate with 0 failures and 0 errors across all suites.

---

## 3. Exact Code Modifications & Commands (الملفات والسطور والأوامر بالتفصيل)

### 3.1 Modification 1: `ALLOWED_CONTROLLERS` in `core/live_memory.py`
**Target lines (around 50 and 98-102)**:
```python
# Authoritative frozenset of exactly 42 controllers required by bot tasks & systems
ALLOWED_CONTROLLERS: FrozenSet[str] = frozenset({
```
to:
```python
# Authoritative frozenset of exactly 43 controllers required by bot tasks & systems
ALLOWED_CONTROLLERS: FrozenSet[str] = frozenset({
```
and:
```python
    # --- Aliases & Internal State Keys (3) ---
    "lord",
    "loginDataInitCtrl",
    "item_sign",
})
```
to:
```python
    # --- Aliases & Internal State Keys (4) ---
    "lord",
    "loginDataInitCtrl",
    "item_sign",
    "local_queues",
})
```

### 3.2 Modification 2: `openChargeQueue` in `core/live_memory.py`
**Target lines (around 644-653)**:
```python
            # 6. Second (charge) build queue
            if "openChargeQueue" in delta and isinstance(delta["openChargeQueue"], dict):
                charge_info = copy.deepcopy(delta["openChargeQueue"])
                try:
                    starttime = int(charge_info.get("starttime", 0) or 0)
                except (ValueError, TypeError):
                    starttime = 0
                if starttime <= 0:
                    starttime = int(time.time())
                charge_info["starttime"] = starttime

                city_ctrl.setdefault("queue", {})["1201"] = charge_info
```
to:
```python
            # 6. Second (charge) build queue
            if "openChargeQueue" in delta and isinstance(delta["openChargeQueue"], dict):
                charge_info = copy.deepcopy(delta["openChargeQueue"])
                if "starttime" in delta["openChargeQueue"] and delta["openChargeQueue"]["starttime"] is not None:
                    try:
                        charge_info["starttime"] = int(float(delta["openChargeQueue"]["starttime"]))
                    except (ValueError, TypeError):
                        pass

                city_ctrl.setdefault("queue", {})["1201"] = charge_info
```

### 3.3 Verification Commands to Run
1. `python -m unittest tests/test_agent14_city_resource_qa.py` -> Expected: Ran 20 tests, OK.
2. `python -m unittest tests/test_live_conn_agent11.py` -> Expected: Ran 6 tests, OK.
3. `python -m unittest tests/test_live_memory.py` -> Expected: Ran 39 tests, OK.
4. `python -m unittest tests/test_game_client_hygiene.py` -> Expected: Ran 7 tests, OK.
5. `python -m unittest tests/test_building_lifecycle_qa.py` -> Expected: Ran 10 tests, OK.
6. `python -m unittest tests/test_gate_fallback_empirical.py` -> Expected: Ran 14 tests, OK.
7. `python -m unittest tests/test_live_memory_marches_army.py` -> Expected: Ran 15 tests, OK.
8. `python -m unittest tests/test_live_socket_spy.py` -> Expected: Ran 14 tests, OK.
9. `python -m unittest tests/test_concurrency_stress.py` -> Expected: Ran 7 tests, OK.
