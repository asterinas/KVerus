---
name: kverus-strip
description: Aggressively strip redundant proof code from a Verus codebase while keeping verification passing. Use when you want to slim down Verus proof bloat, simplify redundant proof asserts, or run postprocess cleanup without breaking verification.
argument-hint: verify="<verification command>" [target-dirs="<dir1,dir2|path.rs>"] [function="<fn_name>"] [base="<git-base>"]
license: MIT
compatibility: Requires a working Verus verification command.
user-invocable: true
metadata:
  author: kverus
  version: "1.0"
---

Aggressively strip redundant proof code from a Verus codebase while keeping verification passing. Be as aggressive as possible — many proof blocks and assertions exist purely for human readability and are not needed for the SMT solver to succeed.

Preferred invocation:

```text
$kverus-strip verify="<verification command>" target-dirs="<dir1,dir2>"
```

If `verify` is missing, ask for it before editing. If `target-dirs` is missing, first run the proof simplification script for changed files; ask for `target-dirs` only before doing broader manual proof-code stripping.

## Arguments

- `verify` (required): The full verification command, e.g. `cargo verus focus my_crate`.
- `target-dirs` (required for broader manual stripping): Comma-separated source directories **or single `.rs` files** to scan, e.g. `src/,specs/` or `ostd/specs/mm/page_table/owners.rs`. A path the script would otherwise need to discover can be passed directly here.
- `function` (optional): Comma-separated function short names to restrict stripping to, e.g. `lemma_vaddr_of_eq_int`. Only matching functions are processed; all others in the file are left untouched.
- `base` (optional): Git base ref for changed-file discovery, e.g. `origin/main`.

## Shared Verus References

If understanding Verus proof constructs (proof blocks, ghost/tracked values, spec/proof functions) is needed before deciding deletions, read the relevant reference under `../kverus-common/references/` before editing.

## Proof Simplification Script

For routine redundant proof-statement cleanup, prefer the bundled script before manual stripping:

```bash
. "$AGENT_DIR/kverus.env"
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-strip/scripts/simplify_proof.py" \
  --base <git-base> \
  --target-dir '<dir1,dir2>' \
  --verify-command '<verification command>' \
  --format-command '<format command>'
```

The script scans changed `.rs` files when no `--target-dir` or `--file` is provided. It simplifies at function scope, matches the `src/refiner/simplifier.py` policy, skips runtime `assert!(...)`, never removes `assert(false)`, skips functions containing `admit`, `assume`, or `#[verifier::external_body]` unless `--deep-clean` is set, removes one proof statement at a time, and keeps the removal only when the verification command still succeeds. With `tree-sitter-verus`, candidates include standalone function-call statements in `proof fn`, `proof {}`, and assertion proof blocks; executable calls are extracted but never offered for deletion. The default mode requires `tree-sitter-verus` and errors out if it is missing; pass `--text-only` to force the lower-precision text-based (asserts-only) parser. Use `--dry-run` to list candidates without editing.

To simplify a single function (or a few) instead of a whole file or directory, point `--target-dir` at the file and pass `--function` (repeatable, or comma-separated). Only functions whose short name matches are processed; every other function in the file is left untouched:

```bash
. "$AGENT_DIR/kverus.env"
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-strip/scripts/simplify_proof.py" \
  --target-dir '<path/to/file.rs>' \
  --function '<function_name>[,<other_name>]' \
  --verify-command '<verification command>' \
  --format-command '<format command>'
```

Names are matched against the short function name (e.g. `lemma_vaddr_of_eq_int`); qualified paths like `Impl::lemma_foo` are also accepted. Pair `--function` with `--verify-command '<verify> -- --verify-only-module <module_path>'` so each trial re-verifies just the relevant module rather than the whole crate.

To restrict stripping to only the functions you actually changed in this diff, pass `--modified-only` (typically with `--base <git-base>`). It intersects discovered function ranges with the added lines of `git diff` (committed `base...HEAD` plus the worktree diff) and skips every function whose lines were not added by the change. This is what `kverus-postprocess` uses by default so it only touches newly modified proof code.

