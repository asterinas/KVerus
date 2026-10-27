# kverus-postprocess knowledge

Companion knowledge for the kverus-postprocess spec. The spec owns the routing — the parallel refresh/checker fan-out with in-member completion gates, the phase cascade with honest skip records, the delegation call, the always-run closing duties, and the outcome precedence. This document carries the objective, the nine static seed rules, the dynamic-rule refresh policy, the checker finding catalogue, the severity definitions, the automation boundary, the bundled script CLI surface (including the surface this spec never passes), the wrapper mapping disclosure, the L1 environment bootstrap note, the report contract, and the shared-reference reading order. Grounded in the source skill's SKILL.md and its references/review-rule-policy.md.

## Objective

Final cleanup for Verus proof changes: consume cached dynamic review rules, delegate a bounded stale-cache refresh instead of blocking on GitHub, verify, delegate redundant-assert simplification to kverus-strip, format, and run the closing local checks. Use after proof-sensitive KVerus work or before finalizing Verus changes.

## Static seed rules

These static rules come from KVerus review practice and repository constraints; they are always available, with no cache and no network:

1. If an axiom is proved, rename it from `axiom_xxx` to `lemma_xxx`.
2. Comments should describe properties and obligations, not the proof technique used to discharge them.
3. Avoid adding unnecessary comments; preserve existing useful property-oriented rustdoc unless the code no longer matches it.
4. Do not use `#[allow(deprecated)]` or broad `#[allow(...)]` attributes to bypass verification or compiler warnings without a narrow justification.
5. Avoid changing executable source behavior or moving definitions solely to make proofs easier.
6. Prefer idiomatic Verus expressions, for example `item matches Pattern ==> cond` over `match item { Pattern => cond, _ => true }`.
7. Avoid unnecessary casts in spec/proof code, especially `as int` when the expression is already in spec integer mode.
8. Avoid accidental reverts of recently merged cleanup changes.
9. Delegate redundant-assert simplification to `kverus-strip` when a targeted verification command is available, then run the configured formatter before presenting final proof-sensitive changes.

## Dynamic rule refresh policy

Dynamic rules come from recent pull-request review comments and issue comments in the configured rule repository, fetched through the GitHub API. Recent commit subjects are lower-confidence context, collected only when commit context is explicitly requested; they may produce informational hints but never hard errors by themselves.

A comment becomes a high-confidence rule only when all three hold:

- The GitHub `author_association` is `COLLABORATOR`, `MEMBER`, or `OWNER`; and
- The body contains normative review language such as `should`, `should not`, `please`, `do not`, `shall not`, `unnecessary`, `prefer`, `can be written`, `revert`, `keep`, or `remove`; and
- The body is relevant to proof style, trusted boundaries, comments, formatting, warnings, source parity, or verification hygiene.

Dynamic rules default to `WARN` severity unless they match an existing hard static rule such as new cheating code or changes outside the verification scope.

Cache policy: successful refreshes are cached for 72 hours by default. Normal checks consume the cache with no network access. When the cache is stale or missing and a repository is configured, exactly one bounded `--refresh-only` pass is delegated — never a synchronous blocking refresh in the main flow, never a retry, never a rate-limit wait, never a block on proof work. A failed refresh preserves and keeps using the previous cache; without any cache the static seed rules above remain available. A repository left unconfigured disables the refresh machinery entirely and the cache verdict reads unconfigured.

Two trap disclosures for automation: `--refresh-only` exits 1 when any of its finding messages contains "refresh failed" — a GitHub failure counts even though the script fell back gracefully and preserved the old cache, so exit 1 with a summary line is a completed graceful fallback, not a crash. And the sync-refresh mode `--refresh-rules` exists for explicit manual runs only; this spec never passes it, in any phase.

## Checker finding catalogue

The bundled checker discovers changed files from the committed diff (`base...HEAD`, falling back to `base` alone) plus the worktree status, records the current branch as context, then applies path-scope rules and added-line regex rules, with dynamic-rule keyword matching carrying a path-scoped boost on top. Findings are sorted ERROR before WARN before INFO and printed as `SEVERITY:location message [source]`, closing with `INFO: Summary: N error(s), M warning(s).`

Path-scope findings:

