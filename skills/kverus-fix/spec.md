# Spec: Fix Verus verification failures with minimal proof-preserving edits
Id: kverus-fix
Goal: Resolve a Verus verification failure through minimal proof-preserving edits under the hard constraints, reusing one resolved verification command, until verification passes or a blocker is documented under the out path.

Constraints:
- Global Verus guide rules carried verbatim from the kverus-common skill; they govern every edit this spec makes:
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
- Hard constraint 1 — Do not modify existing `requires`.
- Hard constraint 2 — Do not modify existing `ensures`.
- Hard constraint 3 — Do not add new `assume(...)` statements.
- Hard constraint 4 — Add or change `assume_specification` only through the missing-standard-library branch.
- Hard constraint 5 — Do not add new `admit`.
- Hard constraint 6 — Do not add `#[verifier::external_body]` to skip proof obligations.
- Hard constraint 7 — Keep edits minimal and localized to the smallest necessary dependency closure.
- Hard constraint 8 — Do not edit unrelated files.
- Hard constraint 9 — Do not modify the exec code.
- Automatic discovery runs when the mode input is "auto" or either the target input or the verification-command input is missing; otherwise explicit mode applies. Any supplied value is authoritative and only the missing value is discovered. Missing inputs are asked for only after the relevant discovery procedure has been exhausted.
- The target input names an entry file for diagnosis, not the only file that may be edited; edits stay within the smallest necessary dependency closure. Broad refactors up front are avoided.
- A supplied initial error message is a first-pass hint for the first inspection only; fresh output from the verification command is always trusted when the two differ.
- The out path input is workspace-relative; when it is empty the default "kverus-fix-blocker-summary.md" is adopted (translator-provisional name — the source skill says only a reasonable workspace-local default; recorded in the translation ledger) and the defaulting is reported in the resolution report.
- This spec edits workspace files in place through its act-free steps; the only file the commit step writes is the blocker summary, and only on the blocked outcome. No other deliverable is produced.
- Candidate verification commands during discovery are executed by the executing agent in the act-free discovery step, because their first words are unknown at spec-writing time. The deterministic subprocess channel is reserved for the resolved command: it is whitespace-split into argv at the engine layer (no shell metacharacters) and its first word must be registered — the approved-commands section lists the two canonical forms cargo and verus, and a differently-prefixed project wrapper must be added to the project's hopjit.yaml command registry as a deployment prerequisite.
- Focused verification runs for the missing-standard-library branch are likewise constructed and executed by the executing agent; only the resolved full verification command goes through the deterministic channel.
- Provisional numeric values (translation ledger): the repair transaction retries 3 rounds (source gives no bound); verification runs time out after 900 seconds (source gives no bound); the confirmation gate allows at most 10 present-and-classify rounds, after which the run proceeds as declined with no edits.
- A repair round may not declare a blocker without first attempting a compliant edit; the retry structure owns round termination. When every compliant edit would violate a hard constraint, the round records that as blocker evidence instead of editing.
- Terminal honesty: a decline makes no edits and reports so; a green diagnosis run makes no edits and reports that no failing target exists; the blocked outcome stops at the smallest blocking point, fabricates nothing, and bypasses no proof obligation.
- Verification captures merge stdout and stderr, because Verus diagnostics typically go to stderr.
- The shared-reference reading order applies before annotating or editing: the quickref first, on-demand references next, and both the std-external-specifications and proof-engineering-and-trust-boundaries references before drafting any missing-standard-library specification.

Inputs:
- target % line  # workspace-relative entry Rust file to diagnose and repair; empty means discovery locates it from fresh diagnostics
- verify % line  # whitespace-split verification command string (no shell metacharacters); empty means discovery resolves it
- error_message % text  # initial failure text used as a first-pass hint for the first inspection only; fresh verification output always overrides it
- out_path % line  # workspace-relative path for the blocker summary written only on the blocked outcome; empty means the documented default
- mode % line  # "auto" requests automatic discovery, anything else selects explicit mode; discovery also triggers automatically when target or verify is empty

Outputs:
- resolution_report % text  # how the verification command, target, and out path were resolved (supplied or discovered, with evidence) and which values the run used
- final_report % markdown  # terminal report: outcome, verification evidence, provenance, and the assume_specification records when present
- verify_rc % int  # exit code of the last verification run; the diagnosis run's code on the declined and green paths; -1 when no run ever happened (explicit mode, supplied target, declined gate)
- repair_outcome % enum(verified, blocked, no_failing_target, declined_no_edits)  # terminal outcome of the repair transaction
- blocker_summary_path % line  # path of the written blocker summary; empty when nothing was written

