#!/usr/bin/env python3
"""Check that kverus-common references are synchronized with a local Verus checkout.

The Verus root is provided by the caller, in this order of precedence:

1. `--verus-root` command-line argument
2. `VERUS_ROOT` environment variable
3. auto-discovery: the agent directory, the working directory, and their
   parents are searched for `database/*/code/tools/verus` and `tools/verus`
   candidates; a candidate counts only when it contains both
   `source/docs/guide/src` and `source/vstd`.

`Sources:` entries follow the kverus-common citation convention: root-relative
paths starting with `source/` or `examples/`, resolved against the Verus root.
Optional `:LINE` or `:LINE-LINE` suffixes are stripped before resolution.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


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


REQUIRED_VERUS_TREES = ("source/docs/guide/src", "source/vstd")
SOURCE_PREFIXES = ("source/", "examples/")
# Workspace-policy citations that resolve against the target workspace, not
# the skill tree; see kverus-common's Source Path Resolution.
WORKSPACE_REF_EXEMPT = ("AGENTS.md", "docs/")
RANGE_SUFFIX = re.compile(r":\d+(-\d+)?$")


def agent_dir() -> Path:
    if "AGENT_DIR" in os.environ:
        return Path(os.environ["AGENT_DIR"])
    return Path(__file__).resolve().parents[3]


def common_rel() -> Path:
    return agent_dir() / "skills" / "kverus-common"


def is_verus_root(candidate: Path) -> bool:
    return all((candidate / tree).is_dir() for tree in REQUIRED_VERUS_TREES)


def discover_verus_root(start: Path) -> Path | None:
    search_roots = [*agent_dir().resolve().parents, *start.resolve().parents]
    seen: set[Path] = set()
    for root in search_roots:
        if root in seen:
            continue
        seen.add(root)
        for candidate in [
            *sorted(root.glob("database/*/code/tools/verus")),
            root / "tools" / "verus",
        ]:
            if is_verus_root(candidate):
                return candidate
    return None


def parse_source_paths(text: str) -> list[str]:
    lines = text.splitlines()
    sources: list[str] = []
    in_sources = False
    for line in lines:
        if line.strip() == "Sources:":
            in_sources = True
            continue
        if in_sources:
            if line.startswith("- "):
                match = re.search(r"`([^`]+)`", line)
                if match:
                    sources.append(match.group(1))
                continue
            if line.strip() == "":
                continue
            break
    return sources


def has_source_scope(text: str) -> bool:
    return re.search(r"^Source scope: ", text, re.MULTILINE) is not None


def markdown_code_refs(text: str) -> list[str]:
    return re.findall(r"`([^`]+\.md)`", text)


def strip_range_suffix(ref: str) -> str:
    return RANGE_SUFFIX.sub("", ref)


def resolve_markdown_ref(ref: str, common: Path) -> Path | None:
    """Resolve an inline `.md` reference; return None when it cannot be resolved here.

    `references/...` resolves relative to the kverus-common skill directory;
    guide (`source/...`, `examples/...`) and workspace (`AGENTS.md`, `docs/...`)
    forms are classified before this is called, and bare sibling filenames are
    resolved by the caller against the referring file's directory.
    """
    if ref.startswith("references/"):
        return common / ref
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verus-root",
        type=Path,
        default=None,
        help="path to the active Verus checkout "
        "(contains source/docs/guide/src and source/vstd)",
    )
    parser.add_argument(
        "--strict-mtime",
        action="store_true",
        help="treat guide files newer than their kverus-common reference as errors",
    )
    args = parser.parse_args()

    common = common_rel()
    refs_dir = common / "references"

    verus_root: Path | None = None
    if args.verus_root:
        verus_root = args.verus_root.resolve()
    elif os.environ.get("VERUS_ROOT"):
        verus_root = Path(os.environ["VERUS_ROOT"]).resolve()
    else:
        verus_root = discover_verus_root(Path.cwd())
    if verus_root is not None and not is_verus_root(verus_root):
        verus_root = None

    errors: list[str] = []
    warnings: list[str] = []

    if not common.is_dir():
        errors.append(f"missing kverus-common directory: {common} (set AGENT_DIR)")
    if not refs_dir.is_dir():
        errors.append(f"missing references directory: {refs_dir}")
    if verus_root is None:
        errors.append(
            "no Verus root provided or discovered: pass --verus-root, "
            "set VERUS_ROOT, or run from a workspace containing "
            "database/*/code/tools/verus"
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    files = sorted([common / "SKILL.md", *refs_dir.glob("*.md")])
    if len(files) <= 1:
        errors.append(f"no reference markdown files found under {refs_dir}")

    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = f"kverus-common/{path.relative_to(common)}"

        if path.parent == refs_dir:
            sources = parse_source_paths(text)
            if not sources and not has_source_scope(text):
                errors.append(f"{rel}: missing Sources block")
            for source in sources:
                if not source.startswith(SOURCE_PREFIXES):
                    errors.append(
                        f"{rel}: source is not a Verus-root-relative path "
                        f"({' or '.join(SOURCE_PREFIXES)}): {source}"
                    )
                    continue
                source_path = verus_root / strip_range_suffix(source)
                if not source_path.is_file():
                    errors.append(f"{rel}: missing guide source: {source}")
                    continue
                if source_path.stat().st_mtime > path.stat().st_mtime:
                    msg = f"{rel}: guide source newer than reference: {source}"
                    if args.strict_mtime:
                        errors.append(msg)
                    else:
                        warnings.append(msg)

        for lineno, line in enumerate(text.splitlines(), start=1):
            for ref in markdown_code_refs(line):
                if ref.startswith(WORKSPACE_REF_EXEMPT):
                    continue
                if ref.startswith(SOURCE_PREFIXES):
                    if not (verus_root / strip_range_suffix(ref)).is_file():
                        errors.append(f"{rel}:{lineno}: missing guide source: {ref}")
                    continue
                resolved = resolve_markdown_ref(ref, common)
                if resolved is not None:
                    if not resolved.is_file():
                        errors.append(f"{rel}:{lineno}: missing reference file: {ref}")
                    continue
                for base in (path.parent, refs_dir):
                    if (base / strip_range_suffix(ref)).is_file():
                        break
                else:
                    errors.append(
                        f"{rel}:{lineno}: unresolvable markdown reference: {ref}"
                    )

    for error in errors:
        print(f"ERROR: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        print(f"\nFAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    if warnings:
        print(f"\nOK with warnings: {len(warnings)} warning(s)")
        return 2
    print("OK: kverus-common is structurally synchronized with the Verus guide sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
