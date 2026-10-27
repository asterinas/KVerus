# kverus-strip knowledge

Companion knowledge for the kverus-strip spec. The spec owns the routing (bundled script first — scoped by the target scope when supplied, changed-file discovery when not — then agent postprocess, then broader manual per-file stripping when a scope exists), the whole-run rlimit guard, and the delete→verify→restore loop discipline. This document carries the objective, the hard constraints, the nine deletion patterns with their keep-forms and cautions, the failure-recovery rules, the guard protocol detail, the bundled script reference, and the report format.

## Objective

Remove all proof code that is not strictly necessary for verification to pass. Prefer maximal removal over conservative trimming. The SMT solver often does not need explicit proof hints that a human would write. Be as aggressive as possible — many proof blocks and assertions exist purely for human readability and are not needed for the solver to succeed.

## Hard constraints

Carried verbatim from the source skill; they govern every deletion on both paths:

1. **Never delete `assert(false)`** — intentionally placed to mark unreachable paths; must be preserved.
2. Do not modify executable Rust code (i.e., code outside `proof{}`, `ghost{}`, `spec fn`, `proof fn`).
3. Do not modify `requires`, `ensures`, `invariant`, `decreases`, or `recommends` clauses.
4. Do not add `assume`, `admit`, or `#[verifier::external_body]`.
5. Keep edits localized per file. Do not change multiple files in one pass.

Related script-side safety envelope: the bundled script skips runtime `assert!(...)`, never removes `assert(false)`, skips functions containing `admit`, `assume`, or `#[verifier::external_body]` unless `--deep-clean` is set (this spec never passes `--deep-clean`), removes one proof statement at a time, and keeps a removal only when verification still succeeds.

## Deletion patterns

Apply these deletions aggressively. If in doubt, delete first and only restore if verification fails. Patterns are listed in priority order — Pattern 1 is by far the most impactful and should be tackled first in every file; the later patterns are supplementary and relatively rare.

### Pattern 1: Standalone `assert(...)` without a `by` proof block — HIGHEST PRIORITY

A "standalone assert" is any `assert(condition);` that provides no explicit proof — no `by { ... }` and no `by (solver_hint)`. The SMT solver is expected to prove it unaided.

Key heuristics for prioritizing standalone asserts (most to least likely redundant):

1. Integer comparisons and overflow guards — `assert(x < y)`, `assert(x < usize::MAX)`, etc. are nearly always redundant for integer types.
2. Trivial arithmetic — `assert(x + y == y + x)`, etc. are highly likely to be redundant.
3. Property checks — `assert(self.wf(...))`, `assert(self.inv())`, `assert(x.is_node())`, etc., after an operation whose post-condition already ensures the property.

How to find them: search for `assert(` and check whether a `by` follows on the same or next non-empty line. If no `by`, it is a deletion candidate. These can appear anywhere: exec code, ghost code, or inside `proof{}` blocks. The ONLY criterion is the absence of `by`.

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

Trigger-aware caution — skip asserts likely to be SMT quantifier triggers:

```rust
assert(x.contains(y));        // likely a trigger — do NOT delete
assert(x.contains_key(y));    // likely a trigger — do NOT delete
assert(set.contains(elem));   // likely a trigger — do NOT delete
assert(map.contains_key(k));  // likely a trigger — do NOT delete
```

If an `assert` contains `.contains()` or `.contains_key()` anywhere in its expression, skip it. These often serve as quantifier triggers the SMT solver needs to instantiate quantified axioms about sets and maps.

### Pattern 2: Redundant `as int` (and other integer type casts) in spec mode