`--function` and `--modified-only` compose: a function is processed only if it matches the `--function` filter **and** overlaps an added diff hunk.

`tree-sitter-verus` ships in the KVerus venv referenced by `kverus.env` (the install
script checks it). Run the script with that venv's Python
(`$KVERUS_PYTHON`, set up by sourcing `$AGENT_DIR/kverus.env`) and full
proof-call simplification is active automatically — no manual availability check is
needed. If the venv is ever unavailable, the default mode errors out — pass
`--text-only` to force text-based (asserts-only) parsing; always run the script
rather than substituting manual
stripping, since only the script performs the delete→verify→restore safety loop per
candidate.

While the script is running, do not repeatedly narrate unchanged status or
reprint its output. Poll silently at coarse intervals. Report only when the
script finishes, times out, fails, or produces materially new information.

If the script reaches its runtime or verification-run budget, continue with
the successfully verified edits already committed by the script; do not
automatically restart it with a larger budget.

After successful removals, pass `--format-command` to run the project formatter and clean up formatter-introduced added empty lines. Omit it only when the caller will run an equivalent formatter and cleanup step.

## Objective

Remove all proof code that is not strictly necessary for verification to pass. Prefer maximal removal over conservative trimming. The SMT solver often does not need explicit proof hints that a human would.

## Hard Constraints

1. **Never delete `assert(false)`** — intentionally placed to mark unreachable paths; must be preserved.
2. Do not modify executable Rust code (i.e., code outside `proof{}`, `ghost{}`, `spec fn`, `proof fn`).
3. Do not modify `requires`, `ensures`, `invariant`, `decreases`, or `recommends` clauses.
4. Do not add `assume`, `admit`, or `#[verifier::external_body]`.
5. Keep edits localized per file. Do not change multiple files in one pass.

## Required Workflow

### Step 0: Collect Target Files

List all `.rs` files in the `target-dirs` directories (including subdirectories).

### Step 1: Per-File Aggressive Deletion

For each `.rs` file, work through the deletion patterns in priority order (Pattern 1 first, as it is the most impactful):

1. Read the file and identify all deletion candidates per the patterns below.
2. Apply deletions aggressively — prefer maximizing removal.
3. After removing assertions, immediately clean up artifacts caused by those removals:
   standalone empty `;` statements, empty proof-only `if` blocks/branches, empty
   `proof {}` blocks, proof-variable bindings whose values are no longer used, and
   comments that only describe proof code, variables, branches, or steps that were deleted.
4. Run per-module verification:

   ```bash
   <verify> -- --verify-only-module <module_path>
   ```

   Use the `--verify-only-module` flag pointing to the Rust module path (not the file path). For example, `src/foo/bar.rs` → `foo::bar`, `src/lib.rs` → the crate name. The exact mapping depends on the crate's module structure.

5. If the targeted module passes, move to the next file.
6. If the targeted module fails, read the error output and restore the minimal set of deletions needed, then re-verify.

### Step 2: Cross-Module Verification

After all individual modules pass:

1. Run the full `<verify>` command.
2. Fix any cross-module regressions by restoring necessary proof code.

## Failure Recovery

1. Read the error carefully to understand what proof fact is missing.
2. Restore ONLY the specific deleted code that provided that fact.
3. If unsure which deletion caused the failure, restore deletions in reverse order (most recent first), re-verifying after each.
4. Do NOT add new proof code. Only restore previously deleted code.

## Deletion Patterns — Safe to Remove Aggressively

Apply these deletions aggressively. If in doubt, delete first and only restore if verification fails.

**Patterns are listed in priority order.** Pattern 1 (standalone `assert`) is by far the most impactful and should be tackled first in every file. The later patterns are supplementary and relatively rare.

### Pattern 1: Standalone `assert(...)` without a `by` proof block ⭐ HIGHEST PRIORITY

This is the single most important pattern. A "standalone assert" is any `assert(condition);` that provides no explicit proof — no `by { ... }` and no `by (solver_hint)`. The SMT solver is expected to prove it unaided.

