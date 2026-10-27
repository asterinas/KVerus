# Spec: Convert a Rust entry file into minimally modified Verus-compatible code
Id: kverus-migrate
Goal: Convert one explicit Rust entry file into minimally modified Verus-compatible code with the smallest possible edit set — syntactically accepted by Verus, the user's verification command green, original structure and locality preserved, every executable change documented in place — iterating until the verification command succeeds or a real blocker remains.

Constraints:
- Global Verus guide rules carried verbatim from the kverus-common skill; they apply to every edit and preservation record this spec makes:
- Global rule 1 — Follow the active task skill's hard constraints for whether contracts, executable code, assumptions, or external bodies may be changed.
- Global rule 2 — When the active Verus version supports it, prefer `#[verus_spec(...)]` for newly added contracts and loop annotations on executable Rust. Keep `verus!` primarily for spec/proof declarations, external specifications, and syntax that attributes cannot express.
- Global rule 3 — Use `requires`, `ensures`, `assert`, loop invariants, and helper lemmas as the modular verification tools described by the guide.
- Global rule 4 — Use `expr@` as the guide's shorthand for `expr.view()` when working with abstract views.
- Global rule 5 — For loops, add invariants strong enough for entry, preservation, and exit reasoning; include surrounding facts explicitly when loop isolation requires them.
- Global rule 6 — Use `assert(...) by (bit_vector)` for bitwise facts, `assert(...) by (compute_only)` for fully computable spec facts, and `assert(...) by (nonlinear_arith)` for nonlinear arithmetic facts.
- Global rule 7 — Treat `#[verifier::external_body]` as a trusted verified/unverified boundary, not as an ordinary proof hint.
- Global rule 8 — Write contiguous bounds as chained comparisons when adjacent comparisons share the same intermediate expressions. Combine comparisons only when the chained form is logically equivalent; do not add a missing relation or strengthen a contract merely to form a chain.
- Global rule 9 — When two or more facts depend on the payload of the same `Option`, bind it once with `option matches Some(value) ==> { &&& ... }`. Keep a single implication as-is when binding the payload would not improve the expression.
- Global rule 10 — For every newly added Verus struct, determine its mode explicitly. Actively try `ghost struct` for constants, models, invariant markers, and other types used only by specifications or proofs. Use `tracked struct` for linear proof resources, and retain an ordinary struct whenever the type has runtime state or participates in executable behavior. Verify the selected mode instead of assuming a zero-sized marker must be executable.
- Global rule 11 — Use `use` declarations as much as possible for proof-only functions, lemmas, broadcast groups, and other proof symbols instead of repeatedly writing long fully qualified paths. Prefer explicit imports that remain unambiguous; retain a qualified path when it makes a rare reference clearer.
- Global rule 12 — In spec expressions over a `Seq` or a view (e.g. `bytes@`), prefer the range-slicing sugar `s[i..j]`, `s[..j]`, `s[i..]`, `s[i..=j]` over the equivalent `.subrange(...)`, `.take(...)`, `.skip(...)` calls.
- Global rule 13 — Use `returns expr` for a contract that fixes the exact return value, and `ensures` for other result or state properties; omit unused named return binders and unit return declarations such as `-> (r: ())`. Keep required casts in the `returns` expression and justify that the value fits.
- Global rule 14 — In ghost code, drop `as int` casts that Verus's auto-coercion makes redundant, keeping only the genuinely required ones. Let `E0308` identify missing casts rather than casting defensively.
- Hard constraints carried verbatim from the source skill:
- Hard constraint A (In-place edits only) — Edit the code at the original location whenever possible. Do not comment out an entire function, impl, or module and rewrite a replacement elsewhere if a local replacement is sufficient.
- Hard constraint B (Preserve original Rust code locally) — For every executable-code modification, follow the exact reason-first block-comment format in `../kverus-common/references/exec-code-preservation.md`. This requirement is not optional when the original code can be recovered from the input or Git history. For unsupported non-executable syntax, preserve the original locally when feasible (the source's example keeps an elided trait bound as a nearby comment: `impl<T /*: ?Sized*/, G: SpinGuardian> RwLock<T, G>`).
- Hard constraint C (No fake placeholders) — Do not introduce any new `unimplemented!()`, `panic!()`, or `loop {}`.
- Hard constraint D (Minimality) — Only change code that is necessary for the requested `target` and its minimal dependency closure. Do not refactor unrelated code.
- Hard constraint E (Preserve structure) — Preserve as much as possible: item order, function order, impl and block structure, source locality, nearby comments. Avoid large structural rewrites.
- Shared reference discipline: if migration requires Verus syntax, modes, ghost/tracked values, atomic ghost code, loop invariants, or tokenized state-machine rules, read the relevant reference under `../kverus-common/references/` before editing; before adding, removing, or rewriting any executable Rust, read and follow `../kverus-common/references/exec-code-preservation.md`. These files live in the deployed skills tree next to this skill's directory.
- Scope: the goal is NOT to fully verify semantic correctness — only to make the code pass at the syntax, compatibility, and front-end acceptance level, leaving a future proof-ready baseline.
- Invocation form (from the source skill): `$kverus-migrate target=path/to/file.rs verify="<verification command>"`. If either value is missing, ask for the missing value and stop — the engine form is the blocking ask gate below, which halts the run until the answer arrives.
- The verification command is user-supplied: it is whitespace-split at the engine layer (no shell metacharacters; L6 ruling); its first word must be registered in the project's command whitelist (已批准命令 below lists the two canonical forms, cargo and verus — a differently-prefixed command is a deployment prerequisite, not a spec defect).
- Verify run timeout is 900 seconds (temporary value: the source skill gives no bound; recorded in the translation ledger).
- The edit-then-verify loop runs at most 3 rounds (subtask retry=3; temporary value: the source skill says "repeat until success or a real blocker remains" without a cap; recorded in the translation ledger).
- This spec edits exactly one repository file (the entry file, in place) through the act-free edit steps; the exit carries a terse report. The source's delivery verbs ("Perform the edits in the workspace", "Return the modified code") are satisfied by that in-place workspace state; no file-generation verb exists in the source, so this spec has no [commit] step (L24 ruling family).
- Failure-policy discipline: when green is unreachable without violating the hard constraints, stop at the smallest blocking point, fabricate nothing, and report the blocking location precisely (carried by the on-fail handler and the blocked report).

Inputs:
- target % line  # workspace-relative path of the single Rust file to convert; empty means missing and triggers the ask gate
- verify % line  # whitespace-splittable verification command string (e.g. "cargo verus build --crate-name my_crate"); empty means missing and triggers the ask gate

Outputs:
- edited_target % line  # the file this spec edited in place
- verify_report % text  # stdout and stderr of the final verification run, or the unreadable-file notice
- verify_rc % int  # exit code of the final verification run (0 = green); sentinel -1 when the run stopped at the readability gate
- migration_outcome % enum(converted, blocked)  # converted: verification green after migration edits; blocked: no compliant path to green (including an unreadable entry file)
- final_report % markdown  # terse terminal note; on the blocked path it carries the precise blocking location

Config:
  requires_commands: [cargo, verus]
## 已批准命令
- cargo
- verus

## Steps
1. [act] Test which invocation inputs are present
  - ← target, verify
  + → has_target % bool  # true when the entry-file input was supplied
  + → has_verify % bool  # true when the verification-command input was supplied
  > Mechanical presence tests on the two required invocation inputs.
  > ```hop_python
  > has_target = len(target) > 0
  > has_verify = len(verify) > 0
  > ```
2. [branch] Complete the entry-file input
  - ← has_target
  + → effective_target % line  # the entry-file path the run will edit, supplied or asked
  2.1. [case(has_target)] Carry the given entry file
    - ← target
    + → effective_target
    2.1.1. [act] Carry the entry file through
      - ← target
      + → effective_target
      > ```hop_python
      > effective_target = target
      > ```
  2.2. [case(has_target == false)] Ask for the entry file and stop until answered
    2.2.1. [ask] Supply the entry-file path
      + → target_answer % line  # user-supplied workspace-relative entry-file path
      > The invocation is missing its required file path. Ask for the workspace-relative Rust entry file to convert. Execution resumes only with the answer — the source skill's ask-and-stop.
    2.2.2. [act] Record the asked entry file
      - ← target_answer
      + → effective_target
      > ```hop_python
      > effective_target = target_answer
      > ```
3. [branch] Complete the verification-command input
  - ← has_verify
  + → effective_verify % line  # the verification command string the run will execute, supplied or asked
  3.1. [case(has_verify)] Carry the given command
    - ← verify
    + → effective_verify
    3.1.1. [act] Carry the command through
      - ← verify
      + → effective_verify
      > ```hop_python
      > effective_verify = verify
      > ```
  3.2. [case(has_verify == false)] Ask for the command and stop until answered
    3.2.1. [ask] Supply the verification command
      + → verify_answer % line  # user-supplied verification command string
      > The invocation is missing its required verification command. Ask for the working verification command for this crate. Execution resumes only with the answer — the source skill's ask-and-stop.
    3.2.2. [act] Record the asked command
      - ← verify_answer
      + → effective_verify
      > ```hop_python
      > effective_verify = verify_answer
      > ```
4. [act] Read the entry file
  - ← effective_target
  + → target_content % text  # current content of the entry file, or empty when the file is missing
  + → target_readable % bool  # false when the file is missing or empty
  > The working style's first step: inspect the entry file before any edit.
  > ```hop_python
  > target_content = read(path: effective_target) if exists(path: effective_target) else ""
  > target_readable = len(target_content) > 0
  > ```
5. [branch] Gate on entry-file readability
  - ← target_readable
  + → verify_report % text  # stdout and stderr of the final verification run, or the unreadable-file notice
  + → verify_rc % int  # exit code of the final verification run (0 = green); sentinel -1 when the run stopped at the readability gate
  + → edited_target % line  # the file this spec edited in place
  + → migration_outcome % enum(converted, blocked)  # converted: green after migration edits; blocked: no compliant path to green
  + → final_report % markdown  # terse terminal note; on the blocked path it carries the precise blocking location
  5.1. [case(target_readable == false)] Report the unreadable entry file honestly
    - ← effective_target
    + → verify_report
    + → verify_rc
    + → edited_target
    + → migration_outcome
    + → final_report
    5.1.1. [act] Build the unreadable-file notice
      - ← effective_target
      + → verify_report
      + → verify_rc
      + → edited_target
      + → migration_outcome
      + → final_report
      > Deterministic notice: without a readable entry file no conversion can start; nothing is fabricated and no edit is attempted.
      > ```hop_python
      > verify_report = "Migration aborted: the entry file '" + effective_target + "' is missing or empty. Supply an existing workspace-relative Rust file and rerun."
      > verify_rc = -1
      > edited_target = effective_target
      > migration_outcome = "blocked"
      > final_report = verify_report
      > ```
  5.2. [case(target_readable)] Plan, migrate, and verify to green
    - ← target_content, effective_target
    + → verify_report
    + → verify_rc
    + → edited_target
    + → migration_outcome
    + → final_report
    5.2.1. [reason] Build the migration plan
      - ← target_content
      + → migration_plan % text  # which transformation rules apply where, the minimal dependency closure, and the edit priority order
      > Study the inspected entry file and its immediate dependencies; identify the minimal dependency closure that the verification command needs. Decide which transformation rules apply where (attribute-first executable conversion, external_body as the default, unsupported-fragment rewrites, dependency adaptation), ordered by the edit priority policy. Honor the hard constraints — in-place edits, local preservation records, no placeholders, minimality, structure preservation — and avoid broad rewrites up front.
      > [[kverus-migrate-knowledge#Objective and scope]]
      > [[kverus-migrate-knowledge#Editing discipline]]
      > [[kverus-migrate-knowledge#Transformation rules]]
      > [[kverus-migrate-knowledge#Edit priority policy]]
      > [[kverus-migrate-knowledge#Shared reference reading order]]
    5.2.2. [subtask retry=3] Apply minimal migration edits and verify to green
      + → verify_report % text  # stdout and stderr of the latest verification run
      + → verify_rc % int  # exit code of the latest verification run
      5.2.2.1. [act free] Apply minimal in-place migration edits
        - ← effective_target, migration_plan, target_content
        > Make minimal edits to the entry file named by effective_target, in place, following the plan: attribute-first executable conversion with native signatures preserved, `#[verifier::external_body]` as the default body strategy, rewrite only unsupported fragments at their original location, adapt only the minimal dependency closure. Before any executable add, remove, or rewrite, read and follow exec-code-preservation.md and record every executable change in the reason-first `Origin Rust:` block-comment format; preserve unsupported non-executable syntax locally when feasible; introduce no `unimplemented!()`, `panic!()`, or `loop {}`; prefer `atomic_with_ghost!` for fetch_add/fetch_sub/compare_exchange migration. The entry file is edited directly — this is the source skill's in-place maintenance flow. On retry rounds, re-read the current file state before editing (the injected correction block carries the latest verification failure).
        > [[kverus-migrate-knowledge#Shared reference reading order]]
        > [[kverus-migrate-knowledge#Transformation rules]]
        > [[kverus-migrate-knowledge#Edit priority policy]]
        > [[kverus-migrate-knowledge#Atomic operations]]
      5.2.2.2. [act] Run the verification command
        - ← effective_verify
        + → verify_report % text  # stdout and stderr of this verification run (reassigned each round)
        + → verify_rc % int  # exit code of this verification run (reassigned each round)
        > Runs the user's verification command against the edited file. The command string is whitespace-split at this layer (no shell metacharacters — see Constraints); cwd uses the workspace-root form. Verus diagnostics typically go to stderr, so the streams merge.
        > ```hop_python
        > argv = split(effective_verify, " ")
        > r = subprocess.run(argv, cwd: ".", timeout: 900)
        > verify_report = r.stdout + r.stderr
        > verify_rc = r.returncode
        > ```
      5.2.2.3. [check final] Verify the migrated code is green
        - ← verify_rc, verify_report
        + → ok % bool  # true when the verification command exits 0
        + → note % text  # failure note: verification excerpt when the command failed
        > Mechanical verdict on the latest verification run; a failed round triggers the retry's correction context for the next minimal repair round.
        > ```hop_python
        > ok = verify_rc == 0
        > note = "" if ok else "verification failed (exit code " + str(verify_rc) + "): " + verify_report
        > ```
    5.2.3. [act] Record the converted outcome
      - ← effective_target
      + → edited_target
      + → migration_outcome
      > Deterministic passthrough of the migrated file path and the green outcome.
      > ```hop_python
      > edited_target = effective_target
      > migration_outcome = "converted"
      > ```
    5.2.4. [reason] Compose the terse conversion report
      - ← effective_target, verify_report
      + → final_report % markdown  # terse terminal note: the edited file and the green verification result, no long explanation
      > The source skill asks for no long explanation. Name the edited file, state that the verification command exited 0, and point to the in-file preservation records; keep it terse.
    5.2.5. [on fail] Report the blocking point precisely
      5.2.5.1. [act] Record the blocked outcome
        - ← effective_target
        + → edited_target
        + → migration_outcome
        > Deterministic record of the blocked terminal state; the file the run worked on is still named honestly.
        > ```hop_python
        > edited_target = effective_target
        > migration_outcome = "blocked"
        > ```
      5.2.5.2. [reason] Compose the blocked report
        - ← verify_report, verify_rc, effective_target, migration_plan
        + → final_report % markdown  # precise blocking location, the constraint that blocks each candidate repair, and the latest diagnostics excerpt
        > Failure policy: stop at the smallest blocking point, fabricate nothing, introduce no placeholders, and report the blocking location precisely. Compose from the last round's verification output and the migration plan: the exact file, region, and diagnostic that block the conversion, which hard constraint blocks each candidate repair, and the latest diagnostics excerpt. Keep it terse.
        > [[kverus-migrate-knowledge#Failure policy]]
6. [exit] Deliver the migration outcome
  + → edited_target, verify_report, verify_rc, migration_outcome, final_report
