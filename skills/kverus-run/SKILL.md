---
name: kverus-run
description: Run the full Rust-to-Verus pipeline (migrate → spec → fix → eval → semantic audit → postprocess) in one command. Use when converting Rust code to verified Verus code end-to-end.
argument-hint: "target=path/to/file_or_dir verify=\"<verification command>\" [out_dir=path/to/reports]"
license: MIT
compatibility: Requires Codex CLI, a working Verus verification command, git workspace, and Python 3.
user-invocable: true
metadata:
  author: kverus
  version: "1.0"
---

Run the complete Rust-to-Verus pipeline for one file or a directory of `.rs` files.

Preferred invocation:

```text
$kverus-run target=path/to/file_or_dir verify="<verification command>"
```

If either `target` or `verify` is missing, ask for the missing value and stop.

If `out_dir` is missing, default to `.kverus-run-output/` under the workspace root.

## Pipeline Overview

```
Phase 0  Pre-flight ─────── validate inputs, snapshot originals
Phase 1  Migrate ─────────── Rust → Verus compatible code
Phase 2  Stage ──────────── git add migrated files
Phase 3  Spec ───────────── add requires/ensures/invariants
Phase 4  Fix ────────────── repair verification failures from spec
Phase 5  Eval ───────────── score spec quality (unstaged changes)
Phase 6  Semantic Audit ──── verify migration preserved runtime behavior
         ── QUALITY GATE ──  pause if critical semantic changes found
Phase 7  Postprocess ────── final review rules, assert simplification, fmt
Phase 8  Report ─────────── final summary
```

## Shared Verus References

All phases that edit Verus code should consult `../kverus-common/references/` when encountering unfamiliar Verus syntax, modes, ghost/tracked values, loop invariants, quantifiers, or tokenized state-machine rules.

---

## Phase 0: Pre-flight

1. Verify `target` exists.
2. Detect input type:
   - If `target` is a single `.rs` file: single-file mode. Set `FILE_LIST = [target]`.
   - If `target` is a directory: directory mode. Discover all `.rs` files recursively. Sort by dependency order when possible (leaf modules first), otherwise alphabetical. Set `FILE_LIST` accordingly.
3. Verify the git workspace is clean for the files in `FILE_LIST` (no uncommitted changes). If dirty, warn the user and ask whether to continue.
4. Snapshot originals for audit:
   - Create a temporary directory: `ORIG_DIR=$(mktemp -d)`.
   - Copy each file from `FILE_LIST` into `ORIG_DIR` preserving relative path structure.
   - Example: if `target=src/lib.rs`, copy to `$ORIG_DIR/src/lib.rs`.
5. Create `out_dir` if it does not exist.
6. Set `AGENT_DIR` to the installed agent directory for script calls. Skills are read from `$AGENT_DIR/skills`.
7. Print a summary: mode (single/directory), file count, target path, verify command.

---

## Phase 1: Migrate

For each file in `FILE_LIST`:

1. Follow the `kverus-migrate` skill workflow:
   - Inspect the target code and its immediate dependencies.
   - Make a short plan before large edits.
   - Apply minimal, incremental edits.
   - Run the verification command after each meaningful change.
   - Use error messages to guide the next minimal repair step.
   - Repeat until verification succeeds or a real blocker remains.

2. Follow all `kverus-migrate` hard constraints:
   - In-place edits only.
   - Preserve original Rust code as nearby comments.
   - No fake placeholders (`unimplemented!()`, `panic!()`, `loop {}`).
   - Only change necessary code in the minimal dependency closure.
   - Preserve structure: item order, function order, impl blocks, comments.

3. Follow the `kverus-migrate` transformation rules:
   - `verus!` wrapping where appropriate.
   - `#[verifier::external_body]` for functions to skip during proof.
   - Unsupported features: keep originals as comments, rewrite minimally.
   - Minimally adapt dependencies.

4. Follow the `kverus-migrate` edit priority:
   1. Local syntax-preserving edits
   2. Adding `#[verifier::external_body]`
   3. Rewriting unsupported expressions
   4. Minimally adapting direct dependencies
   5. Broader edits only as last resort

5. Track result per file: `success` or `blocked(reason)`.
6. In directory mode, if a file is blocked, log the blocker and continue to the next file.

---

## Phase 2: Git Stage

1. Stage the migrated files:

   ```bash
   git add <files in FILE_LIST>
   ```

2. This separates the migration changes (now staged) from subsequent spec/fix changes (unstaged), allowing Phase 5 (Eval) to evaluate only spec quality.