Config:
  requires_commands: [cargo, verus]
## 已批准命令
- cargo
- verus

## Steps
1. [act] Classify the invocation shape
  - ← target, verify, mode
  + → auto_mode % bool  # true when discovery mode is requested or a required input is missing
  + → verify_missing % bool  # true when the verification-command input is empty
  + → target_missing % bool  # true when the target input is empty
  > Mechanical classification of the invocation inputs — the source skill's automatic-discovery predicate. The optional initial-error hint and out path need no gate.
  > ```hop_python
  > verify_missing = len(verify) == 0
  > target_missing = len(target) == 0
  > auto_mode = (mode == "auto") or verify_missing or target_missing
  > ```
2. [act] Default the blocker-summary path
  - ← out_path
  + → effective_out_path % line  # workspace-relative path the blocker summary is written to on the blocked outcome
  + → out_path_defaulted % bool  # true when the documented default was adopted because the input was empty
  > Deterministic defaulting: an empty out path input adopts the documented workspace-local default. The defaulting is reported later in the resolution report.
  > ```hop_python
  > effective_out_path = out_path if len(out_path) > 0 else "kverus-fix-blocker-summary.md"
  > out_path_defaulted = len(out_path) == 0
  > ```
3. [act] Pre-initialize the terminal summary state
  + → summary_content % text  # blocker-summary body, composed on the blocked path only; empty on every other outcome
  + → blocked_evidence % text  # accumulated blocker evidence across repair rounds; empty until a round records some
  + → gate_exhausted % line  # "yes" when the confirmation gate spent its correction budget, empty otherwise
  > Terminal-state defaults: every outcome branch except the blocked one leaves the summary empty, and the gate flags its own exhaustion, so later steps read defined values on all paths.
  > ```hop_python
  > summary_content = ""
  > blocked_evidence = ""
  > gate_exhausted = ""
  > ```
4. [act] Pre-initialize the discovery-evidence sentinels
  + → verify_candidates_checked % text  # discovery evidence for the command: candidates checked and outcomes, or the checked-and-accepted record
  + → root_diagnostic % text  # earliest high-signal root-cause diagnostic, empty until located
  + → diagnosis_report % text  # merged stdout and stderr of the diagnosis run, empty until a run happens
  > Sentinel defaults for the evidence variables the resolution step assembles; the resolving branches below refill them.
  > ```hop_python
  > verify_candidates_checked = ""
  > root_diagnostic = ""
  > diagnosis_report = ""
  > ```
5. [act] Pre-initialize the diagnosis-evidence sentinels
  + → diagnosis_rc % int  # exit code of the diagnosis run; -1 records that no run happened
  + → target_evidence % text  # diagnostic locations and dependency-edge reasoning behind a discovered target
  + → green_evidence % text  # the green diagnosis output proving no failing target exists, empty otherwise
  > Sentinel defaults for the remaining diagnosis variables; the resolving branches below refill them.
  > ```hop_python
  > diagnosis_rc = -1
  > target_evidence = ""
  > green_evidence = ""
  > ```
