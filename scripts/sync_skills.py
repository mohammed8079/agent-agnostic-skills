#!/usr/bin/env python3
"""
Sync skills from the canonical source to all agent-specific destinations.

Source: agents/skills/<name>/SKILL.md (+ optional claude.yaml overrides)
Targets:
  .claude/skills/<name>/SKILL.md  - Claude Code
  .agents/skills/<name>/SKILL.md  - Codex CLI
  .github/skills/<name>/SKILL.md  - GitHub Copilot

Usage:
  python3 scripts/sync_skills.py         # sync (write mode)
  python3 scripts/sync_skills.py --check # verify without writing (exits 1 on drift)
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SOURCE_DIR = REPO_ROOT / "agents" / "skills"
TARGETS: dict[str, Path] = {
    "claude": REPO_ROOT / ".claude" / "skills",
    "codex": REPO_ROOT / ".agents" / "skills",
    "copilot": REPO_ROOT / ".github" / "skills",
}


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter_dict, body) from a SKILL.md string."""
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not match:
        return {}, text
    body = text[match.end():]
    fm: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()
    return fm, body


def parse_yaml_overrides(path: Path) -> dict[str, str]:
    """Parse simple key: value lines from claude.yaml (comments and blank lines ignored)."""
    overrides: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and ":" in line:
            key, _, value = line.partition(":")
            overrides[key.strip()] = value.strip()
    return overrides


def build_frontmatter(fm: dict[str, str]) -> str:
    lines = ["---"]
    for key, value in fm.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Per-skill sync
# ---------------------------------------------------------------------------

def _skill_content_for_agent(
    fm: dict[str, str],
    claude_overrides: dict[str, str],
    body: str,
    agent: str,
) -> str:
    # SKILL.md contains only common keys; claude.yaml holds Claude-specific overrides.
    # Non-Claude agents receive SKILL.md as-is - no stripping needed.
    merged = {**fm, **claude_overrides} if agent == "claude" else fm
    return build_frontmatter(merged) + body


def sync_skill(
    skill_dir: Path,
    targets: dict[str, Path],
    check: bool,
) -> list[str]:
    """Sync one skill directory to all targets. Returns drift messages when check=True."""
    source_file = skill_dir / "SKILL.md"
    claude_yaml = skill_dir / "claude.yaml"

    fm, body = parse_frontmatter(source_file.read_text())
    claude_overrides = parse_yaml_overrides(claude_yaml) if claude_yaml.exists() else {}

    skill_name = fm.get("name") or skill_dir.name
    drift: list[str] = []

    for agent, target_base in targets.items():
        dest_dir = target_base / skill_name
        dest_file = dest_dir / "SKILL.md"
        expected = _skill_content_for_agent(fm, claude_overrides, body, agent)

        if check:
            if not dest_file.exists() or dest_file.read_text() != expected:
                try:
                    display = dest_file.relative_to(REPO_ROOT)
                except ValueError:
                    display = dest_file
                drift.append(f"  [{agent}] {display} is out of sync")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file.write_text(expected)
            # Copy sibling files verbatim (scripts/, assets/, etc.)
            for sibling in skill_dir.iterdir():
                if sibling.name in ("SKILL.md", "claude.yaml"):
                    continue
                dest = dest_dir / sibling.name
                if sibling.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(sibling, dest)
                else:
                    shutil.copy2(sibling, dest)

    return drift


def remove_stale(
    live_names: set[str],
    targets: dict[str, Path],
    check: bool,
) -> list[str]:
    """Remove (or report) destination skill dirs that no longer exist in source."""
    drift: list[str] = []
    for agent, target_base in targets.items():
        if not target_base.exists():
            continue
        for dest_dir in target_base.iterdir():
            if dest_dir.is_dir() and dest_dir.name not in live_names:
                if check:
                    try:
                        display = target_base.relative_to(REPO_ROOT)
                    except ValueError:
                        display = target_base
                    drift.append(f"  [{agent}] stale skill '{dest_dir.name}' in {display}")
                else:
                    shutil.rmtree(dest_dir)
    return drift


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify all destinations match source without writing. Exits 1 on drift.",
    )
    args = parser.parse_args()

    if not SOURCE_DIR.exists():
        print(f"No skills source directory: {SOURCE_DIR.relative_to(REPO_ROOT)}")
        sys.exit(0)

    skill_dirs = sorted(d for d in SOURCE_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists())
    if not skill_dirs:
        print("No skills found in agents/skills/")
        sys.exit(0)

    drift: list[str] = []
    live_names: set[str] = set()

    for skill_dir in skill_dirs:
        fm, _ = parse_frontmatter((skill_dir / "SKILL.md").read_text())
        live_names.add(fm.get("name") or skill_dir.name)
        drift.extend(sync_skill(skill_dir, TARGETS, check=args.check))

    drift.extend(remove_stale(live_names, TARGETS, check=args.check))

    if args.check:
        if drift:
            print("Skills out of sync:")
            for msg in drift:
                print(msg)
            print("\nRun 'make sync-skills' to fix.")
            sys.exit(1)
        else:
            print(f"OK - {len(skill_dirs)} skill(s) in sync across {len(TARGETS)} destinations.")
    else:
        print(f"Synced {len(skill_dirs)} skill(s) to {len(TARGETS)} destinations.")


if __name__ == "__main__":
    main()