In Verus spec code, arithmetic and comparison operators automatically widen operand types to avoid overflow. Per the spec arithmetic typing rules (https://verus-lang.github.io/verus/guide/spec-arithmetic.html#typing):

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
x as int                   // return expression — KEEP (may be needed for return type)
```

Scope: this pattern applies only inside `spec fn`, `proof fn`, `proof{}` blocks, and `ghost{}` blocks. Do NOT remove casts in executable Rust code. How to find them: search for `as int` (or `as u64`, `as usize`, etc.) inside spec/proof/ghost contexts, and check whether the casted expression is an operand of `+`, `-`, `*`, `/`, `%`, `<=`, `<`, `>=`, or `>`.

### Pattern 3: Empty statements left by proof-code removal

Removing a multiline assertion or proof expression can leave its terminating `;` behind on a line by itself. Delete these standalone empty statements as part of the same cleanup pass.

```rust
proof {
    lemma_foo();
    ;                 // DELETE
    lemma_bar();
}
```

Only remove semicolons that are standalone empty statements introduced by the cleanup. Do not remove semicolons that terminate a retained expression or item.

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

Also delete an entire proof-only `if` statement when its body contains only bindings or statements removed by this cleanup:

```rust
// DELETE entirely after `x` and its assertions become unused:
if condition {
    let x = proof_expression;
}
```

Do not rewrite executable control flow. This pattern applies only in proof/spec/ghost contexts covered by the hard constraints.

Caution: a textually empty proof branch is usually NOT dead code — it is the carrier of a case split. When Pattern 1 strips the only statement inside a branch, the branch condition typically still serves two roles:

1. Trivial case: under the condition, the enclosing goal (often an `ensures` existential) is witnessed by a concrete value, so the branch needs no proof code.
2. Sibling path fact: the condition's negation is exactly the fact the other branch needs — e.g. unfolding `!u64_bit_is_set(word, 0)` to `(word & (1u64 << 0)) == 0`, a conjunct of a `by (bit_vector) requires` clause. The explicit `assert` Pattern 1 removed relied on this path fact.

Treat plain removal as a normal proof-code candidate: delete it, verify, and restore the minimal branch if verification fails or a recommendation is unmet.

Preferred treatment — guard flip. Instead of deleting the case split or restoring a redundant witness `assert`, negate the guard of the meaty branch so the trivial case becomes the unhandled fall-through with no branch at all:

```rust
// before: middle branch emptied by Pattern 1 — the case split still stands:
} else if u64_bit_is_set(word, 0) {
} else {
    // recursion; uses !u64_bit_is_set(word, 0) as a path fact
}

// after: trivial case (ensures witnessed by b == 0) falls through:
} else if !u64_bit_is_set(word, 0) {
    // Bit 0 clear: recurse on the shift. Otherwise (bit 0 set, 0 < n) the ensures
    // is witnessed by `b == 0` directly.
    ...
}
```

The vacuous fall-through still closes: the negated branch condition is a ground term that matches the goal's `#[trigger]`, so the SMT finds the witness via model-based quantifier instantiation. Keep a one-line comment on the flipped guard noting why the unhandled case is trivial, verify the flipped form immediately, and only fall back — first to an explicit witness `assert` in the removed branch, then to restoring the branch — if verification fails.

### Pattern 6: Unused proof-variable initializations

```rust
// DELETE when the binding name is never referenced later:
let tracked x = ...;
let ghost y = ...;
let index = path.index(0); // inside proof/spec/ghost code
```

This includes ordinary `let` bindings inside `proof fn`, `proof {}`, `ghost {}`, and other proof/spec contexts when assertion removal eliminated every textual use. Remove the surrounding proof-only branch too if it becomes empty.

Caution: textual non-use is not proof non-use in Verus. Evaluating the RHS can instantiate a broadcast lemma, satisfy a trigger, unfold a spec function, or call a `proof fn` whose `ensures` supplies facts. Delete aggressively, verify, and restore the binding if its removal causes a verification failure or unmet recommendation. Never remove an executable initialization under this pattern.

### Pattern 7: Entire `proof{}` blocks containing only standalone asserts and let-bindings

When a `proof{}` block contains only a mix of Pattern 5, Pattern 6, and Pattern 1 items, try deleting the entire block.

### Pattern 8: Redundant `reveal` / `hide` calls

`reveal` and `hide` calls not strictly needed for subsequent proof steps can be deleted.

Caveat: `reveal` calls inside `assert forall` by-blocks are usually NOT safe — they unfold function bodies needed for quantifier instantiation. Only try standalone `reveal` calls in a `proof{}` block.

### Pattern 9: Orphaned or stale proof comments

Delete comments that became false, misleading, or useless because their referenced proof code was removed. Typical candidates include comments such as "pre-prove X", "stitch the arithmetic below", step markers, explanations of a deleted branch, and comments naming proof variables or assertions that no longer exist.

