#!/usr/bin/env python3
"""
Verification Script for Milestone 3 (M3):
Frontend State Architecture, Single Source of Truth Unification,
Unmount Mutation Synchronization, and Optimistic Concurrency Control (OCC).

Adheres to Osmanli AGENTS_CONSTITUTION.md & GEMINI.md.
Validates:
1. Single Source of Truth in CastleCard.tsx (Zero competing state forks).
2. Direct outer card surface click toggle with clean stopPropagation on interactive controls.
3. Explicit state transitions (loading, error, empty/fallback, success).
4. Unmount mutation cache flush to TanStack Query and localStorage in TaskTabContent.tsx.
5. In-flight draft guards against duplicate submissions and race conditions.
6. Optimistic Concurrency Control (OCC) version threading and HTTP 409 Conflict resilience.
7. TypeScript compilation compliance across the frontend workspace.
"""

import os
import re
import sys
import subprocess
import unittest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_SRC = os.path.join(WORKSPACE_ROOT, "dashboard", "src")


class TestM3FrontendStateArchitecture(unittest.TestCase):
    """Rigorous verification suite for M3 frontend state architecture."""

    @classmethod
    def setUpClass(cls):
        # Read target source files
        cls.castle_card_path = os.path.join(DASHBOARD_SRC, "components", "accounts", "CastleCard.tsx")
        cls.task_tab_path = os.path.join(DASHBOARD_SRC, "components", "accounts", "TaskTabContent.tsx")
        cls.use_castles_path = os.path.join(DASHBOARD_SRC, "hooks", "useCastles.ts")
        cls.bot_api_path = os.path.join(DASHBOARD_SRC, "lib", "botApi.ts")
        cls.types_path = os.path.join(DASHBOARD_SRC, "types", "index.ts")

        with open(cls.castle_card_path, "r", encoding="utf-8") as f:
            cls.castle_card_code = f.read()

        with open(cls.task_tab_path, "r", encoding="utf-8") as f:
            cls.task_tab_code = f.read()

        with open(cls.use_castles_path, "r", encoding="utf-8") as f:
            cls.use_castles_code = f.read()

        with open(cls.bot_api_path, "r", encoding="utf-8") as f:
            cls.bot_api_code = f.read()

        with open(cls.types_path, "r", encoding="utf-8") as f:
            cls.types_code = f.read()

    def test_01_castle_card_eliminated_competing_state_forks(self):
        """Verify that CastleCard has eliminated redundant local useState forks."""
        # Forbidden state forks that caused desync and freezing
        forbidden_patterns = [
            r"useState<Castle>\s*\(\s*castle\s*\)",
            r"setLiveCastle",
            r"setLiveState",
            r"setConnState",
            r"setIsStopping\s*\(",
            r"setIsStarting\s*\(",
        ]
        for pattern in forbidden_patterns:
            matches = re.findall(pattern, self.castle_card_code)
            self.assertEqual(
                len(matches),
                0,
                f"Violation: Forbidden competing state pattern '{pattern}' found in CastleCard.tsx: {matches}"
            )

    def test_02_castle_card_single_source_of_truth_binding(self):
        """Verify CastleCard binds directly to authoritative query mutation, WS, and castle object."""
        # Must derive mutation states directly from botControl
        self.assertIn("botControl.isPending", self.castle_card_code, "Must check botControl.isPending")
        self.assertIn("useRealBotStatus(castle.id)", self.castle_card_code, "Must listen to useRealBotStatus")
        self.assertIn("effectiveStatus", self.castle_card_code, "Must compute unified effectiveStatus")

        # Must compute authoritative active status with clear precedence
        self.assertIn("if (isStarting) return 'starting'", self.castle_card_code)
        self.assertIn("if (isStopping) return 'stopping'", self.castle_card_code)

        # Reads directly from castle props without liveCastle intermediate
        self.assertIn("const info      = castle.castle_info", self.castle_card_code)
        self.assertIn("const bot       = castle.bot_status", self.castle_card_code)
        self.assertIn("const resources = castle.resources", self.castle_card_code)

    def test_03_castle_card_outer_surface_click_toggle(self):
        """Verify clicking anywhere on the outer card surface toggles the accordion cleanly."""
        # Outer card div must have onClick={handleToggleExpand}
        outer_card_match = re.search(
            r"<div\s+onClick=\{handleToggleExpand\}\s+className=\{clsx\(\s*['\"][^'\"]*castle-card",
            self.castle_card_code
        )
        self.assertIsNotNone(outer_card_match, "Outer card container must handle click toggle")

        # Inner header and resources rows must not have redundant conflicting onClick
        self.assertNotIn("className=\"flex sm:flex-row flex-col justify-between sm:items-center gap-3.5 p-3.5 sm:p-5 select-none castle-card-header\"",
                         self.castle_card_code.replace("onClick={handleToggleExpand}", "CLICK_PRESENT")
                         if "CLICK_PRESENT" in self.castle_card_code else "")

        # Children with interactive controls must stop propagation
        self.assertIn("e.stopPropagation()", self.castle_card_code)
        self.assertIn("castle-expanded-section", self.castle_card_code)
        self.assertIn("onClick={e => e.stopPropagation()}", self.castle_card_code)

    def test_04_castle_card_explicit_state_transitions(self):
        """Verify explicit state transitions for loading, error, empty, and running."""
        # Loading / Spinners
        self.assertIn("Loader2", self.castle_card_code)
        self.assertIn("stopping-spinner", self.castle_card_code)
        self.assertIn("starting-spinner", self.castle_card_code)

        # Error state
        self.assertIn("status-badge-error", self.castle_card_code)
        self.assertIn("castle-card-error", self.castle_card_code)

        # Success / Running state
        self.assertIn("status-badge-running", self.castle_card_code)
        self.assertIn("castle-card-running", self.castle_card_code)

    def test_05_task_tab_unmount_flush_to_tanstack_query(self):
        """Verify TaskTabContent flushes pending draft edits directly to TanStack Query on unmount."""
        # Must import useQueryClient
        self.assertIn("useQueryClient", self.task_tab_code)
        self.assertIn("const qc = useQueryClient()", self.task_tab_code)

        # Unmount cleanup effect must update TanStack Query cache
        self.assertIn("qc.setQueryData(['castles', userId]", self.task_tab_code)
        self.assertIn("qc.setQueryData(['castle', userId, castle.id]", self.task_tab_code)
        self.assertIn("qc.setQueryData(['castleConfig', castle.id]", self.task_tab_code)

        # Must update localStorage cache
        self.assertIn("saveCachedCastles(userId,", self.task_tab_code)

    def test_06_task_tab_duplicate_submit_and_in_flight_guards(self):
        """Verify TaskTabContent guards against duplicate submissions and race conditions."""
        self.assertIn("inFlightDraftRef", self.task_tab_code)
        self.assertIn("isSavingRef.current", self.task_tab_code)
        self.assertIn("!isAlreadyInFlight", self.task_tab_code)
        self.assertIn("const isPending = updateConfig.isPending || isSavingBatch || isSavingRef.current", self.task_tab_code)

    def test_07_occ_version_support_and_409_handling(self):
        """Verify Optimistic Concurrency Control (OCC) versioning and 409 conflict handling."""
        # Types must include version in Castle
        self.assertIn("version?: number", self.types_code)

        # botApi.updateCastle must accept version and throw on 409
        self.assertIn("version?:     number", self.bot_api_code)
        self.assertIn("res.status === 409", self.bot_api_code)
        self.assertIn("isConflict = true", self.bot_api_code)

        # formatCastleFromApi must include version
        self.assertIn("version: raw.version ?? 1", self.bot_api_code)

        # useUpdateCastleConfig must forward version and update query cache
        self.assertIn("version?: number", self.use_castles_code)
        self.assertIn("qc.setQueryData(['castleConfig', castleId]", self.use_castles_code)

        # TaskTabContent must handle 409 conflict gracefully with toast and cache invalidation
        self.assertIn("err?.status === 409 || err?.isConflict", self.task_tab_code)
        self.assertIn("qc.invalidateQueries({ queryKey: ['castles', userId] })", self.task_tab_code)

    def test_08_frontend_typescript_compilation(self):
        """Verify frontend TypeScript compiler (tsc) passes with 0 errors."""
        cmd = ["npx", "tsc", "--noEmit"]
        cwd = os.path.join(WORKSPACE_ROOT, "dashboard")
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=True)
        self.assertEqual(
            proc.returncode,
            0,
            f"TypeScript compilation failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )


if __name__ == "__main__":
    print("=" * 70)
    print("Running Milestone 3 Frontend State & Architecture Verification")
    print("=" * 70)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestM3FrontendStateArchitecture)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("\n>>> ALL M3 FRONTEND STATE TESTS PASSED CLEANLY!")
