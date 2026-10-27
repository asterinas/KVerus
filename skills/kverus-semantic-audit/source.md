---
name: kverus-semantic-audit
description: Compare original Rust source folders against migrated Verus code folders, identify executable-code differences that may change runtime semantics, and write per-file audit reports to an output folder. Use when checking whether Rust-to-Verus rewriting preserved executable behavior rather than merely verifying successfully.
argument-hint: "rust_dir=path/to/rust verus_dir=path/to/verus out_dir=path/to/out"
license: MIT
compatibility: Requires a local workspace containing paired Rust and Verus .rs files.
user-invocable: true
metadata:
  author: kverus
  version: "1.0"
---

Audit whether a Rust-to-Verus migration preserved executable semantics.

Preferred invocation:

```text
$kverus-semantic-audit rust_dir=path/to/rust verus_dir=path/to/verus out_dir=path/to/out
```

If any of `rust_dir`, `verus_dir`, or `out_dir` is missing, ask for the missing value and stop.

## Objective

Compare each Rust source file with its Verus counterpart and report cases where executable behavior appears different.

This skill is not a style review and not a proof review. Ignore differences that only affect Verus specifications, proofs, ghost state, attributes, wrappers, or verifier annotations unless they also change executable behavior.

## Required Workflow

1. Run the bundled diff collector:

   ```bash
   . "$AGENT_DIR/kverus.env"
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-semantic-audit/scripts/collect_exec_diffs.py" \
     --rust-dir <rust_dir> \
     --verus-dir <verus_dir> \
     --out-dir <out_dir>
   ```

2. Read `<out_dir>/audit_index.json` first. It lists matched files, missing files, files with normalized executable-code diffs, and files with critical declaration-token diffs.
3. Before reading the full diff, inspect each file entry's `key_token_changes`. These flag changes to critical Rust API/safety tokens such as `unsafe`, `pub(...)` visibility, public modules/re-exports, `async`, `const fn`, `extern`, ABI strings, and `static mut`.
4. For each file with `has_exec_diff: true`, read the generated markdown under `<out_dir>/file_diffs/`. The markdown includes a "Key Token Changes" section when the collector detected critical token changes.
5. Inspect the original files directly when a diff is ambiguous. Use `rg`, `sed`, and nearby dependencies as needed.
6. Decide whether each executable difference is:
   - `semantic-change`: runtime behavior, side effects, panic behavior, return values, control flow, aliasing/mutation, memory ordering, concurrency behavior, or error handling changed.
   - `likely-equivalent`: syntax or structure changed but executable behavior is preserved.
   - `uncertain`: more context, build configuration, macro expansion, or domain knowledge is needed.
7. Write the final reports into `<out_dir>`:
   - `<out_dir>/semantic_audit_summary.md`
   - `<out_dir>/semantic_audit_findings.json`
   - optional per-file detail reports under `<out_dir>/semantic_reports/`.

## Pairing Policy

Default pairing is by relative path under `rust_dir` and `verus_dir`.

If a file is missing on either side, report it as `missing-rust` or `missing-verus`. Do not silently ignore it.

If the migration changed file names or layout, infer likely pairs only when obvious, then record the inference in the report.

## What Counts As Executable Semantics

Treat these as potentially semantic:

- function bodies, method bodies, trait impl executable bodies
- return expressions and early returns
- branches, loops, match arms, short-circuiting conditions
- mutation, assignment, moves, borrows that affect observable behavior
- calls to executable functions, including helper replacements
- panic paths, unwrap/expect behavior, assertions that execute at runtime
- error propagation and `Result`/`Option` handling
- allocation, deallocation, pointer arithmetic, unsafe blocks
- declaration-level safety and API-boundary tokens: `unsafe fn`, `unsafe trait`, `unsafe impl`, `pub`/`pub(crate)`/`pub(super)`/`pub(in ...)`, `pub mod`, `pub use`, `extern`, ABI strings, `async`, `const fn`, and `static mut`
- atomic operations, lock operations, memory ordering, interrupt/preemption state
- visibility or trait-bound changes only when they alter executable dispatch or callable behavior

Treat these as non-executable unless tied to executable code:

