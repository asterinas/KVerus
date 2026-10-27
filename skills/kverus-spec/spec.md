# Spec: Add Verus specification scaffolding to a target file while preserving executable behavior
Id: kverus-spec
Goal: Add minimal specification scaffolding (requires, ensures, invariants, decreases, recommends, spec helpers) to a target Rust file, iterating with the user's verification command until the file becomes a stronger proof-ready baseline with behavior preserved.

Constraints:
- Global Verus guide rules carried verbatim from the kverus-common skill; they apply to every annotation and helper this spec adds:
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
- Hard constraint 1 — In-place edits only: edit the target file in place.
- Hard constraint 2 — Preserve behavior: do not rewrite executable logic unless a tiny local change is required to express a valid specification.
- Hard constraint 3 — Spec-only bias: prefer adding or refining specifications over adding proof steps.
- Hard constraint 4 — Avoid introducing `assert(... ) by (...)`, `calc!`, new proof lemmas, or proof bodies unless the file would otherwise become syntactically invalid.
- Hard constraint 5 — No unsound shortcuts: do not add `assume`, `admit`, or `#[verifier::external_body]`.
- Hard constraint 6 — Preserve source structure as much as possible: item order, function order, impl/block structure, comments, and source locality.
- Hard constraint 7 — If executable logic must change under hard constraint 2's narrow exception, document the change using the exact reason-first `Origin Rust:` block-comment format in exec-code-preservation.md.
- Shared reference discipline: read `../kverus-common/references/verus-syntax-quickref.md` before annotating executable functions or loops; read other relevant references from the sibling kverus-common tree on demand (modes, loop invariants, decreases, recommends, ghost/tracked values, spec/proof helper patterns); consult `../kverus-common/references/exec-code-preservation.md` before the narrow executable-change exception. These files live in the deployed skills tree next to this skill's directory.
- The goal is NOT to fully prove the code: improve the specification layer while preserving executable behavior, preparing the file for a later proof-generation stage.
- The verification command is user-supplied: it is whitespace-split at the engine layer (no shell metacharacters; L6 ruling); its first word must be registered in the project's command whitelist (已批准命令 below lists the two canonical forms, cargo and verus — a differently-prefixed command is a deployment prerequisite, not a spec defect).
- Verify run timeout is 900 seconds (temporary value: the source skill gives no bound; recorded in the translation ledger).
- Missing-target and missing-verify handling: the source skill says "ask for the missing value and stop"; the engine form of that is a blocking ask gate — execution cannot proceed to edits without the value, which is the same stop semantics.
- This spec edits exactly one repository file (the target, in place) through the act-free edit steps; it produces no other deliverable. If the target file is missing or unreadable, the run stops with an honest failure report (score-sentinel style, verify_rc -1) rather than fabricating success.

Inputs:
- target % line  # workspace-relative path to the entry Rust file to scaffold; empty means missing and triggers the ask gate
- verify % line  # whitespace-verification command string (e.g. "cargo verus build --crate-name my_crate"); empty means missing and triggers the ask gate
- knowledge % text  # optional related knowledge supplied by the caller; empty means continue without it

Outputs:
- verify_report % text  # stdout and stderr of the final verification run, or the failure notice when the target file was unreadable
- verify_rc % int  # exit code of the final verification run (0 = green proof-ready baseline); sentinel -1 when the run stopped at the readiness gate
- edited_target % line  # the file this spec edited in place (the effective target)

Config:
  requires_commands: [cargo, verus]
## 已批准命令
- cargo
- verus

## Steps
1. [act] Test which invocation inputs are present
  - ← target, verify
  + → has_target % bool  # true when target was supplied
  + → has_verify % bool  # true when verify was supplied
  > Mechanical presence tests on the two required inputs; the optional third input needs no gate.
  > ```hop_python
  > has_target = len(target) > 0
  > has_verify = len(verify) > 0
  > ```
2. [branch] Complete the target input
  - ← has_target
  + → effective_target % line  # the target path the run will edit, supplied or asked
  2.1. [case(has_target)] Carry the given target
    - ← target
    + → effective_target
    2.1.1. [act] Carry the target through
      - ← target
      + → effective_target
      > ```hop_python
      > effective_target = target
      > ```
  2.2. [case(has_target == false)] Ask for the target and stop until answered
    2.2.1. [ask] Supply the target file path
      + → target_answer % line  # user-supplied workspace-relative target path
      > The invocation is missing its required file path. Ask for the workspace-relative entry Rust file to scaffold. Execution resumes only with the answer — the source skill's ask-and-stop.
    2.2.2. [act] Record the asked target
      - ← target_answer
      + → effective_target
      > ```hop_python
      > effective_target = target_answer
      > ```