- A changed file under a blocked-path prefix → ERROR: "Change is outside the configured verification scope."
- A changed file under a generated-path prefix → WARN (generated artifacts should not be hand-edited).
- An untracked new file (worktree `??`) → WARN.

Added-line regex findings:

- ERROR: new `admit(`, new `assume(`, new `#[verifier::external_body]`, and proved-fn-still-axiom naming (`proved-fn-still-axiom_*` axiom function names).
- WARN: a new axiom-named function, `#[allow(deprecated)]`, narrow `#[allow(...)]` attributes, proof-technique comments, `match _ => true` catch-all, `as int` casts, eight or more added doc comments, and deleted property doc comments.

The script's internal `git diff --check` surfaces as ERROR "git diff --check failed." with the first detail line — the same check this spec runs again as an explicit closing duty.

Exit-code semantics: 1 if and only if the error count is nonzero, otherwise 0. WARN-only findings pass the run — which matches the phase duties: fix every ERROR, review every WARN and fix it unless there is a clear reason to keep the code.

## Severity definitions

- `ERROR`: The change should not be submitted as-is.
- `WARN`: The change needs human review and usually should be fixed.
- `INFO`: Context for the final response or manual review.

A crashed checker worker is not a severity — it is an absorbed terminal recorded as the -1 sentinel, with the final checker pass named as the judge of the tree.

## Automation boundary

The scripts do not remove comments, rename functions, or rewrite specifications. The simplification phase may edit proof code only by removing a proof `assert` when the configured verification command still succeeds. If no verification command is configured, simplification runs in enumeration (dry-run) mode. The checker and refresh scripts edit nothing under the repository; the only writes are the script's own rule-cache file, its lock, and — under the fix and simplification phases — the executing agent's proof edits.

## Script CLI surface

Bundled asset: `scripts/kverus_postprocess.py` (self-bootstrap below). Mode flags are mutually exclusive; the spec passes `--cache-status`, `--refresh-only`, and `--no-refresh-rules` only.