Keep comments that still explain a retained proof step, a specification or API obligation, a non-obvious solver trigger, or the reason for a retained `assert(false)`. Preserve rustdoc unless the documented behavior or proof obligation itself changed. After formatting, rescan nearby comments because line movement and empty-block cleanup can expose additional orphaned comments.

## Failure recovery

Carried from the source skill's Failure Recovery section:

1. Read the error carefully to understand what proof fact is missing.
2. Restore ONLY the specific deleted code that provided that fact.
3. If unsure which deletion caused the failure, restore deletions in reverse order (most recent first), re-verifying after each.
4. Do NOT add new proof code. Only restore previously deleted code.

## Whole-run rlimit guard

The script's `--perf-factor` guard only protects functions carrying an explicit `#[verifier::rlimit(...)]` budget. The protocol below guards the whole run with two total-rlimit measurements — one taken before any proof code is touched, one after the ENTIRE simplification is finished (script done plus the agent's postprocess: orphaned comment/binding/empty-branch cleanup, trusted-axiom-call review, formatter, and the final full verification; the broader manual stripping phase, when it runs, sits inside the same pair — the closing measurement follows it too). One measurement pair wraps the whole session, not one per file.

Both measurements use the project's FULL verification command with verus `--time` appended (e.g. `cargo dv verify --targets ostd -- --time`), and must use the identical command and scope so the numbers compare directly.

- A real run prints one aggregate line at the end:

  ```text
  total smt-run:             233340 ms, 1127340657 rlimit (11 threads)
  ```

  Record the rlimit count. The ms figure is machine-load noise; the rlimit is Z3's deterministic resource count (machine-independent), so pre vs post compares exactly, with no jitter tolerance.
- A run whose content is unchanged since the last successful verify replays a cached no-op — it finishes in ~1–2 seconds and prints NO stats line, so it is silently not a measurement. Force a real run: append a trailing newline to a file in the strip scope, verify, remove the newline again. Trailing whitespace changes nothing verus encodes, so the measured rlimit is the true baseline of the clean content. (Skip both measurements when the strip produced no changes.)
- Before the first deletion, snapshot the pre-strip content of the file(s) being stripped (e.g. copy them aside). If the worktree was already dirty, a plain `git diff` cannot reconstruct the pre-strip text for restores.
- If `post <= pre`: report both numbers and stop — a decrease is the normal outcome (a good strip removes solver work; e.g. the list_store strip landed at −179,176 on a 1,127,340,657 baseline).

If `post > pre` — bring the rlimit as close to the original as possible, first by restoring proof code, then by reporting:

1. Report the growth: both numbers, the delta, and the percentage.
2. Restore stripped proof guidance toward the baseline, most recent deletion first (the last deletions are both the likeliest blame and the cheapest to undo): re-insert the deleted lines from the snapshot, re-run the full `--time` verify, and keep restoring while `post > pre`. Every intermediate state was verified clean during the strip, so each single restore is safe. Bound the loop (≈10 full-verify rounds) — full verifies are minutes each. For attribution, bisect with scoped measurements (`-- --verify-only-module <mod> --time`, then `--verify-function <fn> --time`) to find which function grew before restoring anything.
3. Whatever growth remains after the bounded restores, report it plainly with the follow-up levers (error-span-guided re-add via `--profile`, relaxing the strip for that function), and leave the tree verified green.

Comment-only deletions are rlimit-neutral (whole-crate totals have tested byte-identical), so they never need this recovery loop.

## Script reference

The bundled `simplify_proof.py` is the preferred first move for routine redundant proof-statement cleanup. Source invocation form (the deployed script self-bootstraps the environment per the L1 ruling — env sourcing and interpreter selection are its own entry behavior):

```bash
. "$AGENT_DIR/kverus.env"
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-strip/scripts/simplify_proof.py" \
  --base <git-base> \
  --target-dir '<dir1,dir2>' \
  --verify-command '<verification command>' \
  --format-command '<format command>'
```