3. [branch] Complete the verification command input
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
4. [act] Inspect the target file
  - ← effective_target
  + → target_content % text  # current content of the entry file, or empty when the file is missing
  + → target_readable % bool  # false when the file is missing or empty
  > The working style's first step: inspect the entry file before any annotation.
  > ```hop_python
  > target_content = read(path: effective_target) if exists(path: effective_target) else ""
  > target_readable = len(target_content) > 0
  > ```
5. [branch] Gate on target readability
  - ← target_readable
  + → verify_report % text  # final verification stdout, or the unreadable-target failure notice
  + → verify_rc % int  # final verification exit code, or the -1 readiness sentinel
  + → edited_target % line  # the file this run edited in place
  5.1. [case(target_readable == false)] Report the unreadable target honestly
    - ← effective_target
    + → verify_report
    + → verify_rc
    + → edited_target
    5.1.1. [act] Build the unreadable-target notice
      - ← effective_target
      + → verify_report
      + → verify_rc
      + → edited_target
      > Deterministic notice: without a readable entry file no scaffolding can be applied; no grade or report is fabricated.
      > ```hop_python
      > verify_report = "Scaffolding aborted: the target file '" + effective_target + "' is missing or empty. Supply an existing workspace-relative Rust file and rerun."
      > verify_rc = -1
      > edited_target = effective_target
      > ```
  5.2. [case(target_readable)] Plan, scaffold, and verify to a green baseline
    - ← target_content, knowledge, effective_target
    + → verify_report
    + → verify_rc
    + → edited_target
    5.2.1. [reason] Build the annotation plan
      - ← target_content, knowledge
      + → annotation_plan % text  # which of the seven focus items apply where, and which shared references to consult before each edit
      > Study the inspected file and decide where specification structure improves proof readiness: which functions lack requires/ensures, which loops lack invariants, where decreases is expressible, whether recommends or spec/ghost helpers fit. Honor the hard constraints — spec-only bias, no proof machinery unless the file would become syntactically invalid, no unsound shortcuts, structure preservation. Use the optional knowledge input when relevant. Before annotating, the shared reference reading order applies (quickref first, on-demand references next, exec-code-preservation before any executable-Rust exception).
      > [[kverus-spec-knowledge#Shared reference reading order]]
      > [[kverus-spec-knowledge#Annotation focus]]
      > [[kverus-spec-knowledge#Clarification carried from the source]]
    5.2.2. [subtask retry=3] Apply minimal scaffolding edits and verify to green
      + → verify_report % text  # stdout of the latest verification run
      + → verify_rc % int  # exit code of the latest verification run
      5.2.2.1. [act free] Apply minimal in-place spec edits
        - ← effective_target, annotation_plan, target_content, knowledge
        > Make minimal edits to the entry file named by effective_target, in place, following the plan: add or refine requires/ensures, loop invariants, decreases, recommends, spec fn and ghost/spec helper declarations per the annotation focus. Prefer #[verus_spec(...)] for executable-function contracts and supported loop annotations; verus! for helpers and attribute-inexpressible constructs. Do not finish proofs; do not introduce by-assertions, calc!, new lemmas, or proof bodies unless the file would otherwise be syntactically invalid; never add assume, admit, or #[verifier::external_body]; preserve item order, function order, impl structure, comments, and source locality. If a tiny executable change is unavoidable to express a valid specification, read and follow the exec-code-preservation reference first and record it in the Origin Rust: block-comment format. The entry file is edited directly — this is the source skill's in-place maintenance flow. Re-read the current file state before editing on retry rounds (the injected correction block carries the latest verification failure).
        > [[kverus-spec-knowledge#Shared reference reading order]]
        > [[kverus-spec-knowledge#Annotation focus]]
        > [[kverus-spec-knowledge#Origin Rust record format]]
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
      5.2.2.3. [check final] Verify the edited baseline is green
        - ← verify_rc, verify_report
        + → ok % bool  # true when the verification command exits 0
        + → note % text  # failure note: verification excerpt when the command failed
        > Mechanical verdict on the latest verification run; a failed round triggers the retry's correction context for the next edit round.
        > ```hop_python
        > ok = verify_rc == 0
        > note = "" if ok else "verification failed (exit code " + str(verify_rc) + "): " + verify_report
        > ```
    5.2.3. [act] Record the edited file
      - ← effective_target
      + → edited_target
      > Deterministic passthrough of the scaffolded file path.
      > ```hop_python
      > edited_target = effective_target
      > ```
6. [exit] Deliver the scaffolding outcome
  + → verify_report, verify_rc, edited_target
