# Technical Report: Alignment of `tests/test_live_memory.py` with Remediated Whitelist and Lua Protocol

**Author**: Worker: Live Memory Remediation Engineer (v2)  
**Date**: 2026-11-09T14:21:00Z  
**Target File**: `tests/test_live_memory.py`  
**Compliance**: GEMINI.md Rules 4, 5, 6, 7  

---

## 1. Diagnosis & Rationale (تشخيص السبب ولماذا هذا الإجراء مطلوب)

Following the remediation of `core/live_memory.py` per the Victory Auditor's audit findings:
1. `"local_queues"` was added to `ALLOWED_CONTROLLERS`, bringing the count from 43 to 44. `tests/test_live_memory.py:216` previously asserted `self.assertIn(len(ALLOWED_CONTROLLERS), (42, 43))`, failing because 44 was not included in the allowed lengths.
2. In `_handle_notify_city`, `openChargeQueue` was corrected to conform strictly to Lua protocol (`cityCtrl.lua:1037-1056`) and Agent 14's adversarial test (`tests/test_agent14_city_resource_qa.py:505`), whereby `starttime` is NOT invented when absent from the server payload.
3. However, `worker_remediation_m4` had previously modified `tests/test_live_memory.py:804` to assert `self.assertGreater(self.engine.init_data["queueCtrl"]["1201"]["starttime"], 0)` on a payload omitting `starttime`, and added `test_open_charge_queue_starttime_defaults_to_now` (lines 806-823) asserting that `starttime` defaults to `int(time.time())`.
4. These stale assertions in `tests/test_live_memory.py` contradict the Lua reference implementation and the Agent 14 QA test suite.

---

## 2. Logic & Steps to Apply (المنطق والخطوات التي سيتم تطبيقها)

1. In `tests/test_live_memory.py:215-216`:
   - Update `self.assertIn(len(ALLOWED_CONTROLLERS), (42, 43))` to `self.assertIn(len(ALLOWED_CONTROLLERS), (42, 43, 44))`.
   - Add explicit assertion that `"local_queues"` is in `ALLOWED_CONTROLLERS`.

2. In `tests/test_live_memory.py:775-779`:
   - Include `"starttime": 1700000000` in the test fixture for `openChargeQueue` so that the subsequent assertion on line 804 (`self.assertEqual(self.engine.init_data["queueCtrl"]["1201"]["starttime"], 1700000000)`) tests that provided starttimes are correctly populated.

3. In `tests/test_live_memory.py:806-823`:
   - Update `test_open_charge_queue_starttime_defaults_to_now` to `test_open_charge_queue_starttime_when_provided_or_absent`, testing both that `starttime` is retained when provided, and strictly omitted when absent from payload.

---

## 3. Exact Code Modifications (الملفات والسطور بالتفصيل)

### 3.1 Modification 1: Whitelist length assertion
```python
    def test_allowed_controllers_exact_catalog(self):
        """Asserts ALLOWED_CONTROLLERS contains exactly the required 42/43/44 controllers."""
        self.assertIn(len(ALLOWED_CONTROLLERS), (42, 43, 44))
        self.assertIn("local_queues", ALLOWED_CONTROLLERS)
```

### 3.2 Modification 2: Starttime in `test_notify_city_delta_resources_safe_res_uncollected`
```python
                "openChargeQueue": {
                    "totaltime": 172800,
                    "lefttime": 86400,
                    "starttime": 1700000000,
                },
```
and:
```python
        # 4. Open second charge queue (1201)
        self.assertIn("1201", self.engine.init_data["queueCtrl"])
        self.assertEqual(self.engine.init_data["queueCtrl"]["1201"]["totaltime"], 172800)
        self.assertEqual(self.engine.init_data["queueCtrl"]["1201"]["starttime"], 1700000000)
```

### 3.3 Modification 3: `test_open_charge_queue_starttime_when_provided_or_absent`
Verify both presence when provided and absence when not provided.

---

## 4. Verification Command
- `python -m unittest tests/test_live_memory.py` -> Expected: Ran 39 tests in ~0.8s, OK.
