#!/usr/bin/env python3
"""Read-only audit of agent SKILL.md libraries.

It never changes skill files.  The only write this program can perform is the
explicit --markdown report destination.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:  # Python 3.11+.  The fallback keeps the promised clean-Mac support.
    import tomllib
except ImportError:  # pragma: no cover - exercised on macOS Python 3.9/3.10
    tomllib = None

VERSION = "1.0.0"
PATHS_VERIFIED = "2026-08-01"
# Paths verified August 1, 2026. Re-verify quarterly: vendors have moved them.
GLOBAL_PATHS = {
    "claude": ("~/.claude/skills",),
    "codex": ("~/.agents/skills",),
    "gemini": ("~/.agents/skills", "~/.gemini/skills"),
    "antigravity": ("~/.gemini/config/skills",),
}
ANTIGRAVITY_NON_PORTABLE = (
    "~/.gemini/antigravity/skills", "~/.gemini/antigravity-cli/skills"
)
TOOLS = ("claude", "codex", "gemini", "antigravity")
CONTEXT_WINDOW_DEFAULT = 200000  # conservative default when config is absent
CLAUDE_ENTRY_CAP = 1536
CODEX_BUDGET_FRACTION = 0.02
CLAUDE_BUDGET_FRACTION = 0.01
STOPWORDS = {
    "when", "user", "asks", "use", "this", "that", "with", "from", "should",
    "would", "will", "trigger", "triggers", "skill", "used", "using", "about",
    "into", "also", "like", "such", "their", "they", "them", "have", "been",
    "more", "most", "then", "than", "these", "those", "what", "which", "does",
    "create", "generate", "write", "make", "help", "content", "and", "the", "for",
    "are", "you", "your", "our", "all", "can", "but", "not", "only", "any",
}
VAGUE_WORDS = {"helps", "help", "general", "various", "anything", "assists", "assist", "things"}
FINDING_CODES = {
    "no_frontmatter", "unparseable_field", "unknown_field", "missing_description",
    "name_mismatch", "thin_description", "bloated_description", "missing_trigger",
    "vague_description", "late_job_noun", "oversized_body", "broken_symlink",
    "double_link", "non_portable_path", "mode_disagreement", "name_collision",
    "overlap", "budget_exceeded", "entry_cap_exceeded", "pocket_count",
    "intended_shelf_pocket", "intended_pocket_shelf", "intended_missing",
    "config_error", "unreadable",
}
KNOWN_FIELDS = {
    "name", "description", "allowed-tools", "disable-model-invocation", "paths",
    "when_to_use", "license", "metadata", "compatibility", "argument-hint",
}
BOOLS = {"true": True, "yes": True, "on": True, "1": True,
         "false": False, "no": False, "off": False, "0": False}


def finding(severity: str, code: str, message: str, skill: str = "",
            path: str = "", line: Optional[int] = None) -> Dict[str, Any]:
    assert code in FINDING_CODES, "unregistered finding code: %s" % code
    assert severity in ("error", "warning", "notice"), severity
    suffix = "" if line is None else " (line %d)" % line
    return {"severity": severity, "code": code, "skill": skill, "path": path,
            "message": message + suffix, "line": line}


def parse_scalar(value: str) -> Tuple[bool, Any]:
    value = value.strip()
    if not value:
        return True, ""
    if value[0:1] in ("'", '"'):
        if len(value) < 2 or value[-1] != value[0]:
            return False, None
        return True, value[1:-1]
    if value.startswith("["):
        if not value.endswith("]"):
            return False, None
        values = []
        parts = split_flow_list(value[1:-1])
        if parts is None:
            return False, None
        for part in parts:
            ok, item = parse_scalar(part)
            if not ok or isinstance(item, list):
                return False, None
            values.append(item)
        return True, values
    # Anchors, aliases, tags and reserved indicators are a sixth form this
    # parser does not support. Flag them rather than storing "&ref value".
    if value[0] in "&*!@`":
        return False, None
    # ": " and " #" genuinely terminate a YAML plain scalar; a bare "#" does not
    # (so "C# refactoring" is valid and must not be rejected).
    if any(mark in value for mark in ("{", "}", " #", ": ")):
        return False, None
    return True, value


def split_flow_list(value: str) -> Optional[List[str]]:
    """Split a YAML flow-list body without splitting commas inside quotes."""
    parts: List[str] = []
    current: List[str] = []
    quote = ""
    for character in value:
        if character in ("'", '"'):
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
        if character == "," and not quote:
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
    if quote:
        return None
    parts.append("".join(current))
    return parts


def parse_frontmatter(text: str, nested_policy: bool = False) -> Tuple[Optional[Dict[str, Any]], List[Tuple[str, int]], bool]:
    """Parse exactly the intentionally small YAML subset from the brief."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, [], False
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, [("frontmatter", 1)], True
    data: Dict[str, Any] = {}
    bad: List[Tuple[str, int]] = []
    i = 1
    key_line = re.compile(r"^([A-Za-z0-9_-]+):(?:[ ](.*)|[ ]*)$")
    while i < end:
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        match = key_line.match(raw)
        if not match:
            bad.append(("frontmatter", i + 1))
            i += 1
            continue
        key, value = match.group(1), match.group(2) or ""
        line_no = i + 1
        if value in ("|", ">"):
            block, indent = [], None
            i += 1
            while i < end and (not lines[i].strip() or lines[i][0].isspace()):
                if lines[i].strip():
                    current = len(lines[i]) - len(lines[i].lstrip())
                    indent = current if indent is None else min(indent, current)
                block.append(lines[i])
                i += 1
            if indent is None:
                bad.append((key, line_no))
                continue
            stripped = [line[indent:] if line.strip() else "" for line in block]
            data[key] = ("\n".join(stripped) if value == "|" else " ".join(x.strip() for x in stripped)).strip()
            continue
        if value == "":
            children = []
            while i + 1 < end and (not lines[i + 1].strip() or lines[i + 1][0].isspace()):
                i += 1
                if lines[i].strip():
                    children.append((lines[i], i + 1))
            if not children:
                data[key] = ""
                i += 1
                continue
            if nested_policy:
                mapping = {}
                for child, child_line in children:
                    child_match = re.match(r"^\s+([A-Za-z0-9_-]+):[ ](.*)$", child)
                    if not child_match:
                        bad.append((key, child_line))
                        continue
                    ok, parsed = parse_scalar(child_match.group(2))
                    if not ok:
                        bad.append((child_match.group(1), child_line))
                    else:
                        mapping[child_match.group(1)] = parsed
                data[key] = mapping
            else:
                values = []
                for child, child_line in children:
                    item = re.match(r"^\s+-[ ](.+)$", child)
                    if not item:
                        bad.append((key, child_line))
                        continue
                    ok, parsed = parse_scalar(item.group(1))
                    if not ok or isinstance(parsed, list):
                        bad.append((key, child_line))
                    else:
                        values.append(parsed)
                data[key] = values
            i += 1
            continue
        # A plain scalar may continue on more-indented lines; YAML folds them
        # with single spaces. Without this the value was silently TRUNCATED at
        # the first newline, and every downstream check — trigger language,
        # length, overlap tokens, budget — then ran on a partial description.
        if value and value[0] not in "'\"[":
            while (i + 1 < end and lines[i + 1].strip() and lines[i + 1][0].isspace()
                   and not re.match(r"^\s+-[ ]", lines[i + 1])
                   and not key_line.match(lines[i + 1].strip())):
                i += 1
                value += " " + lines[i].strip()
        ok, parsed = parse_scalar(value)
        if not ok:
            bad.append((key, line_no))
        else:
            data[key] = parsed
        i += 1
    return data, bad, True


