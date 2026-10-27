---
name: kverus-eval
description: Evaluate current unstaged spec modifications for semantic quality and intent preservation, then score the modification out of 10. Use when reviewing spec edits before staging or committing.
argument-hint: "[target=path/to/entry.rs] [context='<original spec intent>']"
license: MIT
compatibility: Requires a git workspace with unstaged changes.
user-invocable: true
metadata:
  author: kverus
  version: "1.0"
---

Evaluate spec modifications in current unstaged changes.

Preferred invocation:

```text
$kverus-eval target=path/to/entry.rs context="<original spec intent>"
```

If `target` is provided, prioritize that file but include closely related unstaged spec edits when necessary.

If `context` is missing, infer original intent from nearby comments, names, and unchanged surrounding code.

## Evaluation Scope

Review current unstaged spec-related modifications from these aspects:

1. Whether the modification strengthens or weakens the spec.
2. Whether the modification changes the original purpose of the spec.
3. Whether unnecessary spec content is added.

## Required Workflow

1. Inspect unstaged diff first.
2. Isolate spec-related changes (`requires`, `ensures`, invariants, `decreases`, `recommends`, spec/ghost declarations).
3. Compare modified clauses with previous intent from unchanged code and nearby context.
4. Evaluate the three aspects.
5. Produce a final score out of 10 with concise justification.

## Scoring Policy (Max 10)

Start from 10 and subtract deductions:

1. Weakens safety/correctness guarantees without justification: minus 2 to 5.
2. Changes original spec purpose or contract intent: minus 2 to 5.
3. Adds redundant or unused spec clauses that increase maintenance burden: minus 1 to 3.
4. If a change is neutral but clearer, no penalty.
5. If a change strengthens spec while preserving intent and avoids redundancy, keep 9 to 10.

Clamp final score to range [0, 10].

## Output Format

Return:

1. Strength assessment: stronger, weaker, or mixed.
2. Intent preservation assessment: preserved or changed.
3. Redundancy assessment: none, minor, or significant.
4. Score: X/10.
5. Short rationale with concrete diff references.

Keep output concise and review-focused.
