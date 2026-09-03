# Command Engine & Chat Administration Architecture

## Overview
The Phase 4 Command Engine powers real-time viewer and creator interactions across live streams. It operates under a strict role-based access control (RBAC) hierarchy and prioritizes safety:
1. Built-in utility commands (`!help`, `!rules`, `!discord`, `!uptime`, `!level`, `!xp`, `!coins`, `!rank`, `!leaderboard`, `!shop`, `!buy`, `!inventory`, `!trivia`, `!word`).
2. Creator-scoped custom commands stored dynamically in PostgreSQL (`custom_commands` and `command_aliases`).
3. Administrative chat management under the reserved prefix `!uk`.
4. Output brevity (<200 characters) enforced by `OutputGuard` and styled through `HonneyPersonaEngine`.

---

## Role-Based Access Control (RBAC) Hierarchy

| Role | Hierarchy Level | Capabilities |
|---|---|---|
| **VIEWER** | 1 | Access public commands (`!help`, `!level`, `!shop`, `!buy`, `!trivia`), play games, earn XP/coins. |
| **MODERATOR** | 2 | Everything in VIEWER + custom commands with `MODERATOR` minimum role + `!uk` subcommands (`!uk add`, `!uk edit`, `!uk delete`, `!uk punish`). |
| **CREATOR** | 3 | Full channel authority: store creation, coin grants (`!uk give`), permission delegation (`!uk perms`), toggles. |
| **DEVELOPER** | 4 | Global system access via REST API (`X-Admin-Secret`). |

---

## Chat-First Administration (`!uk` Commands)

The `!uk` prefix is strictly reserved for authorized stream staff. Any execution attempt by a `VIEWER` is blocked with `PERMISSION_DENIED`.

### Command Syntax
- **Add Custom Command**:
  ```text
  !uk add discord "Join our community at https://discord.gg/streamer!" [MODERATOR]
  ```
- **Edit Custom Command**:
  ```text
  !uk edit discord "New invite link: https://discord.gg/newlink!"
  ```
- **Delete Custom Command**:
  ```text
  !uk delete discord
  ```
- **Manage Store Items**:
  ```text
  !uk store add VIP "Exclusive VIP badge in chat" 250 10
  !uk store delete VIP
  ```
- **Grant Virtual Coins**:
  ```text
  !uk give @username 100
  ```
- **Delegate Permissions**:
  ```text
  !uk perms twitter MODERATOR
  ```
- **Phase 3 Human-In-The-Loop Punish Approval**:
  ```text
  !uk punish <review_id_prefix> yes
  !uk punish <review_id_prefix> no
  ```
