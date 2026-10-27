---
name: kverus-common-sync
description: Check whether the installed `kverus-common` skill stays synchronized with an active Verus checkout (guide sources under `source/docs/guide/src` and `source/vstd`). Use when validating kverus-common after guide updates, before committing skill changes, or when checking for stale guide-derived references and missing source files.
---

# KVerus Common Sync

Use this skill to audit the installed `kverus-common` skill against the active Verus checkout. Skills are read from `$AGENT_DIR/skills` when `AGENT_DIR` is set, otherwise from the directory containing this skill's repository checkout.

## Required Check

Point the checker at the active Verus checkout — the directory that contains `source/docs/guide/src` and `source/vstd`. It is provided in this order of precedence:

1. `--verus-root` command-line argument
2. `VERUS_ROOT` environment variable
3. auto-discovery: the agent directory, the working directory, and their parents are searched for `database/*/code/tools/verus` and `tools/verus` candidates

```bash
. "$AGENT_DIR/kverus.env"
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-common-sync/scripts/check_sync.py" --verus-root /path/to/verus
```

Running with auto-discovery from a workspace that contains the layout works without arguments:

```bash
 VERUS_ROOT=/path/to/verus "$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-common-sync/scripts/check_sync.py"
```

## What It Checks

The script verifies:

1. `$AGENT_DIR/skills/kverus-common` exists and has reference files, and a Verus root was provided or discovered.
2. Every `Sources:` path in `kverus-common/references/*.md` is Verus-root-relative (`source/...` or `examples/...`, optionally with a `:LINE` or `:LINE-LINE` suffix). Reference files that are not guide-derived must declare `Source scope: ...` instead of a `Sources:` block.
3. Every referenced source file resolves under the Verus root and exists.
4. Every inline Markdown cross-reference resolves: `references/...` against the skill directory, bare sibling filenames or `../`/subdirectory paths against the referring file, and guide citations against the Verus root. Workspace-policy citations (`AGENTS.md`, `docs/...`) are exempt.
5. Whether any referenced guide source is newer than the `kverus-common` reference that cites it.

## Interpreting Results

Exit codes:

- `0`: synchronized enough for the structural checks.
- `2`: no blocking errors, but warnings such as newer guide files exist.
- `1`: one or more blocking errors, or no Verus root could be provided or discovered.

Warnings about newer guide files mean the reference may be stale. Inspect the listed guide file and update the corresponding `kverus-common` reference if the changed content matters.

## Repair Policy

When a check fails:

1. Fix structural errors first: a missing Verus root, missing files, or invalid source paths.
2. Fix unresolvable cross-references: point them at the file they intend, using `references/...`, a sibling filename, or a Verus-root-relative guide path.
3. For stale-source warnings, compare the cited guide source with the current reference and update only relevant summaries.
4. Re-run the checker and `quick_validate.py` for `kverus-common`.
