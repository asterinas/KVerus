#!/usr/bin/env python3
"""Postprocess checks for KVerus proof changes."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _bootstrap_kverus_env() -> None:
    """Load kverus.env (written by install-skills.sh) without shell sourcing
    and re-exec this script under KVERUS_PYTHON when the current interpreter
    is not it. The search walks up from this file without resolving symlinks
    so symlinked skill installs find the target project's env file. Idempotent:
    safe to call again when the caller already sourced kverus.env."""
    import os
    import re
    import sys
    from pathlib import Path

    if os.environ.get("KVERUS_ENV_BOOTSTRAPPED") == "1":
        return
    here = Path(os.path.abspath(__file__)).parent
    env_path = os.environ.get("KVERUS_ENV_FILE")
    if not env_path:
        for ancestor in [here, *here.parents][:5]:
            candidate = ancestor / "kverus.env"
            if candidate.is_file():
                env_path = str(candidate)
                break
    if env_path:
        values = {}
        for raw in Path(env_path).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line.removeprefix("export ").lstrip()
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
        var_ref = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
        for key in list(values):
            for _ in range(3):
                expanded = var_ref.sub(
                    lambda m: values.get(m.group(1), m.group(0)), values[key]
                )
                if expanded == values[key]:
                    break
                values[key] = expanded
        os.environ.update(values)
    python = os.environ.get("KVERUS_PYTHON")
    if python and python != sys.executable and Path(python).is_file():
        os.environ["KVERUS_ENV_BOOTSTRAPPED"] = "1"
        try:
            os.execv(python, [python, *sys.argv])
        except OSError as exc:
            print(
                f"warning: re-exec under KVERUS_PYTHON failed: {exc}", file=sys.stderr
            )
    os.environ["KVERUS_ENV_BOOTSTRAPPED"] = "1"


_bootstrap_kverus_env()


SKILL_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = SKILL_DIR / ".cache"
DEFAULT_RULE_REPO = os.environ.get("KVERUS_POSTPROCESS_RULE_REPO", "")
DEFAULT_CACHE_TTL_HOURS = 72.0
DEFAULT_GITHUB_TIMEOUT = 4
REFRESH_LOCK_MAX_AGE_SECONDS = 300


def agent_dir() -> str:
    if "AGENT_DIR" in os.environ:
        return os.environ["AGENT_DIR"]
    return str(SKILL_DIR.parent.parent)


def git_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


TRUSTED_ASSOCIATIONS = {"COLLABORATOR", "MEMBER", "OWNER"}
NORMATIVE_RE = re.compile(
    r"\b(should|shouldn't|should not|shall not|please|do not|don't|"
    r"unnecessary|prefer|can be written|revert|keep|remove|avoid)\b",
    re.IGNORECASE,
)
RELEVANT_RE = re.compile(
    r"\b(axiom|lemma|proof|verus|kverus|comment|doc|rustdoc|fmt|format|"
    r"warning|deprecated|allow|assume|admit|external_body|trusted|trust|"
    r"source code|original source|spec|trigger|cast|as int|matches|revert)\b",
    re.IGNORECASE,
)

STATIC_RULES = [
    {
        "id": "proved-axiom-name",
        "severity": "ERROR",
        "summary": "Proved functions must not keep an axiom_* name; rename proved axioms to lemma_*.",
        "source": "static:#562",
    },
    {
        "id": "comment-properties-not-proof-method",
        "severity": "WARN",
        "summary": "Comments should describe properties or obligations, not proof techniques.",
        "source": "static:#562",
    },
    {
        "id": "no-unnecessary-comments",
        "severity": "WARN",
        "summary": "Avoid adding unnecessary comments; keep useful property-oriented docs.",
        "source": "static:#560,#562,#550",
    },
    {
        "id": "no-warning-bypass",
        "severity": "WARN",
        "summary": "Do not bypass warnings with broad allow attributes such as #[allow(deprecated)].",
        "source": "static:#557",
    },
    {
        "id": "preserve-source-shape",
        "severity": "WARN",
        "summary": "Avoid changing executable source behavior or moving definitions solely for proofs.",
        "source": "static:#553",
    },
    {
        "id": "idiomatic-matches",
        "severity": "WARN",
        "summary": "Prefer idiomatic Verus clauses like `item matches Pattern ==> cond`.",
        "source": "static:#560",
    },
    {
        "id": "avoid-unneeded-casts",
        "severity": "WARN",
        "summary": "Avoid unnecessary casts in spec/proof code, especially `as int`.",
        "source": "static:#553",
    },
    {
        "id": "run-make-fmt",
        "severity": "INFO",
        "summary": "Run the configured formatter before finalizing proof-sensitive changes.",
        "source": "static:kverus-postprocess",
    },
]


@dataclass
class Finding:
    severity: str
    message: str
    location: str | None = None
    source: str | None = None


@dataclass
class AddedLine:
    path: str
    new_lineno: int | None
    text: str


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=check,
        encoding="utf-8",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def print_finding(finding: Finding) -> None:
    location = f" {finding.location}" if finding.location else ""
    source = f" [{finding.source}]" if finding.source else ""
    print(f"{finding.severity}:{location} {finding.message}{source}")


def cache_file_for_rule_repo(rule_repo: str) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", rule_repo).strip("_")
    return CACHE_DIR / f"{safe_name or 'rules'}_review_rules.json"


def lock_file_for_rule_repo(rule_repo: str) -> Path:
    return cache_file_for_rule_repo(rule_repo).with_suffix(".lock")


def cache_age_seconds(payload: dict | None, now: int | None = None) -> int | None:
    if not payload:
        return None
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, int):
        return None
    current = int(time.time()) if now is None else now
    return max(0, current - generated_at)


def cache_status(payload: dict | None, ttl_seconds: int, now: int | None = None) -> str:
    age = cache_age_seconds(payload, now)
    if age is None:
        return "missing"
    return "fresh" if age < ttl_seconds else "stale"


def refresh_lock_owner(lock_file: Path) -> str | None:
    try:
        payload = json.loads(lock_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    token = payload.get("owner_token")
    return token if isinstance(token, str) else None


@contextmanager
def refresh_lock(rule_repo: str):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = lock_file_for_rule_repo(rule_repo)
    owner_token = secrets.token_hex(16)
    try:
        descriptor = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            age = max(0, int(time.time() - lock_file.stat().st_mtime))
        except OSError:
            age = 0
        if age < REFRESH_LOCK_MAX_AGE_SECONDS:
            raise RuntimeError(f"dynamic rule refresh already in progress ({age}s)")
        try:
            lock_file.unlink()
        except FileNotFoundError:
            pass
        descriptor = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        lock_payload = {
            "created_at": int(time.time()),
            "owner_token": owner_token,
            "pid": os.getpid(),
        }
        os.write(descriptor, (json.dumps(lock_payload, sort_keys=True) + "\n").encode())
        os.close(descriptor)
        yield
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        if refresh_lock_owner(lock_file) == owner_token:
            try:
                lock_file.unlink()
            except FileNotFoundError:
                pass


def github_repo_api(rule_repo: str) -> str:
    return f"https://api.github.com/repos/{rule_repo.strip('/')}"


def github_get_json(url: str, timeout: int) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "kverus-postprocess",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def summarize_body(body: str, limit: int = 220) -> str:
    one_line = re.sub(r"\s+", " ", body).strip()
    if len(one_line) <= limit:
        return one_line
    return one_line[: limit - 3].rstrip() + "..."


def write_cache_atomically(rule_repo: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = cache_file_for_rule_repo(rule_repo)
    temporary = cache_file.with_name(f".{cache_file.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, cache_file)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def collect_dynamic_rules(
    rule_repo: str,
    recent_prs: int,
    timeout: int,
    include_commit_context: bool = False,
) -> dict:
    # Repository-level comment endpoints avoid N requests per PR. Commit context is
    # optional because it does not participate in dynamic-rule matching.
    repo_api = github_repo_api(rule_repo)
    review_comments = github_get_json(
        f"{repo_api}/pulls/comments?sort=updated&direction=desc&per_page={recent_prs}",
        timeout,
    )
    issue_comments = github_get_json(
        f"{repo_api}/issues/comments?sort=updated&direction=desc&per_page={recent_prs}",
        timeout,
    )
    recent_commits: object = []
    if include_commit_context:
        recent_commits = github_get_json(
            f"{repo_api}/commits?per_page={recent_prs}",
            timeout,
        )

    rules: list[dict] = []
    commits: list[dict] = []
    if isinstance(review_comments, list):
        rules.extend(
            extract_rules_from_comments(rule_repo, None, "review", review_comments)
        )
    if isinstance(issue_comments, list):
        rules.extend(
            extract_rules_from_comments(rule_repo, None, "issue", issue_comments)
        )
    if isinstance(recent_commits, list):
        for commit in recent_commits:
            message = commit.get("commit", {}).get("message", "")
            if message:
                commits.append(
                    {
                        "sha": commit.get("sha", "")[:12],
                        "summary": message.splitlines()[0],
                        "source": commit.get(
                            "html_url", f"https://github.com/{rule_repo}/commits"
                        ),
                    }
                )

    payload = {
        "schema_version": 2,
        "generated_at": int(time.time()),
        "repo": rule_repo,
        "recent_items": recent_prs,
        "rules": dedupe_rules(rules),
        "commit_context": commits[:80],
    }
    write_cache_atomically(rule_repo, payload)
    return payload


def extract_rules_from_comments(
    rule_repo: str,
    pr_number: int | None,
    kind: str,
    comments: list[dict],
) -> list[dict]:
    rules = []
    for comment in comments:
        body = comment.get("body") or ""
        association = comment.get("author_association") or ""
        if association not in TRUSTED_ASSOCIATIONS:
            continue
        if not NORMATIVE_RE.search(body) or not RELEVANT_RE.search(body):
            continue
        path = comment.get("path")
        source = comment.get("html_url")
        if source is None and pr_number is not None:
            source = f"https://github.com/{rule_repo}/pull/{pr_number}"
        if source is None:
            source = f"https://github.com/{rule_repo}"
        rules.append(
            {
                "id": f"{kind}-{comment.get('id')}",
                "severity": "WARN",
                "summary": summarize_body(body),
                "path": path,
                "author_association": association,
                "source": source,
            }
        )
    return rules


def dedupe_rules(rules: Iterable[dict]) -> list[dict]:
    seen = set()
    out = []
    for rule in rules:
        key = (rule.get("summary"), rule.get("path"))
        if key in seen:
            continue
        seen.add(key)
        out.append(rule)
    return out


def load_cached_rules(rule_repo: str) -> dict | None:
    cache_file = cache_file_for_rule_repo(rule_repo)
    if not cache_file.exists():
        return None
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def refresh_or_load_rules(args: argparse.Namespace, findings: list[Finding]) -> dict:
    if not args.rule_repo:
        findings.append(
            Finding("INFO", "Dynamic rule refresh skipped; no rule repo configured.")
        )
        return {"rules": [], "commit_context": [], "generated_at": None}

    cached = load_cached_rules(args.rule_repo)
    if args.no_refresh_rules:
        if cached:
            findings.append(
                Finding(
                    "INFO",
                    f"Dynamic rule refresh skipped; using cached rules from {format_age(cached.get('generated_at'))}.",
                )
            )
            return cached
        findings.append(
            Finding("INFO", "Dynamic rule refresh skipped; no cache available.")
        )
        return {"rules": [], "commit_context": [], "generated_at": None}

    ttl_seconds = max(0, int(args.rule_cache_ttl_hours * 3600))
    status = cache_status(cached, ttl_seconds)
    if (
        cached
        and status == "fresh"
        and not args.refresh_rules
        and not args.refresh_only
    ):
        findings.append(
            Finding(
                "INFO",
                f"Dynamic rule cache hit; using rules from {format_age(cached.get('generated_at'))}.",
            )
        )
        return cached

    try:
        with refresh_lock(args.rule_repo):
            payload = collect_dynamic_rules(
                args.rule_repo,
                args.recent_prs,
                args.github_timeout,
                args.include_commit_context,
            )
        findings.append(
            Finding(
                "INFO",
                f"Refreshed {len(payload.get('rules', []))} dynamic review rules from recent {args.rule_repo} PRs.",
            )
        )
        return payload
    except (
        urllib.error.URLError,
        TimeoutError,
        RuntimeError,
        OSError,
        json.JSONDecodeError,
    ) as err:
        cached = load_cached_rules(args.rule_repo)
        if cached:
            findings.append(
                Finding(
                    "WARN",
                    f"Dynamic rule refresh failed ({err}); using cached rules from {format_age(cached.get('generated_at'))}.",
                )
            )
            return cached
        findings.append(
            Finding(
                "WARN",
                f"Dynamic rule refresh failed ({err}); no cache available, using static rules only.",
            )
        )
        return {"rules": [], "commit_context": [], "generated_at": None}


def format_age(timestamp: object) -> str:
    if not isinstance(timestamp, int):
        return "unknown time"
    age = max(0, int(time.time()) - timestamp)
    if age < 120:
        return f"{age}s ago"
    if age < 7200:
        return f"{age // 60}m ago"
    if age < 172800:
        return f"{age // 3600}h ago"
    return f"{age // 86400}d ago"


def changed_files(base: str) -> list[str]:
    result = run_git(["diff", "--name-only", f"{base}...HEAD"], check=False)
    if result.returncode != 0:
        result = run_git(["diff", "--name-only", base])
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    status = run_git(["status", "--porcelain"], check=False)
    for line in status.stdout.splitlines():
        if len(line) > 3:
            path = line[3:].strip()
            if path and path not in files:
                files.append(path)
    return files


def collect_diff_text(base: str, diff_paths: list[str]) -> str:
    parts: list[str] = []
    path_args = ["--", *diff_paths] if diff_paths else []
    committed = run_git(
        [
            "diff",
            "--find-renames",
            "--find-copies",
            f"{base}...HEAD",
            *path_args,
        ],
        check=False,
    )
    if committed.returncode != 0:
        committed = run_git(
            [
                "diff",
                "--find-renames",
                "--find-copies",
                base,
                *path_args,
            ],
            check=False,
        )
    if committed.stdout:
        parts.append(committed.stdout)

    worktree = run_git(
        [
            "diff",
            "--find-renames",
            "--find-copies",
            *path_args,
        ],
        check=False,
    )
    if worktree.stdout:
        parts.append(worktree.stdout)
    return "\n".join(parts)


def parse_added_lines(diff_text: str) -> list[AddedLine]:
    added: list[AddedLine] = []
    current_path = None
    new_lineno: int | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_path = line[len("+++ b/") :]
            continue
        if line.startswith("@@ "):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            new_lineno = int(match.group(1)) if match else None
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.append(AddedLine(current_path or "<unknown>", new_lineno, line[1:]))
            if new_lineno is not None:
                new_lineno += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        else:
            if new_lineno is not None:
                new_lineno += 1
    return added


def parse_deleted_doc_comments(diff_text: str) -> list[AddedLine]:
    deleted: list[AddedLine] = []
    current_path = None
    old_lineno: int | None = None
    for line in diff_text.splitlines():
        if line.startswith("--- a/"):
            current_path = line[len("--- a/") :]
            continue
        if line.startswith("@@ "):
            match = re.search(r"-(\d+)(?:,(\d+))?", line)
            old_lineno = int(match.group(1)) if match else None
            continue
        if line.startswith("-") and not line.startswith("---"):
            text = line[1:]
            if text.lstrip().startswith("///"):
                deleted.append(AddedLine(current_path or "<unknown>", old_lineno, text))
            if old_lineno is not None:
                old_lineno += 1
        elif line.startswith("+") and not line.startswith("+++"):
            continue
        else:
            if old_lineno is not None:
                old_lineno += 1
    return deleted


def location(line: AddedLine) -> str:
    if line.new_lineno is None:
        return line.path
    return f"{line.path}:{line.new_lineno}"


def is_rust_source_path(path: str) -> bool:
    return path.endswith(".rs")


def collect_local_findings(
    base: str,
    dynamic_rules: list[dict],
    diff_paths: list[str],
    blocked_paths: list[str],
    generated_paths: list[str],
) -> list[Finding]:
    findings: list[Finding] = []
    branch = run_git(["branch", "--show-current"], check=False).stdout.strip()
    files = changed_files(base)
    findings.append(Finding("INFO", f"Branch: {branch or '<detached>'}; base: {base}."))
    findings.append(
        Finding("INFO", f"Changed files: {', '.join(files) if files else '<none>'}.")
    )

    for path in files:
        if path_starts_with_any(path, blocked_paths):
            findings.append(
                Finding(
                    "ERROR",
                    "Change is outside the configured verification scope.",
                    path,
                )
            )
        if path_starts_with_any(path, generated_paths):
            findings.append(
                Finding("WARN", "Generated artifact appears in git status.", path)
            )

    status = run_git(["status", "--porcelain"], check=False).stdout
    for line in status.splitlines():
        if line.startswith("??"):
            findings.append(
                Finding("WARN", "Untracked file or directory present.", line[3:])
            )

    diff = collect_diff_text(base, diff_paths)
    added = parse_added_lines(diff)
    deleted_doc_comments = parse_deleted_doc_comments(diff)

    for line in added:
        text = line.text
        stripped = text.strip()
        loc = location(line)
        if is_rust_source_path(line.path):
            if re.search(r"\badmit!\s*\(|\badmit\s*\(", text):
                findings.append(Finding("ERROR", "New admit() found.", loc))
            if re.search(r"\bassume!\s*\(|\bassume\s*\(", text):
                findings.append(Finding("ERROR", "New assume() found.", loc))
            if "#[verifier::external_body]" in text:
                findings.append(
                    Finding("ERROR", "New #[verifier::external_body] found.", loc)
                )
            if re.search(r"\b(?:pub\s+)?proof\s+fn\s+axiom_[A-Za-z0-9_]*", text):
                findings.append(
                    Finding(
                        "ERROR",
                        "Proved function still uses axiom_* naming; rename it to lemma_*.",
                        loc,
                        "static:#562",
                    )
                )
            if re.search(r"\b(?:pub\s+)?axiom\s+fn\b", text):
                findings.append(
                    Finding(
                        "WARN",
                        "New axiom fn added; confirm this is an intended trusted boundary.",
                        loc,
                    )
                )
            if "#[allow(deprecated)]" in text:
                findings.append(
                    Finding(
                        "WARN",
                        "Do not bypass deprecation warnings with #[allow(deprecated)]; fix the cause.",
                        loc,
                        "static:#557",
                    )
                )
            elif re.search(r"#\s*\[\s*allow\s*\(", text):
                findings.append(
                    Finding(
                        "WARN", "New #[allow(...)] needs narrow justification.", loc
                    )
                )
            if stripped.startswith(("///", "//")) and re.search(
                r"\b(proved by|by expanding|compute_only|nonlinear_arith|kverus can prove|verus can prove)\b",
                stripped,
                re.IGNORECASE,
            ):
                findings.append(
                    Finding(
                        "WARN",
                        "Comment appears to describe proof technique instead of property.",
                        loc,
                        "static:#562",
                    )
                )
            if re.search(r"match\s+.+\{", text) and "_ => true" in text:
                findings.append(
                    Finding(
                        "WARN",
                        "Consider idiomatic `x matches Pattern ==> cond` instead of match-with-_=>true.",
                        loc,
                        "static:#560",
                    )
                )
            if " as int" in text:
                findings.append(
                    Finding(
                        "WARN",
                        "New `as int` cast; confirm it is necessary in this proof/spec context.",
                        loc,
                        "static:#553",
                    )
                )

    added_doc_comments = [
        line
        for line in added
        if is_rust_source_path(line.path)
        and (
            line.text.lstrip().startswith("///") or line.text.lstrip().startswith("//")
        )
    ]
    if len(added_doc_comments) >= 8:
        findings.append(
            Finding(
                "WARN",
                f"{len(added_doc_comments)} comment lines added; review for unnecessary proof narration.",
                "diff",
                "static:#560,#562",
            )
        )

    for line in deleted_doc_comments:
        text = line.text.lower()
        if re.search(
            r"verified|properties|property|gets|returns|ensures|requires", text
        ):
            findings.append(
                Finding(
                    "WARN",
                    "Deleted property-oriented doc comment; confirm generated docs should lose it.",
                    location(line),
                    "static:#550",
                )
            )

    diff_check = run_git(["diff", "--check"], check=False)
    if diff_check.returncode != 0:
        message = "git diff --check failed."
        detail = diff_check.stdout.strip() or diff_check.stderr.strip()
        if detail:
            message += f" {detail.splitlines()[0]}"
        findings.append(Finding("ERROR", message, "git diff --check"))

    findings.extend(match_dynamic_rules(dynamic_rules, files, added))
    return findings


def match_dynamic_rules(
    dynamic_rules: list[dict],
    files: list[str],
    added: list[AddedLine],
) -> list[Finding]:
    findings: list[Finding] = []
    if not dynamic_rules:
        return findings
    changed_set = set(files)
    added_text_by_path: dict[str, str] = {}
    for line in added:
        added_text_by_path.setdefault(line.path, "")
        added_text_by_path[line.path] += line.text.lower() + "\n"
    all_added_text = "\n".join(added_text_by_path.values())
    for rule in dynamic_rules:
        summary = str(rule.get("summary", ""))
        rule_path = rule.get("path")
        keywords = keywords_for_rule(summary)
        if not keywords:
            continue
        relevant = bool(keywords) and any(
            keyword in all_added_text for keyword in keywords
        )
        if isinstance(rule_path, str) and rule_path in changed_set:
            path_text = added_text_by_path.get(rule_path, "")
            relevant = relevant or (
                bool(keywords) and any(keyword in path_text for keyword in keywords)
            )
        if relevant:
            findings.append(
                Finding(
                    "WARN",
                    f"Dynamic review rule may apply: {summary}",
                    rule_path if isinstance(rule_path, str) else "diff",
                    str(rule.get("source", "dynamic")),
                )
            )
    return findings


def keywords_for_rule(summary: str) -> list[str]:
    words = []
    low = summary.lower()
    keyword_groups = {
        "axiom": ["axiom", "axiom_"],
        "lemma": ["lemma", "lemma_"],
        "comment": ["///", "//", "comment", "rustdoc"],
        "allow": ["#[allow", "allow("],
        "deprecated": ["deprecated"],
        "matches": [" matches ", "match "],
        "as int": [" as int"],
        "external_body": ["external_body"],
        "admit": ["admit("],
        "assume": ["assume("],
        "new_assuming_finite": ["new_assuming_finite"],
    }
    for keyword, triggers in keyword_groups.items():
        if keyword in low:
            words.extend(triggers)
    return words


def print_rule_summary(payload: dict) -> None:
    print("INFO: Static seed rules:")
    for rule in STATIC_RULES:
        print(
            f"INFO:   {rule['severity']} {rule['id']}: {rule['summary']} [{rule['source']}]"
        )
    dynamic = payload.get("rules", [])
    if dynamic:
        print(f"INFO: Dynamic review rules loaded: {len(dynamic)}")
        for rule in dynamic[:12]:
            path = f" ({rule.get('path')})" if rule.get("path") else ""
            print(f"INFO:   {rule.get('summary')}{path} [{rule.get('source')}]")
        if len(dynamic) > 12:
            print(f"INFO:   ... {len(dynamic) - 12} more cached dynamic rules")
    else:
        print("INFO: Dynamic review rules loaded: 0")
    commits = payload.get("commit_context", [])
    if commits:
        print(f"INFO: Recent commit subjects loaded: {len(commits)}")
        for commit in commits[:8]:
            print("INFO:   " f"{commit.get('sha')}: {commit.get('summary')}")
        if len(commits) > 8:
            print(f"INFO:   ... {len(commits) - 8} more commit subjects")


def split_csv(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        for item in value.split(","):
            stripped = item.strip()
            if stripped:
                out.append(stripped)
    return out


def env_csv(name: str) -> list[str]:
    value = os.environ.get(name, "")
    return split_csv([value]) if value else []


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def diff_paths_from_args(args: argparse.Namespace) -> list[str]:
    paths = split_csv(args.target_path) or env_csv("KVERUS_POSTPROCESS_TARGET_PATHS")
    if args.include_skills:
        skills_path = git_path(Path(agent_dir()) / "skills")
        if skills_path not in paths:
            paths.append(skills_path)
    return paths


def blocked_paths_from_args(args: argparse.Namespace) -> list[str]:
    return split_csv(args.blocked_path) or env_csv("KVERUS_POSTPROCESS_BLOCKED_PATHS")


def generated_paths_from_args(args: argparse.Namespace) -> list[str]:
    return split_csv(args.generated_path) or env_csv(
        "KVERUS_POSTPROCESS_GENERATED_PATHS"
    )


def path_starts_with_any(path: str, prefixes: list[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", default="origin/main", help="Git base ref for changed-file context"
    )
    parser.add_argument(
        "--target-path",
        action="append",
        default=[],
        help="Path or comma-separated paths to inspect in diffs. Defaults to all changed paths.",
    )
    parser.add_argument(
        "--include-skills",
        action="store_true",
        help="Also inspect the installed skills directory from AGENT_DIR.",
    )
    parser.add_argument(
        "--rule-repo",
        default=DEFAULT_RULE_REPO,
        help="GitHub owner/repo used for dynamic review rules.",
    )
    parser.add_argument(
        "--blocked-path",
        action="append",
        default=[],
        help="Path prefix or comma-separated prefixes that should not change.",
    )
    parser.add_argument(
        "--generated-path",
        action="append",
        default=[],
        help="Path prefix or comma-separated prefixes for generated artifacts.",
    )
    parser.add_argument(
        "--recent-prs",
        type=int,
        default=20,
        help="Number of recent comments to inspect",
    )
    parser.add_argument(
        "--github-timeout",
        type=int,
        default=DEFAULT_GITHUB_TIMEOUT,
        help="GitHub request timeout in seconds",
    )
    parser.add_argument(
        "--rule-cache-ttl-hours",
        type=float,
        default=env_float(
            "KVERUS_POSTPROCESS_RULE_CACHE_TTL_HOURS", DEFAULT_CACHE_TTL_HOURS
        ),
        help="Reuse successful rule refreshes for this many hours (default: 72)",
    )
    rule_action = parser.add_mutually_exclusive_group()
    rule_action.add_argument(
        "--refresh-rules",
        action="store_true",
        help="Force a GitHub refresh even when the cache is fresh",
    )
    rule_action.add_argument(
        "--no-refresh-rules",
        action="store_true",
        help="Skip GitHub refresh and use cache/static rules",
    )
    rule_action.add_argument(
        "--refresh-only",
        action="store_true",
        help="Force-refresh the dynamic rule cache without inspecting the local git workspace",
    )
    rule_action.add_argument(
        "--cache-status",
        action="store_true",
        help="Print dynamic rule cache status as JSON without network or git access",
    )
    parser.add_argument(
        "--include-commit-context",
        action="store_true",
        help="Also fetch recent commit subjects; disabled by default because they are informational only",
    )
    parser.add_argument(
        "--print-rules",
        action="store_true",
        help="Print loaded static and dynamic rules",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ttl_seconds = max(0, int(args.rule_cache_ttl_hours * 3600))
    if args.cache_status:
        cached = load_cached_rules(args.rule_repo) if args.rule_repo else None
        age = cache_age_seconds(cached)
        status = cache_status(cached, ttl_seconds) if args.rule_repo else "unconfigured"
        print(
            json.dumps(
                {
                    "age_seconds": age,
                    "cache_path": (
                        str(cache_file_for_rule_repo(args.rule_repo))
                        if args.rule_repo
                        else None
                    ),
                    "repo": args.rule_repo or None,
                    "rule_count": len(cached.get("rules", [])) if cached else 0,
                    "status": status,
                    "ttl_seconds": ttl_seconds,
                },
                sort_keys=True,
            )
        )
        return 0

    findings: list[Finding] = []
    if args.refresh_only:
        args.refresh_rules = True
        payload = refresh_or_load_rules(args, findings)
        for finding in findings:
            print_finding(finding)
        failed = any(
            "refresh failed" in finding.message.lower() for finding in findings
        )
        print(
            "INFO: Refresh-only summary: "
            f"rules={len(payload.get('rules', []))}, "
            f"cache={cache_file_for_rule_repo(args.rule_repo) if args.rule_repo else '<unconfigured>'}."
        )
        return 1 if failed else 0

    diff_paths = diff_paths_from_args(args)
    blocked_paths = blocked_paths_from_args(args)
    generated_paths = generated_paths_from_args(args)
    payload = refresh_or_load_rules(args, findings)
    if args.print_rules:
        print_rule_summary(payload)
    findings.extend(
        collect_local_findings(
            args.base,
            payload.get("rules", []),
            diff_paths,
            blocked_paths,
            generated_paths,
        )
    )
    commit_context = payload.get("commit_context", [])
    if commit_context:
        findings.append(
            Finding(
                "INFO",
                f"Loaded {len(commit_context)} recent official commit subject(s) as low-confidence context.",
            )
        )

    severity_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    findings.sort(
        key=lambda item: (
            severity_order.get(item.severity, 9),
            item.location or "",
            item.message,
        )
    )
    for finding in findings:
        print_finding(finding)

    error_count = sum(1 for finding in findings if finding.severity == "ERROR")
    warn_count = sum(1 for finding in findings if finding.severity == "WARN")
    print(f"INFO: Summary: {error_count} error(s), {warn_count} warning(s).")
    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main())
