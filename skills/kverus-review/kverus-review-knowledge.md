# kverus-review knowledge

Companion knowledge for the kverus-review spec. Mirrors the source skill's Shared Verus References, Step 0–5 substance, and scope disclaimers; this spec performs no edits, so there are no hard-constraint blocks to carry. This spec is strictly read-only.

## Shared reference reading order

Locate reference files under the `kverus-common` skill's `references/` directory (the sibling kverus-common tree, deployed next to this spec's skill directory) by topic:

| Topic | Reference File |
|-------|---------------|
| Set / extensional equality / `=~=` vs `==` | `set-reasoning.md` |
| Verus syntax / modes / exec-vs-spec-vs-proof | `verus-syntax-quickref.md` |
| Ghost / tracked / erasure | `ghost-tracked.md` |
| Verification error triage | `common-errors.md` |
| Exec-code reason and original-source comments | `exec-code-preservation.md` |

Mandated readings: when evaluating `=~=` usage, read the "Set Extensional Equality via Bidirectional Forall" section of `set-reasoning.md` and its "Auto-promotion of `==` to `=~=`" table; when the diff modifies exec code, read and apply `exec-code-preservation.md`.

## Diff collection forms

Committed scope (a commit hash was given): list files with `git diff <commit>..HEAD --name-only -- '*.rs'`; per-file content with `git diff <commit>..HEAD -- <file>`.

Uncommitted scope (no commit hash): list files with `git diff HEAD --name-only -- '*.rs'` merged with `git diff --cached --name-only -- '*.rs'` (unstaged plus staged); per-file content with `git diff HEAD -- <file>` merged with `git diff --cached -- <file>`. A file changed in both streams appears once in the review — deduplicate by path before classifying.

The engine's deterministic channel constructs these argv lists directly (no shell, so the shell-protective quotes around `*.rs` are dropped; git receives the pathspec verbatim). The per-file diff streams are fetched by the reviewing executor from the scope-appropriate forms above.

## Review categories

Check the change set for four categories of issues and produce a structured report:

1. Exec code modifications, whether they change runtime semantics, and whether their preservation comments are compliant.
2. New `=~=` introductions and whether they can be replaced by `==`.
3. Deleted comments and whether the deletion is justified.
4. Verification pass/fail and problematic warnings.

## Exec code scope

What counts as exec code (include in review):

- Function bodies of `fn` functions (default exec mode — no `spec` or `proof` prefix)
- Exec-mode variable declarations and assignments
- Branches (`if`/`else`/`match`), loops (`while`/`for`/`loop`), early returns
- Calls to exec functions
- `unsafe` blocks and `extern` declarations
- `panic!`, `unwrap`, `expect`, error propagation (`?`)
- Trait impl executable bodies
- `pub`/visibility annotations when they alter callable behavior
- Atomic operations, lock operations, memory ordering

What does NOT count as exec code (exclude from review):

- `spec fn` function definitions and their bodies
- `proof fn` function definitions and their bodies
- `requires` / `ensures` / `invariant` / `decreases` / `recommends` clauses
- Code inside `ghost { }` or `proof { }` blocks
- `#[verifier::...]` attributes
- `verus!` macro wrapping
- Imports used only by spec or proof code
- Type aliases, trait definitions, and `spec`/`proof` helper declarations
- Comments (including preserved original Rust code as comments)
- `assert` statements used only inside proof/spec contexts

When a diff hunk is ambiguous, read the surrounding code (the full file if needed) to determine whether the changed lines belong to an exec function body, a spec function, a proof block, or a ghost context.

## Exec modification classification

Classify each added/removed exec line:

| Classification | Meaning |
|----------------|---------|
| `semantic-change` | Runtime behavior may differ: changed branches, loops, return values, side effects, error handling, atomic operations, panic paths, overflow behavior, or ordering of side effects. |
| `likely-equivalent` | Syntax or structure changed but executable behavior is preserved: expression restructuring, type annotation additions, equivalent helper extraction, local variable introduction. |
| `uncertain` | Cannot determine confidently; needs more context, macro expansion, or domain knowledge. |

Semantic-change heuristics — classify as `semantic-change` when the change:

- Replaces a computation with a constant, placeholder, stub, or weaker fallback
- Removes or adds a branch, loop iteration, side effect, lock operation, atomic operation, or error path
- Changes arithmetic, comparison, casts, overflow behavior, indexing, or bounds checks
- Changes panic behavior or converts checked to unchecked behavior
- Changes ordering of side effects or concurrency synchronization
- Adds executable assumptions not present in the original runtime checks
- Changes `unsafe` boundaries on public APIs

