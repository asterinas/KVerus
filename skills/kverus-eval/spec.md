# Spec: Evaluate unstaged spec modifications for semantic quality and intent preservation
Id: kverus-eval
Goal: Review the current unstaged spec-related changes against the original contract intent, assess strengthening, intent preservation, and redundancy, and return a score out of 10 with a concise, diff-referenced rationale.

Constraints:
- Global Verus guide rules carried verbatim from the kverus-common skill; they are the background against which "weakens safety/correctness guarantees" and "changes contract intent" are judged:
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
- This spec is strictly read-only over the workspace: it runs `git diff`, reads files, and emits a text report; no step may modify any repository file.
- Scoring is judgment exercised by the scoring reason step; it must stay grounded in the injected deduction rubric and in the concrete diff hunks quoted into the evaluation inputs, never in recalled material.
- target is a workspace-relative file path; when empty, the whole unstaged diff is the evaluation input. The caller's intent statement is an optional input; when empty, intent is inferred from the code itself.
- The workspace must be a git repository with unstaged changes (source frontmatter compatibility note); gather failures and empty diffs are reported honestly through the readiness classification with score sentinel -1, never as a numeric grade.

Inputs:
- target % line  # workspace-relative entry file to prioritize (e.g. src/engine/mod.rs); empty means the whole unstaged diff
- intent_context % text  # caller-stated original spec intent; empty means infer intent from nearby comments, names, and unchanged surrounding code

Outputs:
- eval_report % markdown  # the five-item review report (strength, intent preservation, redundancy, score, rationale) or the readiness-gate failure notice
- score_num % int  # final score in [0, 10]; sentinel -1 when the evaluation could not run (git failure or no unstaged changes)

Config:
  requires_commands: [git]
## 已批准命令
- git

## Steps
1. [act] Gather the unstaged diff
  - ← target
  + → git_diff % text  # full `git diff` output for the whole workspace or the target file; empty string when nothing is unstaged
  + → git_rc % int  # git exit code for the gather
  > Reads the working tree's unstaged changes only (staged and committed content excluded). cwd uses the workspace-root form so git finds the repository from any engine working directory.
  > ```hop_python
  > argv = ["git", "diff"]
  > argv = argv + ["--", target] if target else argv
  > r = subprocess.run(argv, cwd: ".", timeout: 300)
  > git_diff = r.stdout
  > git_rc = r.returncode
  > ```
2. [act] Classify workspace readiness
  - ← git_rc, git_diff
  + → readiness % enum(git_failed, no_changes, ready)  # git_failed: gather command failed; no_changes: empty diff; ready: diff present
  > Mechanical classification of the gather result — no judgment involved. Failures and empty diffs are first-class states here so the report never presents a grade for an evaluation that could not run.
  > ```hop_python
  > readiness = "git_failed" if git_rc != 0 else ("no_changes" if len(git_diff) == 0 else "ready")
  > ```
3. [branch] Route by readiness
  - ← readiness
  + → eval_report % markdown  # the five-item report, or the readiness-gate notice
  + → score_num % int  # graded score, or the -1 not-scored sentinel
  3.1. [case(readiness == "git_failed")] Report the gather failure
    - ← git_rc
    + → eval_report
    + → score_num
    3.1.1. [act] Build the gather-failure notice
      - ← git_rc
      + → eval_report
      + → score_num
      > Deterministic notice: the source skill's compatibility prerequisite (git workspace with unstaged changes) is unmet.
      > ```hop_python
      > eval_report = "Evaluation aborted: `git diff` failed with exit code " + str(git_rc) + ". This skill requires a git workspace with unstaged changes; fix the workspace state and rerun."
      > score_num = -1
      > ```
  3.2. [case(readiness == "no_changes")] Report that there is nothing to evaluate
    + → eval_report
    + → score_num
    3.2.1. [act] Build the empty-diff notice
      + → eval_report
      + → score_num
      > ```hop_python
      > eval_report = "Nothing to evaluate: there are no unstaged changes in the workspace. kverus-eval reviews current unstaged spec modifications; make spec edits first, then rerun."
      > score_num = -1
      > ```
  3.3. [case(readiness == "ready")] Run the full evaluation
    - ← git_diff, target, intent_context
    + → eval_report
    + → score_num
    3.3.1. [act] Read the target file when one was given
      - ← target
      + → target_content % text  # current content of the target file, or empty when no target was given or the file is gone
      > Grounding read for intent recovery: unchanged code and nearby lines come from here plus the diff's own surrounding lines.
      > ```hop_python
      > target_content = read(path: target) if target and exists(path: target) else ""
      > ```
    3.3.2. [reason] Isolate the spec-related changes
      - ← git_diff, target_content
      + → spec_changes % text  # the hunks touching spec machinery, quoted with their diff hunk headers
      > Keep only hunks that touch spec machinery — requires, ensures, invariants, decreases, recommends clauses, and spec/ghost declarations; drop implementation-only hunks from the evaluation input. Quote the kept hunks with their hunk headers so later steps and the final rationale can reference them concretely.
      > [[kverus-eval-knowledge#Spec-related change classes]]
    3.3.3. [reason] Recover the original spec intent
      - ← spec_changes, target_content, intent_context
      + → intent_note % text  # the pre-modification intent each modified clause served, with its recovery basis
      > For every modified clause, recover the intent it served before the change: from the intent_context argument when provided, otherwise from unchanged surrounding code, nearby comments, and names; the diff's removed lines and surrounding lines carry the before-state. Record the recovery basis next to each intent statement.
    3.3.4. [reason] Evaluate the three aspects
      - ← spec_changes, intent_note
      + → strength % enum(stronger, weaker, mixed)  # whether the modification strengthens or weakens the spec
      + → intent_preservation % enum(preserved, changed)  # whether the modification changes the original purpose
      + → redundancy % enum(none, minor, significant)  # whether unnecessary spec content was added
      > Classify each aspect against the recovered intent and the isolated hunks: strengthening or weakening, purpose change, and added redundancy. Each classification must cite the hunks it rests on.
      > [[kverus-eval-knowledge#Evaluation scope]]
    3.3.5. [reason] Score the modification per the rubric
      - ← strength, intent_preservation, redundancy
      + → score_num % int  # final score clamped to [0, 10]
      + → score_justification % text  # deduction arithmetic with concrete diff references
      > Start from 10 and subtract per the rubric: safety/correctness weakening without justification -2 to 5 (fueled by the strength aspect); changed original purpose or contract intent -2 to 5 (fueled by the intent-preservation aspect); redundant or unused clauses adding maintenance burden -1 to 3 (fueled by the redundancy aspect); neutral-but-clearer changes take no penalty; strengthening while preserving intent and avoiding redundancy stays at 9 to 10. Clamp the result to [0, 10]. The justification shows the arithmetic and cites the concrete hunks.
      > [[kverus-eval-knowledge#Scoring policy]]
    3.3.6. [act] Assemble the review report
      - ← strength, intent_preservation, redundancy, score_num, score_justification
      + → eval_report
      > Deterministic assembly of the source skill's five-item output format from the classified values.
      > ```hop_python
      > eval_report = "1. Strength assessment: " + strength + "\n2. Intent preservation assessment: " + intent_preservation + "\n3. Redundancy assessment: " + redundancy + "\n4. Score: " + str(score_num) + "/10\n5. Rationale: " + score_justification
      > ```
4. [exit] Deliver the evaluation
  + → eval_report, score_num