3. Print confirmation of staged files.

---

## Phase 3: Spec

For each file in `FILE_LIST` that succeeded in Phase 1:

1. Follow the `kverus-spec` skill workflow:
   - Inspect the target file.
   - Add specification structure incrementally: `requires`, `ensures`, loop invariants, `decreases`, `recommends`, `spec fn`, ghost/spec helpers.
   - Run the verification command after meaningful changes.
   - Use verification results to guide follow-up edits.

2. Follow all `kverus-spec` hard constraints:
   - In-place edits only.
   - Preserve executable behavior strictly.
   - Spec-only bias: prefer adding/refining specs over adding proof steps.
   - Do NOT add `assert(...) by (...)`, `calc!`, proof lemmas, or proof bodies unless absolutely necessary for syntactic validity.
   - No unsound shortcuts: do NOT add `assume`, `admit`, or `#[verifier::external_body]`.
   - Preserve source structure.

3. The goal is NOT to fully prove the code. The goal is to improve the specification layer while preparing for later proof.

---

## Phase 4: Fix

For each file in `FILE_LIST` that has verification failures after Phase 3:

1. Follow the `kverus-fix` skill workflow:
   - Inspect the entry target file and immediate dependencies.
   - Run the verification command to collect current errors.
   - Apply the smallest fix addressing the highest-signal error.
   - Re-run verification.
   - Repeat until verification succeeds or a real blocker remains.

2. Follow all `kverus-fix` hard constraints:
   - Do NOT modify existing `requires` clauses.
   - Do NOT modify existing `ensures` clauses.
   - Do NOT add new `assume` statements.
   - Do NOT add new `admit` statements.
   - Do NOT add `#[verifier::external_body]` to skip proof obligations.
   - Keep edits minimal and localized to smallest dependency closure.
   - Do NOT modify executable code.

3. If verification cannot succeed without violating constraints:
   - Stop at the smallest blocking point.
   - Record the blocking location and reason for the final report.

---

## Phase 5: Eval

1. At this point, migrated code is staged (Phase 2) and spec/fix changes are unstaged.

2. Follow the `kverus-eval` skill workflow:
   - Inspect unstaged diff.
   - Isolate spec-related changes: `requires`, `ensures`, invariants, `decreases`, `recommends`, spec/ghost declarations.
   - Compare modified clauses with previous intent.
   - Evaluate three aspects:
     1. Whether the modification strengthens or weakens the spec.
     2. Whether the modification changes the original purpose of the spec.
     3. Whether unnecessary spec content is added.

3. Produce per-file evaluation:
   - Strength assessment: stronger, weaker, or mixed.
   - Intent preservation assessment: preserved or changed.
   - Redundancy assessment: none, minor, or significant.
   - Score: X/10.
   - Short rationale with concrete diff references.

4. Follow the `kverus-eval` scoring policy:
   - Start from 10, subtract deductions.
   - Weakens safety/correctness guarantees: -2 to -5.
   - Changes original spec purpose: -2 to -5.
   - Adds redundant/unused spec clauses: -1 to -3.
   - Clamp to [0, 10].

### Eval Quality Gate (threshold: 7/10)

After scoring each file:

- If **any** file scores **below 7/10**:
  1. Print the failing file(s), their scores, and the rationale.
  2. Attempt an automatic retry: return to Phase 3 (Spec) → Phase 4 (Fix) → Phase 5 (Eval) for that file only, up to **2 retries**.
  3. On each retry, use the previous eval rationale as guidance: focus on the specific weaknesses identified (e.g. redundant clauses, weakened guarantees, changed intent).
  4. If the score is still below 7 after all retries:
     - Ask the user to choose:
       - **accept**: keep the current spec as-is and proceed to the final report.
       - **manual**: stop the pipeline here so the user can manually edit the spec.
     - Wait for the user's decision before proceeding.

- If all files score **7/10 or above**: proceed automatically to Phase 6.

---

## Phase 6: Semantic Audit

1. Determine the `verus_dir`:
   - Single-file mode: use the directory containing the target file.
   - Directory mode: use the `target` directory itself.

2. Set `rust_dir` to `ORIG_DIR` (the snapshot from Phase 0).

3. Run the bundled diff collector:

   ```bash
   . "$AGENT_DIR/kverus.env"
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-semantic-audit/scripts/collect_exec_diffs.py" \
     --rust-dir "$ORIG_DIR" \
     --verus-dir <verus_dir> \
     --out-dir <out_dir>/audit
   ```

4. Read `<out_dir>/audit/audit_index.json` for an overview.

