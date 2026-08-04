#!/usr/bin/env python3
"""Read-only audit of agent SKILL.md libraries.

It never changes skill files.  The only write this program can perform is the
explicit --markdown report destination.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
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

VERSION = "1.1.0"
PATHS_VERIFIED = "2026-08-04"
# Re-verified 2026-08-04 against primary vendor sources, not summaries:
#   Claude    code.claude.com/docs/en/skills  -> ~/.claude/skills, enterprise>personal>project
#   Codex     learn.chatgpt.com/docs/build-skills -> $HOME/.agents/skills, /etc/codex/skills
#   Gemini    github.com/google-gemini/gemini-cli docs/cli/using-agent-skills.md
#   Antigravity  community write-ups only; still no vendor doc.
# Re-verify quarterly: vendors have moved them.
GLOBAL_PATHS = {
    "claude": ("~/.claude/skills",),
    # Codex moved to ~/.agents/skills, but the old path still holds installs on
    # any machine set up before the move, and scanning a missing directory costs
    # nothing. Dropping it made 26 real skills invisible on this machine.
    # /etc/codex/skills is the documented system/admin location. It is not on
    # this machine, but scanning a missing directory costs nothing and an
    # admin-installed skill you cannot see is exactly the failure this tool exists to catch.
    "codex": ("~/.agents/skills", "~/.codex/skills", "/etc/codex/skills"),
    "gemini": ("~/.agents/skills", "~/.gemini/skills"),
    "antigravity": ("~/.gemini/config/skills",),
    # Claude Desktop caches the account's synced skills under two identifiers it
    # assigns, so the '*' segments are load-bearing — there is no fixed path.
    # Observed on macOS 2026-08-04; this is one machine, not documentation, and
    # it is a cache the app owns, so treat a miss as "not synced yet", never as
    # "no skills". Linux/Windows equivalents are unverified and not listed.
    "claude-desktop": (
        "~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/*/*/skills",
    ),
}
ANTIGRAVITY_NON_PORTABLE = (
    "~/.gemini/antigravity/skills", "~/.gemini/antigravity-cli/skills"
)
TOOLS = ("claude", "codex", "gemini", "antigravity", "claude-desktop")
# Skills only compete with others in the same listing. Claude Desktop's library
# syncs from the account and never shares a listing with the local filesystem
# one, so a name present in both is two libraries agreeing, not a collision —
# and comparing their descriptions for overlap compares skills that can never
# be offered to the same model at the same time.
DESKTOP = "claude-desktop"
# Skills you did not write and cannot edit: Anthropic's Desktop built-ins and
# Codex's bundled .system skills. Their quality findings are demoted to notice
# so a vendor's wording can never fail your --strict run. They are NOT hidden:
# their descriptions still consume real listing budget, so you need to see them.
# Matched on the `.system` directory rather than the full `~/.codex/skills/...`
# path, so a Codex install that keeps its skills anywhere else still matches.
VENDOR_MARKERS = ("/.system/",)
QUALITY_CODES = {"thin_description", "bloated_description", "missing_trigger",
                 "vague_description", "late_job_noun", "oversized_body",
                 "unknown_field", "overlap", "intent_shadow",
                 # A vendor's malformed frontmatter is as unfixable as its
                 # wording: Codex ships skill-creator with a nested `metadata:`
                 # block this parser cannot read, and no edit of yours changes it.
                 "unparseable_field"}
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
    "config_error", "unreadable", "suppress_unmatched", "dangling_reference",
    "intent_shadow",
}
# A body pointing at another skill's file. Only path-shaped mentions count: a
# bare skill name in prose is indistinguishable from ordinary English.
REFERENCE_RE = re.compile(r"\bskills/([A-Za-z0-9][\w.-]*)/SKILL\.md", re.I)
KNOWN_FIELDS = {
    "name", "description", "allowed-tools", "disable-model-invocation", "paths",
    "when_to_use", "license", "metadata", "compatibility", "argument-hint",
}
# Documented agents/openai.yaml blocks whose nested shape the one-level parser
# cannot read. None of them affects invocation mode, so reporting them as
# unparseable was noise about a correct file.
CODEX_NESTED_BLOCKS = ("dependencies", "interface", "tools")
# Overlap labels are joined with this, and config pair entries are split on it.
PAIR_SEPARATOR = " / "
# The documented config shape. A section mapped to None is a free-form table of
# string -> string; anything not listed here is ignored rather than validated.
CONFIG_SHAPE = {
    "pocket": {"skills": list},
    "ownership": None,
    "overlap": {"suppress": list},
    "budget": {"context_window": int},
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
        # A whole-line comment is legal YAML and common in a hand-written
        # agents/openai.yaml. Reporting one as an unparseable field made a valid
        # file look broken.
        if not raw.strip() or raw.lstrip().startswith("#"):
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
                if lines[i].strip() and not lines[i].lstrip().startswith("#"):
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


def paths_under(root: Path) -> Tuple[List[Path], List[Path]]:
    """Skill directories under root, plus every broken symlink met on the way."""
    if not root.exists(): return [], []
    found: List[Path] = []
    broken: List[Path] = []
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
            # A dangling link is not a directory, so os.walk reports it under
            # `files`. Collecting it here is what makes depth > 1 visible: the
            # old iterdir pass in scan_root only ever saw the root's children.
            for name in files:
                candidate = current_path / name
                if candidate.is_symlink() and not candidate.exists():
                    broken.append(candidate)
    except OSError:
        pass
    return found, broken


def expand_root(raw: str) -> List[Path]:
    """Expand one configured location, which may be a glob.

    A '*' means the vendor nests the directory under identifiers that cannot be
    predicted, so every match is a real root. A pattern that matches nothing is
    returned as-is so it still shows up in locations_scanned as 'not present' —
    a location that silently vanishes from the summary is the one failure mode
    this tool exists to prevent.
    """
    expanded = os.path.expanduser(raw)
    if "*" not in expanded: return [Path(expanded)]
    matches = sorted(glob.glob(expanded))
    return [Path(match) for match in matches] if matches else [Path(expanded)]


def desktop_states(skill_dir: Path) -> Optional[bool]:
    """Claude Desktop's per-skill 'enabled' flag, from the sibling manifest.

    This is Desktop's equivalent of disable-model-invocation, and reading it
    beats assuming POCKET: the field demonstrably exists, so guessing would be
    the same mistake as guessing Gemini's mode instead of reporting UNKNOWN.
    Returns None when the manifest is missing or unreadable, which the caller
    reports as UNKNOWN. Only a literal JSON boolean counts: an entry with no
    'enabled' key, or a truthy stand-in like "true" or 1, is an absent signal,
    and coercing it with bool() would silently invent SHELF for a skill whose
    mode the manifest never stated.
    """
    manifest = skill_dir.parent.parent / "manifest.json"
    text, error = safe_read(manifest)
    if error or not text: return None
    try:
        entries = json.loads(text).get("skills", [])
    except (ValueError, AttributeError):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == skill_dir.name:
            enabled = entry.get("enabled")
            return enabled if isinstance(enabled, bool) else None
    return None


def path_family(root: Path) -> str:
    """Which cupboard a root belongs to: .agents, .gemini, .claude, .codex, or other.

    Gemini reads both .agents/skills and .gemini/skills at the same tier, and
    resolves a same-tier tie in favour of .agents, so the family is needed to
    tell those two apart.

    Walks from the leaf so the *nearest* marker wins: a repo that happens to sit
    under ~/.agents still has its own .claude/skills classified as claude.
    """
    for part in reversed(Path(root).parts):
        if part in (".agents", ".gemini", ".claude", ".codex"): return part[1:]
    return "other"


def scan_root(root: Path, tool: str, label: str, nested: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    records, problems = [], []
    if root.is_symlink() and not root.exists():
        return records, [finding("warning", "broken_symlink", "Broken symlink", path=str(root))]
    if not root.exists(): return records, []
    try:  # paths_under swallows OSError; probe first so an unreadable root still reports.
        os.scandir(root).close()
    except OSError as exc:
        return records, [finding("warning", "unreadable", "Cannot scan location: %s" % exc, path=str(root))]
    skill_dirs, broken = paths_under(root)
    problems.extend(finding("warning", "broken_symlink", "Broken symlink", path=str(p)) for p in broken)
    prec_key = "%s:%s" % (path_family(root), label)
    for skill_dir in skill_dirs:
        file_path = skill_dir / "SKILL.md"
        try: real = str(skill_dir.resolve(strict=True))
        except OSError:
            problems.append(finding("warning", "broken_symlink", "Broken skill path", path=str(skill_dir))); continue
        records.append({"source": str(skill_dir), "real_path": real, "file": str(file_path),
                        "tool": tool, "label": label, "nested": nested,
                        "precedence_key": prec_key})
    return records, problems


def entry_identity(path: str) -> Any:
    """What makes two paths the same filesystem entry, for dedupe purposes.

    lstat does not follow the final component but does follow the parents, so
    alternate routes to one link (~/.agents/skills -> ~/.claude/skills) share a
    (device, inode) while two distinct links never do — which is exactly the
    line between an alias and a second thing to clean up.
    """
    try:
        info = os.lstat(path)
        return (info.st_dev, info.st_ino)
    except OSError:  # vanished mid-scan, or a path that was never on disk
        return os.path.realpath(path)


def dedupe_scan_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One dead link reachable from four cupboards is one problem, not four.

    Coalescing is by identity of the entry itself (see entry_identity), NOT by
    realpath: a dangling link realpaths to its missing *target*, so two separate
    links aimed at the same absent path collapsed into one finding and the
    second one silently never got cleaned up.
    """
    seen, kept = set(), []
    for item in findings:
        key = (item["code"], entry_identity(item["path"]) if item["path"] else item["skill"])
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
            for marker, tool in ((".claude", "claude"), (".agents", "codex"), (".agents", "gemini"), (".gemini", "gemini")):
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


