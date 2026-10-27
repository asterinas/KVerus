---
name: kverus-migrate
description: Convert a Rust target into minimally modified Verus-compatible code using an explicit verification command. Use when migrating a specific file and iterating until the verification command succeeds.
license: MIT
compatibility: Requires Codex CLI and a working Verus verification command.
metadata:
  author: kverus
  version: "1.0"
---

Convert Rust code into minimally modified Verus-compatible code for one explicit target file and verification command.

Preferred invocation:

```text
$kverus-migrate target=path/to/file.rs verify="<verification command>"
```

If either `target` or `verify` is missing, ask for the missing value and stop.

## Shared Verus References

If migration requires Verus syntax, modes, ghost/tracked values, atomic ghost code, loop invariants, or tokenized state-machine rules, read the relevant reference under `../kverus-common/references/` before editing.

Before adding, removing, or rewriting any executable Rust, read and follow
`../kverus-common/references/exec-code-preservation.md`.

## Objective

Convert the Rust code in `target` into Verus-compatible code with the smallest possible set of edits such that:

1. the code is syntactically accepted by Verus
2. the verification command succeeds
3. the original source structure is preserved as much as possible
4. the result is suitable as a future proof-ready baseline, even if it is not fully proved now

The goal is not to fully verify semantic correctness. The goal is only to make the code pass at the syntax, compatibility, and front-end acceptance level.

## Required Workflow

Before making large edits:

1. inspect the target code and its immediate dependencies
2. make a short plan
3. edit incrementally
4. run the verification command after meaningful changes
5. use the error messages to guide the next minimal repair step

Avoid broad rewrites up front.

## Hard Constraints

### A. In-place edits only

Edit the code at the original location whenever possible.

Do not comment out an entire function, impl, or module and rewrite a replacement elsewhere if a local replacement is sufficient.

### B. Preserve original Rust code locally

For every executable-code modification, follow the exact reason-first block-comment
format in `../kverus-common/references/exec-code-preservation.md`. This requirement is
not optional when the original code can be recovered from the input or Git history.

For unsupported non-executable syntax, preserve the original locally when feasible.
For example:

```rust
impl<T /*: ?Sized*/, G: SpinGuardian> RwLock<T, G>
```

### C. No fake placeholders

Do not introduce any new:

- `unimplemented!()`
- `panic!()`
- `loop {}`

### D. Minimality

Only change code that is necessary for:

- the requested `target`
- its minimal dependency closure

Do not refactor unrelated code.

### E. Preserve structure

Preserve as much as possible:

- item order
- function order
- impl and block structure
- source locality
- nearby comments

Avoid large structural rewrites.

## Transformation Rules

### Rule 1: Attribute-first executable verification

Prefer `#[verus_spec]` for executable functions and supported annotations on
their loops, preserving native Rust signatures and bodies. Use `verus!` for
spec/proof declarations, external specifications, and constructs unsupported by
the active attribute syntax.

Keep `use` statements outside `verus!` unless required by syntax.

### Rule 2: `#[verifier::external_body]`

Add `#[verifier::external_body]` to functions whose bodies should be skipped during proof checking.

Use this as the default strategy unless it prevents syntactic acceptance.

### Rule 3: Unsupported Rust features

If Verus does not support a Rust feature or syntax fragment:

1. if executable code changes, preserve it using `exec-code-preservation.md`; otherwise keep the original syntax as a nearby comment when feasible
2. rewrite only the unsupported fragment
3. keep the rewritten code at the same location

### Rule 4: Compile-failed Rust

If the original Rust code does not compile, still convert it into the closest Verus-compatible form using minimal edits.

### Rule 5: Dependencies

If the target relies on other code, minimally adapt only the necessary dependencies.

If a required dependency is commented out, uncomment only the minimum necessary portion.

Do not expand edits beyond the smallest dependency closure needed to pass the verification command.

## Edit Priority Policy

When multiple repair strategies exist, prefer them in the following order:

1. local syntax-preserving edits
2. adding `#[verifier::external_body]`
3. rewriting unsupported expressions or type fragments
4. minimally adapting direct dependencies
5. broader edits only as a last resort

## Validation Loop

Use this workflow:

1. inspect code
2. make a short plan
3. apply minimal edits
4. run `verify`
5. inspect errors
6. apply the smallest necessary repair
7. repeat until success or a real blocker remains

## Failure Policy

If the verification command cannot succeed without violating the constraints:

1. stop at the smallest blocking point
2. do not fabricate behavior
3. do not introduce placeholders
4. report the blocking location precisely

## Output Expectations

Perform the edits in the workspace when allowed.

Return the modified code with every executable change documented according to
`exec-code-preservation.md`, including any necessary minimal dependency edits.

Do not add long explanations unless the user asks for them.

## Domain-Specific Guidance

### Atomic operations

For operations such as:

- `fetch_add`
- `fetch_sub`
- `compare_exchange`

prefer `atomic_with_ghost!` when required by Verus compatibility.

Example:

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