Behavior: scans changed `.rs` files when no `--target-dir` or `--file` is provided; simplifies at function scope; matches the `src/refiner/simplifier.py` policy; skips runtime `assert!(...)`; never removes `assert(false)`; skips functions containing `admit`, `assume`, or `#[verifier::external_body]` unless `--deep-clean` (never passed by this spec); removes one proof statement at a time; keeps the removal only when verification still succeeds. Candidates (with `tree-sitter-verus`): standalone function-call statements in `proof fn`, `proof {}`, and assertion proof blocks; executable calls are extracted but never offered for deletion.

The rlimit perf guard (revert a passing strip when the Z3 rlimit grew by more than `--perf-factor`, measured via verus `--time`) applies only to functions carrying an explicit `#[verifier::rlimit(...)]` budget — those have a real cap a strip could push toward. Every other function strips purely on pass/fail: rlimit growth is not checked and no baseline probe verify is spent. `--no-perf-guard` applies that pass/fail-only behavior everywhere.

Outcome lines — each candidate prints one bare line (DEBUG-level sink, shown by default; `--quiet` hides them; colored on a tty, symbols only when piped):

- `✓ removed mod.rs:218 assert(fid != id);`
- `✗ kept … (verify failed)`
- `~ kept … (rlimit exceeded: N > Kx baseline M)`

The tqdm bar postfix carries the live `✓N ✗N` tally plus the candidate currently being verified, so there is no separate `trying` line. Each file first logs `stripping <path>: N function(s)` so the short filename in outcome lines stays unambiguous; `kept …` lines end with the bare reason and no more detail than that.

Flags used or noted by this spec:

