# kverus-migrate knowledge

Companion knowledge for the kverus-migrate spec. Mirrors the source skill's Objective, Required Workflow, Transformation Rules, Edit Priority Policy, Failure Policy, and Domain-Specific Guidance; the Hard Constraints live verbatim in the spec's Constraints, not here.

## Shared reference reading order

If migration requires Verus syntax, modes, ghost/tracked values, atomic ghost code, loop invariants, or tokenized state-machine rules, read the relevant reference under `../kverus-common/references/` (the sibling kverus-common tree, deployed next to this spec's skill directory) before editing. Start with `verus-syntax-quickref.md`; consult the topical references (invariants, ghost-tracked, tokenized-state-machine, solvers) and the `unsupported-features/` index on demand.

Before adding, removing, or rewriting any executable Rust, read and follow `../kverus-common/references/exec-code-preservation.md`. This requirement is not optional when the original code can be recovered from the input or Git history.

## Objective and scope

Convert the Rust code in the entry file into Verus-compatible code with the smallest possible set of edits such that:

1. the code is syntactically accepted by Verus
2. the verification command succeeds
3. the original source structure is preserved as much as possible
4. the result is suitable as a future proof-ready baseline, even if it is not fully proved now

The goal is NOT to fully verify semantic correctness. The goal is only to make the code pass at the syntax, compatibility, and front-end acceptance level.

## Editing discipline

Before making large edits: inspect the entry file and its immediate dependencies, make a short plan, edit incrementally, run the verification command after meaningful changes, and use the error messages to guide the next minimal repair step. Avoid broad rewrites up front.

The validation loop repeats: inspect code, make a short plan, apply minimal edits, run the verification command, inspect errors, apply the smallest necessary repair — until success or a real blocker remains.

## Transformation rules

Rule 1 — Attribute-first executable verification: prefer `#[verus_spec]` for executable functions and supported annotations on their loops, preserving native Rust signatures and bodies. Use `verus!` for spec/proof declarations, external specifications, and constructs unsupported by the active attribute syntax. Keep `use` statements outside `verus!` unless required by syntax.

Rule 2 — `#[verifier::external_body]`: add `#[verifier::external_body]` to functions whose bodies should be skipped during proof checking. Use this as the default strategy unless it prevents syntactic acceptance.

Rule 3 — Unsupported Rust features: if Verus does not support a Rust feature or syntax fragment: (1) if executable code changes, preserve it using exec-code-preservation.md; otherwise keep the original syntax as a nearby comment when feasible; (2) rewrite only the unsupported fragment; (3) keep the rewritten code at the same location. The sibling references tree's `unsupported-features/` index catalogs common unsupported constructs and their workarounds.

Rule 4 — Compile-failed Rust: if the original Rust code does not compile, still convert it into the closest Verus-compatible form using minimal edits.

Rule 5 — Dependencies: if the entry file relies on other code, minimally adapt only the necessary dependencies. If a required dependency is commented out, uncomment only the minimum necessary portion. Do not expand edits beyond the smallest dependency closure needed to pass the verification command.

## Edit priority policy

When multiple repair strategies exist, prefer them in the following order:

1. local syntax-preserving edits
2. adding `#[verifier::external_body]`
3. rewriting unsupported expressions or type fragments
4. minimally adapting direct dependencies
5. broader edits only as a last resort

## Atomic operations

For operations such as `fetch_add`, `fetch_sub`, and `compare_exchange`, prefer `atomic_with_ghost!` when required by Verus compatibility. The source skill's canonical example (note the inline reason-first preservation comments, per exec-code-preservation.md):

```rust
impl<T /*: ?Sized*/, G: SpinGuardian> RwLock<T, G> {
    pub fn try_read(&self) -> Option<RwLockReadGuard<T, G>> {
        let guard = G::read_guard();

        /* `fetch_add` needs `atomic_with_ghost!` to expose its transition to Verus.
         * Origin Rust: let lock = self.lock.fetch_add(READER, Acquire);
         */
        let lock = atomic_with_ghost!(
            &self.lock => fetch_add(READER);
            returning res;
            ghost g => { }
        );

        if lock & (WRITER | MAX_READER | BEING_UPGRADED) == 0 {
            Some(RwLockReadGuard {
                inner: self,
                guard,
                v_perm: Tracked::assume_new(),
            })
        } else {
            /* `fetch_sub` needs `atomic_with_ghost!` to expose its transition to Verus.
             * Origin Rust: self.lock.fetch_sub(READER, Release);
             */
            atomic_with_ghost!(
                &self.lock => fetch_sub(READER);
                ghost g => { }
            );

            None
        }
    }
}
```

## Failure policy

If the verification command cannot succeed without violating the constraints: stop at the smallest blocking point, do not fabricate behavior, do not introduce placeholders, and report the blocking location precisely. The blocked report names the exact file, region, and diagnostic that block the conversion, plus which hard constraint blocks each candidate repair — nothing more, and no long explanation beyond that.