Likely-equivalent heuristics — classify as `likely-equivalent` when the change:

- Restructures expressions while preserving evaluation and side effects
- Adds type annotations without changing values
- Extracts code into a helper with the same preconditions and effects
- Replaces unsupported syntax with an equivalent explicit form

Be conservative: when in doubt, classify as `uncertain` rather than `likely-equivalent`.

## Preservation comment compliance

Separately classify the preservation comment for every exec-code modification as `compliant`, `missing`, or `malformed` using `exec-code-preservation.md`. This check is required even when the executable change is `likely-equivalent`. A comment does not affect the semantic classification.

## =~= introduction review

Search the diff for newly added lines containing `=~=`. For each introduction, use the "Auto-promotion of `==` to `=~=`" table in `set-reasoning.md` to determine whether it can be replaced by `==`:

| Context | Replaceable? | Reason |
|---------|-------------|--------|
| Inside `assert(...)` | `replaceable` | Auto-promotion applies; `==` is equivalent. |
| Inside `ensures` clause | `replaceable` | Auto-promotion applies. |
| Inside `invariant` clause | `replaceable` | Auto-promotion applies. |
| Inside `spec fn` return expression | `replaceable` | Spec function `==` is also auto-promoted to extensional equality. |
| Inside `if` condition | `required` | Auto-promotion does NOT apply in conditions; `=~=` is needed for extensional check. |
| Inside `requires` clause | `required` | `requires` does not auto-promote. |
| Inside `recommends` clause | `required` | `recommends` does not auto-promote. |
| In a `proof` variable assignment | `required` | Assignment contexts do not auto-promote. |
| Inside `assert(...) by { ... }` body | `context-dependent` | The `by` block is proof code; if the assertion target is `assert(a =~= b)`, it may be needed for the proof strategy, but if the intent is extensional equality and it appears inside an `assert`, `==` auto-promotes. Default to `replaceable` unless the `by` block relies on `=~=` for trigger control. |

The "Set Extensional Equality via Bidirectional Forall" section of `set-reasoning.md` is the required background: by default Verus promotes `==` to `=~=` inside assert, ensures, and invariant, so explicit `=~=` is redundant in those contexts. When context is ambiguous, read the surrounding code to determine the enclosing syntactic form before classifying. Record each introduction with its file, line, enclosing context, replaceability, and reason.

## Deleted comment classification

Search the diff for removed lines that are comments. In Verus projects, comments often preserve important context — especially the original Rust code preserved during migration (see the kverus-migrate hard constraint "Preserve original as comments"). Deleting such comments can lose migration provenance. Classify each deleted comment:

| Classification | Meaning |
|----------------|---------|
| `justified` | The deletion is reasonable, e.g.: the commented code corresponds to a function/module that was entirely removed or reverted; the comment was clearly obsolete (e.g. `// TODO: ...` for a completed task); the comment's content is now duplicated by an updated spec/clause; or the code structure changed making an ordinary non-provenance comment no longer relevant. |
| `unjustified` | The deletion removes migration-preserved original Rust code or design rationale without a corresponding structural change that makes it obsolete. |
| `uncertain` | Cannot determine whether the deletion is justified; needs more context about why the comment existed and why it was removed. |

Heuristics for judgment:

- If the deleted comment contains original Rust code (e.g. `// let x = ...`, `// fn old_func()`, `// unsafe { ... }`), check whether the corresponding Verus code still exists and is unchanged. If the Verus code is unchanged but the preserved-Rust comment was deleted, classify as `unjustified` — the comment serves as migration provenance.
- If the deleted comment contains `Origin Rust:`, classify deletion as `justified` only when the corresponding executable modification was reverted or removed. When executable code is rewritten again, require an updated compliant preservation comment instead of silently deleting the old one.
- If the deleted comment is an ordinary code comment (not migration-preserved code), and its content is no longer accurate after the changes, classify as `justified`.
- If the deleted comment is an ordinary code comment and the surrounding code is unchanged, classify as `uncertain` — the intent of the deletion is unclear.
- If multiple ordinary comments were deleted in a block where the entire function or module was rewritten, classify them as `justified` when obsolete. This does not apply to `Origin Rust:` preservation comments, which must be updated to describe the new executable rewrite.