5. For each file with `has_exec_diff: true`:
   - Inspect `key_token_changes` for critical declaration-token diffs.
   - Read the generated markdown under `<out_dir>/audit/file_diffs/`.
   - Inspect original files directly when diffs are ambiguous.
   - Classify each difference as `semantic-change`, `likely-equivalent`, or `uncertain`.

6. Follow the `kverus-semantic-audit` classification heuristics:
   - `semantic-change`: computation replaced with constant/stub, branch/loop/side effect removed, arithmetic/comparison changed, panic behavior altered, concurrency ordering changed, `unsafe` removed without equivalent, `unsafe` added to public API, visibility widened, `extern`/`static mut`/`const fn` status changed.
   - `likely-equivalent`: unsupported syntax rewritten equivalently, type annotations added, expressions restructured, helper functions introduced, Verus-forced rewrites.
   - `uncertain`: macros, cfg flags, external dependencies, or large helper rewrites.

7. Write audit reports to `<out_dir>/audit/`:
   - `semantic_audit_summary.md`
   - `semantic_audit_findings.json`
   - Per-file detail reports under `semantic_reports/` for `semantic-change` or `uncertain` files.

### Quality Gate

After completing the audit reports:

- If **any** finding is classified as `semantic-change` with severity `high`:
  1. Print a clear summary of the critical findings to the user.
  2. Ask the user to choose:
     - **continue**: proceed to Phase 7 despite findings.
     - **abort**: restore original files from `ORIG_DIR` and stop.
  3. Wait for the user's decision before proceeding.

- If no high-severity semantic changes: proceed automatically with a brief audit summary.

---

## Phase 7: Postprocess

Run final cleanup only after Eval and Semantic Audit gates pass or the user explicitly chooses to continue. Use `kverus-postprocess` when a verification command and target paths are available; otherwise skip this phase unless the user provides an equivalent postprocess command.

1. Follow the `kverus-postprocess` skill workflow:
   - Refresh dynamic review rules and inspect findings.
   - Run verification.
   - Delegate redundant proof-assert simplification to `kverus-strip`.
   - Re-run verification.
   - Run formatting.
   - Run final local checks.

2. Use the pipeline `verify` command as `KVERUS_POSTPROCESS_VERIFY_CMD`, `FILE_LIST` or the target directory as `KVERUS_POSTPROCESS_TARGET_PATHS`, and the project formatter as `KVERUS_POSTPROCESS_FORMAT_CMD`. If no verification command is available for the target, run strip in dry-run mode as described by `kverus-postprocess`.

3. Record postprocess results for the final report:
   - Dynamic rule check result.
   - Verification command(s) and pass/fail.
   - Assert simplification attempted/removed counts when available.
   - Formatting result.
   - Final local check result.

---

## Phase 8: Final Report

Write `<out_dir>/pipeline_summary.md` containing:

1. **Pipeline Configuration**: target path, mode (single/directory), verify command, timestamp.

2. **Phase 1 — Migrate**: per-file status (success/blocked), total files processed.

3. **Phase 3 — Spec**: per-file status, number of specs added.

4. **Phase 4 — Fix**: per-file status (verification passed/blocked), blocking locations if any.

5. **Phase 5 — Eval**: per-file scores, average score.

6. **Phase 6 — Semantic Audit**: number of semantic changes, likely-equivalent, uncertain findings. Note any high-severity items and user decision at quality gate.

7. **Phase 7 — Postprocess**: dynamic rule check, verification, assert simplification, formatting, and final local check results.

8. **Blockers & Warnings**: consolidated list of all files with unresolved issues across all phases.

9. **Suggested Next Steps**: e.g. commit changes, review specific findings, manually fix blockers.

Print the report summary to the user and note the full report path.

---

## Cleanup

After the pipeline completes (or aborts):

1. Remove `ORIG_DIR` temporary directory.
2. If aborted at quality gate with user choosing "abort", restore files from `ORIG_DIR` before removing it. Unstage any staged changes with `git restore --staged <files>`.

---

## Error Handling

- Each phase tracks per-file status independently.
- A file that fails in Phase 1 (Migrate) is excluded from Phases 3-6.
- A file that fails in Phase 4 (Fix) still gets its Eval score in Phase 5.
- Phase 7 (Postprocess) runs only after the whole pipeline is allowed to proceed past quality gates.
- The pipeline never silently drops a file; all files appear in the final report.
- If the verification command itself fails to execute (not verification errors, but command-not-found or crash), stop the pipeline and report the issue.
