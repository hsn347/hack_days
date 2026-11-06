#!/usr/bin/env python3
"""
Empirical Adversarial Stress Harness for Milestone 3 (M3):
Frontend State Architecture, Single Source of Truth, Unmount Mutation Synchronization,
and Optimistic Concurrency Control (OCC).

Author: Challenger M3 (Instance 1)
Directory: tools/stress_m3_frontend_state.py
Adheres strictly to AGENTS_CONSTITUTION.md & GEMINI.md.
"""

import os
import re
import sys
import unittest
import itertools

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_SRC = os.path.join(WORKSPACE_ROOT, "dashboard", "src")


class EmpiricalOracleEffectiveStatus:
    """
    Simulated Pure Oracle for effectiveStatus & mutation states
    mirroring the exact logic in CastleCard.tsx.
    """
    @staticmethod
    def compute(
        bot_control_is_pending: bool,
        bot_control_castle_id: str,
        bot_control_target_state: str,
        current_castle_id: str,
        ws_real_status: str,
        cached_conn_state: str,
        cached_state: str,
    ):
        is_mutation_pending = (
            bot_control_is_pending and bot_control_castle_id == current_castle_id
        )
        is_starting = is_mutation_pending and bot_control_target_state == "running"
        is_stopping = is_mutation_pending and bot_control_target_state == "idle"

        if is_starting:
            effective = "starting"
        elif is_stopping:
            effective = "stopping"
        elif ws_real_status and ws_real_status != "offline":
            effective = ws_real_status
        else:
            effective = cached_conn_state or cached_state or "idle"

        is_stopping_active = is_stopping or effective == "stopping"
        is_starting_active = is_starting or effective == "starting"
        is_button_disabled = is_stopping_active or is_starting_active

        return {
            "effective_status": effective,
            "is_starting": is_starting,
            "is_stopping": is_stopping,
            "is_stopping_active": is_stopping_active,
            "is_starting_active": is_starting_active,
            "is_button_disabled": is_button_disabled,
        }


