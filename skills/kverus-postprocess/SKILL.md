---
name: kverus-postprocess
description: Finalize Verus changes with cached review rules, formatting, verification, and optional proof simplification.
---

# KVerus Postprocess

Use the project's Git base, target paths, verification command, and formatter.
Set `AGENT_DIR` to the installation and load `$AGENT_DIR/kverus.env`.

1. Prepare the rule cache if configured and not already handled in pre-flight.
   Run the checker below, fix errors, and review warnings.
2. Run `kverus-strip` only on request or with
   `KVERUS_POSTPROCESS_ENABLE_SIMPLIFY=1`. Use the same base and target paths,
   establish a passing verification baseline, and pass `--modified-only`
   unless `KVERUS_POSTPROCESS_SIMPLIFY_SCOPE=all`. Without a verification
   command, use `--dry-run`.
3. Run the formatter if available, then verify. Reuse a passing result only
   if the command, working directory, and verification inputs still match.
4. Repeat the cached check and run `git diff --check` and
   `git status --short --branch`. If a correction changes source, verify and
   check again. Report the checks, formatting, verification, and strip outcomes.

```bash
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-postprocess/scripts/kverus_postprocess.py" \
  --base "$BASE" --target-path "$TARGET_PATHS" --no-refresh-rules
```

## Review Rule Cache

With `KVERUS_POSTPROCESS_RULE_REPO` configured, run the same checker with
`--cache-status`. For a stale or missing cache, delegate one `--refresh-only`
call to a subagent if available. The subagent only refreshes the cache and
preserves the old cache on failure. Continue immediately with cached or static
rules. The default TTL is 72 hours. See
[review rule policy](references/review-rule-policy.md) for details.

## Manual and CI Entry Points

Run `scripts/run_postprocess.sh <base-ref>` or
`scripts/run_postprocess.ps1 <base-ref>` from the project workspace. Set
`KVERUS_POSTPROCESS_TARGET_PATHS`, `KVERUS_POSTPROCESS_VERIFY_CMD`, and
`KVERUS_POSTPROCESS_FORMAT_CMD` as needed. The wrappers format once, verify if
configured, and run the final checks. They also verify before opt-in strip.
`KVERUS_POSTPROCESS_SKIP_SIMPLIFY=1` overrides opt-in.
`KVERUS_POSTPROCESS_REFRESH_RULES=1` explicitly enables a blocking refresh.
Use `KVERUS_POSTPROCESS_BLOCKED_PATHS` and
`KVERUS_POSTPROCESS_GENERATED_PATHS` for optional path checks.
