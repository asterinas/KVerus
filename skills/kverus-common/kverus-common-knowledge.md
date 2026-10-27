# Knowledge: kverus-common — the shared reference layer, its router, and the Verus-root resolver

Id: kverus-common-knowledge
Spec: kverus-common

## 1. Objective and scope split

kverus-common is the reference layer of the KVerus family, not a workflow: it ships the shared Verus proof references, routes a proof situation to exactly the relevant files, and machine-verifies a candidate Verus checkout root. The spec owns three machine duties — the acceptance probe, the topic router, and the citation confirmation — and nothing else. The cognition stays with the executor: which situation class applies (the topic input), which file inside a routed shelf applies (`sub_reference` for the unsupported-features directory), where the Verus checkout lives (the locate step), and whether a reference actually answers the question at hand. No other KVerus spec statically calls this one; they duplicate its fourteen global guide rules into their own Constraints per the L11/Q3=A ruling and point at this tree for the reference files themselves.

## 2. Loading rule — the source's nine bullets as a routing table

The source's Loading Rule maps a situation to a reference (or a shelf). The spec's topic enum carries the same nine groups; the executor classifies, the machine routes:

| Situation (source wording, condensed) | topic | Machine-selected files |
|---|---|---|
| Syntax or mode confusion | syntax | verus-syntax-quickref.md |
| Verification repair strategy or error triage | repair-triage | common-errors.md |
| Proof construction, quantifiers, arithmetic, bit-vector, or SMT context issues | proof-constructs | proof-localization.md, quantifiers.md, solvers.md, arithmetic-lemmas.md, calc-blocks.md, opaque-reveal.md, lemma-shape.md, set-reasoning.md |
| Loop or recursive proof failures; type invariant vs explicit `inv()` contracts | invariants | invariants.md |
| `ghost`, `tracked`, `Tracked<T>`, `Ghost<T>`, `@`, mode-marker placement, erasure | ghost-tracked | ghost-tracked.md |
| Axiom-like declarations, external API specs, trusted boundaries, `dual_spec`/spec twins/`when_used_as_spec`, proof helper naming and scoping, proof cleanup | trust-boundaries | proof-engineering-and-trust-boundaries.md |
| Missing or incomplete vstd specifications for `std`, `core`, or `alloc` APIs | std-external | std-external-specifications.md **plus** proof-engineering-and-trust-boundaries.md |
| Any addition, removal, or rewrite of executable Rust; verification-added `use` imports relative to the original import list | exec-preservation | exec-code-preservation.md — mandatory **before** editing or reviewing the change |
| Concurrency, invariants, permissions, state-machine navigation | concurrency | tokenized-state-machine.md |
| Verus-unsupported features, forced rewrites, trait associated constant limitations | unsupported | unsupported-features/index.md, then the named topic file via `sub_reference` |

Loading discipline (from the source, not machine-enforced): load **only** the relevant reference for the situation — the router outputs a set, not a mandate to read all of it; `topic` = none outputs the empty set.

## 3. The unsupported-features shelf (`references/unsupported-features/`)

Thirteen files; the index is always loaded first, the topic file rides `sub_reference`: index.md, await.md, async-blocks.md, async-functions.md, debug-serde-traits.md, destructuring-assignment.md, drop.md, function-pointer-types.md, hardware-intrinsics.md, pin.md, printing-io.md, std-mutex-rwlock.md, transmute.md. (The shelf inventory is machine-checked by the sibling kverus-common-sync checker against the Verus guide source.)

## 4. Source path resolution protocol

The source's four-step procedure splits across executor and machine:

1. **Locate** (executor cognition): inspect the verification command, repository scripts and configuration, environment, and submodule metadata to find the active Verus checkout. The machine never guesses a root — `candidate_root` arrives pre-located.
2. **Accept** (machine, spec step 3): the candidate is accepted only when it contains both `source/docs/guide/src` and `source/vstd` trees. Anything else — a partial checkout, a plain Rust repo, a missing directory — is rejected, `verus_root` stays empty, and the report says so.
3. **Resolve** (machine where cited): `source/docs/...`, `source/vstd/...`, and `examples/...` citations resolve relative to the accepted root; project paths resolve relative to `workspace`. Citations stay in root-relative form; nothing resolves against the spec's own directory.
4. **Confirm** (machine, spec step 5): an optional `citation` is existence-checked against the accepted root — `resolved` / `unresolved` / `no-root` (citation requested but the candidate failed acceptance) / `not-requested`. The source's rule "if no active checkout can be located, report the unresolved citation rather than inventing a path" is the `no-root` word: the status is reported, no path is fabricated.

## 5. Project policy and source basis

Read the target workspace's own instructions before applying these general references; for an Asterinas/VOSTD workspace that means `AGENTS.md` then `docs/coding-guidelines/README.md` and the guideline it links. The references summarize the Verus guide under `source/docs/guide/src`, resolved against the accepted Verus root — when the checkout moves, the summaries move with it, which is exactly why the acceptance probe gates everything.

## 6. Deviation and approximation register (this spec)

- **Topic granularity** — the source's bullet 3 names eight proof references with the executor picking the relevant one; the topic enum routes the whole shelf as `proof-constructs` and leaves the intra-shelf pick to the knowledge table above (registered grouping, no merge of distinct triggers).
- **LOCATE stays executor-side** — machine verification covers acceptance and citation existence only (the source's steps 1–2 cognition is not machine-able; registered approximation).
- **`no-root` word** — source says "report the unresolved citation" when no checkout is located; the spec distinguishes `no-root` from a checked-and-missing `unresolved` for report honesty. Same user-facing outcome, finer diagnosis.
- **`case(else)` catch-all** — unreachable under the closed eleven-word enum; present because branch grammar defaults last. Foreign topic words would honestly load nothing and the seal check reports the inconsistency.
- **No `[commit]`** — the source defines no file deliverable; results ride the exit payload (L3 family).
- **No `requires_commands`** — zero subprocess surface; existence probes only.

## 7. Deployment prerequisites

- The `references/` tree (including `unsupported-features/`) and `agents/openai.yaml` ship as-is in the skill directory (L7 ruling: host ancillary files are not translated); packaging carries them via `hopjit ant pack --assets references/ agents/`.
- Reference drift against the Verus guide source is governed by the sibling kverus-common-sync skill (check_sync.py, `--verus-root` or auto-discovery); `--strict-mtime` remains an internal checker flag, deliberately not exposed (L25).
- Consumers read references relative to their own deployed tree (`../kverus-common/references/...` in the repo layout; same-flat-name in a packed HopAnt). The fourteen global guide rules ship verbatim in this spec's Constraints and in every KVerus spec's Constraints per the L11 duplication ruling.

## 8. Fidelity quick-index

Router exactness: eleven topic words cover the source's nine bullets one-to-one (proof-constructs carries bullet 3's eight-file shelf; std-external carries the bullet-7 pair; unsupported carries index-plus-named-file). Acceptance exactness: both trees required, `verus_root` empty on rejection, no invented paths. Citation exactness: existence confirmed only against an accepted root. Loading-rule narrative, project policy, and the fourteen rules live verbatim in the spec's Constraints and this document — the source's "carry these rules into all KVerus skills" is thereby machine-duplicated into every translated spec of the batch.