Checker surface (the spec's two cache-only passes share the composed argument vector):

- `--base <ref>` — git base ref; empty defaults to `origin/main`.
- `--target-path <p1,p2>` — repeatable; path prefixes restricting the finding scope; env fallback `KVERUS_POSTPROCESS_TARGET_PATHS`.
- `--rule-repo <owner/repo>` — trusted dynamic-rule source; env fallback `KVERUS_POSTPROCESS_RULE_REPO`.
- `--blocked-path <prefix>` — repeatable; env fallback `KVERUS_POSTPROCESS_BLOCKED_PATHS`.
- `--generated-path <prefix>` — repeatable; env fallback `KVERUS_POSTPROCESS_GENERATED_PATHS`.

Cache and refresh surface:

- `--cache-status` — prints one line of sorted-key JSON `{"age_seconds", "cache_path", "repo", "rule_count", "status", "ttl_seconds"}` with status `fresh`, `stale`, or `missing` (repository configured) or `unconfigured` (none configured); exits 0 always; touches neither the network nor git.
- `--refresh-only` — one bounded pass: refresh lock (300-second max age; concurrent-refresh `RuntimeError` caught and degraded to cache consumption), two timed GitHub GETs plus optional commit subjects, the trust/normative/relevance filters, WARN-severity deduplicated rules, atomic cache write, and the closing `INFO: Refresh-only summary: rules=N, cache=…` line.
- `--refresh-rules` — synchronous full refresh. Never passed by this spec; reserved for explicit manual runs (`KVERUS_POSTPROCESS_REFRESH_RULES=1` in the wrapper).
- `--no-refresh-rules` — forbids network access; passed by both checker passes.

Surface never passed by this spec (disclosed for operators driving the script by hand): `--include-skills`, `--include-commit-context`, `--recent-prs` (default 20), `--github-timeout` (default 4 seconds per request), `--rule-cache-ttl-hours` (default env `KVERUS_POSTPROCESS_RULE_CACHE_TTL_HOURS` or 72.0), `--print-rules`.

Cache artifacts live under the script's own `.cache/` directory: the rules cache `<safe-repo-name>_review_rules.json` and its refresh lock.

L1 environment bootstrap: the script self-sources `kverus.env` at entry — idempotently (single marker line), by walking at most five directory layers upward without resolving symlinks, honors the `KVERUS_ENV_FILE` override, and re-execs itself under `KVERUS_PYTHON` when the env file names a Python. Plain `python3` invocations therefore carry the same environment the wrapper sourced by hand; the spec never sources env files itself.

## Wrapper mapping disclosure

The source ships `scripts/run_postprocess.sh` (and a Windows `.ps1` twin, retained as a human asset). This spec drives the bundled Python CLI directly; the wrapper is not executed. Operators invoking the wrapper by hand get this mapping:

- `BASE` (default `origin/main`) → `--base`; `RULE_REPO` → `--rule-repo`; `TARGET_PATHS` → `--target-path`; `VERIFY_CMD` → the verify phases (`sh -c` of the whole string, skipped when empty); `FORMAT_CMD` → the format phase (skipped when empty); `BLOCKED_PATHS` → `--blocked-path`; `GENERATED_PATHS` → `--generated-path`; `INCLUDE_SKILLS` → `--include-skills`.
- `SIMPLIFY_SCOPE=all` → the strip delegation receives whole-file scope; anything else (the default `modified`) → the changed-lines scope relay.
- `REFRESH_RULES=1` → synchronous `--refresh-rules` on the initial pass only (manual runs; the wrapper never refreshes synchronously by default); otherwise `--no-refresh-rules`.
- `SKIP_SIMPLIFY=1` → the simplification delegation is skipped.
- Sequence: initial checker (cache only) → verify → simplifier (bundled `simplify_proof.py` dry-run when no verify command exists) → re-verify → format → final checker (cache only) → `git diff --check` → `git status --short --branch`.
- Exit precedence: the first nonzero phase status is echoed (non-terminal), and the process exits with the final checker status if nonzero, else the whitespace-check status.

Registered deviation carried from the spec: the wrapper's `set -eu` hard-deaths on a red verification or format command before the closing duties run; the spec keeps report-duty priority — closing duties always run, upstream failures compose into the outcome family instead of killing the run.

Assert-simplification scope env controls (wrapper operators): `KVERUS_POSTPROCESS_SIMPLIFY_SCOPE=modified` (default) relays the changed-lines scope — only functions whose added diff lines (committed `base...HEAD` plus worktree) overlap the change; `=all` strips every function in the targeted files; `KVERUS_POSTPROCESS_SKIP_SIMPLIFY=1` skips the delegation.

## Report

The final response reports five elements, labels verbatim: dynamic rule refresh/check result, verification command(s), assert simplification result, formatter result, and final `git diff --check`. The spec composes them into `postprocess_report` and soft-gates the five label phrases:

1. **Dynamic rule refresh/check result** — the cache verdict, the bounded refresh outcome (rc and captured summary, or the skip cause), the initial checker verdict with its findings report, and the fix-phase record.
2. **Verification command(s)** — the supplied command and both verification phases' verdicts with exit codes, or the skip records.
3. **Assert simplification result** — the delegated report embedded verbatim with the callee outcome, its script exit code, and the rlimit pair, or the skip record with its cause.
4. **Formatter result** — verdict, exit code, and captured output, or the skip record.
5. **Final git diff --check** — the whitespace rc and captured output, the final checker verdict with its rc and findings report, and the tree status capture.

Honesty rules: sentinels are reported and marked as such; a killed worker is never presented as a green or red run; the delegation's own report is embedded verbatim rather than paraphrased.

The delegated assert-simplification phase follows its own knowledge document — deletion patterns, the delete→verify→restore loop, the whole-run rlimit guard, and failure recovery: [[kverus-strip-knowledge#Failure recovery]].

## Shared reference reading order

When the fix phase or the report must reason about proof constructs, read the relevant reference under `../kverus-common/references/` first: `exec-code-preservation.md` (what counts as executable code that must not change), `ghost-tracked.md` (ghost/tracked mode decisions), `lemma-shape.md` and `verus-syntax-quickref.md` (idiomatic shapes the seed rules push toward), and `unsupported-features/index.md` (trusted-boundary constructs the ERROR findings flag). The proof-technique-comment WARN and the property-doc-comment findings map directly onto the comment-shape guidance in those references.
