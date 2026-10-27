# Spec: Review changed Verus code for exec-semantics, =~=, comment-deletion, and verification regressions
Id: kverus-review
Goal: Review the workspace's changed Rust code — uncommitted changes or a commit..HEAD range — for exec-semantics regressions, new `=~=` introductions, unjustified comment deletions, and verification problems, and return a structured four-category Markdown report with prominent highlights for the serious findings.

Constraints:
- Global Verus guide rules carried verbatim from the kverus-common skill; they are the background against which exec-semantics and proof-quality regressions are judged:
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
- This spec is strictly read-only over the workspace: it runs git, reads the diffs, runs the verification command, and emits a text report through the exit; no step may modify any repository file.
- Delivery is the exit-carried report: the source's delivery verb is "produce a structured report" with no file-generation verb, so this spec has no [commit] step (L24 ruling family).
- Invocation forms (from the source skill): `$kverus-review verify="<verification command>"` or `$kverus-review commit=abc1234 verify="<verification command>"`. The verification command is required — when missing, ask for it and stop, which the engine expresses as the blocking ask gate below. The commit hash is optional; when omitted, all uncommitted changes (unstaged plus staged) are reviewed. The source's `commit=<hash>` argument is carried in this spec as the input `revision`, because `commit` is a reserved step-type keyword in HopSpec; its git meaning (the range `<revision>..HEAD`) is unchanged.
- The verification command is user-supplied: it is whitespace-split at the engine layer (no shell metacharacters; L6 ruling); its first word must be registered in the project's command whitelist (已批准命令 below lists the canonical forms git, cargo, verus — a differently-prefixed command is a deployment prerequisite, not a spec defect).
- Collection and verification run timeouts are 60 seconds for git and 900 seconds for the verification command (temporary values: the source skill gives no bounds; recorded in the translation ledger).
- Conservative classification: when in doubt, classify as `uncertain` rather than `likely-equivalent`; when a report category has no findings, the report records the source's explicit "No ... found" line.
- The report must follow the source template and its report rules: a failed verification is always stated as failed with the error summary; every problematic warning is listed with count and locations; semantic-change exec modifications, missing/malformed preservation comments, and unjustified/uncertain comment deletions are highlighted prominently.
- Scope: four review categories (exec code modifications, `=~=` introductions, deleted comments, verification status and warnings); the skill is not a full code review, not a migration tool, not a proof repair tool, not a spec quality scorer, and not a migration audit — it reviews incremental changes for regressions, not the full Rust-to-Verus migration. Shared reference files live in the sibling kverus-common tree, deployed next to this skill's directory.

Inputs:
- verify % line  # whitespace-splittable verification command string; empty means missing and triggers the ask gate
- revision % line  # optional git commit hash (the source skill's `commit=` argument, renamed because commit is a HopSpec reserved word); empty means review all uncommitted changes (unstaged + staged)

Outputs:
- review_report % markdown  # the four-category structured report, or the collection-gate failure/empty notice
- verify_rc % int  # exit code of the verification run; sentinel -1 when the run stopped at the collection gate (git failure or no changed Rust files)
- review_outcome % enum(completed, no_rs_changes, git_failed)  # completed: the full four-category review ran; no_rs_changes / git_failed: honest early stops

Config:
  requires_commands: [git, cargo, verus]
## 已批准命令
- git
- cargo
- verus

## Steps
1. [act] Test which invocation inputs are present
  - ← verify, revision
  + → has_verify % bool  # true when the verification-command input was supplied
  + → has_revision % bool  # true when the revision-hash input was supplied
  > Mechanical presence tests on the two invocation inputs.
  > ```hop_python
  > has_verify = len(verify) > 0
  > has_revision = len(revision) > 0
  > ```
