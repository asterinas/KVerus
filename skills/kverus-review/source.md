---
name: kverus-review
description: Review uncommitted or recent Verus code changes for exec-code modifications, unnecessary =~= introductions, and verification issues. Use before committing to catch regressions in executable semantics, set reasoning, and proof quality.
argument-hint: '[commit=<commit-hash>] verify="<verification command>"'
license: MIT
compatibility: Requires a working Verus verification command and git.
user-invocable: true
metadata:
  author: kverus
  version: "1.0"
---

Review Verus code changes for exec semantics, `=~=` usage, and verification quality before committing.

Preferred invocation:

```text
$kverus-review verify="<verification command>"
$kverus-review commit=abc1234 verify="<verification command>"
```

If `verify` is missing, ask for it and stop. `commit` is optional.

## Objective

Check uncommitted changes (or changes since a given commit) for four categories of issues and produce a structured report:

1. Exec code modifications, whether they change runtime semantics, and whether their preservation comments are compliant.
2. New `=~=` introductions and whether they can be replaced by `==`.
3. Deleted comments and whether the deletion is justified.
4. Verification pass/fail and problematic warnings.

## Arguments

- `commit` (optional): A git commit hash. When provided, review changes from that commit to HEAD. When omitted, review all uncommitted changes (unstaged + staged).
- `verify` (required): The target repository's documented verification command.

## Shared Verus References

Locate reference files under the `kverus-common` skill's `references/` directory by topic:

| Topic | Reference File |
|-------|---------------|
| Set / extensional equality / `=~=` vs `==` | `set-reasoning.md` |
| Verus syntax / modes / exec-vs-spec-vs-proof | `verus-syntax-quickref.md` |
| Ghost / tracked / erasure | `ghost-tracked.md` |
| Verification error triage | `common-errors.md` |
| Exec-code reason and original-source comments | `exec-code-preservation.md` |

When evaluating `=~=` usage, read the "Set Extensional Equality via Bidirectional Forall" section from the `set-reasoning.md` reference.
When the diff modifies exec code, read and apply `exec-code-preservation.md`.

## Required Workflow

### Step 0: Collect Change Set

Determine the diff scope:

**With `commit` argument:**

```bash
# List changed .rs files
git diff <commit>..HEAD --name-only -- '*.rs'

# Get diff content for a specific file
git diff <commit>..HEAD -- <file>
```

**Without `commit` argument:**

```bash
# List changed .rs files (unstaged + staged)
git diff HEAD --name-only -- '*.rs'
git diff --cached --name-only -- '*.rs'

# Get diff content
git diff HEAD -- <file>
git diff --cached -- <file>
```

If no `.rs` files are changed, report that and stop.

### Step 1: Exec Code Modification Check

For each changed `.rs` file, read the diff and classify every added/removed line.

**What counts as exec code (include in review):**

- Function bodies of `fn` functions (default exec mode — no `spec` or `proof` prefix)
- Exec-mode variable declarations and assignments
- Branches (`if`/`else`/`match`), loops (`while`/`for`/`loop`), early returns
- Calls to exec functions
- `unsafe` blocks and `extern` declarations
- `panic!`, `unwrap`, `expect`, error propagation (`?`)
- Trait impl executable bodies
- `pub`/visibility annotations when they alter callable behavior
- Atomic operations, lock operations, memory ordering

**What does NOT count as exec code (exclude from review):**

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

**How to determine context:** When a diff hunk is ambiguous, read the surrounding code (the full file if needed) to determine whether the changed lines belong to an exec function body, a spec function, a proof block, or a ghost context.

If any exec code lines are modified, classify each modification:

| Classification | Meaning |
|----------------|---------|
| `semantic-change` | Runtime behavior may differ: changed branches, loops, return values, side effects, error handling, atomic operations, panic paths, overflow behavior, or ordering of side effects. |
| `likely-equivalent` | Syntax or structure changed but executable behavior is preserved: expression restructuring, type annotation additions, equivalent helper extraction, local variable introduction. |
| `uncertain` | Cannot determine confidently; needs more context, macro expansion, or domain knowledge. |

Separately classify the preservation comment for every exec-code modification as
`compliant`, `missing`, or `malformed` using `exec-code-preservation.md`. This check is
required even when the executable change is `likely-equivalent`. A comment does not
affect the semantic classification.

**Semantic-change heuristics** — classify as `semantic-change` when the change:

- Replaces a computation with a constant, placeholder, stub, or weaker fallback
- Removes or adds a branch, loop iteration, side effect, lock operation, atomic operation, or error path
- Changes arithmetic, comparison, casts, overflow behavior, indexing, or bounds checks
- Changes panic behavior or converts checked to unchecked behavior
- Changes ordering of side effects or concurrency synchronization
- Adds executable assumptions not present in the original runtime checks
- Changes `unsafe` boundaries on public APIs

**Likely-equivalent heuristics** — classify as `likely-equivalent` when the change:

