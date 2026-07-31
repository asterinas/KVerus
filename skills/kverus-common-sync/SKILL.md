---
name: kverus-common-sync
description: Check whether the installed `kverus-common` skill stays synchronized with the local Verus guide under `database/verified/code/tools/verus/source/docs/guide/src`. Use when validating kverus-common after guide updates, before committing skill changes, or when checking for stale guide-derived references and missing source files.
---

# KVerus Common Sync

Use this skill to audit the installed `kverus-common` skill against the local Verus guide source tree. Set `AGENT_DIR` to the installed agent directory; skills are read from `$AGENT_DIR/skills`.

## Required Check

Run the checker from the repository root:

```bash
. "$AGENT_DIR/kverus.env"
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-common-sync/scripts/check_sync.py"
```

If the user is working from a subdirectory, pass the repository root explicitly:

```bash
. "$AGENT_DIR/kverus.env"
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-common-sync/scripts/check_sync.py" --repo-root /path/to/project
```

## What It Checks

The script verifies:

1. `$AGENT_DIR/skills/kverus-common` exists and has reference files.
2. Every `Sources:` path in `kverus-common/references/*.md` points into `database/verified/code/tools/verus/source/docs/guide/src`.
3. Every referenced guide source file exists.
4. Every non-source Markdown cross-reference in reference prose uses `references/...` instead of a bare `.md` filename.
5. Whether any referenced guide source is newer than the `kverus-common` reference that cites it.

## Interpreting Results

Exit codes:

- `0`: synchronized enough for the structural checks.
- `1`: one or more blocking errors.
- `2`: no blocking errors, but warnings such as newer guide files exist.

Warnings about newer guide files mean the reference may be stale. Inspect the listed guide file and update the corresponding `kverus-common` reference if the changed content matters.

## Repair Policy

When a check fails:

1. Fix structural errors first: missing files or bad source paths.
2. Convert bare Markdown cross-references to skill-root paths such as `references/invariants.md`.
3. For stale-source warnings, compare the cited guide source with the current reference and update only relevant summaries.
4. Re-run the checker and `quick_validate.py` for `kverus-common`.
