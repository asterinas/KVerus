# Verified Insertion Sort Example

This example records an actual KVerus run from a variable-length Rust insertion sort to verified Verus code. It was generated in an isolated Git repository without consulting an existing verified sorting solution.

- [`insertion_sort.rs`](insertion_sort.rs) is the original executable Rust input.
- [`insertion_sort_verus.rs`](insertion_sort_verus.rs) is the final KVerus output.

## How Verus and KVerus Work Together

[Verus](https://github.com/verus-lang/verus/) extends Rust with specifications such as preconditions, postconditions, and loop invariants. It statically proves that the executable code satisfies those specifications for every possible execution; specifications and proof code are erased from the executable.

KVerus automates the work around that checker. It migrates Rust code to Verus, proposes the properties the code should satisfy, generates proof scaffolding, and repairs verification failures. Verus remains the independent checker, so a KVerus run succeeds only when all proof obligations pass.

```text
Rust code
  │
  │ KVerus adds:
  │   • what the code must guarantee (specifications)
  │   • why those guarantees hold (proofs)
  ▼
Rust code with Verus annotations
  │
  │ Verus checks that the implementation satisfies the specifications
  ▼
Verified Rust code
```

## What This Example Proves

The original insertion sort describes how to sort a vector of any length:

```rust
fn insertion_sort(nums: &mut Vec<u32>) {
    let n = nums.len();
    let mut i = 1;
    while i < n {
        let mut j = i;
        while j > 0 && nums[j - 1] > nums[j] {
            nums.swap(j - 1, j);
            j -= 1;
        }
        i += 1;
    }
}
```

KVerus generated an explicit correctness contract:

```rust
spec fn sorted(s: Seq<u32>) -> bool {
    forall|a: int, b: int| 0 <= a < b < s.len() ==> s[a] <= s[b]
}

fn insertion_sort(nums: &mut Vec<u32>)
    ensures
        sorted(final(nums)@),
        final(nums)@.to_multiset() == old(nums)@.to_multiset(),
```

The generated contract proves, for every input length:

1. `sorted(final(nums)@)`: the output vector is sorted in nondecreasing order.
2. `final(nums)@.to_multiset() == old(nums)@.to_multiset()`: the output contains exactly the input elements with the same multiplicities.

KVerus generated the helper specifications, loop invariants, termination measures, ghost snapshots, and `swap_preserves_multiset` proof lemma. Verus checked the resulting proof without `assume`, `admit`, or an `external_body` boundary.

During migration, KVerus expanded `nums.swap(j - 1, j)` into two equivalent indexed assignments because the local Verus library does not provide a specification for the Rust slice `swap` operation. The original statement remains beside the rewrite as a comment.

## Run the Rust Version

From the repository root:

```bash
rustc docs/examples/insertion-sort/insertion_sort.rs -o /tmp/kverus-insertion-sort-rust
/tmp/kverus-insertion-sort-rust
```

The runtime tests cover an empty vector, duplicate values, and a ten-element shuffled vector.

## Verify and Run the Verus Version

With `verus` on `PATH`:

```bash
verus docs/examples/insertion-sort/insertion_sort_verus.rs --no-cheating
verus docs/examples/insertion-sort/insertion_sort_verus.rs --no-cheating --compile \
  -o /tmp/kverus-insertion-sort-verus
/tmp/kverus-insertion-sort-verus
```

The checked-in result was validated with the local Verus build `0.2026.08.01.ff8a251` (`macos_aarch64`). Both verification commands reported:

```text
verification results:: 4 verified, 0 errors
```