## Verification status and error summary

Run the user-supplied verification command and capture both stdout and stderr (the engine's subprocess channel merges the streams; the source's `tee` to a temp file was shell scaffolding only). Record the exit code. Exit code 0 means verification passed; non-zero means verification failed — extract and summarize the error messages, looking for `error:` lines and the `error: aborting due to` summary.

## Problematic warnings

Regardless of verification pass/fail, scan the captured output for these three patterns, count occurrences, and list the matching lines with line numbers:

- `note: automatically chose triggers for this expression:` — Verus has low confidence in auto-chosen SMT quantifier triggers; the expression should carry an explicit trigger annotation (`#[trigger]`, `#![trigger ...]`; the source also names `#![auto]` — prefer the explicit form).
- `` warning: use of deprecated method `vstd::set::Set::<A>::finite` `` — `Set::finite()` is deprecated; every `Set` is always finite in modern Verus; this call is a no-op.
- `` warning: use of deprecated associated function `vstd::set::Set::<A>::new_assuming_finite` `` — `Set::new_assuming_finite` is deprecated and dangerous; it unsoundly assumes finiteness.

## Report template

Produce a Markdown report with this structure:

```markdown
# KVerus Review Report

## Summary
- Commit range: <commit>..HEAD (or "uncommitted changes")
- Files reviewed: N
- Verification: ✅ passed / ❌ failed

## 1. Exec Code Modifications

| File | Lines Changed | Classification | Preservation Comment | Reason |
|------|---------------|----------------|----------------------|--------|
| path/to/file.rs | L10-L15 (added), L20-L22 (removed) | semantic-change | missing | ... |
| path/to/file.rs | L30 (added) | likely-equivalent | compliant | ... |

_Or: No exec code modifications found._

### Findings by Severity

**semantic-change:**
- **path/to/file.rs**: <concrete description of what changed and why it affects runtime behavior>

**likely-equivalent:**
- **path/to/file.rs**: <description of what changed and why behavior is preserved>

**uncertain:**
- **path/to/file.rs**: <description of what changed and why it is ambiguous>

**preservation-comment violations:**
- **path/to/file.rs**: <missing or malformed reason-first `Origin Rust:` comment>

## 2. =~= Introductions

| File | Line | Context | Replaceable? | Reason |
|------|------|---------|-------------|--------|
| path/to/file.rs | L42 | `assert(s1 =~= s2)` | replaceable | Auto-promotion applies inside assert |
| path/to/file.rs | L55 | `if s1 =~= s2` | required | Auto-promotion does not apply in if conditions |

_Or: No `=~=` introductions found._

## 3. Deleted Comments

| File | Line(s) | Deleted Comment (excerpt) | Classification | Reason |
|------|---------|---------------------------|----------------|--------|
| path/to/file.rs | L12-L15 | `// fn old_func() { ... }` | unjustified | Migration-preserved Rust code removed without corresponding structural change |
| path/to/file.rs | L30 | `// TODO: optimize` | justified | Comment is obsolete — task completed in this diff |

_Or: No comment deletions found._

## 4. Verification Issues

### Verification Status
✅ passed / ❌ failed (exit code: N)

_(If failed, include error summary:)_
**Error summary:**
<relevant error lines from verification output>

### Warnings

| Warning Pattern | Count | Locations |
|-----------------|-------|-----------|
| automatically chose triggers | 2 | L103, L456 |
| deprecated Set::finite | 1 | L78 |
| deprecated Set::new_assuming_finite | 0 | — |

_Or: No problematic warnings found._
```

## Report rules

- If verification fails, the report MUST include the verification status as `❌ failed` with the error summary.
- If any problematic warning is found, the report MUST list each one with count and locations.
- If any exec code modification is classified as `semantic-change`, highlight it prominently.
- If any exec-code preservation comment is `missing` or `malformed`, highlight it prominently.
- If any deleted comment is classified as `unjustified` or `uncertain`, highlight it prominently.
- Be conservative: when in doubt, classify as `uncertain` rather than `likely-equivalent`.

## Scope boundaries

This skill is not: a full code review (no style, naming, or architecture feedback); a migration tool (use `kverus-migrate`); a proof repair tool (use `kverus-fix`); a spec quality scorer (use `kverus-eval`); a Rust-vs-Verus migration audit (use `kverus-semantic-audit`). It reviews **incremental changes** for regressions, not the full Rust-to-Verus migration.
