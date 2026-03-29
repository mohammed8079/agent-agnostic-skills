# Shared Skills Demo

This folder is a self-contained example of sharing one canonical SKILL.md across Claude Code, GitHub Copilot, and Codex CLI.

Layout
- agents/skills/<skill>/SKILL.md is the canonical source
- agents/skills/<skill>/claude.yaml holds Claude-only frontmatter
- scripts/sync_skills.py copies and merges into .claude/skills, .github/skills, .agents/skills
- githooks/post-checkout is a sample git hook

Quickstart
1. Run `python3 scripts/sync_skills.py`
2. Inspect `.claude/skills`, `.github/skills`, `.agents/skills`

Make targets
- `make sync-skills`
- `make check-skills`

Notes
- The sync script expects simple `key: value` frontmatter and overrides.
- Add new skills under `agents/skills/<name>/SKILL.md` and rerun sync.
