# Codex project instructions — Everyday Shop

The authoritative scope and release gates are in `IMPLEMENTATION.md`. Read `AGENTS.md` and the applicable task section of `IMPLEMENTATION.md` before making changes.

This project includes *Codex subagent registrations* in `.codex/agents/*.toml` and their readable source prompts in `agents/*.md`. Use named subagents `conductor`, `atlas`, `forge`, `probe`, `spec`, `smoke`, `watchtower`, and `permit` when your Codex client supports subagents. The `@NAME` notation in the vendor-neutral prompts is a human shorthand, not an automatic Codex command.

**CRITICAL**: No commit, push, PR, merge, staging deploy, production deploy, third-party authorization, package install requiring external approval, or charges without the owner's *specific explicit approval*. Local read-only validation is allowed. Prepare proposed file changes locally in a task branch only after the user authorizes local edits. Stop at the P0->P1 gate. Verify independent `watchtower` review and post-deploy smoke after each *authorized* deployment. Report missing runtime checks as NOT RUN, never PASS.

**Cost**: Use the parent model by default to maximize compatibility. Delegate tightly scoped work; use deterministic scripts before model calls; invoke high reasoning effort only for risky security, data or architecture questions. Do not imply that a cheaper model was selected unless runtime actually confirms it.

# Everyday Shop — Agent Instructions

This pack defines *eight* task-specific agent prompts. It does **not** deploy runtime AI agents. Load/register the prompts in an approved coding-agent environment, then run behavior dry-runs before marking them ready.

**Authoritative plan:** `IMPLEMENTATION.md`.

## Calls

- `@CONDUCTOR plan P0-00` — route tasks and model tier
- `@ATLAS specify P0-02` — business contract and acceptance
- `@FORGE implement P0-02 locally` — patch plan, no remote write
- `@PROBE compare P0-02 A=<sha> B=<sha>` — baseline/candidate
- `@SPEC test P0-02` — Python Playwright tests
- `@SMOKE verify deployment <sha> <url>` — post-deploy smoke
- `@WATCHTOWER audit P0-02` — independent monitor every step
- `@PERMIT approval-check <action>` — third-party and repo approval

## Safety

No push without approval. Owner must separately authorize push, staging deploy, production deploy, P1, and third-party permissions. Agents must not touch real payment systems or mutate production datasets. Any unexecuted runtime test is `NOT RUN` / `BLOCK`, not PASS.

## Local static validation

`python scripts/validate_agents.py`

Local static validation checks that the prompt pack is structurally complete. It cannot verify that a chosen coding-agent platform obeys the prompts. Runtime behavior dry-runs AG-03…AG-07 remain required.
