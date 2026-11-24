# KVerus Skills

Agent skills for converting Rust code to verified Verus code. The collection includes the core pipeline stages, an end-to-end orchestrator, postprocessing support, and shared reference material.

## Skills

### Pipeline Stages

| Stage | Skill                   | Purpose                                                                                                                                                                                                                     |
| ----- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | `kverus-migrate`        | Convert Rust into minimally modified Verus-compatible code and iterate until the verification command succeeds. It preserves original Rust constructs as nearby comments where practical.                                   |
| 2     | `kverus-spec`           | Add proof-ready specification scaffolding such as `requires`, `ensures`, invariants, `decreases`, `recommends`, `spec fn`, and ghost/spec helpers while preserving executable behavior.                                     |
| 3     | `kverus-fix`            | Repair Verus verification failures with minimal proof-preserving edits. It does not weaken existing `requires`/`ensures`, add `assume`/`admit`, or hide proof obligations with new `external_body` annotations.             |
| 4     | `kverus-eval`           | Review unstaged spec-related changes and score whether they strengthen or weaken the spec, preserve intent, and avoid redundant clauses. Scores below `7/10` trigger retry or user review in the full pipeline.             |
| 5     | `kverus-semantic-audit` | Compare the original Rust snapshot with the migrated Verus code and report executable behavior changes, likely-equivalent rewrites, and uncertain cases. High-severity semantic changes pause the pipeline for user review. |
| 6     | `kverus-postprocess`    | Run final review-rule checks, formatting, and verification. Proof simplification is opt-in.                                                                                                    |

### Orchestration and Support

| Skill                | Purpose                                                                                                                           |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `kverus-run`         | Orchestrate all six pipeline stages end to end, including quality gates and reporting.                                            |
| `kverus-strip`       | Remove redundant proof asserts and unnecessary proof code while keeping verification passing; available as an opt-in postprocess step. |
| `kverus-common`      | Provide shared Verus syntax and proof-pattern reference material; it is not invoked directly.                                     |
| `kverus-common-sync` | Validate that `kverus-common` stays in sync with the Verus guide source.                                                          |

## Pipeline

`kverus-run` composes the individual skills into a single pipeline:

```
                    ┌─────────────────── kverus-run ───────────────────┐
                    │                                                  │
Rust Code
  └─→ Migrate ──→ Spec ──→ Fix ──→ Eval ──→ Semantic Audit ──→ Postprocess ──→ Verified Code
        │           │       │        │            │                 │
        │           │       │        │            │                 └─ kverus-postprocess
        │           │       │        │            │                    └─ kverus-strip
        │           │       │        │            └─ kverus-semantic-audit
        │           │       │        └─ kverus-eval
        │           │       └─ kverus-fix
        │           └─ kverus-spec
        └─ kverus-migrate
```

Quality gates after Eval (score >= 7/10) and Semantic Audit (no high-severity changes) can pause the pipeline for user review. Postprocess runs after those gates and calls `kverus-strip` only when explicitly enabled. Standalone fix uses a static diff check after verification.

## Installation

See the root [README](../README.md#setup-skills) for installation instructions using `scripts/install-skills.sh`.
