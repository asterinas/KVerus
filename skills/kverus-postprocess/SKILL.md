---
name: kverus-postprocess
description: "Final cleanup for Verus proof changes: refresh review rules, verify with a user-provided command, delegate redundant proof-assert removal to kverus-strip, re-verify, format, and run local checks. Use after proof-sensitive KVerus skill work or before finalizing Verus changes."
---

# KVerus Postprocess

Set `AGENT_DIR` to the installed agent directory when running commands manually. Skills are read from `$AGENT_DIR/skills`.

## Required Inputs

- `base`: git base ref for diff context, e.g. `origin/main`.
- `target-path`: changed source paths to inspect and simplify, e.g. `src/,specs/`.
- `verify-command`: full verification command. If unavailable, simplification must run in `--dry-run`.
- `format-command`: project formatter command, e.g. `cargo fmt`, `make fmt`, or an equivalent.
- Optional scope controls: `blocked-path` for path prefixes that must not change, and `generated-path` for generated artifact prefixes.

## Workflow

1. Refresh dynamic review rules and inspect findings:

```bash
. "$AGENT_DIR/kverus.env"
"$KVERUS_ROOT/.venv/bin/python" "$AGENT_DIR/skills/kverus-postprocess/scripts/kverus_postprocess.py" \
  --base <base-ref> \
  --target-path <path1,path2> \
  --rule-repo <owner/repo> \
  --refresh-rules
```

Fix every `ERROR`. Review every `WARN` and fix it unless there is a clear reason to keep the code.

2. Verify the current code:

```bash
<verify-command>
```

3. Remove redundant proof statements through `kverus-strip`:

```text
$kverus-strip verify="<verify-command>" target-dirs="<path1,path2>" base="<base-ref>"
```

By default postprocess strips **only functions whose added diff lines (against `base`) overlap the change** — newly touched proof code only, not unrelated functions in the same file. To strip every function in the targeted files instead, set the scope to `all` (see Assert Simplification below). Follow the skill's workflow for script-based simplification and broader manual cleanup.

4. Re-run verification:

```bash
<verify-command>
```

5. Format:

```bash
<format-command>
```

6. Run the final local check:

```bash
. "$AGENT_DIR/kverus.env"
"$KVERUS_ROOT/.venv/bin/python" "$AGENT_DIR/skills/kverus-postprocess/scripts/kverus_postprocess.py" \
  --base <base-ref> \
  --target-path <path1,path2> \
  --rule-repo <owner/repo> \
  --refresh-rules
git diff --check
git status --short --branch
```

The wrapper runs the same sequence:

```bash
KVERUS_POSTPROCESS_TARGET_PATHS='src/,specs/' \
KVERUS_POSTPROCESS_VERIFY_CMD='<verify-command>' \
KVERUS_POSTPROCESS_FORMAT_CMD='<format-command>' \
KVERUS_POSTPROCESS_RULE_REPO='<owner/repo>' \
KVERUS_POSTPROCESS_BLOCKED_PATHS='kernel/,docs/' \
KVERUS_POSTPROCESS_GENERATED_PATHS='target/,doc/' \
  sh "$AGENT_DIR/skills/kverus-postprocess/scripts/run_postprocess.sh" <base-ref>
```

## Assert Simplification

Postprocess does not own assert simplification logic. It delegates that phase to `kverus-strip`.

By default (`KVERUS_POSTPROCESS_SIMPLIFY_SCOPE=modified`) the simplifier receives `--modified-only`, so it only strips proof code inside functions that contain added lines in the current diff (committed `base...HEAD` plus worktree). Functions you did not touch in this change are left alone, even if they live in a targeted file. This keeps postprocess from churning unrelated, already-verified proofs.

Set `KVERUS_POSTPROCESS_SIMPLIFY_SCOPE=all` to strip every function in the targeted files/dirs (the previous whole-file behavior) — e.g. when running a deliberate cleanup pass over an entire module.

Set `KVERUS_POSTPROCESS_SKIP_SIMPLIFY=1` to skip assert simplification.

## Dynamic Rules

Dynamic rules are refreshed from recent review and issue comments in the configured `--rule-repo`. If GitHub is unavailable, cached rules for that repo are used when available; otherwise static rules are used.

## Report

In the final response, report dynamic rule refresh/check result, verification command(s), assert simplification result, formatter result, and final `git diff --check`.