6. [branch] Resolve the verification command
  - ← verify_missing
  + → effective_verify % line  # the resolved command string every later run executes
  + → verify_cwd % line  # working directory the resolved command runs from
  + → verify_provenance % enum(supplied, discovered)  # where the resolved command came from
  6.1. [case(verify_missing == false)] Carry the supplied command
    - ← verify
    + → effective_verify % line
    + → verify_cwd % line
    + → verify_provenance
    + → verify_candidates_checked
    6.1.1. [act] Carry the supplied command through
      - ← verify
      + → effective_verify
      + → verify_cwd
      + → verify_provenance
      + → verify_candidates_checked
      > Deterministic passthrough: a supplied command is authoritative and discovery is not required.
      > ```hop_python
      > effective_verify = verify
      > verify_cwd = "."
      > verify_provenance = "supplied"
      > verify_candidates_checked = "Supplied command used as-is; discovery not required."
      > ```
  6.2. [case(verify_missing)] Discover the command before the target
    6.2.1. [act free] Execute the command-discovery procedure
      - ← target
      + → verify_discovery_failed % bool  # true when no supported candidate could be executed
      + → verify_discovered_command % line  # strongest executable candidate, empty when discovery failed
      + → verify_discovered_cwd % line  # working directory the discovered command requires, empty when discovery failed
      + → verify_candidates_checked
      > The executing agent works the discovery procedure — inspect workspace instructions and documented workflows, rank candidates against the known entry file and repository layout, and execute the strongest safe candidate from the repository root or the directory its documentation requires, capturing output, exit status, and working directory. A verification failure counts as successful discovery; command-not-found, usage errors, and infrastructure failures do not. Never install tools, change project configuration, or run deploy, publish, cleanup, or other destructive targets while discovering. Record every candidate checked and its outcome.
      > [[kverus-fix-knowledge#Verification command discovery procedure]]
    6.2.2. [branch] Adopt the discovered command or ask for it
      - ← verify_discovery_failed, verify_discovered_command, verify_discovered_cwd
      + → effective_verify % line
      + → verify_cwd % line
      + → verify_provenance
      6.2.2.1. [case(verify_discovery_failed)] Ask for the command after discovery is exhausted
        6.2.2.1.1. [ask present_inputs=verify_candidates_checked] Supply the verification command
          - ← verify_candidates_checked
          + → verify_answer % line  # user-supplied verification command string
          > No supported verification command could be found or launched — the checked evidence is attached. Ask for the working verification command for this crate. Execution resumes only with the answer; nothing is edited before it.
        6.2.2.1.2. [act] Adopt the asked command
          - ← verify_answer
          + → effective_verify
          + → verify_cwd
          + → verify_provenance
          + → verify_candidates_checked
          > Deterministic adoption: the asked value becomes the resolved command, run from the workspace root, provenance recorded honestly as user-supplied after discovery exhaustion.
          > ```hop_python
          > effective_verify = verify_answer
          > verify_cwd = "."
          > verify_provenance = "supplied"
          > verify_candidates_checked = "Asked after discovery exhaustion; adopted as supplied."
          > ```
      6.2.2.2. [case(verify_discovery_failed == false)] Adopt the discovered command
        6.2.2.2.1. [act] Adopt the discovered command
          - ← verify_discovered_command, verify_discovered_cwd
          + → effective_verify
          + → verify_cwd
          + → verify_provenance
          > Deterministic adoption of the strongest executable candidate and its required working directory.
          > ```hop_python
          > effective_verify = verify_discovered_command
          > verify_cwd = verify_discovered_cwd if len(verify_discovered_cwd) > 0 else "."
          > verify_provenance = "discovered"
          > ```
7. [branch] Resolve the entry file from supplied input or fresh diagnostics
  - ← target_missing
  + → effective_target % line  # the file the repair enters from; an entry file, not the only editable file
  + → target_provenance % enum(supplied, discovered, none)  # where the target came from; "none" when verification was green and no target was needed
  7.1. [case(target_missing == false)] Carry the supplied entry file
    - ← target
    + → effective_target % line
    + → target_provenance
    7.1.1. [act] Carry the supplied target through
      - ← target
      + → effective_target
      + → target_provenance
      > Deterministic passthrough: a supplied target is authoritative, no diagnosis run happens, and the sentinel exit code keeps recording that no run occurred.
      > ```hop_python
      > effective_target = target
      > target_provenance = "supplied"
      > ```
  7.2. [case(target_missing)] Run the resolved command and locate the entry file from its output
    7.2.1. [act] Run the resolved verification command for fresh diagnostics
      - ← effective_verify, verify_cwd
      + → diagnosis_report
      + → diagnosis_rc
      > Fresh diagnostics ground the entry-file choice even when an initial error message was supplied — the source procedure runs the command first. Output and error streams are merged.
      > ```hop_python
      > argv = split(effective_verify, " ")
      > r = subprocess.run(argv, cwd: verify_cwd, timeout: 900)
      > diagnosis_report = r.stdout + r.stderr
      > diagnosis_rc = r.returncode
      > ```
    7.2.2. [branch] Route by the diagnosis result
      - ← diagnosis_rc
      + → effective_target % line
      + → target_provenance
      7.2.2.1. [case(diagnosis_rc == 0)] Record that verification passes with no failing target
        7.2.2.1.1. [act] Record the green evidence
          - ← diagnosis_report
          + → green_evidence
          + → effective_target
          + → target_provenance
          + → root_diagnostic
          + → target_evidence
          > Deterministic recording: the command exited green, so no failing entry file exists, none is needed, and the green output itself is the evidence.
          > ```hop_python
          > green_evidence = diagnosis_report
          > effective_target = ""
          > target_provenance = "none"
          > root_diagnostic = ""
          > target_evidence = ""
          > ```
      7.2.2.2. [case(diagnosis_rc != 0)] Locate the entry file from the diagnostics
        7.2.2.2.1. [reason] Locate the entry file from the root-cause diagnostic
          - ← diagnosis_report, verify_cwd
          + → located_target % line  # chosen entry file, empty when location is not confident
          + → located_confident % bool  # false when the diagnostics do not identify an in-workspace source file with confidence
          + → root_diagnostic
          + → target_evidence
          > Apply the location procedure to the fresh diagnosis output: read the earliest high-signal root-cause diagnostic, preferring verification errors over cascaded Rust errors and warnings; resolve its locations against the command's working directory; exclude generated output, caches, vendored code, and external dependencies; when the primary diagnostic points at a call site but the failed obligation lives in a local callee, specification, or proof module, choose the file owning the smallest compliant repair; one entry file per root cause, earliest failure first. Quote the chosen locations and the dependency-edge reasoning into the evidence.
          > [[kverus-fix-knowledge#Target location from diagnostics]]
        7.2.2.2.2. [branch] Adopt the located entry file or ask for it
          - ← located_confident, located_target
          + → effective_target % line
          + → target_provenance
          7.2.2.2.2.1. [case(located_confident)] Adopt the located entry file
            7.2.2.2.2.1.1. [act] Adopt the located entry file
              - ← located_target
              + → effective_target
              + → target_provenance
              > Deterministic adoption of the confidently located entry file; the repair stays within its smallest necessary dependency closure.
              > ```hop_python
              > effective_target = located_target
              > target_provenance = "discovered"
              > ```
          7.2.2.2.2.2. [case(located_confident == false)] Ask for the entry file after location is not confident
            7.2.2.2.2.2.1. [ask present_inputs=target_evidence] Supply the entry file path
              - ← target_evidence
              + → target_answer % line  # user-supplied workspace-relative entry file path
              > The diagnostics did not identify an editable in-workspace source file with confidence — the diagnostic evidence is attached. Ask for the workspace-relative entry file to repair, including the relevant diagnostic locations. Execution resumes only with the answer; nothing is edited before it.
            7.2.2.2.2.2.2. [act] Adopt the asked entry file
              - ← target_answer
              + → effective_target
              + → target_provenance
              > Deterministic adoption: the asked value becomes the entry file, provenance recorded honestly as user-supplied.
              > ```hop_python
              > effective_target = target_answer
              > target_provenance = "supplied"
              > ```
8. [branch] Run the confirmation gate when discovery mode is active
  - ← auto_mode
  + → gate_state % enum(skipped, approved, declined)  # skipped for explicit invocations; declined also covers gate-round exhaustion
  8.1. [case(auto_mode == false)] Skip the gate for explicit invocations
    8.1.1. [act] Record the skipped gate
      + → gate_state
      > Deterministic record: every required value was supplied explicitly, so the source gate — which exists for automatic discovery — does not run.
      > ```hop_python
      > gate_state = "skipped"
      > ```
  8.2. [case(auto_mode)] Present the resolved pair until the answer is terminal
    8.2.1. [subtask retry=10] Present the resolved pair and classify the answer
      + → gate_state
      8.2.1.1. [act] Reset the round state to the decline default
        + → gate_state
        > Per-round default: a round that ends in a correction keeps the decline posture for the next presentation, and budget exhaustion inherits the same honest terminal instead of silent approval.
        > ```hop_python
        > gate_state = "declined"
        > ```
      8.2.1.2. [act] Assemble the gate presentation
        - ← effective_verify, verify_cwd, effective_target, verify_provenance, target_provenance, root_diagnostic, diagnosis_report
        + → gate_presentation % text  # labeled presentation of the command-file pair with provenance and diagnostic evidence
        > Deterministic assembly of the source gate's four presentation items into one labeled text: the exact command with its working directory, the selected entry file, which values were supplied versus discovered, and the root diagnostic with the diagnosis output behind the file choice.
        > ```hop_python
        > gate_presentation = "Verification command: " + effective_verify + "\nWorking directory: " + verify_cwd + "\nTarget file: " + effective_target + "\nCommand provenance: " + verify_provenance + "\nTarget provenance: " + target_provenance + "\nRoot diagnostic: " + root_diagnostic + "\nDiagnosis output: " + diagnosis_report
        > ```
      8.2.1.3. [ask present_inputs=gate_presentation] Confirm the resolved command-target pair
        - ← gate_presentation
        + → gate_answer % line  # free-text answer: approval, corrections, or decline
        > The source gate stops and waits here: present the resolved pair and ask the user to approve it, correct either value, or decline. No code is edited and no repair round runs before an explicit answer.
      8.2.1.4. [reason] Classify the gate answer
        - ← gate_answer
        + → gate_decision % enum(approved, corrected, declined)  # mechanical reading of the answer's intent
        + → corrected_verify % line  # corrected command string when the answer corrected the command, empty otherwise
        + → corrected_target % line  # corrected entry-file path when the answer corrected the entry file, empty otherwise
        > Classify the free-text answer: approval maps to approved, a decline maps to declined, and a correction maps to corrected with the replacement command or file path extracted verbatim. A correction must carry at least one replacement value; an unclear answer without any replacement value counts as declined — no silent re-presentation loop.
      8.2.1.5. [branch] Apply the gate decision
        - ← gate_decision, corrected_verify, corrected_target
        8.2.1.5.1. [case(gate_decision == "approved")] Approve the resolved pair
          8.2.1.5.1.1. [act] Record the approval
            + → gate_state
            > ```hop_python
            > gate_state = "approved"
            > ```
        8.2.1.5.2. [case(gate_decision == "declined")] Decline without edits
          8.2.1.5.2.1. [act] Record the decline
            + → gate_state
            > Re-record the round default explicitly so the terminal state is visible in the step trail; a decline means no edits are made.
            > ```hop_python
            > gate_state = "declined"
            > ```
        8.2.1.5.3. [case(gate_decision == "corrected")] Adopt the corrections, refresh evidence, present again
          8.2.1.5.3.1. [act] Adopt the corrected values
            - ← corrected_verify, corrected_target, effective_verify, effective_target, target_provenance
            + → effective_verify
            + → effective_target
            + → target_provenance
            > Deterministic adoption: a correction replaces the value it corrects, and a corrected entry file is user-supplied and authoritative. An empty correction leaves that value untouched.
            > ```hop_python
            > effective_verify = corrected_verify if len(corrected_verify) > 0 else effective_verify
            > effective_target = corrected_target if len(corrected_target) > 0 else effective_target
            > target_provenance = "supplied" if len(corrected_target) > 0 else target_provenance
            > ```
          8.2.1.5.3.2. [act] Refresh the diagnosis with the resolved command
            - ← effective_verify, verify_cwd
            + → diagnosis_report
            + → diagnosis_rc
            > Re-run the resolved command so no downstream step reads stale diagnostic evidence (the source gate refreshes any affected evidence). Merged capture as elsewhere.
            > ```hop_python
            > argv = split(effective_verify, " ")
            > r = subprocess.run(argv, cwd: verify_cwd, timeout: 900)
            > diagnosis_report = r.stdout + r.stderr
            > diagnosis_rc = r.returncode
            > ```
          8.2.1.5.3.3. [act] Refresh the green-evidence state
            - ← diagnosis_report, diagnosis_rc
            + → green_evidence
            > Deterministic refresh: the corrected command may pass, and the routing step must see the current green state, not the pre-correction one.
            > ```hop_python
            > green_evidence = diagnosis_report if diagnosis_rc == 0 else ""
            > ```
          8.2.1.5.3.4. [reason] Re-ground the root diagnostic when the command was corrected
            - ← corrected_verify, diagnosis_report, verify_cwd
            + → root_diagnostic
            + → target_evidence
            > When the answer corrected the command, the refreshed diagnosis output supersedes the old evidence: re-read the earliest high-signal root cause and re-record the location evidence behind the current entry file. When only the entry file was corrected, the user's correction already carried the authority and this step re-affirms the existing evidence.
            > [[kverus-fix-knowledge#Target location from diagnostics]]
      8.2.1.6. [check final] Judge the round
        - ← gate_decision
        + → ok % bool  # true when the answer was terminal (approved or declined)
        + → note % text  # correction note: the corrected pair is re-presented on the next round
        > Mechanical verdict on the classified answer. A correction is not a failure of the gate — it is the gate working — so the retry simply presents the corrected pair again.
        > ```hop_python
        > ok = (gate_decision == "approved") or (gate_decision == "declined")
        > note = "" if ok else "gate round ended in a correction; the corrected pair is re-presented"
        > ```
    8.2.2. [on fail] Record gate exhaustion
      8.2.2.1. [act] Flag that the correction budget was spent
        + → gate_exhausted
        > The ten-round budget ended without an explicit approval or decline; the round-default decline posture stands and the flag makes it visible in the resolution report. No edits were made.
        > ```hop_python
        > gate_exhausted = "yes"
        > ```
9. [reason] Assemble the resolution report
  - ← auto_mode, mode, effective_verify, verify_cwd, verify_provenance, verify_candidates_checked, effective_target, target_provenance, root_diagnostic, diagnosis_report, diagnosis_rc, target_evidence, green_evidence, effective_out_path, out_path_defaulted, gate_state, gate_exhausted
  + → resolution_report % text
  > Report the resolution faithfully per the source output expectations: which values were supplied and which were discovered; when discovered, the resolved command, its working directory, the entry-file path, and the diagnostic evidence used to select it; the gate state including any exhausted correction budget; and the effective blocker-summary path with its defaulting flag. Quote the evidence, never recall it.
10. [act] Classify the terminal route
  - ← gate_state, green_evidence
  + → route_state % enum(declined, no_failing_target, repair)  # declined: gate ended without approval; no_failing_target: diagnosis was green; repair: proceed to the validation loop
  > Mechanical routing precedence: a decline outranks everything because no edits may follow it; a green diagnosis outranks repair because there is nothing to fix; otherwise the repair rounds run.
  > ```hop_python
  > route_state = "declined" if gate_state == "declined" else ("no_failing_target" if len(green_evidence) > 0 else "repair")
  > ```
11. [branch] Produce the terminal outcome and final report
  - ← route_state
  + → repair_outcome % enum(verified, blocked, no_failing_target, declined_no_edits)  # terminal outcome of the repair transaction
  + → final_report % markdown  # terminal report for the caller
  + → verify_rc % int  # exit code of the last verification run, or the -1 no-run sentinel
  11.1. [case(route_state == "declined")] End with no edits
    11.1.1. [act] Record the declined outcome
      - ← diagnosis_rc
      + → repair_outcome
      + → verify_rc
      > Deterministic record: no edits were made. The verification status is the diagnosis run's exit code, or the -1 no-run sentinel when the entry file was supplied outright and no command ever ran.
      > ```hop_python
      > repair_outcome = "declined_no_edits"
      > verify_rc = diagnosis_rc
      > ```
    11.1.2. [reason] Compose the declined final report
      - ← effective_verify, verify_cwd, verify_provenance, effective_target, target_provenance, diagnosis_report, green_evidence, gate_state
      + → final_report
      > Short report per the source output expectations: the resolved command with its working directory and provenance, the entry file with its provenance, the decline or exhausted budget, and — when the diagnosis had run green before the decline — the green evidence. Keep it short.
  11.2. [case(route_state == "no_failing_target")] End with the green evidence
    11.2.1. [act] Record the green-diagnosis outcome
      - ← diagnosis_rc
      + → repair_outcome
      + → verify_rc
      > Deterministic record: the verification command passed before any edit, so the outcome records that no failing entry file exists and no edits were made.
      > ```hop_python
      > repair_outcome = "no_failing_target"
      > verify_rc = diagnosis_rc
      > ```
    11.2.2. [reason] Compose the green final report
      - ← effective_verify, verify_cwd, verify_provenance, effective_target, green_evidence
      + → final_report
      > Short report: the command, its working directory and provenance, the green output as evidence that no failing entry file exists, and the fact that no edits were made.
  11.3. [case(route_state == "repair")] Run the validation loop to green or blocker
    11.3.1. [act free] Inspect the entry file and its immediate dependencies
      - ← effective_target, error_message, diagnosis_report
      + → inspection_note % text
      > The validation loop opens with inspection. Read the entry file and its immediate dependency closure; when an initial error hint was supplied it prioritizes this first inspection only — every later round trusts fresh command output. Apply the shared-reference reading order before planning any annotation or edit.
      > [[kverus-fix-knowledge#Shared reference reading order]]
    11.3.2. [subtask retry=3] Repair rounds: verify, classify, edit, verify again
      + → verify_report % text  # merged output of the latest verification run
      + → verify_rc % int  # exit code of the latest verification run
      + → blocked_evidence % text  # accumulated blocker evidence across rounds, empty when no round found a blocker
      + → assume_spec_changes % text  # the assume_specification record when the missing-standard-library branch ran, empty otherwise
      + → edit_note % text  # what this transaction edited and where
      11.3.2.1. [act] Collect fresh verification output
        - ← effective_verify, verify_cwd
        + → verify_report % text
        + → verify_rc % int
        > Each round opens by trusting fresh command output. The resolved command runs whitespace-split from its recorded working directory; streams merge.
        > ```hop_python
        > argv = split(effective_verify, " ")
        > r = subprocess.run(argv, cwd: verify_cwd, timeout: 900)
        > verify_report = r.stdout + r.stderr
        > verify_rc = r.returncode
        > ```
      11.3.2.2. [act free] Classify the failure and plan the smallest edit
        - ← verify_report, error_message, inspection_note, blocked_evidence
        + → round_classification % enum(ordinary, missing_stdlib)  # ordinary: proof repair; missing_stdlib: the missing-specification branch
        + → round_edit_plan % text  # the smallest edit addressing the highest-signal error
        + → round_blocked_evidence % text  # nonempty when every compliant edit would violate a hard constraint
        > Classify the fresh failure: ordinary proof repair, or the missing-standard-library branch — only when the output implicates a std, core, or alloc API with no applicable contract in the active version (read both std references first). Plan the smallest fix for the highest-signal error, inside the smallest necessary dependency closure. Record round_blocked_evidence only when no compliant edit exists without violating a hard constraint — declaring a blocker without attempting a compliant edit is not allowed. Prior consolidated evidence arrives through the blocker-evidence variable; carry it into the judgment. On retry rounds, the injected correction block carries the previous round's verification failure.
        > [[kverus-fix-knowledge#Shared reference reading order]]
        > [[kverus-fix-knowledge#Missing standard-library specification branch]]
      11.3.2.3. [act] Merge the round's blocker evidence
        - ← blocked_evidence, round_blocked_evidence
        + → blocked_evidence
        > Deterministic accumulation: a round with blocker evidence appends it to the running record; a clean round leaves the record untouched.
        > ```hop_python
        > blocked_evidence = blocked_evidence + "\n---\n" + round_blocked_evidence if len(round_blocked_evidence) > 0 else blocked_evidence
        > ```
      11.3.2.4. [branch] Apply the planned edit
        - ← round_classification, round_edit_plan
        11.3.2.4.1. [case(round_classification == "ordinary")] Make the minimal proof-preserving edit
          11.3.2.4.1.1. [act free] Edit the workspace files per the plan
            - ← round_edit_plan, effective_target
            + → assume_spec_changes
            + → edit_note
            > Apply the smallest fix addressing the highest-signal error, in place, within the smallest necessary dependency closure. The hard constraints in this spec's Constraints section govern the edit; the shared references are read per the reading order before annotating. No assume_specification may be added on this path, so assume_spec_changes stays empty. Re-read the current file state before editing on retry rounds. Record what was edited and where in edit_note.
            > [[kverus-fix-knowledge#Shared reference reading order]]
        11.3.2.4.2. [case(round_classification == "missing_stdlib")] Add the missing external specification
          11.3.2.4.2.1. [act free] Execute the missing-standard-library branch
            - ← round_edit_plan, effective_target
            + → assume_spec_changes
            + → edit_note
            > Work the branch procedure: confirm the root cause is a missing specification rather than a missing import, disabled module, version mismatch, unsupported type, unsatisfied trait bound, or an unproved precondition; search the active vstd and the repository's existing external-spec libraries for the exact API and reuse or extend a sound model; inspect the standard-library implementation for the exact Rust toolchain in use; draft the smallest sound specification preserving every relevant runtime effect. Edits land in place: the repository's dedicated external-spec library receives the reusable contract, plus any minimal model, external type specification, proved bridge lemma, or broadcast group it requires. Focused verification of the spec library and the entry file is constructed and run by the executing agent here; the round's fresh full-command run happens next. Record into assume_spec_changes: the qualified API, the spec location, the Rust source and documentation basis, the focused and full verification results, and the residual trusted boundary. Record the edits in edit_note.
            > [[kverus-fix-knowledge#Missing standard-library specification branch]]
            > [[kverus-fix-knowledge#Shared reference reading order]]
      11.3.2.5. [act] Verify again with the same command and working directory
        - ← effective_verify, verify_cwd
        + → verify_report
        + → verify_rc
        > The round closes by re-running the same resolved command from the same working directory; the check below judges this run.
        > ```hop_python
        > argv = split(effective_verify, " ")
        > r = subprocess.run(argv, cwd: verify_cwd, timeout: 900)
        > verify_report = r.stdout + r.stderr
        > verify_rc = r.returncode
        > ```
      11.3.2.6. [check final] Judge the round
        - ← verify_rc, verify_report
        + → ok % bool  # true when the verification command exits 0
        + → note % text  # failure note: the failing excerpt injected into the next round's correction context
        > Mechanical verdict on the round's closing verification run. A failed round feeds its output back as the next round's correction context; three exhausted rounds fail this transaction honestly.
        > ```hop_python
        > ok = verify_rc == 0
        > note = "" if ok else "verification still failing (exit code " + str(verify_rc) + "): " + verify_report
        > ```
    11.3.3. [act] Record the verified outcome
      + → repair_outcome
      > Deterministic record of the green terminal; the closing run's exit code carries forward unchanged. (This step runs on the transaction's success path; the exhausted path is handled by the on-fail block below.)
      > ```hop_python
      > repair_outcome = "verified"
      > ```
    11.3.4. [reason] Compose the verified final report
      - ← effective_verify, verify_cwd, verify_provenance, effective_target, target_provenance, verify_report, verify_rc, edit_note, assume_spec_changes
      + → final_report % markdown
      > Short report: the resolved command with provenance, the verification evidence (the closing green run), what was edited, and — when the missing-standard-library branch ran — the full assume_specification record: qualified API, spec location, Rust source and documentation basis, focused and full verification results, residual trusted boundary. Keep it short unless the caller asks for details.
    11.3.5. [on fail] Handle the exhausted repair transaction
      11.3.5.1. [act] Merge the final round's output into the blocker evidence
        - ← blocked_evidence, verify_report, verify_rc
        + → blocked_evidence
        > The retry budget ran out with verification still failing — append the final round's output so the summary and report quote it.
        > ```hop_python
        > blocked_evidence = blocked_evidence + "\n---\nFinal round verification output (exit code " + str(verify_rc) + "):\n" + verify_report
        > ```
      11.3.5.2. [reason] Compose the blocker summary content
        - ← blocked_evidence, effective_target, root_diagnostic, assume_spec_changes
        + → summary_content % text
        > Compose the source failure-policy summary concisely from the accumulated blocker evidence: the blocking location(s), why the hard constraints prevent a compliant fix, and what additional assumptions or spec changes would be required. Stop at the smallest blocking point; fabricate nothing; bypass no proof obligation.
        > [[kverus-fix-knowledge#Failure policy summary contents]]
      11.3.5.3. [act] Record the blocked outcome
        + → repair_outcome
        > Deterministic record of the blocked terminal; the final failing exit code carries forward unchanged, and the summary content composed above is written by this spec's commit step.
        > ```hop_python
        > repair_outcome = "blocked"
        > ```
      11.3.5.4. [reason] Compose the blocked final report
        - ← effective_verify, verify_cwd, verify_provenance, effective_target, target_provenance, verify_report, verify_rc, blocked_evidence, summary_content, assume_spec_changes, effective_out_path
        + → final_report % markdown
        > Short report: the resolved command with provenance, the final failing verification output, the blocker evidence, where the summary file was written, and the assume_specification record when the missing-standard-library branch ran. Keep it short.
12. [subtask] Gate the terminal summary content
  + → summary_gate_ok % bool  # true when the summary content matches the terminal outcome
  + → summary_gate_note % text  # invariant description when it breaks
  12.1. [check final] Check the summary-content invariant
    - ← repair_outcome, summary_content, effective_out_path
    + → summary_gate_ok % bool  # true when the summary content matches the outcome
    + → summary_gate_note % text  # invariant description when it breaks
    > Mechanical invariant: the blocked outcome must carry composed summary content and an effective out path; every other outcome must carry none. A failure here means a spec-internal invariant broke, and the run stops before any write happens.
    > ```hop_python
    > summary_gate_ok = ((repair_outcome == "blocked") and (len(summary_content) > 0) and (len(effective_out_path) > 0)) or ((repair_outcome == "verified" or repair_outcome == "no_failing_target" or repair_outcome == "declined_no_edits") and (len(summary_content) == 0))
    > summary_gate_note = "" if summary_gate_ok else "summary-content invariant broken: blocked outcome needs summary content and an out path; every other outcome needs none"
    > ```
13. [commit] Write the blocker summary when the outcome is blocked
  - ← repair_outcome, summary_content, effective_out_path
  + → blocker_summary_path % line  # path the summary was written to; empty when nothing was written
  > Writes exactly one file — the blocker summary under the effective out path — and only when the outcome is blocked; that is the source failure policy's deliverable and the only file this spec commits. The summary-content gate immediately before this step is the check final that authorizes the write. The write is conditional in the body: no summary content, no write.
  > ```hop_python
  > needs_write = repair_outcome == "blocked"
  > written = write(path: effective_out_path, content: summary_content) if needs_write else ""
  > blocker_summary_path = effective_out_path if needs_write else ""
  > ```
14. [exit] Deliver the repair transaction outcome
  + → resolution_report, final_report, verify_rc, repair_outcome, blocker_summary_path