**Key heuristics for prioritizing standalone asserts (most→least likely redundant):**

1. **Integer comparisons and overflow guards** — `assert(x < y)`, `assert(x < usize::MAX)`, etc. are nearly always redundant for integer types.
2. **Trivial arithmetic** — `assert(x + y == y + x)`, etc. are highly likely to be redundant.
3. **Property checks** — `assert(self.wf(...))`, `assert(self.inv())`, `assert(x.is_node())`, etc., after an operation whose post-condition already ensures the property.

**How to find them:** Search for `assert(` and check whether a `by` follows on the same or next non-empty line. If no `by` → candidate for deletion. These can appear anywhere: exec code, ghost code, or inside `proof{}` blocks. **The ONLY criterion is the absence of `by`.**

```rust
// ── DELETE: standalone asserts (NO `by`) ──
// Location (exec/ghost/proof{} block) is irrelevant.

// In exec code:
assert(!self.some_panic_check(args));
assert(count < usize::MAX);
assert(self.wf(*owner));
assert(old(self).field % size == 0);

// Inside proof{} blocks — still standalone (no `by`):
proof {
    some_lemma();
    assert(result.inv());            // DELETE
    assert(new_val == expected);     // DELETE
    do_something_tracked();
}

// Inside ghost code:
assert(!ptr.is_null());
assert(token.frac() == 1);

// ── KEEP: asserts WITH `by` ──

assert(cond) by {                // explicit proof body
    lemma_foo();
};
assert(cond) by (bit_vector);    // solver hint
assert(cond) by (nonlinear_arith);
assert(cond) by (compute_only);
assert(cond) by (compute);
```

**Trigger-aware caution — skip asserts likely to be SMT quantifier triggers:**

```rust
assert(x.contains(y));        // likely a trigger — do NOT delete
assert(x.contains_key(y));    // likely a trigger — do NOT delete
assert(set.contains(elem));   // likely a trigger — do NOT delete
assert(map.contains_key(k));  // likely a trigger — do NOT delete
```

If an `assert` contains `.contains()` or `.contains_key()` anywhere in its expression, skip it. These often serve as quantifier triggers the SMT solver needs to instantiate quantified axioms about sets and maps.

### Pattern 2: Redundant `as int` (and other integer type casts) in spec mode