- `--base <git-base>` — git base ref for changed-file discovery (passed when supplied).
- `--target-dir '<dir1,dir2>'` — explicit scan scope (directories or a single `.rs` file). Passed when the target-scope input was supplied; absent, the script discovers changed files itself.
- `--verify-command '<verification command>'` — passed when the effective command is non-empty (always on the standalone flow); omitted under the enumeration degradation, where there is nothing to check. Two scoping mechanisms compose with it: the caller may pre-scope the command string with `-- --verify-only-module <module_path>` (the source's pairing guidance), or embed the literal `{fn}` placeholder as `--verify-function {fn}` — the script substitutes each stripped function's short name so trials verify just that function, automatically falling back to the unscoped command when the name is ambiguous or unresolvable (a `{fn}` outside a `--verify-function` clause is refused with exit 1). The script auto-appends `--time` to the command for its own rlimit accounting.
- `--format-command '<format command>'` — runs the project formatter after successful removals and cleans formatter-introduced added empty lines. Omit only when the caller runs an equivalent formatter and cleanup itself; this spec passes the derived formatter command when non-empty.
- `--function '<fn_name>[,<other_name>]'` — restrict to matching functions (short names; qualified paths like `Impl::lemma_foo` accepted), repeatable or comma-separated. Compose with `--target-dir` pointing at the file for single-function work.
- `--modified-only` — intersect discovered function ranges with the added lines of the git diff (committed `base...HEAD` plus the worktree diff), skipping functions the change did not touch. This is what `kverus-postprocess` uses by default. Composes with `--function`: a function is processed only when it matches the filter AND overlaps an added diff hunk. Passed only when the optional `modified_only` input is set — the `kverus-postprocess` spec relays its default changed-lines scope this way; this spec's standalone invocation never sets it, preserving the whole-file scope within the supplied target dirs.
- `--dry-run` — list candidates without editing. Passed only when the optional `dry_run` input is set (the `kverus-postprocess` spec's degradation when no verification command exists); under it this spec skips the baseline measurement, the manual-phase scope question, the whole-tree check, and the guard — an enumeration-only run that never asks and never edits. The spec also omits `--verify-command` and `--format-command` under this degradation (the source wrapper's no-verification branch behaves the same).
- `--perf-factor` / `--no-perf-guard` — control the per-function rlimit perf guard described above.
- `--quiet` — hide the per-candidate outcome lines.
- `--timeout` — never passed; the script's per-command timeout defaults to disabled (`0`), and the engine-level subprocess timeout on this spec's script step bounds the whole run instead.
- `--repo-root` / `--file` / `--no-cleanup` — never passed; discovery defaults to the git root, `--target-dir` accepts file paths directly, and the formatter's empty-line cleanup stays enabled.

Classification anchors for this spec's verdict step: a finished run closes with a machine-readable summary line — `assert simplification files=N, functions=N, skipped_unproven=N, attempted=N, removed=N, restored=N, assert_attempted=N, assert_removed=N, call_attempted=N, call_removed=N, verification_runs=N, kept_as_perf_hint=N` — from which files processed (`files=`), deletions made (`removed=`), and restores (`restored=`) are read. A non-zero exit carrying diagnostics (the `{fn}` misuse refusal, the missing-venv error-out, argparse errors) is a hard failure. A run killed by an external budget before finishing prints no summary line; its committed deletions stand as the exhausted verdict. An empty discovery prints `assert simplification found no Rust files` and exits 0 with nothing done.

`tree-sitter-verus` is required: the script errors out when it is missing. It ships in the KVerus venv referenced by `kverus.env` (the install script checks it); run the script with that venv's Python and full proof-call simplification is active automatically — no manual availability check is needed. If the venv is ever unavailable, the script errors out; fix the venv rather than substituting manual stripping, since only the script performs the delete→verify→restore safety loop per candidate.

Runtime discipline while the script runs: do not repeatedly narrate unchanged status or reprint its output. Poll silently at coarse intervals. Report only when the script finishes, times out, fails, or produces materially new information. If the script reaches its runtime or verification-run budget, continue with the successfully verified edits it already committed — do not automatically restart it with a larger budget.

## Routing and invocation forms

Preferred invocation (source form):

```text
$kverus-strip verify="<verification command>" target-dirs="<dir1,dir2>"
```

Routing (chain model, per the source's unconditional script-first rule): every run takes the bundled script first — scoped by `--target-dir` when the target-scope input was supplied, scanning changed files when it was not — followed by the agent's postprocess (orphaned comment/binding/empty-branch cleanup, trusted-axiom-call review, formatter). The broader manual stripping with the nine deletion patterns follows when a target scope exists: a scope supplied at invocation routes straight into it; when absent, the source defers — this spec asks for the scope at that point, and an empty answer skips the manual phase. The whole-run rlimit guard wraps the entire session; the closing measurement follows the final full verification. Single-function runs pass the name filter to the script and pair the command with module or `{fn}` scoping per the Script reference above.

Single-function simplification: point the script at the file and pass the name filter, pairing it with a module-scoped verification command so each trial re-verifies just the relevant module rather than the whole crate:

```bash
. "$AGENT_DIR/kverus.env"
"$KVERUS_PYTHON" "$AGENT_DIR/skills/kverus-strip/scripts/simplify_proof.py" \
  --target-dir '<path/to/file.rs>' \
  --function '<function_name>[,<other_name>]' \
  --verify-command '<verify> -- --verify-only-module <module_path>' \
  --format-command '<format command>'
```

Names are matched against the short function name; qualified paths are also accepted. Only matching functions are processed; every other function in the file is left untouched. The same name filter applies to the manual path's deletion passes.

## Module path mapping

Per-module verification uses a module path, not a file path: `src/foo/bar.rs` maps to `foo::bar`; `src/lib.rs` maps to the crate name. The exact mapping depends on the crate's module structure — derive the crate name from the workspace manifest when it is not obvious. The scoped verification form is `<verify> -- --verify-only-module <module_path>`, and scoped rlimit attribution uses `-- --verify-only-module <mod> --time` then `-- --verify-function <fn> --time`.

## Report requirements

After completion, report (source Output section, labels kept verbatim):

- Number of files processed
- Number of deletions made (total lines removed)
- Number of deletions that had to be restored
- Final verification result (pass/fail)
- Whole-run rlimit, pre vs post (and the delta; plus any guard restores if the total grew)

Keep the report behavior-led and honest: failed script runs state the failure and the restoration performed; skipped measurements state why (no changes); unresolved guard growth states both numbers, the delta, the percentage, and the follow-up levers.

## Shared reference reading order

If understanding Verus proof constructs (proof blocks, ghost/tracked values, spec/proof functions) is needed before deciding deletions, read the relevant reference under `../kverus-common/references/` before editing. For this skill's decision surface, the most relevant are `exec-code-preservation.md` (what must never be touched), `ghost-tracked.md`, `proof-localization.md`, `lemma-shape.md`, `verus-syntax-quickref.md`, and `unsupported-features/index.md` — all under the sibling kverus-common references tree.