def validated_config(config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Drop config values that parse as TOML but are the wrong shape.

    Every consumer of this dictionary indexes, iterates, or coerces it. Valid
    TOML with a scalar where a list belongs used to raise out of the run and
    exit 3 — the one outcome a read-only audit must never produce. Unknown
    sections pass through untouched: this validates the documented shape, it
    does not police the file.
    """
    if not isinstance(config, dict): return {}, ["top level is not a table"]
    clean, problems = {}, []
    for section, value in config.items():
        if section not in CONFIG_SHAPE:
            clean[section] = value
            continue
        if not isinstance(value, dict):
            problems.append("[%s] is not a table" % section)
            continue
        fields = CONFIG_SHAPE[section]
        if fields is None:  # ownership: a free-form table of string -> string
            clean[section] = {key: val for key, val in value.items() if isinstance(val, str)}
            problems += ["[%s] %s is not a string" % (section, key) for key in sorted(set(value) - set(clean[section]))]
            continue
        kept = {}
        for key, val in value.items():
            expected = fields.get(key)
            if expected is None: kept[key] = val
            elif expected is list:
                if isinstance(val, list) and all(isinstance(item, str) for item in val): kept[key] = val
                else: problems.append("[%s] %s must be a list of strings" % (section, key))
            # bool is an int subclass, and `context_window = true` would quietly
            # become a one-character budget.
            elif isinstance(val, int) and not isinstance(val, bool) and val > 0: kept[key] = val
            else: problems.append("[%s] %s must be a positive integer" % (section, key))
        clean[section] = kept
    return clean, problems


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
        if not re.search(r"\b(use (?:when|before|after|at the (?:start|end) of)|trigger|when (the )?user|for .* requests?)\b", description, re.I):
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
            if field in CODEX_NESTED_BLOCKS: continue
            findings.append(finding("warning", "unparseable_field", "Unparseable Codex policy field '%s'" % field, name, real_path, line - 1 if synthetic_policy else line))
        policy_value = policy.get("policy", {}).get("allow_implicit_invocation") if isinstance(policy.get("policy"), dict) else None
        parsed_bool = bool_value(policy_value)
        if policy_value is not None and parsed_bool is None:
            findings.append(finding("warning", "unparseable_field", "Invalid boolean allow_implicit_invocation", name, real_path))
        codex_shelf = parsed_bool is False
    visible = {entry["tool"] for entry in entries}
    desktop_enabled = desktop_states(skill_dir) if DESKTOP in visible else None
    states = {}
    for tool in TOOLS:
        if tool not in visible: continue
        if tool == "claude": states[tool] = "SHELF" if claude_shelf else "POCKET"
        elif tool == "codex": states[tool] = "SHELF" if codex_shelf else "POCKET"
        elif tool == DESKTOP:
            states[tool] = "UNKNOWN" if desktop_enabled is None else ("POCKET" if desktop_enabled else "SHELF")
        else: states[tool] = "UNKNOWN"
    known = {state for state in states.values() if state != "UNKNOWN"}
    if len(known) > 1:
        findings.append(finding("warning", "mode_disagreement", "Tools disagree on invocation mode", name, real_path))
    return {"name": name, "real_path": real_path, "file": str(skill_dir / "SKILL.md"),
            "library": DESKTOP if DESKTOP in visible else "local",
            "reachable_from": sorted({entry["source"] for entry in entries}), "tools": sorted(visible),
            "states": states, "line_count": line_count, "character_count": len(text or ""),
            "description": description, "nested": any(entry["nested"] for entry in entries),
            "references": sorted(set(REFERENCE_RE.findall(text or "")) - {name}),
            "scopes": sorted({entry["label"] for entry in entries}),
            "precedence_keys": sorted({entry["precedence_key"] for entry in entries}),
            "occurrences": sorted({(entry["tool"], entry["label"], entry["source"]) for entry in entries})}


def is_vendor(real_path: str, library: str = "local") -> bool:
    """A skill installed by a vendor rather than authored by the user."""
    return library == DESKTOP or any(marker in real_path for marker in VENDOR_MARKERS)


def demote_vendor_findings(findings: List[Dict[str, Any]], skills: List[Dict[str, Any]],
                           overlaps: Optional[List[Dict[str, Any]]] = None) -> None:
    """Vendor wording is not the user's bug, so it must not fail --strict.

    The matching overlap records are demoted too: leaving them at the old
    severity would let a JSON consumer filtering on overlaps[].severity
    disagree with the findings list about the same pair.
    """
    vendor_paths = {s["real_path"] for s in skills if is_vendor(s["real_path"], s.get("library", "local"))}
    vendor_names = {s["name"] for s in skills if is_vendor(s["real_path"], s.get("library", "local"))}
    for item in findings:
        if item["severity"] != "warning" or item["code"] not in QUALITY_CODES: continue
        # An overlap finding carries the joined pair label, not one skill.
        subjects = item["skill"].split(PAIR_SEPARATOR) if PAIR_SEPARATOR in item["skill"] else [item["skill"]]
        if item["path"] in vendor_paths or (subjects and all(s in vendor_names for s in subjects if s)):
            item["severity"] = "notice"
            item["message"] += " [vendor-installed]"
    for pair in overlaps or []:
        if pair["severity"] == "warning" and all(n in vendor_names for n in pair["skills"]):
            pair["severity"] = "notice"
            pair["vendor_installed"] = True


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    selected = set(args.tool or TOOLS)
    entries: List[Dict[str, Any]] = []; findings: List[Dict[str, Any]] = []; locations = []
    home = Path.home()
    for tool in TOOLS:
        if tool not in selected: continue
        for raw in GLOBAL_PATHS[tool]:
            for root in expand_root(raw):
                locations.append({"path": str(root), "status": "present" if root.exists() else "not present"})
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
    config, config_problems = validated_config(config)
    for problem in config_problems:
        findings.append(finding("warning", "config_error", "Ignoring malformed config value: %s" % problem, path=str(config_path)))
    collisions = collision_report(skills, findings)
    dangling = reference_report(skills, findings)
    overlaps = overlap_report(skills, config, findings)
    budget = budget_report(skills, config, findings)
    pocket = pocket_report(skills, config, findings)
    demote_vendor_findings(findings, skills, overlaps)
    recommendations = recommendations_for(findings)
    return {"meta": {"version": VERSION, "paths_verified": PATHS_VERIFIED,
                      "scan_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                      "locations_scanned": locations, "config": str(config_path), "config_present": config_path.exists()},
            "skills": skills, "findings": findings, "collisions": collisions, "overlaps": overlaps,
            "dangling_references": dangling,
            "budget": budget, "pocket_check": pocket, "recommendations": recommendations}


# Documented precedence, expressed as tiers. Lower number wins.
# "global" is a user-level install; "project"/"nested" live inside a repo.
# Enterprise (Claude) and extension/built-in (Gemini) are not discoverable from
# the filesystem paths this tool scans, so they never appear as a tier here.
# Keys are "<cupboard family>:<scope>". Lower rank wins.
#
# Claude: enterprise > personal > project. Enterprise is not filesystem-visible
# from the paths scanned here, so rank 1 is unused.
# Verified 2026-08-03 against code.claude.com/docs/en/skills: "When skills share
# the same name across levels, enterprise overrides personal, and personal
# overrides project." Note this is the OPPOSITE of Claude's *settings*
# precedence (where project beats user) — do not "fix" it to match settings.
# Plugin skills are namespaced plugin-name:skill-name and cannot collide, so
# they need no rank. Nested skills hold rank 3 alongside project skills, but a
# nested/project pair is NOT an unresolvable tie: re-verified 2026-08-04, the
# docs state a clashing nested skill stays available under a path-prefixed name
# ("apps/web/.claude/skills/deploy" -> /apps/web:deploy), so both load. The tie
# note says so rather than claiming no winner can be determined.
#
# Gemini: workspace > user > extension > built-in (documented rules).
# WITHIN a tier, .agents/skills beats .gemini/skills. Re-checked 2026-08-04: the
# vendor doc calls the two "aliases" and states no within-tier order, so this
# stays an observation, NOT a documented rule. The evidence is first-party
# runtime output rather than community report -- `gemini skills list --all`
# prints e.g. "Skill conflict detected: <name> from ~/.agents/skills/... is
# overriding the same skill from ~/.gemini/skills/...", naming the direction.
# Extension and built-in skills do not live in a scanned path, so they never
# rank here.
# "non-portable" is an Antigravity-only label and never reaches these tables.
PRECEDENCE = {
    "claude": {"claude:global": (2, "personal"),
               "claude:project": (3, "project"), "claude:nested": (3, "project")},
    "gemini": {"agents:project": (1, "workspace"), "agents:nested": (1, "workspace"),
               "gemini:project": (2, "workspace"), "gemini:nested": (2, "workspace"),
               "agents:global": (3, "user"), "gemini:global": (4, "user")},
}
PRECEDENCE_TEXT = {"claude": "enterprise > personal > project",
                   "claude-desktop": "separate account-synced library; names are unique server-side",
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
        tiers = [PRECEDENCE[tool][key] for key in skill["precedence_keys"] if key in PRECEDENCE[tool]]
        # Defensive assertion, not a normal path: every root the scanner yields
        # carries a .claude/.agents/.gemini marker, so path_family always returns
        # a known family. This catches a future root added without a PRECEDENCE
        # entry, and refuses to guess rather than reporting a wrong winner.
        if not tiers and any(k.endswith((":global", ":project", ":nested")) for k in skill["precedence_keys"]):
            return {"winner": None, "tier": None, "tied": [s["real_path"] for s in group],
                    "note": "unrecognized skill root — precedence not determinable"}
        if tiers: ranked.append((min(tiers), skill))
    if not ranked:
        return {"winner": None, "tier": None, "tied": [], "note": "not visible to this tool"}
    best = min(rank for rank, _ in ranked)
    top = [skill for rank, skill in ranked if rank == best]
    if len(top) > 1:
        # A Claude project/nested pair is a documented coexistence, not a tie:
        # the nested copy stays available under a path-prefixed name, so saying
        # "no winner" would send you hunting for a conflict that does not exist.
        keys = {key for skill in top for key in skill["precedence_keys"]}
        if tool == "claude" and {"claude:project", "claude:nested"} <= keys:
            return {"winner": None, "tier": best[1], "tied": [s["real_path"] for s in top],
                    "note": "both load — the nested copy is namespaced <path>:<name>"}
        return {"winner": None, "tier": best[1], "tied": [s["real_path"] for s in top],
                "note": "same tier — winner not determinable from documented rules"}
    return {"winner": top[0]["real_path"], "tier": best[1], "tied": [], "note": ""}


def collision_report(skills: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    # Grouped per library: a name in both the local library and the Desktop one
    # is the same skill synced two ways, not two skills fighting over a listing,
    # and no precedence rule relates them because they never meet.
    for skill in skills: by_name[(skill.get("library", "local"), skill["name"])].append(skill)
    results = []
    for (_, name), group in sorted(by_name.items()):
        if len(group) < 2: continue
        resolution = {tool: collision_winner(tool, group) for tool in ("claude", "gemini", "codex")}
        results.append({"name": name,
                        "occurrences": [{"path": s["real_path"], "scopes": s["scopes"],
                                         "precedence_keys": s["precedence_keys"], "tools": s["tools"]} for s in group],
                        "paths": [s["real_path"] for s in group],
                        "resolution": resolution, "precedence": PRECEDENCE_TEXT})
        findings.append(finding("warning", "name_collision", "Multiple distinct skills share this name", name))
    return results


def overlap_report(skills: List[Dict[str, Any]], config: Dict[str, Any], findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    owners = set((config.get("ownership") or {}).values())
    # A pair entry is split on the " / " separator the labels are printed with,
    # not on any slash: a label is a real path when two skills share a name, and
    # splitting on the first slash turned "/home/dup / /repo/dup" into nonsense
    # that silently matched nothing.
    suppressed_pairs, suppressed_names = set(), set()
    for entry in (config.get("overlap") or {}).get("suppress", []):
        entry = entry.strip()
        if not entry: continue
        if PAIR_SEPARATOR in entry:
            suppressed_pairs.add(tuple(sorted(part.strip() for part in entry.split(PAIR_SEPARATOR, 1))))
        else:
            suppressed_names.add(entry)
    used_pairs, used_names = set(), set()
    results = []
    for index, first in enumerate(skills):
        for second in skills[index + 1:]:
            # Two skills that are never offered to the same model at the same
            # time cannot shadow each other, whatever they share.
            if first.get("library", "local") != second.get("library", "local"): continue
            shared = sorted(description_tokens(first["description"]) & description_tokens(second["description"]))
            phrases = sorted(quoted_phrases(first["description"]) & quoted_phrases(second["description"]))
            shadows = phrase_shadows(first["description"], second["description"])
            count = len(shared)
            if count <= 2 and not phrases and not shadows: continue
            first_states = first.get("states") or {t: "POCKET" for t in TOOLS}
            second_states = second.get("states") or {t: "POCKET" for t in TOOLS}
            both_pocket = any(first_states.get(t) == "POCKET" and second_states.get(t) == "POCKET" for t in TOOLS)
            if both_pocket:
                severity = "warning" if count >= 5 or phrases else "notice"
                if severity == "notice" and first["name"] not in owners and second["name"] not in owners: severity = "warning"
            else:
                severity = "notice"
            # Two copies of one name are a real pair; label them by path so the
            # output is not the useless "brand-voice / brand-voice".
            if first["name"] == second["name"]:
                labels = [first["real_path"], second["real_path"]]
            else:
                labels = [first["name"], second["name"]]

            matched_pairs = {key for key in (tuple(sorted([first["name"], second["name"]])), tuple(sorted(labels)))
                             if key in suppressed_pairs}
            matched_names = {name for name in (first["name"], second["name"]) if name in suppressed_names}
            used_pairs |= matched_pairs
            used_names |= matched_names
            is_suppressed = bool(matched_pairs or matched_names)

            item = {"skills": [first["name"], second["name"]], "labels": labels, "shared_terms": shared,
                    "shared_term_count": count, "shared_quoted_phrases": phrases, "severity": severity,
                    "shadowed_phrases": shadows, "suppressed": is_suppressed}
            results.append(item)
            if not is_suppressed:
                if count > 2 or phrases:
                    findings.append(finding(severity, "overlap", "These two may overlap — read them (shared terms: %d)" % count, PAIR_SEPARATOR.join(labels)))
                for shorter, longer in shadows:
                    findings.append(finding("notice", "intent_shadow",
                                            "Trigger '%s' is contained in '%s' — read both (routing is the model's call, not a rule)" % (shorter, longer),
                                            PAIR_SEPARATOR.join(labels)))
    # A mute list that can rot invisibly is worse than no mute list: a renamed
    # skill or a typo would otherwise stop suppressing and never say so.
    stale = sorted(PAIR_SEPARATOR.join(pair) for pair in suppressed_pairs - used_pairs)
    stale += sorted(suppressed_names - used_names)
    for entry in stale:
        findings.append(finding("warning", "suppress_unmatched", "Config suppresses an overlap that was not detected", entry))
    return results


def reference_report(skills: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Skill bodies that point at a SKILL.md no longer in the scanned library.

    A rename or a delete rots these silently. Only missing targets are reported:
    a reference to a SHELF skill is the correct pattern, not a fault — explicit
    invocation is exactly what a shelved skill is for.
    """
    known = {skill["name"] for skill in skills}
    dangling = []
    for skill in skills:
        for target in skill["references"]:
            if target in known: continue
            dangling.append({"skill": skill["name"], "missing": target})
            findings.append(finding("warning", "dangling_reference",
                                    "Body references skills/%s/SKILL.md, which is not in the scanned library" % target,
                                    skill["name"], skill["real_path"]))
    return dangling


def phrase_shadows(one: str, other: str) -> List[List[str]]:
    """Quoted trigger phrases where one is a whole-word slice of the other.

    A hint, not a verdict: the shorter trigger covers every request the longer
    one names, so the pair is worth reading. Which skill actually gets picked is
    the model's call over both full descriptions and the surrounding context —
    this tool does not verify triggering, so containment cannot show that either
    skill is unreachable. Single-word phrases are excluded: they match far too
    much to say anything.
    """
    first, second = quoted_phrases(one), quoted_phrases(other)
    pairs = [(a, b) for a in first for b in second] + [(a, b) for a in second for b in first]
    return [list(pair) for pair in sorted({
        (shorter, longer) for shorter, longer in pairs
        if shorter != longer and len(shorter.split()) >= 2 and " %s " % shorter in " %s " % longer})]


def budget_report(skills: List[Dict[str, Any]], config: Dict[str, Any], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    window = int((config.get("budget") or {}).get("context_window", CONTEXT_WINDOW_DEFAULT))
    result = {"context_window": window, "claude": {"total": 0, "limit": int(window * CLAUDE_BUDGET_FRACTION), "pocket_skills": 0},
              "codex": {"total": 0, "limit": min(8000, int(window * CODEX_BUDGET_FRACTION)), "pocket_skills": 0},
              # Counted but not judged: no published listing budget exists for
              # Desktop, and inventing a limit would manufacture a pass/fail the
              # vendor never stated. The total is the useful part.
              DESKTOP: {"total": 0, "limit": None, "pocket_skills": 0, "status": "not measured"},
              "excluded_unknown": 0}
    for skill in skills:
        chars = len(skill["name"]) + len(skill["description"])
        # Each tool's budget counts only what that tool can see. A skill being
        # UNKNOWN in Gemini says nothing about Claude's or Codex's listing.
        for tool in ("claude", "codex", DESKTOP):
            if skill["states"].get(tool) == "POCKET":
                result[tool]["total"] += chars
                result[tool]["pocket_skills"] += 1
        # Excluded entirely: no tool with a readable invocation mode can see it.
        if not {"claude", "codex", DESKTOP} & set(skill["states"]) and "UNKNOWN" in skill["states"].values():
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
    # Judged per library. This config cannot turn a Claude Desktop skill off —
    # that switch lives in the app — so a name is measured against it only when
    # a LOCAL copy is pocket. Keying on the name alone reported 15 Desktop
    # skills as drift no edit to this file could ever resolve, including names
    # like brand-voice whose local copy is correctly shelved.
    pocket_in = lambda group: {s["name"] for s in group if "POCKET" in s["states"].values()}
    local_skills = [s for s in skills if s.get("library", "local") != DESKTOP]
    actual = pocket_in(local_skills)
    desktop_pocket = sorted(pocket_in([s for s in skills if s.get("library") == DESKTOP]))
    # Counted by distinct name, matching the rule above. Summing the per-library
    # lists instead counted a name synced to both libraries twice.
    pocket_count = len(pocket_in(skills))
    # Union the scopes: when two distinct skills share a name, a dict
    # comprehension keeps only the last, so a name that is global in one copy
    # and project in another could lose its global scope and escape the check.
    by_name_scopes: Dict[str, Set[str]] = defaultdict(set)
    for skill in skills: by_name_scopes[skill["name"]] |= set(skill["scopes"])
    rule = "a skill counts as pocket if it is POCKET in at least one tool that can see it"
    if not intended:
        if pocket_count > 5: findings.append(finding("warning", "pocket_count", "More than five pocket skills and no config is present"))
        return {"configured": False, "rule": rule, "pocket_count": pocket_count, "correct": [],
                "intended_shelf_but_pocket": [], "intended_pocket_but_shelf": [], "project_pocket": [],
                "desktop_pocket": desktop_pocket}
    # A repo's own skills are not governed by a global pocket list, so comparing
    # them against it produced false "intended shelf" hits. They are counted and
    # listed, just not measured against the config.
    project_pocket = sorted(name for name in actual
                            if not {"global", "non-portable"} & set(by_name_scopes.get(name, set())))
    actual = actual - set(project_pocket)
    rule += "; the config comparison covers global-scope skills only"
    rule += "; Claude Desktop's library is counted but not measured against it"
    # A configured name with no skill on disk is a stale config or a typo, not
    # a flag added by mistake. Reporting it as the latter sends you hunting for
    # a file that is not there.
    known = {s["name"] for s in local_skills}
    correct = sorted(intended & actual)
    shelf_but_pocket = sorted(actual - intended)
    pocket_but_shelf = sorted((intended - actual) & known)
    missing = sorted(intended - known)
    for name in shelf_but_pocket: findings.append(finding("warning", "intended_shelf_pocket", "Intended shelf skill is actually pocket", name))
    for name in pocket_but_shelf: findings.append(finding("warning", "intended_pocket_shelf", "Intended pocket skill is not actually pocket", name))
    for name in missing: findings.append(finding("warning", "intended_missing", "Config lists a pocket skill that is not installed", name))
    return {"configured": True, "rule": rule,
            "pocket_count": pocket_count, "correct": correct,
            "intended_shelf_but_pocket": shelf_but_pocket, "intended_pocket_but_shelf": pocket_but_shelf,
            "intended_but_not_installed": missing, "project_pocket": project_pocket,
            "desktop_pocket": desktop_pocket}


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
        # Print precedence keys, not scopes: two copies can share a scope and
        # still resolve differently (Gemini's .agents-over-.gemini preference),
        # and "[global] / [global]" cannot explain the winner below.
        collisions.extend("    %s [%s]" % (occurrence["path"], "/".join(occurrence["precedence_keys"])) for occurrence in item["occurrences"])
        for tool in ("claude", "gemini", "codex"):
            resolution = item["resolution"][tool]
            if resolution["winner"]:
                verdict = "%s wins (%s tier)" % (resolution["winner"], resolution["tier"])
            else:
                verdict = resolution["note"] or "no winner"
            collisions.append("    %-8s %s" % (tool + ":", verdict))
    lines += section("Name collisions", collisions)
    # A silently shorter section reads as "no overlaps", which is the one thing
    # a mute list must never be able to imply.
    overlaps = []
    for item in report["overlaps"]:
        if item.get("suppressed"): continue
        overlaps.append("%s: %d shared distinctive terms (heuristic — read both files)" % (PAIR_SEPARATOR.join(item["labels"]), item["shared_term_count"]))
        overlaps.extend("    trigger '%s' is contained in '%s' (heuristic — read both files)" % (shorter, longer)
                        for shorter, longer in item.get("shadowed_phrases", []))
    muted = sum(1 for o in report["overlaps"] if o.get("suppressed"))
    if muted: overlaps.append("%d suppressed by config" % muted)
    lines += section("Overlap candidates", overlaps)
    if not quiet:
        budget = report["budget"]
        lines += section("Budget", [
            "Claude: %(total)d/%(limit)d chars across %(pocket_skills)d pocket skills (%(status)s)" % budget["claude"],
            "Codex:  %(total)d/%(limit)d chars across %(pocket_skills)d pocket skills (%(status)s)" % budget["codex"],
            "Desktop: %(total)d chars across %(pocket_skills)d enabled skills (%(status)s — no published limit)" % budget[DESKTOP],
            "%d skills excluded: only Gemini/Antigravity can see them, and their mode is UNKNOWN" % budget["excluded_unknown"]])
        pocket = report["pocket_check"]
        lines += section("Pocket check", ["rule: %s" % pocket["rule"],
                                          "(this is deliberately broader than the per-tool budgets above)",
                                          "pocket count: %d" % pocket["pocket_count"],
                                          "correct: %s" % ", ".join(pocket["correct"]),
                                          "intended shelf but pocket: %s" % ", ".join(pocket["intended_shelf_but_pocket"]),
                                          "intended pocket but shelf: %s" % ", ".join(pocket["intended_pocket_but_shelf"]),
                                          "in config but not installed: %s" % ", ".join(pocket.get("intended_but_not_installed", [])),
                                          "project-scope pocket (not measured against config): %s" % ", ".join(pocket.get("project_pocket", [])),
                                          "Claude Desktop pocket (managed in the app, not this config): %s" % ", ".join(pocket.get("desktop_pocket", []))])
    if quiet:
        # The brief's rule is that a section never vanishes silently, because a
        # missing one reads as a bug. Naming the suppression keeps that true.
        lines += ["\nInventory, Budget, Pocket check", "-" * 30, "suppressed by --quiet (exit code is unaffected)"]
    lines += section("Recommended actions", ["%d. %s" % (i + 1, item) for i, item in enumerate(report["recommendations"])])
    lines += ["\nPath note: these paths moved recently. Re-verify quarterly; Antigravity portable-path evidence is community testing, not official documentation."]
    return lines


def gh_escape(value: str, data: bool = False) -> str:
    for old, new in (("%", "%25"), ("\r", "%0D"), ("\n", "%0A")):
        value = value.replace(old, new)
    return value if data else value.replace(":", "%3A").replace(",", "%2C")


def github_lines(report: Dict[str, Any]) -> List[str]:
    """One GitHub workflow command per finding, for inline PR annotations.

    Severities match GitHub's own error/warning/notice, so no mapping is needed.
    """
    lines = []
    for item in report["findings"]:
        path = item["path"]
        # A skill finding carries the skill directory; annotate its SKILL.md.
        if path and Path(path).is_dir(): path = str(Path(path) / "SKILL.md")
        if path:
            try: path = str(Path(path).resolve().relative_to(Path.cwd()))
            except (ValueError, OSError): pass  # outside the workspace: absolute is the best we have
        properties = ["file=" + gh_escape(path)] if path else []
        if item["line"]: properties.append("line=%d" % item["line"])
        properties.append("title=" + gh_escape("skill-audit %s: %s" % (item["code"], item["skill"] or "library")))
        lines.append("::%s %s::%s" % (item["severity"], ",".join(properties), gh_escape(item["message"], data=True)))
    return lines


def markdown_for(report: Dict[str, Any]) -> str:
    return "# skill-audit report\n\n```text\n%s\n```\n" % "\n".join(lines_for(report))


def parser() -> argparse.ArgumentParser:
    non_goals = "Non-goals: does not detect real prose conflicts; does not fix anything; does not verify triggering; does not check Gemini or Antigravity shelf state (it reports UNKNOWN)."
    arg = argparse.ArgumentParser(description="Read-only audit of local agent skills. " + non_goals, epilog="Exit 0: clean/warnings; 1: strict warnings; 2: errors; 3: script failure. " + non_goals)
    arg.add_argument("--repo", action="append", default=[], metavar="PATH", help="Repository to scan (repeatable)")
    arg.add_argument("--config", help="TOML config path (default ~/.skill-audit.toml)")
    arg.add_argument("--json", action="store_true", help="Emit full JSON report (wins over --format)")
    arg.add_argument("--format", choices=("text", "github"), default="text",
                     help="github: emit one workflow command per finding for inline PR annotations, "
                          "instead of the text report. Never changes the exit code.")
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
        elif args.format == "github": print("\n".join(github_lines(report)))
        else: print("\n".join(lines_for(report, args.quiet)))
        severities = {item["severity"] for item in report["findings"]}
        return 2 if "error" in severities else (1 if args.strict and "warning" in severities else 0)
    except Exception as exc:
        print("skill-audit failed: %s" % exc, file=sys.stderr); return 3


if __name__ == "__main__":
    raise SystemExit(main())