2. [branch] Complete the verification-command input
  - ← has_verify
  + → effective_verify % line  # the verification command string the run will execute, supplied or asked
  2.1. [case(has_verify)] Carry the given command
    - ← verify
    + → effective_verify
    2.1.1. [act] Carry the command through
      - ← verify
      + → effective_verify
      > ```hop_python
      > effective_verify = verify
      > ```
  2.2. [case(has_verify == false)] Ask for the command and stop until answered
    2.2.1. [ask] Supply the verification command
      + → verify_answer % line  # user-supplied verification command string
      > The invocation is missing its required verification command. Ask for the working verification command for this repository. Execution resumes only with the answer — the source skill's ask-and-stop.
    2.2.2. [act] Record the asked command
      - ← verify_answer
      + → effective_verify
      > ```hop_python
      > effective_verify = verify_answer
      > ```
3. [branch] Resolve the diff-collection command form
  - ← has_revision
  + → files_listing % text  # raw git name-only output of changed Rust files (both streams merged for the uncommitted scope; the reviewing executor deduplicates by path)
  + → listing_rc % int  # worst git exit code across the collection commands
  + → listing_stderr % text  # merged stderr of the collection commands, for the honest failure notice
  3.1. [case(has_revision)] List files changed in the committed range
    - ← revision
    + → files_listing
    + → listing_rc
    + → listing_stderr
    3.1.1. [act] List committed-range Rust files
      - ← revision
      + → files_listing
      + → listing_rc
      + → listing_stderr
      > Deterministic collection for the committed scope: one git invocation, no shell (the pathspec glob is passed verbatim to git).
      > ```hop_python
      > argv = ["git", "diff", revision + "..HEAD", "--name-only", "--", "*.rs"]
      > r = subprocess.run(argv, cwd: ".", timeout: 60)
      > files_listing = r.stdout
      > listing_rc = r.returncode
      > listing_stderr = r.stderr
      > ```
  3.2. [case(has_revision == false)] List uncommitted Rust files
    + → files_listing
    + → listing_rc
    + → listing_stderr
    3.2.1. [act] List unstaged and staged Rust files
      + → files_listing
      + → listing_rc
      + → listing_stderr
      > Deterministic collection for the uncommitted scope: the unstaged and staged listings run unconditionally and merge; an empty pair of outputs concatenates to an empty string, which the next step classifies honestly.
      > ```hop_python
      > argv1 = ["git", "diff", "HEAD", "--name-only", "--", "*.rs"]
      > argv2 = ["git", "diff", "--cached", "--name-only", "--", "*.rs"]
      > r1 = subprocess.run(argv1, cwd: ".", timeout: 60)
      > r2 = subprocess.run(argv2, cwd: ".", timeout: 60)
      > files_listing = r1.stdout + r2.stdout
      > listing_rc = r1.returncode if r1.returncode == 0 else r2.returncode
      > listing_stderr = r1.stderr + r2.stderr
      > ```
4. [act] Classify the collection outcome
  - ← files_listing, listing_rc
  + → collection_state % enum(git_failed, no_rs_changes, ready)  # git_failed: a collection command failed; no_rs_changes: no changed Rust files; ready: listing present
  > Mechanical classification of the collection result — no judgment involved. Failures and empty listings are first-class states so the report never reviews a change set that could not be gathered.
  > ```hop_python
  > collection_state = "git_failed" if listing_rc != 0 else ("no_rs_changes" if len(files_listing) == 0 else "ready")
  > ```
