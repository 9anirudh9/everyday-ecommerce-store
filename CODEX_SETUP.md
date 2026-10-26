# Add to your EXISTING Everyday Shop Codex project

This archive is a **file overlay**, NOT a replacement project. It does not write to GitHub by itself. The files are designed for the root of `9anirudh9/everyday-ecommerce-store`.

## Local Codex desktop / IDE / CLI

1. Open the existing repository folder in Codex. Download this ZIP to your computer.
2. Check your working tree and ensure any local edits are saved: `git status --short`.
3. Unzip the archive **into the existing repository root**, preserving `.codex/` and directories. Do not overwrite an existing `AGENTS.md`, `IMPLEMENTATION.md` or `.codex/config.toml` without inspecting/merging.
4. Run `python3 scripts/validate_agents.py` to statically validate the source Markdown prompt definitions.
5. Optional registered-agent sanity check (Python 3.11+):
   `python3 -c "import tomllib,pathlib; ps=list(pathlib.Path('.codex/agents').glob('*.toml')); [tomllib.loads(p.read_text()) for p in ps]; print(len(ps),'Codex subagent TOMLs parsed')"`
6. Reopen/restart the Codex session in the SAME repository. Ask it to list active instructions and named subagents; request a simulated dry-run only. Actual behavior is not proven by static checks.
7. Keep untracked modifications local until you explicitly approve pushing the exact diff and destination branch.

## Cloud-only Codex

Cloud agents only see files inside the checked-out repository/environment (plus supported task attachments). A local ZIP is not automatically visible to cloud tasks. Review the overlay locally and authorize a branch push/PR separately if you want it made available in GitHub-backed cloud sessions. Do not assume attaching a ZIP to a ChatGPT chat configures Codex.

## Directory map

- `AGENTS.md`: Codex automatically reads repository instructions.
- `IMPLEMENTATION.md`: master execution plan for all P0 and P1 gates; not automatically read in full, but referenced in AGENTS.md.
- `.codex/config.toml`: 3-subagent concurrency cap (cost control); verify your Codex client supports it.
- `.codex/agents/*.toml`: eight Codex project-scoped subagent definitions.
- `agents/*.md`: portable agent role source prompts.
- `agents/manifest.json`: role inventory.
- `scripts/validate_agents.py`: static validation only.
- `python-playwright/`: minimal **read-only** smoke tests (not yet executed against browser).

**Approval:** no push, merge, deployment, or third-party authorization occurred when this ZIP was produced.
