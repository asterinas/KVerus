# kverus-eval knowledge

Companion knowledge for the kverus-eval spec. Mirrors the source skill's "Evaluation Scope", "Required Workflow", "Scoring Policy", and "Output Format" sections; nothing here adds to or contradicts the source.

## Spec-related change classes

The isolation step keeps only hunks touching spec machinery:

- `requires` clauses
- `ensures` clauses
- loop invariants
- `decreases` clauses
- `recommends` clauses
- spec and ghost declarations

Everything else in the unstaged diff (implementation bodies, tests, non-spec code) is excluded from the evaluation input.

## Evaluation scope

Review the isolated spec-related modifications from these aspects:

1. Whether the modification strengthens or weakens the spec.
2. Whether the modification changes the original purpose of the spec.
3. Whether unnecessary spec content is added.

## Scoring policy

Max 10.

Start from 10 and subtract deductions:

1. Weakens safety/correctness guarantees without justification: minus 2 to 5.
2. Changes original spec purpose or contract intent: minus 2 to 5.
3. Adds redundant or unused spec clauses that increase maintenance burden: minus 1 to 3.
4. If a change is neutral but clearer, no penalty.
5. If a change strengthens spec while preserving intent and avoids redundancy, keep 9 to 10.

Clamp the final score to range [0, 10].

## Output format

The report carries, in order:

1. Strength assessment: stronger, weaker, or mixed.
2. Intent preservation assessment: preserved or changed.
3. Redundancy assessment: none, minor, or significant.
4. Score: X/10.
5. Short rationale with concrete diff references.

Keep the report concise and review-focused.