- Restructures expressions while preserving evaluation and side effects
- Adds type annotations without changing values
- Extracts code into a helper with the same preconditions and effects
- Replaces unsupported syntax with an equivalent explicit form

If no exec code is modified, record: "No exec code modifications found."

### Step 2: `=~=` Introduction Check

Search the diff for newly added lines containing `=~=`.

Read the `set-reasoning.md` reference (see the topic table in "Shared Verus References"), specifically the "Auto-promotion of `==` to `=~=`" table, which lists every syntactic context and whether `=~=` can be safely replaced by `==`.

For each introduced `=~=`, use that table to determine whether it can be replaced by `==`.

When context is ambiguous, read the surrounding code to determine the enclosing syntactic form before classifying.

If no `=~=` is introduced, record: "No `=~=` introductions found."

### Step 3: Deleted Comment Check

Search the diff for removed lines that are comments. In Verus projects, comments often preserve important context — especially the original Rust code preserved during migration (see `kverus-migrate` hard constraint: "Preserve original as comments"). Deleting such comments can lose migration provenance.

For each deleted comment, classify the deletion:

| Classification | Meaning |
|----------------|---------|
| `justified` | The deletion is reasonable, e.g.: the commented code corresponds to a function/module that was entirely removed or reverted; the comment was clearly obsolete (e.g. `// TODO: ...` for a completed task); the comment's content is now duplicated by an updated spec/clause; or the code structure changed making an ordinary non-provenance comment no longer relevant. |
| `unjustified` | The deletion removes migration-preserved original Rust code or design rationale without a corresponding structural change that makes it obsolete. |
| `uncertain` | Cannot determine whether the deletion is justified; needs more context about why the comment existed and why it was removed. |

**Heuristics for judgment:**

- If the deleted comment contains original Rust code (e.g. `// let x = ...`, `// fn old_func()`, `// unsafe { ... }`), check whether the corresponding Verus code still exists and is unchanged. If the Verus code is unchanged but the preserved-Rust comment was deleted, classify as `unjustified` — the comment serves as migration provenance.
- If the deleted comment contains `Origin Rust:`, classify deletion as `justified` only when the corresponding executable modification was reverted or removed. When executable code is rewritten again, require an updated compliant preservation comment instead of silently deleting the old one.
- If the deleted comment is an ordinary code comment (not migration-preserved code), and its content is no longer accurate after the changes, classify as `justified`.
- If the deleted comment is an ordinary code comment and the surrounding code is unchanged, classify as `uncertain` — the intent of the deletion is unclear.
- If multiple ordinary comments were deleted in a block where the entire function or module was rewritten, classify them as `justified` when obsolete. This does not apply to `Origin Rust:` preservation comments, which must be updated to describe the new executable rewrite.

If no comments were deleted, record: "No comment deletions found."

### Step 4: Verification Check

Run the user-provided verification command and capture both stdout and stderr.

1. **Run verification:**

   ```bash
   <verify-command> 2>&1 | tee /tmp/kverus-review-verify-output.txt
   ```

   Record the exit code.

2. **Check verification status:**

   - Exit code 0: Verification passed.
   - Exit code non-zero: Verification failed. Extract and summarize the error messages (look for `error:` lines and `error: aborting due to` summary).

3. **Check for problematic warnings** (regardless of verification pass/fail):

   Grep the captured output for each of these three patterns:

   - `note: automatically chose triggers for this expression:`
     - Meaning: Verus has low confidence in auto-chosen SMT quantifier triggers. Should be annotated with `#[trigger]`, `#![trigger ...]`, or `#![auto]`.
   - `` warning: use of deprecated method `vstd::set::Set::<A>::finite` ``
     - Meaning: `Set::finite()` is deprecated — every `Set` is always finite in modern Verus; this call is a no-op.
   - `` warning: use of deprecated associated function `vstd::set::Set::<A>::new_assuming_finite` ``
     - Meaning: `Set::new_assuming_finite` is deprecated and dangerous — it unsoundly assumes finiteness.

   For each pattern, count occurrences and list the matching lines with line numbers.

### Step 5: Generate Report

Produce a Markdown report with the following structure:

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

**Report rules:**

- If verification fails, the report MUST include the verification status as `❌ failed` with the error summary.
- If any problematic warning is found, the report MUST list each one with count and locations.
- If any exec code modification is classified as `semantic-change`, highlight it prominently.
- If any exec-code preservation comment is `missing` or `malformed`, highlight it prominently.
- If any deleted comment is classified as `unjustified` or `uncertain`, highlight it prominently.
- Be conservative: when in doubt, classify as `uncertain` rather than `likely-equivalent`.

## What This Skill Is Not

- Not a full code review (no style, naming, or architecture feedback).
- Not a migration tool (use `kverus-migrate`).
- Not a proof repair tool (use `kverus-fix`).
- Not a spec quality scorer (use `kverus-eval`).
- Not a Rust-vs-Verus migration audit (use `kverus-semantic-audit`).

This skill reviews **incremental changes** for regressions, not the full Rust-to-Verus migration.