5. [branch] Route by collection outcome
  - ← collection_state
  + → review_report % markdown  # the four-category report, or the collection-gate notice
  + → verify_rc % int  # verification exit code; sentinel -1 when the run stopped at the collection gate
  + → review_outcome % enum(completed, no_rs_changes, git_failed)  # completed: full review ran; otherwise the honest early stop
  5.1. [case(collection_state == "git_failed")] Report the collection failure
    - ← listing_rc, listing_stderr
    + → review_report
    + → verify_rc
    + → review_outcome
    5.1.1. [act] Build the collection-failure notice
      - ← listing_rc, listing_stderr
      + → review_report
      + → verify_rc
      + → review_outcome
      > Deterministic notice: the change set could not be gathered, so no review runs and no verification is attempted.
      > ```hop_python
      > review_report = "Review aborted: git change collection failed with exit code " + str(listing_rc) + ". Stderr: " + listing_stderr + " This skill requires a working git workspace; fix the repository state and rerun."
      > verify_rc = -1
      > review_outcome = "git_failed"
      > ```
  5.2. [case(collection_state == "no_rs_changes")] Report that no Rust files changed
    + → review_report
    + → verify_rc
    + → review_outcome
    5.2.1. [act] Build the empty-listing notice
      + → review_report
      + → verify_rc
      + → review_outcome
      > The source skill's rule: when no Rust files are changed, report that and stop. No verification is run, so the exit code stays at the not-run sentinel.
      > ```hop_python
      > review_report = "No Rust files changed: git reports no .rs file changes in the reviewed scope. kverus-review reviews changed Rust code for exec-semantics, =~=, comment-deletion, and verification regressions; make changes first, then rerun."
      > verify_rc = -1
      > review_outcome = "no_rs_changes"
      > ```
  5.3. [case(collection_state == "ready")] Run the four-category review
    - ← files_listing, effective_verify, has_revision, revision
    + → review_report
    + → verify_rc
    + → review_outcome
    5.3.1. [subtask] Conduct the four-category review and assemble the report
      + → exec_changes % yaml  # per-file exec-code modifications: added/removed line ranges, semantic classification, preservation-comment status, reasons
      + → tilde_changes % yaml  # per-introduction =~= records: file, line, enclosing context, replaceability, reason
      + → deleted_comments % yaml  # per-deleted-comment records: file, line range, excerpt, classification, reason
      + → verify_report % text  # stdout and stderr of the verification run
      + → verify_rc % int  # exit code of the verification run
      + → verification_status % enum(passed, failed)  # mechanical pass/fail of the verification run
      + → error_summary % text  # extracted error summary when verification failed; empty when it passed
      + → warnings_record % yaml  # per-pattern warning counts and matching line locations
      + → review_report % markdown  # the assembled four-category report
      5.3.1.1. [act free] Check exec code modifications
        - ← files_listing
        + → exec_changes % yaml  # one record per changed Rust file: modified exec lines with ranges, semantic-change / likely-equivalent / uncertain classification, preservation-comment compliant / missing / malformed status, and the reason for each verdict
        > For each changed Rust file in the listing, obtain its diff content using the scope-appropriate git forms in the knowledge doc, then classify every added and removed line: exec code versus the excluded spec/proof/ghost/attribute/comment classes, reading surrounding code or the full file whenever a hunk's context is ambiguous. Classify each exec modification as semantic-change, likely-equivalent, or uncertain per the heuristics, conservatively preferring uncertain. Separately classify each exec modification's preservation comment as compliant, missing, or malformed — required even for likely-equivalent changes — without letting the comment affect the semantic verdict. When no exec code is modified, record "No exec code modifications found."
        > [[kverus-review-knowledge#Diff collection forms]]
        > [[kverus-review-knowledge#Exec code scope]]
        > [[kverus-review-knowledge#Exec modification classification]]
        > [[kverus-review-knowledge#Preservation comment compliance]]
        > [[kverus-review-knowledge#Shared reference reading order]]
      5.3.1.2. [act free] Check =~= introductions
        - ← files_listing
        + → tilde_changes % yaml  # one record per newly introduced =~=: file, line, enclosing syntactic context, replaceable / required verdict, reason
        > Search the diff's added lines for `=~=`. For each introduction, determine the enclosing syntactic form — reading surrounding code when the context is ambiguous — and apply the auto-promotion table: replaceable inside assert, ensures, invariant, and spec-fn return expressions; required in if conditions, requires, recommends, and proof variable assignments; context-dependent inside assert-by bodies, defaulting to replaceable unless the block relies on =~= for trigger control. Record file, line, context, verdict, and reason per introduction. When none are introduced, record "No =~= introductions found."
        > [[kverus-review-knowledge#=~= introduction review]]
        > [[kverus-review-knowledge#Shared reference reading order]]
      5.3.1.3. [act free] Check deleted comments
        - ← files_listing
        + → deleted_comments % yaml  # one record per deleted comment: file, line range, excerpt, justified / unjustified / uncertain classification, reason
        > Search the diff's removed lines for comments. Classify each deletion as justified, unjustified, or uncertain per the heuristics, with special care for migration provenance: deleted comments carrying original Rust code or `Origin Rust:` records are unjustified unless the corresponding executable modification was reverted or removed, and re-executable rewrites require an updated compliant preservation comment instead of silent deletion. Record file, line range, excerpt, classification, and reason per deletion. When no comments were deleted, record "No comment deletions found."
        > [[kverus-review-knowledge#Deleted comment classification]]
      5.3.1.4. [act] Run the verification command
        - ← effective_verify
        + → verify_report % text  # stdout and stderr of the verification run (streams merged)
        + → verify_rc % int  # exit code of the verification run
        + → verification_status % enum(passed, failed)  # passed when the command exits 0
        > Runs the user's verification command once against the workspace. The command string is whitespace-split at this layer (no shell metacharacters — see Constraints); cwd uses the workspace-root form. Verus diagnostics typically go to stderr, so the streams merge.
        > ```hop_python
        > argv = split(effective_verify, " ")
        > r = subprocess.run(argv, cwd: ".", timeout: 900)
        > verify_report = r.stdout + r.stderr
        > verify_rc = r.returncode
        > verification_status = "passed" if r.returncode == 0 else "failed"
        > ```
      5.3.1.5. [act free] Analyze the verification output
        - ← verify_report, verify_rc
        + → error_summary % text  # extracted error summary when verification failed; empty when it passed
        + → warnings_record % yaml  # per warning pattern: occurrence count and the matching lines with line numbers
        > When verification failed, extract and summarize the error messages — the `error:` lines and the `error: aborting due to` summary. Regardless of pass or fail, scan the captured output for the three problematic-warning patterns (auto-chosen triggers note, deprecated Set::finite, deprecated Set::new_assuming_finite), count occurrences of each, and list the matching lines with their line numbers.
        > [[kverus-review-knowledge#Verification status and error summary]]
        > [[kverus-review-knowledge#Problematic warnings]]
      5.3.1.6. [reason] Compose the structured review report
        - ← exec_changes, tilde_changes, deleted_comments, verification_status, verify_rc, error_summary, warnings_record, files_listing, has_revision, revision
        + → review_report % markdown  # the source template's Markdown report, with prominent highlights per the report rules
        > Assemble the source template: summary block (commit range — the given revision range or the uncommitted wording — files reviewed count, verification status), then the four category sections with their tables, the "No ... found" fallback lines where a category is empty, the severity-grouped exec findings, and the error and warning details. Apply the report rules: failed verification always appears as failed with the error summary; every problematic warning appears with count and locations; semantic-change modifications, missing/malformed preservation comments, and unjustified/uncertain comment deletions are highlighted prominently.
        > [[kverus-review-knowledge#Report template]]
        > [[kverus-review-knowledge#Report rules]]
      5.3.1.7. [check final] Gate the report skeleton
        - ← review_report
        + → ok % bool  # true when the report carries the summary block plus all four numbered category sections
        + → note % text  # gap note when the skeleton is incomplete
        > Mechanical skeleton gate: counts the top-level section markers (each `### ` subsection also contains a `## ` marker, so subsections are subtracted out). Cognitive duties — prominence of highlights and conservative classification — belong to the compose step above.
        > ```hop_python
        > sections = split(review_report, "## ")
        > subsections = split(review_report, "### ")
        > top_level = len(sections) - len(subsections)
        > ok = top_level >= 5
        > note = "" if ok else "report skeleton incomplete: expected the summary block plus the four numbered category sections"
        > ```
    5.3.2. [act] Record the completed outcome
      + → review_outcome
      > Deterministic record of the completed terminal state for the reviewed change set.
      > ```hop_python
      > review_outcome = "completed"
      > ```
6. [exit] Deliver the review
  + → review_report, verify_rc, review_outcome
