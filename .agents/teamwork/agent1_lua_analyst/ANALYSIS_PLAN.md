# Technical Report: Lua Source Code Discovery and Investigation Plan
**Date**: 2026-11-09T13:06:00Z
**Author**: Agent 1 (Lua Protocol & Notify Analyst)

## 1. Diagnostic & Motivation
To extract all notification IDs (`gNotifyID`), controller payload structures, queue lifecycles, and model update algorithms from `e:\osmanli\game file\lua_src`, we must inspect the files located in the game source directory. Specifically, locating files such as `notifyCtrl.lua`, `cityCtrl.lua`, `queueCtrl.lua`, `armyCtrl.lua`, `heroCtrl.lua`, `lordInfoCtrl.lua`, `buffCtrl.lua`, `backpackCtrl.lua`, `meritoriousTaskCtrl.lua`, and `timeRewardCtrl.lua`.

## 2. Logic & Steps to Execute
1. Execute a directory search command in PowerShell to locate the exact path of `notifyCtrl.lua`, `notifyDef.lua`, `cityCtrl.lua`, `queueCtrl.lua`, and other controller files within `e:\osmanli\game file`.
2. Inspect the content of notification definition files (e.g. `notifyDef.lua`, `gNotifyID`, or `notifyCtrl.lua`) to extract all numeric / symbolic IDs and their events.
3. Inspect `cityCtrl.lua` to extract resource updates (`reslist`, `saferes`, `dayMaxRes`, `updateUnCollectRes`, `openChargeQueue`, `blist`, `BUILD_STATE.NORMAL`, building levels).
4. Inspect `queueCtrl.lua` to extract `NOTIFY_QUEUE`, `NOTIFY_PLAYER_QUEUE_CHANGE`, `NOTIFY_LOCAL_QUEUE_SYNC`, callbacks, queue structures.
5. Inspect `armyCtrl.lua`, `heroCtrl.lua`, `lordInfoCtrl.lua`, `buffCtrl.lua`, `backpackCtrl.lua`, `meritoriousTaskCtrl.lua`, and `timeRewardCtrl.lua`.
6. Inspect the base controller or data merging patterns (`updateData`, `mergeData`, notification registration/dispatch).

## 3. Files, Lines, and Commands to Execute
- Command: `Get-ChildItem -Path "e:\osmanli\game file" -Recurse -Filter "*Ctrl.lua" | Select-Object FullName` and similarly for `*notify*`.
- Expected Outcome: Exact relative/absolute file paths for all key controllers and notification definitions.