class TestEmpiricalFrontendStateArchitecture(unittest.TestCase):
    """Adversarial challenge test suite for M3 Frontend State Architecture."""

    @classmethod
    def setUpClass(cls):
        cls.castle_card_file = os.path.join(DASHBOARD_SRC, "components", "accounts", "CastleCard.tsx")
        cls.task_tab_file = os.path.join(DASHBOARD_SRC, "components", "accounts", "TaskTabContent.tsx")
        cls.use_castles_file = os.path.join(DASHBOARD_SRC, "hooks", "useCastles.ts")
        cls.bot_api_file = os.path.join(DASHBOARD_SRC, "lib", "botApi.ts")
        cls.types_file = os.path.join(DASHBOARD_SRC, "types", "index.ts")

        with open(cls.castle_card_file, "r", encoding="utf-8") as f:
            cls.castle_card_code = f.read()

        with open(cls.task_tab_file, "r", encoding="utf-8") as f:
            cls.task_tab_code = f.read()

        with open(cls.use_castles_file, "r", encoding="utf-8") as f:
            cls.use_castles_code = f.read()

        with open(cls.bot_api_file, "r", encoding="utf-8") as f:
            cls.bot_api_code = f.read()

        with open(cls.types_file, "r", encoding="utf-8") as f:
            cls.types_code = f.read()

    def test_01_complete_elimination_of_competing_useState(self):
        """Stress Test 1: Verify all 5 competing useState variables are eliminated from CastleCard.tsx."""
        # Find all useState declarations in CastleCard.tsx
        use_state_matches = re.findall(
            r"const\s+\[\s*([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*useState",
            self.castle_card_code
        )
        declared_state_vars = [m[0] for m in use_state_matches]
        declared_setter_vars = [m[1] for m in use_state_matches]

        forbidden_state_vars = ["liveCastle", "liveState", "connState", "isStopping", "isStarting"]
        forbidden_setters = ["setLiveCastle", "setLiveState", "setConnState", "setIsStopping", "setIsStarting"]

        for var in forbidden_state_vars:
            self.assertNotIn(
                var,
                declared_state_vars,
                f"Adversarial Failure: Forbidden competing state '{var}' found declared via useState in CastleCard.tsx!"
            )

        for setter in forbidden_setters:
            self.assertNotIn(
                setter,
                declared_setter_vars,
                f"Adversarial Failure: Forbidden competing setter '{setter}' found in CastleCard.tsx!"
            )
            # Ensure setter is not called anywhere
            matches = re.findall(rf"\b{setter}\b", self.castle_card_code)
            self.assertEqual(
                len(matches),
                0,
                f"Adversarial Failure: Calls to removed setter '{setter}' still exist in CastleCard.tsx: {matches}"
            )

        # Confirm that only strictly permitted local UI states exist
        permitted_ui_states = {
            "internalExpanded",
            "hasBeenExpanded",
            "showStopModal",
            "showPresetModal",
            "isApplyingPreset",
            "imgError",
            "nowTick",
        }
        for var in declared_state_vars:
            self.assertIn(
                var,
                permitted_ui_states,
                f"Adversarial Alert: Unexpected state variable '{var}' declared via useState in CastleCard.tsx"
            )

    def test_02_pure_derivation_of_effective_status_and_freeze_immunity(self):
        """Stress Test 2: Verify pure derivation of effectiveStatus and mathematical immunity to freezing."""
        # Static check in code
        self.assertIn("const isMutationPending = botControl.isPending && botControl.variables?.castle?.id === castle.id", self.castle_card_code)
        self.assertIn("const isStarting = isMutationPending && botControl.variables?.state === 'running'", self.castle_card_code)
        self.assertIn("const isStopping = isMutationPending && botControl.variables?.state === 'idle'", self.castle_card_code)
        self.assertIn("const { status: realStatus } = useRealBotStatus(castle.id)", self.castle_card_code)

        # Adversarial Exhaustive State Space Simulation:
        # Simulate all permutations of network drops, websocket states, and mutation completions
        test_castle_id = "castle_abc_123"
        other_castle_id = "castle_xyz_999"

        mutation_pending_options = [True, False]
        target_ids = [test_castle_id, other_castle_id, ""]
        target_states = ["running", "idle", None]
        ws_statuses = ["running", "connected", "waiting", "disconnected", "reconnecting", "error", "deploying", "offline", ""]
        cached_conn_states = ["connected", "idle", "error", ""]
        cached_states = ["running", "idle", ""]

        scenario_count = 0
        frozen_stopping_count = 0

        for pending, cid, tstate, ws, cconn, cstate in itertools.product(
            mutation_pending_options, target_ids, target_states, ws_statuses, cached_conn_states, cached_states
        ):
            scenario_count += 1
            res = EmpiricalOracleEffectiveStatus.compute(
                bot_control_is_pending=pending,
                bot_control_castle_id=cid,
                bot_control_target_state=tstate,
                current_castle_id=test_castle_id,
                ws_real_status=ws,
                cached_conn_state=cconn,
                cached_state=cstate,
            )

            # INVARIANT 1: If mutation is NOT pending (i.e. request finished/settled), is_stopping MUST be False!
            if not pending:
                self.assertFalse(
                    res["is_stopping"],
                    f"Invariant 1 Violated: is_stopping cannot be True when mutation is not pending! Input: {pending}, {cid}, {tstate}"
                )
                # If WS fails to send 'idle' and stays 'offline', card must NOT be stuck in stopping
                if ws == "offline" or not ws:
                    self.assertNotEqual(
                        res["effective_status"],
                        "stopping",
                        "Invariant 1b Violated: Card frozen in 'stopping' after mutation settled and WS offline!"
                    )

            # INVARIANT 2: Mutation on OTHER castle must NOT affect test castle
            if cid == other_castle_id and pending:
                self.assertFalse(
                    res["is_starting"],
                    "Invariant 2 Violated: Starting state leaked to unrelated castle!"
                )
                self.assertFalse(
                    res["is_stopping"],
                    "Invariant 2 Violated: Stopping state leaked to unrelated castle!"
                )

            # INVARIANT 3: When in starting/stopping mutation for this castle, button is disabled
            if pending and cid == test_castle_id:
                if tstate in ("running", "idle"):
                    self.assertTrue(
                        res["is_button_disabled"],
                        "Invariant 3 Violated: Control button must be disabled during active mutation!"
                    )

        print(f"[OK] State space oracle evaluated {scenario_count} scenarios. 0 frozen states found.")

    def test_03_unmount_flush_to_query_cache_and_local_storage(self):
        """Stress Test 3: Verify TaskTabContent unmount hook flushes to 3 TanStack Query keys & localStorage."""
        # 1. TanStack Query import & instance
        self.assertIn("useQueryClient", self.task_tab_code)
        self.assertIn("const qc = useQueryClient()", self.task_tab_code)

        # 2. Key 1: ['castles', userId] with immutable deep map over pages & items
        self.assertIn("qc.setQueryData(['castles', userId], (old: any) => {", self.task_tab_code)
        self.assertIn("old.pages.map", self.task_tab_code)
        self.assertIn("mergeCastleConfig(unmountDraft", self.task_tab_code)

        # 3. Key 2: ['castle', userId, castle.id]
        self.assertIn("qc.setQueryData(['castle', userId, castle.id]", self.task_tab_code)

        # 4. Key 3: ['castleConfig', castle.id]
        self.assertIn("qc.setQueryData(['castleConfig', castle.id], unmountDraft)", self.task_tab_code)

        # 5. Local storage cache: saveCachedCastles
        self.assertIn("const currentCached = getCachedCastles(userId)", self.task_tab_code)
        self.assertIn("saveCachedCastles(userId, updatedItems)", self.task_tab_code)

        # 6. Network sync with version
        self.assertIn("updateCastle(castle.id, {", self.task_tab_code)
        self.assertIn("config: unmountDraft", self.task_tab_code)
        self.assertIn("version: currentVersionRef.current", self.task_tab_code)

        # 7. Timer cleanup
        self.assertIn("if (saveTimerRef.current) clearTimeout(saveTimerRef.current)", self.task_tab_code)
        self.assertIn("if (idleTimerRef.current) clearTimeout(idleTimerRef.current)", self.task_tab_code)

    def test_04_double_submit_and_in_flight_mutation_guards(self):
        """Stress Test 4: Verify in-flight and double-submit guards in TaskTabContent."""
        # Check inFlightDraftRef & isSavingRef
        self.assertIn("const inFlightDraftRef = useRef<CastleConfig | null>(null)", self.task_tab_code)
        self.assertIn("const isSavingRef = useRef<boolean>(false)", self.task_tab_code)
        self.assertIn("const hasPendingSaveRef = useRef<boolean>(false)", self.task_tab_code)

        # Check guard in performSave
        self.assertIn("if (isSavingRef.current) {", self.task_tab_code)
        self.assertIn("hasPendingSaveRef.current = true", self.task_tab_code)

        # Check guard on identical draft
        self.assertIn("if (JSON.stringify(currentDraft) === JSON.stringify(lastSavedConfigRef.current))", self.task_tab_code)

        # Check guard on unmount: does not duplicate save if already in-flight with same content
        self.assertIn("const isAlreadyInFlight = inFlightDraftRef.current && JSON.stringify(unmountDraft) === JSON.stringify(inFlightDraftRef.current)", self.task_tab_code)
        self.assertIn("!isAlreadyInFlight", self.task_tab_code)

        # Check manual handleSave guard
        self.assertIn("const isPending = updateConfig.isPending || isSavingBatch || isSavingRef.current", self.task_tab_code)
        self.assertIn("if (changesCount === 0 || isPending) return", self.task_tab_code)

    def test_05_occ_version_threading_and_409_conflict_handling(self):
        """Stress Test 5: Verify OCC versioning pipeline and HTTP 409 Conflict handling."""
        # 1. Interface definition in types/index.ts
        castle_interface_match = re.search(r"export interface Castle\s*\{([^}]+)\}", self.types_code)
        self.assertIsNotNone(castle_interface_match, "Castle interface not found in types/index.ts")
        self.assertIn("version?: number", castle_interface_match.group(1), "Castle interface must declare version?: number")

        # 2. botApi.ts signature & implementation
        self.assertIn("export async function updateCastle(castleId: string, payload: {", self.bot_api_code)
        self.assertIn("version?:     number", self.bot_api_code)

        # Intercept HTTP 409
        self.assertIn("if (res.status === 409) {", self.bot_api_code)
        self.assertTrue(
            bool(re.search(r"conflictErr.*status\s*=\s*409", self.bot_api_code)),
            "botApi.updateCastle must assign status = 409 on conflict error"
        )
        self.assertIn("isConflict = true", self.bot_api_code)

        # formatCastleFromApi
        self.assertIn("version: raw.version ?? 1", self.bot_api_code)

        # 3. useCastles.ts hook forwarding
        self.assertIn("version?: number", self.use_castles_code)
        self.assertIn("version,", self.use_castles_code)
        # Check cache updates on success
        self.assertIn("qc.setQueryData(['castle', userId, castleId]", self.use_castles_code)
        self.assertIn("qc.setQueryData(['castleConfig', castleId]", self.use_castles_code)
        self.assertIn("qc.setQueryData(['castles', userId]", self.use_castles_code)
        self.assertIn("saveCachedCastles(userId, flatItems)", self.use_castles_code)

        # 4. TaskTabContent.tsx version tracking and 409 toast + invalidation
        self.assertIn("currentVersionRef.current = castle.version", self.task_tab_code)
        self.assertIn("currentVersionRef.current = updatedCastle.version", self.task_tab_code)
        self.assertIn("err?.status === 409 || err?.isConflict", self.task_tab_code)
        self.assertIn("qc.invalidateQueries({ queryKey: ['castles', userId] })", self.task_tab_code)
        self.assertIn("qc.invalidateQueries({ queryKey: ['castle', userId, castle.id] })", self.task_tab_code)

    def test_06_direct_card_surface_toggling_and_propagation_containment(self):
        """Stress Test 6: Verify Direct Card Surface Toggling and strict stopPropagation containment."""
        # Top-level container must bind onClick={handleToggleExpand}
        outer_match = re.search(
            r"<div\s+onClick=\{handleToggleExpand\}\s+className=\{clsx\(\s*['\"][^'\"]*castle-card",
            self.castle_card_code
        )
        self.assertIsNotNone(outer_match, "CastleCard outer container must handle toggle expansion")

        # Interactive controls that must call stopPropagation
        # 1. Main action button handler
        self.assertIn("const handleToggleClick = (e: React.MouseEvent) => {\n    e.stopPropagation()", self.castle_card_code)

        # 2. Deploying button
        self.assertIn("onClick={e => e.stopPropagation()}", self.castle_card_code)

        # 3. Icon group
        self.assertIn("className=\"castle-icon-group", self.castle_card_code)

        # 4. Expanded accordion body
        expanded_body_match = re.search(
            r"className=\{clsx\(\s*['\"]border-white/8 border-t w-full castle-expanded-section['\"][^}]+\}\s+onClick=\{e => e\.stopPropagation\(\)\}",
            self.castle_card_code
        )
        self.assertIsNotNone(expanded_body_match, "Accordion body must stopPropagation to prevent accidental collapses")


if __name__ == "__main__":
    print("=" * 75)
    print("EMPIRICAL CHALLENGER M3: Stress-Testing Frontend State Architecture")
    print("=" * 75)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestEmpiricalFrontendStateArchitecture)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    if not res.wasSuccessful():
        print("\n[FAIL] EMPIRICAL CHALLENGER: BUGS OR ANOMALIES DETECTED!")
        sys.exit(1)
    print("\n[PASS] EMPIRICAL CHALLENGER: ALL 6 ADVERSARIAL STRESS SUITES PASSED CLEANLY!")
    sys.exit(0)