In Verus spec code, arithmetic and comparison operators automatically widen operand types to avoid overflow. Per the [spec arithmetic typing rules](https://verus-lang.github.io/verus/guide/spec-arithmetic.html#typing):

- `+`, `-`, `*` → result is `int` (except `nat + nat` → `nat`, `nat * nat` → `nat`)
- `/` → `int` for signed operands; same type for unsigned
- `%` → same type as operands
- `<=`, `<`, `>=`, `>` → work across any integer types, result is `bool`

Therefore, `as int` casts (and casts like `as u64`, `as usize`) on operands of these operators in spec code (`spec fn`, `proof fn`, `proof{}` blocks, `assert(...)`) are redundant and can be removed.

```rust
// ── DELETE: redundant integer casts on arithmetic/comparison operands in spec mode ──

(x as int) + (y as int)    →  x + y
(x as int) - (y as int)    →  x - y
(x as int) * (y as int)    →  x * y
(x as int) / (y as int)    →  x / y
(x as int) % (y as int)    →  x % y
(x as int) <= (y as int)   →  x <= y
(x as int) <  (y as int)   →  x <  y
(x as int) >= (y as int)   →  x >= y
(x as int) >  (y as int)   →  x >  y

// Mixed operands — remove casts on either side:
(x as int) + y    →  x + y
x + (y as int)    →  x + y
(x as int) <= y   →  x <= y
x <= (y as int)   →  x <= y

// ── KEEP: casts NOT on arithmetic/comparison operands ──

let z: int = x as int;     // standalone let-binding — KEEP (type annotation may be needed)
f(x as int);               // function argument — KEEP (may be needed for type matching)
x as int                    // return expression — KEEP (may be needed for return type)
```

**Scope:** This pattern applies only inside `spec fn`, `proof fn`, `proof{}` blocks, and `ghost{}` blocks. Do NOT remove casts in executable Rust code.

**How to find them:** Search for `as int` (or `as u64`, `as usize`, etc.) inside spec/proof/ghost contexts, and check whether the casted expression is an operand of `+`, `-`, `*`, `/`, `%`, `<=`, `<`, `>=`, or `>`.

### Pattern 3: Empty statements left by proof-code removal

Removing a multiline assertion or proof expression can leave its terminating `;`
behind on a line by itself. Delete these standalone empty statements as part of the
same cleanup pass.

```rust
proof {
    lemma_foo();
    ;                 // DELETE
    lemma_bar();
}
```

Only remove semicolons that are standalone empty statements introduced by the
cleanup. Do not remove semicolons that terminate a retained expression or item.

### Pattern 4: Empty `proof{}` blocks

```rust
// DELETE entirely:
proof {
}
```

### Pattern 5: Empty proof-only `if` blocks and branches

```rust
// DELETE both branches if both are empty:
proof {
    if condition {
    } else {
    }
}

// DELETE only the empty branch:
proof {
    if condition {
        // keep this
    } else {
        // DELETE this
    }
}
```

Also delete an entire proof-only `if` statement when its body contains only
bindings or statements removed by this cleanup:

```rust
// DELETE entirely after `x` and its assertions become unused:
if condition {
    let x = proof_expression;
}
```

Do not rewrite executable control flow. This pattern applies only in proof/spec/
ghost contexts covered by the hard constraints.

**Caution:** A textually empty proof branch can still add its condition or negation
to the SMT context. Treat removal as a normal proof-code candidate: delete it,
verify, and restore the minimal branch if verification fails or a recommendation
is unmet. When only one branch is empty, rewrite the proof-only condition only if
needed to remove that branch, and verify the equivalent form immediately.

### Pattern 6: Unused proof-variable initializations

```rust
// DELETE when the binding name is never referenced later:
let tracked x = ...;
let ghost y = ...;
let index = path.index(0); // inside proof/spec/ghost code
```

This includes ordinary `let` bindings inside `proof fn`, `proof {}`, `ghost {}`,
and other proof/spec contexts when assertion removal eliminated every textual use.
Remove the surrounding proof-only branch too if it becomes empty.

**Caution:** textual non-use is not proof non-use in Verus. Evaluating the RHS can
instantiate a broadcast lemma, satisfy a trigger, unfold a spec function, or call a
`proof fn` whose `ensures` supplies facts. Delete aggressively, verify, and restore
the binding if its removal causes a verification failure or unmet recommendation.
Never remove an executable initialization under this pattern.

### Pattern 7: Entire `proof{}` blocks containing only standalone asserts and let-bindings

When a `proof{}` block contains only a mix of Pattern 5, Pattern 6, and Pattern 1
items, try deleting the entire block.

### Pattern 8: Redundant `reveal` / `hide` calls

`reveal` and `hide` calls not strictly needed for subsequent proof steps can be deleted.

**Caveat:** `reveal` calls inside `assert forall` by-blocks are usually NOT safe — they unfold function bodies needed for quantifier instantiation. Only try standalone `reveal` calls in a `proof{}` block.

### Pattern 9: Orphaned or stale proof comments

Delete comments that became false, misleading, or useless because their referenced
proof code was removed. Typical candidates include comments such as "pre-prove X",
"stitch the arithmetic below", step markers, explanations of a deleted branch, and
comments naming proof variables or assertions that no longer exist.

Keep comments that still explain a retained proof step, a specification or API
obligation, a non-obvious solver trigger, or the reason for a retained
`assert(false)`. Preserve rustdoc unless the documented behavior or proof obligation
itself changed. After formatting, rescan nearby comments because line movement and
empty-block cleanup can expose additional orphaned comments.

## Output

After completion, report:
- Number of files processed
- Number of deletions made (total lines removed)
- Number of deletions that had to be restored
- Final verification result (pass/fail)
