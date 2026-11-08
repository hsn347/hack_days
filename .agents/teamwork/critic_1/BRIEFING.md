# BRIEFING — 2026-11-08T16:30:00Z

## Mission
Conduct an adversarial Red Team trial and exhaustive critique of `tasks/base_task.py`, `tasks/march_coordinator.py`, `tasks/monster.py`, `tasks/stronghold.py`, and `tasks/abra.py`. Formulate complete failure mode catalogs, priority inversion maps, error code flowcharts, and unified architectural designs without summarization.

## 🔒 My Identity
- Archetype: reviewer / critic / specialist
- Roles: reviewer, critic, specialist
- Working directory: e:\osmanli\.agents\teamwork\critic_1\
- Original parent: 2fe1a59e-c1ac-4e58-8bed-3e6333fd6e77
- Milestone: Red Team Trial & Unified Combat March Architecture
- Instance: 1 of 1

## 🔒 Key Constraints
- Review-only — do NOT modify implementation code.
- Strict prohibition on summarization: absolutely NO "etc.", "similarly for other files", or "in brief".
- Full exhaustive coverage across all 10 coordinator priorities and combat tasks.
- Deliverables: `critique.md`, `handoff.md`, and messaging to caller ID `2fe1a59e-c1ac-4e58-8bed-3e6333fd6e77`.

## Current Parent
- Conversation ID: 2fe1a59e-c1ac-4e58-8bed-3e6333fd6e77
- Updated: 2026-11-08T16:30:00Z

## Review Scope
- **Files to review**:
  - `tasks/base_task.py`
  - `tasks/march_coordinator.py`
  - `tasks/monster.py`
  - `tasks/stronghold.py`
  - `tasks/abra.py`
  - `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md`
  - `e:\osmanli\.agents\teamwork\explorer_grp1\analysis.md`
  - `e:\osmanli\.agents\teamwork\explorer_grp2\analysis.md`
- **Review criteria**: Correctness, concurrency, error-handling completeness, state machine integrity, race conditions, prestige quest alignment.

## Review Checklist
- **Items reviewed**:
  - `tasks/base_task.py` (all 1396 lines, zero-request memory helpers, `PRESTIGE_QUEST_IDS`, `get_march_army`, `TaskResult`)
  - `tasks/march_coordinator.py` (all 803 lines, 10 priority handlers, `_fallback_action`, `CoordinatorAction`, local `PRESTIGE_QUEST_IDS`)
  - `tasks/monster.py` (all 1642 lines, official FC power matrices, `_send_one_attack`, blanket `80xx` fallback, inline 8035 retry, rebel prerequisites)
  - `tasks/stronghold.py` (all 507 lines, missing 8027 handler, 8009 returning march omission, unverified target dispatch)
  - `tasks/abra.py` (all 1194 lines, pipelined marching, killing-blow race condition, missing 8035 handler, outbound-only hit timing)
- **Verdict**: REQUEST_CHANGES (Architectural overhaul required — unified combat march methods must be consolidated in `BaseTask` to eliminate 1,680+ lines of duplicated code, resolve priority inversion deadlocks, stop `ExcludeManager` cache poisoning, and unify prestige quest schemas).
- **Unverified claims**: All verified through line-by-line inspection of source files.

## Attack Surface
- **Hypotheses tested**:
  - Priority Inversion in `march_coordinator.py`: Confirmed (Ruins/gathering queue saturation deadlocks coordinator for up to 20 minutes; stamina cannibalization by Abra).
  - Missing Coordinator Troop Tracking: Confirmed (`self._used_army` absent at coordinator level, causing cross-priority ghost troop dispatch and error 8009 termination).
  - `_fallback_action` Dropouts: Confirmed (Unhandled `WEAK_ARMY`, `SUICIDE_RISK`, `NPC_LEVEL_LOCKED`, `REBEL_PREREQUISITE_FAILED`, `CMD_OPTING` 16001).
  - Dual `PRESTIGE_QUEST_IDS` Definition: Confirmed (Collisions on stronghold `4112019` vs `4112030`, and `4112001` train vs gather wood).
  - Blanket `80xx` ExcludeManager Poisoning: Confirmed (`monster.py:1566`, `stronghold.py:435` permanently blacklist targets on client-side errors 8041, 8042, 8046, 8037, 8095).
  - Error 8027 Misclassification in `stronghold.py`: Confirmed (Bans level-locked strongholds instead of lowering search level).
  - Premature 8009 Abort in `stronghold.py`: Confirmed (Returns `NO_ARMY` without checking returning marches, triggering coordinator `TERMINATE`).
  - Missing 8035 Handling in `abra.py`: Confirmed (Aborts weekly boss session on capacity fluctuations).
  - Abra Killing-Blow Race Condition: Confirmed (Mid-flight damage and concurrent combat land killing blow during pipelined dispatch).
- **Vulnerabilities found**: 8 critical vulnerabilities documented with mathematical proofs, call stacks, and code lines.

## Loaded Skills
- **Source**: `e:\osmanli\.agents\skills\empire-bot\SKILL.md`
- **Local copy**: `e:\osmanli\.agents\skills\empire-bot\SKILL.md`
- **Core methodology**: Empire bot protocol reference, packet structure, Lua decompilation analysis, combat and march mechanics.

## Key Decisions Made
- Authored exhaustive 1,000+ line Red Team critique at `e:\osmanli\.agents\teamwork\critic_1\critique.md` with zero summarization.
- Formulated production-ready Python implementation for `BaseTask` absorbing hero selection, pet resolution, same-branch military substitution, anti-suicide checks, and centralized error handling.
- Formulated Before-and-After refactoring maps for `march_coordinator.py`, `monster.py`, `stronghold.py`, and `abra.py`.

## Artifact Index
- `e:\osmanli\.agents\teamwork\critic_1\DISPATCH.md` — Inbound instructions
- `e:\osmanli\.agents\teamwork\critic_1\BRIEFING.md` — Situational awareness
- `e:\osmanli\.agents\teamwork\critic_1\progress.md` — Liveness & heartbeat
- `e:\osmanli\.agents\teamwork\critic_1\critique.md` — Exhaustive red team report
- `e:\osmanli\.agents\teamwork\critic_1\handoff.md` — 5-component handoff report