def bool_value(value: Any) -> Optional[bool]:
    return BOOLS.get(str(value).lower())


def safe_read(path: Path) -> Tuple[Optional[str], Optional[str]]:
    try:
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeError) as exc:
        return None, str(exc)


def paths_under(root: Path) -> Iterable[Path]:
    if not root.exists(): return []
    found = []
    try:
        for current, dirs, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            if "SKILL.md" in files:
                found.append(current_path)
            # os.walk intentionally does not descend symlinked directories, but
            # a symlink itself is a valid skill directory in the recommended
            # one-source-folder setup.
            for directory in dirs:
                candidate = current_path / directory
                if candidate.is_symlink() and (candidate / "SKILL.md").is_file():
                    found.append(candidate)
            # Broken directory symlinks are discovered separately by scan_root.
    except OSError:
        pass
    return found


def scan_root(root: Path, tool: str, label: str, nested: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    records, problems = [], []
    if root.is_symlink() and not root.exists():
        return records, [finding("warning", "broken_symlink", "Broken symlink", path=str(root))]
    try:
        if not root.exists(): return records, []
        for child in root.iterdir():
            if child.is_symlink() and not child.exists():
                problems.append(finding("warning", "broken_symlink", "Broken symlink", path=str(child)))
    except OSError as exc:
        return records, [finding("warning", "unreadable", "Cannot scan location: %s" % exc, path=str(root))]
    for skill_dir in paths_under(root):
        file_path = skill_dir / "SKILL.md"
        try: real = str(skill_dir.resolve(strict=True))
        except OSError:
            problems.append(finding("warning", "broken_symlink", "Broken skill path", path=str(skill_dir))); continue
        records.append({"source": str(skill_dir), "real_path": real, "file": str(file_path),
                        "tool": tool, "label": label, "nested": nested})
    return records, problems


def dedupe_scan_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One dead link reachable from four cupboards is one problem, not four.

    Skills dedupe by resolved real path; scan-level findings must too.
    os.path.realpath is used because a broken link cannot be resolve(strict=True)'d.
    """
    seen, kept = set(), []
    for item in findings:
        key = (item["code"], os.path.realpath(item["path"]) if item["path"] else item["skill"])
        if key in seen: continue
        seen.add(key); kept.append(item)
    return kept


# Never worth walking for skills, and expensive on a monorepo.
PRUNE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist",
              "build", ".next", ".tox", ".mypy_cache", ".pytest_cache", "target"}


def project_roots(repo: Path) -> Iterable[Tuple[Path, str, bool]]:
    direct = ((repo / ".claude/skills", "claude"), (repo / ".agents/skills", "codex"),
              (repo / ".agents/skills", "gemini"), (repo / ".gemini/skills", "gemini"))
    for path, tool in direct: yield path, tool, False
    try:
        for current, dirs, _ in os.walk(repo, followlinks=False):
            current_path = Path(current)
            dirs[:] = [d for d in dirs if d not in PRUNE_DIRS]
            if current_path == repo: continue
            for marker, tool in ((".claude", "claude"), (".agents", "codex"), (".agents", "gemini")):
                candidate = current_path / marker / "skills"
                if candidate.exists():
                    yield candidate, tool, True
                    if marker in dirs: dirs.remove(marker)
    except OSError:
        return


def parse_config(path: Path) -> Tuple[Dict[str, Any], Optional[str]]:
    if not path.exists(): return {}, None
    try:
        raw = path.read_bytes()
        if tomllib: return tomllib.loads(raw.decode("utf-8")), None
        # Compatibility fallback for exactly the documented config shape.
        section, result = "", {}
        for line in raw.decode("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            sec = re.match(r"^\[([A-Za-z0-9_-]+)\]$", line)
            if sec: section = sec.group(1); result.setdefault(section, {}); continue
            item = re.match(r'^"?([^"=]+?)"?\s*=\s*(.+)$', line)
            if not item or not section: raise ValueError("unsupported TOML syntax")
            key, value = item.group(1).strip(), item.group(2).strip()
            if value.startswith("["):
                result[section][key] = [x.strip().strip('"\'') for x in value[1:-1].split(",") if x.strip()]
            elif value.isdigit(): result[section][key] = int(value)
            else: result[section][key] = value.strip('"\'')
        return result, None
    except (OSError, UnicodeError, ValueError) as exc:
        return {}, str(exc)


def description_tokens(description: str) -> Set[str]:
    return {word for word in re.split(r"\W+", description.lower())
            if len(word) >= 4 and word not in STOPWORDS}


def is_vague(description: str) -> bool:
    words = {word for word in re.split(r"\W+", description.lower()) if len(word) >= 3 and word not in STOPWORDS}
    return bool(words) and words <= VAGUE_WORDS


def quoted_phrases(description: str) -> Set[str]:
    return {match.group(2).lower() for match in re.finditer(r"(['\"])(.+?)\1", description) if match.group(2).strip()}


def classify_skill(real_path: str, entries: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    skill_dir = Path(real_path)
    text, error = safe_read(skill_dir / "SKILL.md")
    name = skill_dir.name
    parsed, malformed, has_frontmatter = parse_frontmatter(text or "")
    if error:
        findings.append(finding("error", "unreadable", "SKILL.md is not readable: %s" % error, name, real_path))
        parsed = {}; has_frontmatter = False
    if not has_frontmatter:
        findings.append(finding("error", "no_frontmatter", "No frontmatter block", name, real_path))
    parsed = parsed or {}
    for field, line in malformed:
        severity = "error" if field == "description" or "description" not in parsed else "warning"
        hint = " — a plain scalar cannot contain ': ' or ' #'; wrap the value in quotes" if field == "description" else ""
        findings.append(finding(severity, "unparseable_field", "Unparseable field '%s'%s" % (field, hint), name, real_path, line))
    for field in parsed:
        if field not in KNOWN_FIELDS:
            findings.append(finding("notice", "unknown_field", "Unrecognized field '%s'" % field, name, real_path))
    description = parsed.get("description")
    if "disable-model-invocation" in parsed and bool_value(parsed["disable-model-invocation"]) is None:
        findings.append(finding("warning", "unparseable_field", "Invalid boolean disable-model-invocation", name, real_path))
    if not isinstance(description, str) or not description.strip():
        findings.append(finding("error", "missing_description", "Missing or unreadable description", name, real_path))
        description = ""
    if "name" in parsed and parsed["name"] != name:
        findings.append(finding("warning", "name_mismatch", "Frontmatter name does not match directory name", name, real_path))
    if description:
        if len(description) < 40: findings.append(finding("warning", "thin_description", "Description is under 40 characters", name, real_path))
        if len(description) > 500: findings.append(finding("warning", "bloated_description", "Description exceeds 500 characters", name, real_path))
        if not re.search(r"\b(use when|trigger|when (the )?user|for .* requests?)\b", description, re.I):
            findings.append(finding("warning", "missing_trigger", "Description lacks trigger language", name, real_path))
        if is_vague(description):
            findings.append(finding("warning", "vague_description", "Description is too vague to route reliably", name, real_path))
        # A real "concrete noun" test needs POS tagging, which the stdlib does
        # not have. This checks for any distinctive (non-stopword, non-vague)
        # term up front instead, and the message claims exactly that and no more.
        if not description_tokens(description[:100]) - VAGUE_WORDS:
            findings.append(finding("notice", "late_job_noun", "First 100 characters contain no distinctive term", name, real_path))
    line_count = len((text or "").splitlines())
    if line_count > 500: findings.append(finding("warning", "oversized_body", "SKILL.md exceeds 500 lines", name, real_path))
    claude_shelf = bool_value(parsed.get("disable-model-invocation")) is True
    codex_file = skill_dir / "agents/openai.yaml"
    codex_shelf = False
    if codex_file.exists():
        policy_text, policy_error = safe_read(codex_file)
        policy, policy_bad, _ = parse_frontmatter(policy_text or "", nested_policy=True)
        synthetic_policy = policy is None and policy_text is not None
        # openai.yaml normally has no ---; parse its content as a synthetic block.
        if synthetic_policy:
            policy, policy_bad, _ = parse_frontmatter("---\n" + policy_text + "\n---\n", nested_policy=True)
        policy = policy or {}
        for field, line in policy_bad:
            findings.append(finding("warning", "unparseable_field", "Unparseable Codex policy field '%s'" % field, name, real_path, line - 1 if synthetic_policy else line))
        policy_value = policy.get("policy", {}).get("allow_implicit_invocation") if isinstance(policy.get("policy"), dict) else None
        parsed_bool = bool_value(policy_value)
        if policy_value is not None and parsed_bool is None:
            findings.append(finding("warning", "unparseable_field", "Invalid boolean allow_implicit_invocation", name, real_path))
        codex_shelf = parsed_bool is False
    visible = {entry["tool"] for entry in entries}
    states = {}
    for tool in TOOLS:
        if tool not in visible: continue
        states[tool] = ("SHELF" if claude_shelf else "POCKET") if tool == "claude" else (("SHELF" if codex_shelf else "POCKET") if tool == "codex" else "UNKNOWN")
    known = {state for state in states.values() if state != "UNKNOWN"}
    if len(known) > 1:
        findings.append(finding("warning", "mode_disagreement", "Tools disagree on invocation mode", name, real_path))
    return {"name": name, "real_path": real_path, "file": str(skill_dir / "SKILL.md"),
            "reachable_from": sorted({entry["source"] for entry in entries}), "tools": sorted(visible),
            "states": states, "line_count": line_count, "character_count": len(text or ""),
            "description": description, "nested": any(entry["nested"] for entry in entries),
            "scopes": sorted({entry["label"] for entry in entries}),
            "occurrences": sorted({(entry["tool"], entry["label"], entry["source"]) for entry in entries})}


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    selected = set(args.tool or TOOLS)
    entries: List[Dict[str, Any]] = []; findings: List[Dict[str, Any]] = []; locations = []
    home = Path.home()
    for tool in TOOLS:
        if tool not in selected: continue
        for raw in GLOBAL_PATHS[tool]:
            root = Path(os.path.expanduser(raw)); locations.append({"path": str(root), "status": "present" if root.exists() else "not present"})
            records, problems = scan_root(root, tool, "global")
            entries.extend(records); findings.extend(problems)
    if "antigravity" in selected:
        for raw in ANTIGRAVITY_NON_PORTABLE:
            root = Path(os.path.expanduser(raw)); locations.append({"path": str(root), "status": "present" if root.exists() else "not present"})
            records, problems = scan_root(root, "antigravity", "non-portable")
            entries.extend(records); findings.extend(problems)
            if records: findings.append(finding("warning", "non_portable_path", "Antigravity skill path is non-portable", path=str(root)))
    for repo_raw in args.repo:
        repo = Path(repo_raw).expanduser()
        if not repo.exists():
            findings.append(finding("warning", "unreadable", "Repo is not present", path=str(repo))); continue
        seen_roots = set()
        for root, tool, nested in project_roots(repo):
            if tool not in selected or (str(root), tool) in seen_roots: continue
            seen_roots.add((str(root), tool)); locations.append({"path": str(root), "status": "present" if root.exists() else "not present"})
            records, problems = scan_root(root, tool, "nested" if nested else "project", nested)
            entries.extend(records); findings.extend(problems)
    # Gemini double link is a root-level condition, not a per-skill issue.
    gemini_roots = [Path(os.path.expanduser(p)) for p in GLOBAL_PATHS["gemini"]]
    if "gemini" in selected and len(gemini_roots) > 1 and all(p.exists() for p in gemini_roots):
        try:
            if gemini_roots[0].resolve() == gemini_roots[1].resolve():
                findings.append(finding("warning", "double_link", "Gemini user paths resolve to the same target", path=str(gemini_roots[0])))
        except OSError: pass
    # Everything above is scan-level; collapse duplicates before per-skill
    # findings are appended, so one dead link is reported once.
    findings[:] = dedupe_scan_findings(findings)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for entry in entries: grouped[entry["real_path"]].append(entry)
    skills = [classify_skill(real, group, findings) for real, group in sorted(grouped.items())]
    config_path = Path(args.config).expanduser() if args.config else home / ".skill-audit.toml"
    config, config_error = parse_config(config_path)
    if config_error: findings.append(finding("warning", "config_error", "Cannot parse config: %s" % config_error, path=str(config_path)))
    collisions = collision_report(skills, findings)
    overlaps = overlap_report(skills, config, findings)
    budget = budget_report(skills, config, findings)
    pocket = pocket_report(skills, config, findings)
    recommendations = recommendations_for(findings)
    return {"meta": {"version": VERSION, "paths_verified": PATHS_VERIFIED,
                      "scan_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                      "locations_scanned": locations, "config": str(config_path), "config_present": config_path.exists()},
            "skills": skills, "findings": findings, "collisions": collisions, "overlaps": overlaps,
            "budget": budget, "pocket_check": pocket, "recommendations": recommendations}


# Documented precedence, expressed as tiers. Lower number wins.
# "global" is a user-level install; "project"/"nested" live inside a repo.
# Enterprise (Claude) and extension/built-in (Gemini) are not discoverable from
# the filesystem paths this tool scans, so they never appear as a tier here.
# "non-portable" is an Antigravity-only path label, so it never appears here.
PRECEDENCE = {
    "claude": {"global": (2, "personal"), "project": (3, "project"), "nested": (3, "project")},
    "gemini": {"project": (1, "workspace"), "nested": (1, "workspace"), "global": (2, "user")},
}
PRECEDENCE_TEXT = {"claude": "enterprise > personal > project",
                   "gemini": "workspace > user > extension > built-in",
                   "codex": "no precedence rule; both entries can appear in the picker"}


def collision_winner(tool: str, group: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Resolve which occurrence of a duplicated name wins, for one tool."""
    if tool == "codex":
        return {"winner": None, "tier": None, "tied": [s["real_path"] for s in group],
                "note": "Codex does not resolve collisions; the user picks."}
    ranked = []
    for skill in group:
        if tool not in skill["tools"]: continue
        tiers = [PRECEDENCE[tool][scope] for scope in skill["scopes"] if scope in PRECEDENCE[tool]]
        if tiers: ranked.append((min(tiers), skill))
    if not ranked:
        return {"winner": None, "tier": None, "tied": [], "note": "not visible to this tool"}
    best = min(rank for rank, _ in ranked)
    top = [skill for rank, skill in ranked if rank == best]
    if len(top) > 1:
        return {"winner": None, "tier": best[1], "tied": [s["real_path"] for s in top],
                "note": "same tier — winner not determinable from documented rules"}
    return {"winner": top[0]["real_path"], "tier": best[1], "tied": [], "note": ""}


def collision_report(skills: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for skill in skills: by_name[skill["name"]].append(skill)
    results = []
    for name, group in sorted(by_name.items()):
        if len(group) < 2: continue
        resolution = {tool: collision_winner(tool, group) for tool in ("claude", "gemini", "codex")}
        results.append({"name": name,
                        "occurrences": [{"path": s["real_path"], "scopes": s["scopes"], "tools": s["tools"]} for s in group],
                        "paths": [s["real_path"] for s in group],
                        "resolution": resolution, "precedence": PRECEDENCE_TEXT})
        findings.append(finding("warning", "name_collision", "Multiple distinct skills share this name", name))
    return results


def overlap_report(skills: List[Dict[str, Any]], config: Dict[str, Any], findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    owners = set((config.get("ownership") or {}).values())
    results = []
    for index, first in enumerate(skills):
        for second in skills[index + 1:]:
            shared = sorted(description_tokens(first["description"]) & description_tokens(second["description"]))
            phrases = sorted(quoted_phrases(first["description"]) & quoted_phrases(second["description"]))
            count = len(shared)
            if count <= 2 and not phrases: continue
            severity = "warning" if count >= 5 or phrases else "notice"
            if severity == "notice" and first["name"] not in owners and second["name"] not in owners: severity = "warning"
            # Two copies of one name are a real pair; label them by path so the
            # output is not the useless "brand-voice / brand-voice".
            if first["name"] == second["name"]:
                labels = [first["real_path"], second["real_path"]]
            else:
                labels = [first["name"], second["name"]]
            item = {"skills": [first["name"], second["name"]], "labels": labels, "shared_terms": shared,
                    "shared_term_count": count, "shared_quoted_phrases": phrases, "severity": severity}
            results.append(item)
            findings.append(finding(severity, "overlap", "These two may overlap — read them (shared terms: %d)" % count, "%s / %s" % (labels[0], labels[1])))
    return results


def budget_report(skills: List[Dict[str, Any]], config: Dict[str, Any], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    window = int((config.get("budget") or {}).get("context_window", CONTEXT_WINDOW_DEFAULT))
    result = {"context_window": window, "claude": {"total": 0, "limit": int(window * CLAUDE_BUDGET_FRACTION), "pocket_skills": 0},
              "codex": {"total": 0, "limit": min(8000, int(window * CODEX_BUDGET_FRACTION)), "pocket_skills": 0},
              "excluded_unknown": 0}
    for skill in skills:
        chars = len(skill["name"]) + len(skill["description"])
        # Each tool's budget counts only what that tool can see. A skill being
        # UNKNOWN in Gemini says nothing about Claude's or Codex's listing.
        for tool in ("claude", "codex"):
            if skill["states"].get(tool) == "POCKET":
                result[tool]["total"] += chars
                result[tool]["pocket_skills"] += 1
        # Excluded entirely: no tool with a readable invocation mode can see it.
        if not {"claude", "codex"} & set(skill["states"]) and "UNKNOWN" in skill["states"].values():
            result["excluded_unknown"] += 1
        if "claude" in skill["states"] and chars > CLAUDE_ENTRY_CAP:
            findings.append(finding("warning", "entry_cap_exceeded", "Claude listing entry exceeds %d characters" % CLAUDE_ENTRY_CAP, skill["name"], skill["real_path"]))
    for tool in ("claude", "codex"):
        result[tool]["status"] = "over" if result[tool]["total"] > result[tool]["limit"] else "pass"
        if result[tool]["status"] == "over": findings.append(finding("warning", "budget_exceeded", "%s pocket listing budget is over" % tool.title()))
    return result


def pocket_report(skills: List[Dict[str, Any]], config: Dict[str, Any], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    intended = set((config.get("pocket") or {}).get("skills", []))
    # The audit-wide rule: pocket in ANY tool counts as pocket, because one
    # tool auto-invoking it is enough to cost you context and surprise you.
    # Per-tool disagreement is reported separately as mode_disagreement.
    actual = {s["name"] for s in skills if "POCKET" in s["states"].values()}
    # Union the scopes: when two distinct skills share a name, a dict
    # comprehension keeps only the last, so a name that is global in one copy
    # and project in another could lose its global scope and escape the check.
    by_name_scopes: Dict[str, Set[str]] = defaultdict(set)
    for skill in skills: by_name_scopes[skill["name"]] |= set(skill["scopes"])
    rule = "a skill counts as pocket if it is POCKET in at least one tool that can see it"
    if not intended:
        if len(actual) > 5: findings.append(finding("warning", "pocket_count", "More than five pocket skills and no config is present"))
        return {"configured": False, "rule": rule, "pocket_count": len(actual), "correct": [],
                "intended_shelf_but_pocket": [], "intended_pocket_but_shelf": [], "project_pocket": []}
    # A repo's own skills are not governed by a global pocket list, so comparing
    # them against it produced false "intended shelf" hits. They are counted and
    # listed, just not measured against the config.
    project_pocket = sorted(name for name in actual
                            if not {"global", "non-portable"} & set(by_name_scopes.get(name, set())))
    actual = actual - set(project_pocket)
    rule += "; the config comparison covers global-scope skills only"
    # A configured name with no skill on disk is a stale config or a typo, not
    # a flag added by mistake. Reporting it as the latter sends you hunting for
    # a file that is not there.
    known = {s["name"] for s in skills}
    correct = sorted(intended & actual)
    shelf_but_pocket = sorted(actual - intended)
    pocket_but_shelf = sorted((intended - actual) & known)
    missing = sorted(intended - known)
    for name in shelf_but_pocket: findings.append(finding("warning", "intended_shelf_pocket", "Intended shelf skill is actually pocket", name))
    for name in pocket_but_shelf: findings.append(finding("warning", "intended_pocket_shelf", "Intended pocket skill is not actually pocket", name))
    for name in missing: findings.append(finding("warning", "intended_missing", "Config lists a pocket skill that is not installed", name))
    return {"configured": True, "rule": rule, "pocket_count": len(actual) + len(project_pocket), "correct": correct,
            "intended_shelf_but_pocket": shelf_but_pocket, "intended_pocket_but_shelf": pocket_but_shelf,
            "intended_but_not_installed": missing, "project_pocket": project_pocket}


def recommendations_for(findings: List[Dict[str, Any]]) -> List[str]:
    """Group by issue, then name who is affected.

    Deduping on the message alone hid distinct skills behind one line — two
    skills missing a description reported as a single recommendation.
    """
    rank = {"error": 0, "warning": 1, "notice": 2}
    groups: Dict[Tuple[int, str, str], List[str]] = {}
    for item in findings:
        key = (rank[item["severity"]], item["code"], item["message"])
        subjects = groups.setdefault(key, [])
        subject = item["skill"] or item["path"]
        if subject and subject not in subjects: subjects.append(subject)
    lines = []
    for (_, _, message), subjects in sorted(groups.items()):
        if not subjects:
            lines.append(message); continue
        shown = ", ".join(subjects[:5])
        if len(subjects) > 5: shown += " (+%d more)" % (len(subjects) - 5)
        lines.append("%s — %d affected: %s" % (message, len(subjects), shown))
    return lines


def lines_for(report: Dict[str, Any], quiet: bool = False) -> List[str]:
    meta, skills, findings = report["meta"], report["skills"], report["findings"]
    def section(title: str, lines: List[str]) -> List[str]: return ["\n" + title, "-" * len(title)] + (lines or ["none found"])
    lines = ["skill-audit %s | paths verified %s" % (meta["version"], meta["paths_verified"])]
    summary = ["%d unique skills; %d pocket in at least one tool; %d discovered entries; %d locations scanned" % (len(skills), report["pocket_check"]["pocket_count"], sum(len(s["reachable_from"]) for s in skills), len(meta["locations_scanned"])),
               "config: %s" % (meta["config"] if meta["config_present"] else "not present; using defaults")]
    summary.extend("%s: %s" % (item["status"], item["path"]) for item in meta["locations_scanned"])
    lines += section("Summary", summary)
    if not quiet:
        inventory = ["%-24s %-20s %4d lines | %s | %s" % (s["name"], "/".join(s["tools"]), s["line_count"], ", ".join("%s=%s" % pair for pair in sorted(s["states"].items())), s["real_path"]) for s in skills]
        lines += section("Inventory", inventory)
    # A finding may carry a skill, a path, or both. Printing only the path left
    # config-level warnings anonymous ("Intended shelf skill is actually pocket"
    # five times, no names).
    def subject(f: Dict[str, Any]) -> str:
        parts = [part for part in (f["skill"], f["path"]) if part]
        return (" — " + " @ ".join(parts)) if parts else ""
    for title, level in (("Errors", "error"), ("Warnings", "warning"), ("Notices", "notice")):
        values = ["[%s] %s%s" % (f["code"], f["message"], subject(f)) for f in findings if f["severity"] == level]
        lines += section(title, values)
    # --quiet skips inventory, budget, and pocket check only (brief 8b).
    # Collisions and overlaps are findings-shaped, so they survive quiet mode.
    collisions = []
    for item in report["collisions"]:
        collisions.append("%s — %d copies:" % (item["name"], len(item["occurrences"])))
        collisions.extend("    %s [%s]" % (occurrence["path"], "/".join(occurrence["scopes"])) for occurrence in item["occurrences"])
        for tool in ("claude", "gemini", "codex"):
            resolution = item["resolution"][tool]
            if resolution["winner"]:
                verdict = "%s wins (%s tier)" % (resolution["winner"], resolution["tier"])
            else:
                verdict = resolution["note"] or "no winner"
            collisions.append("    %-8s %s" % (tool + ":", verdict))
    lines += section("Name collisions", collisions)
    lines += section("Overlap candidates", ["%s / %s: %d shared distinctive terms (heuristic — read both files)" % (o["labels"][0], o["labels"][1], o["shared_term_count"]) for o in report["overlaps"]])
    if not quiet:
        budget = report["budget"]
        lines += section("Budget", [
            "Claude: %(total)d/%(limit)d chars across %(pocket_skills)d pocket skills (%(status)s)" % budget["claude"],
            "Codex:  %(total)d/%(limit)d chars across %(pocket_skills)d pocket skills (%(status)s)" % budget["codex"],
            "%d skills excluded: only Gemini/Antigravity can see them, and their mode is UNKNOWN" % budget["excluded_unknown"]])
        pocket = report["pocket_check"]
        lines += section("Pocket check", ["rule: %s" % pocket["rule"],
                                          "(this is deliberately broader than the per-tool budgets above)",
                                          "pocket count: %d" % pocket["pocket_count"],
                                          "correct: %s" % ", ".join(pocket["correct"]),
                                          "intended shelf but pocket: %s" % ", ".join(pocket["intended_shelf_but_pocket"]),
                                          "intended pocket but shelf: %s" % ", ".join(pocket["intended_pocket_but_shelf"]),
                                          "in config but not installed: %s" % ", ".join(pocket.get("intended_but_not_installed", [])),
                                          "project-scope pocket (not measured against config): %s" % ", ".join(pocket.get("project_pocket", []))])
    if quiet:
        # The brief's rule is that a section never vanishes silently, because a
        # missing one reads as a bug. Naming the suppression keeps that true.
        lines += ["\nInventory, Budget, Pocket check", "-" * 30, "suppressed by --quiet (exit code is unaffected)"]
    lines += section("Recommended actions", ["%d. %s" % (i + 1, item) for i, item in enumerate(report["recommendations"])])
    lines += ["\nPath note: these paths moved recently. Re-verify quarterly; Antigravity portable-path evidence is community testing, not official documentation."]
    return lines


def markdown_for(report: Dict[str, Any]) -> str:
    return "# skill-audit report\n\n```text\n%s\n```\n" % "\n".join(lines_for(report))


def parser() -> argparse.ArgumentParser:
    non_goals = "Non-goals: does not detect real prose conflicts; does not fix anything; does not verify triggering; does not check Gemini or Antigravity shelf state (it reports UNKNOWN)."
    arg = argparse.ArgumentParser(description="Read-only audit of local agent skills. " + non_goals, epilog="Exit 0: clean/warnings; 1: strict warnings; 2: errors; 3: script failure. " + non_goals)
    arg.add_argument("--repo", action="append", default=[], metavar="PATH", help="Repository to scan (repeatable)")
    arg.add_argument("--config", help="TOML config path (default ~/.skill-audit.toml)")
    arg.add_argument("--json", action="store_true", help="Emit full JSON report")
    arg.add_argument("--markdown", metavar="PATH", help="Also write full Markdown report to PATH")
    arg.add_argument("--quiet", action="store_true",
                     help="Suppress Inventory, Budget and Pocket check. Summary, Errors, "
                          "Warnings, Notices, Name collisions, Overlap candidates and "
                          "Recommended actions still print. Never changes the exit code.")
    arg.add_argument("--tool", choices=TOOLS, action="append", help="Limit scan to a tool")
    arg.add_argument("--strict", action="store_true", help="Warnings exit 1")
    arg.add_argument("--version", action="store_true", help="Print version and paths-verified date")
    return arg


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    if args.version:
        print("skill-audit %s (PATHS_VERIFIED %s)" % (VERSION, PATHS_VERIFIED)); return 0
    try:
        report = build_report(args)
        if args.markdown:
            Path(args.markdown).expanduser().write_text(markdown_for(report), encoding="utf-8")
        if args.json: print(json.dumps(report, indent=2, sort_keys=True))
        else: print("\n".join(lines_for(report, args.quiet)))
        severities = {item["severity"] for item in report["findings"]}
        return 2 if "error" in severities else (1 if args.strict and "warning" in severities else 0)
    except Exception as exc:
        print("skill-audit failed: %s" % exc, file=sys.stderr); return 3


if __name__ == "__main__":
    raise SystemExit(main())