- `requires`, `ensures`, `invariant`, `decreases`, `recommends`
- `proof`, `spec`, `closed spec`, `open spec`, `tracked`, `ghost`
- `assert` statements used only for proof inside proof/spec contexts
- `verus!` wrapping and verifier attributes such as `#[verifier::external_body]`
- comments that preserve old Rust code
- imports used only by specs or proofs

## Semantic Review Heuristics

Classify as `semantic-change` when the Verus version:

- replaces a computation with a constant, placeholder, stub, or weaker fallback
- removes a branch, loop iteration, side effect, lock operation, atomic operation, or error path
- changes arithmetic, comparison, casts, overflow behavior, indexing, or bounds checks
- changes panic behavior or converts checked behavior into unchecked behavior
- changes ordering of side effects or concurrency synchronization
- changes ownership/borrowing in a way that changes mutation or aliasing outcomes
- removes `unsafe` from a function, trait, impl, or unsafe operation boundary without an equivalent replacement that still requires callers to uphold the same safety contract
- adds `unsafe` to a previously safe public API, because this changes caller obligations and can break downstream use
- widens visibility, e.g. `pub(crate)` or private to `pub`, when it exposes an operation or type outside the original API boundary
- changes `extern` ABI, `static mut`, or `const fn` status in a way that can affect linking, mutability, initialization, const-evaluation, or caller obligations
- adds executable assumptions that were not runtime checks in Rust
- comments out executable Rust code without an equivalent replacement

Classify as `uncertain` and inspect more context when a key token change may be intentionally replaced by Verus-only tracked permissions, ghost preconditions, or wrapper APIs. Do not assume a token change is safe just because the verified code proves.

Classify as `likely-equivalent` when the change is a local Verus-compatible rewrite that preserves data flow and observable effects, such as:

- replacing unsupported syntax with an equivalent explicit form
- adding type annotations without changing values
- restructuring expressions while preserving evaluation and side effects
- moving executable code into a helper with the same preconditions and effects
- narrowing visibility or moving `unsafe` inward while preserving the same externally visible safety contract and all unsafe call sites
- **Verus-forced rewrites**: converting a trait associated constant to a trait method (or standalone constant) because Verus does not support verification of trait associated constants (`ensures` cannot be attached to them). This is a language-limitation-driven rewrite, not a semantic choice. Classify as `likely-equivalent` when the method returns the same value the constant held and call sites are updated consistently. See `kverus-common/references/unsupported-features.md` for the full list of unsupported features and their migration patterns

Use `uncertain` instead of guessing when macro expansion, cfg flags, external dependencies, or large helper rewrites prevent a confident judgment.

## Report Requirements

`semantic_audit_summary.md` must contain:

1. Input paths and timestamp.
2. Totals: matched files, missing files, files with executable diffs, semantic changes, likely equivalent, uncertain.
3. Totals for files with critical declaration-token diffs, if present in `audit_index.json`.
4. A findings table with relative path, classification, severity, comment status, and short reason. For each removed or stubbed function/impl (e.g. `Drop`, `unimplemented!()`), report **comment status**: `commented` if the original Rust implementation is preserved as comments in the Verus file, `deleted` if it is completely absent. Mention key token changes in the reason when they drive the classification.
5. Missing-file list.
6. Notes on skipped generated/vendor files, if any.

`semantic_audit_findings.json` must be machine-readable and include for each reviewed file:

- `path`
- `rust_path`
- `verus_path`
- `classification`
- `severity`: `high`, `medium`, `low`, or `none`
- `comment_status`: for each removed or stubbed function/impl, `"commented"` if the original Rust code is preserved as comments in the Verus file, `"deleted"` if completely absent, `"partial"` if only some removed items are commented. Omit or set to `null` when the file has no removed/stubbed functions.
- `summary`
- `evidence`: line references or concise code snippets
- `key_token_changes`: copy relevant entries from `audit_index.json` when unsafe/pub/etc. changes are involved; use an empty list otherwise
- `recommended_action`

For each `semantic-change` or `uncertain` file, create `<out_dir>/semantic_reports/<relative_path>.md` with concrete evidence and reasoning.

## Output Style

Be conservative and concrete. Lead with behavior, not syntax.

Good finding summary:

```text
semantic-change, high: `fetch_add(Ordering::Acquire)` was replaced by a plain load/store sequence, which changes atomic read-modify-write behavior under concurrency.
```

Poor finding summary:

```text
The code is different.
```

Do not mark a difference as safe only because Verus verifies it.
