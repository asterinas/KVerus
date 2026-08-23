use vstd::prelude::*;

verus! {

pub assume_specification<T>[ <[T]>::swap ](slice: &mut [T], a: usize, b: usize)
    requires
        a < old(slice)@.len(),
        b < old(slice)@.len(),
    ensures
        final(slice)@ == old(slice)@.update(a as int, old(slice)@[b as int]).update(
            b as int,
            old(slice)@[a as int],
        ),
    no_unwind
;

spec fn sorted(s: Seq<u32>) -> bool {
    forall|a: int, b: int| 0 <= a < b < s.len() ==> s[a] <= s[b]
}

spec fn sorted_before(s: Seq<u32>, end: int) -> bool {
    forall|a: int, b: int| 0 <= a < b < end && b < s.len() ==> s[a] <= s[b]
}

spec fn sorted_except_at(s: Seq<u32>, end: int, gap: int) -> bool {
    forall|a: int, b: int| 0 <= a < b < end && b < s.len() && b != gap ==> s[a] <= s[b]
}

proof fn swap_preserves_multiset(s: Seq<u32>, a: int, b: int)
    requires
        0 <= a < s.len(),
        0 <= b < s.len(),
        a != b,
    ensures
        s.update(a, s[b]).update(b, s[a]).to_multiset() == s.to_multiset(),
{
    broadcast use {
        vstd::seq_lib::group_to_multiset_ensures,
        vstd::multiset::group_multiset_axioms,
        vstd::multiset::group_multiset_properties,
    };

}

fn insertion_sort(nums: &mut Vec<u32>)
    ensures
        sorted(final(nums)@),
        final(nums)@.to_multiset() == old(nums)@.to_multiset(),
{
    let ghost original = nums@;
    let n = nums.len();
    let mut i = 1;
    while i < n
        invariant
            n == nums@.len(),
            1 <= i,
            i <= n || n == 0,
            sorted_before(nums@, i as int),
            nums@.to_multiset() == original.to_multiset(),
        decreases n - i,
    {
        let mut j = i;
        while j > 0 && nums[j - 1] > nums[j]
            invariant
                n == nums@.len(),
                i < n,
                j <= i,
                sorted_except_at(nums@, i + 1, j as int),
                nums@.to_multiset() == original.to_multiset(),
            decreases j,
        {
            let ghost before = nums@;
            nums.swap(j - 1, j);
            proof {
                swap_preserves_multiset(before, (j - 1) as int, j as int);
            }
            j -= 1;
        }
        i += 1;
    }
}

} // verus!
fn main() {
    let mut empty = vec![];
    insertion_sort(&mut empty);
    assert_eq!(empty, vec![]);

    let mut duplicates = vec![4, 2, 4, 1, 2];
    insertion_sort(&mut duplicates);
    assert_eq!(duplicates, vec![1, 2, 2, 4, 4]);

    let mut shuffled = vec![9, 3, 7, 1, 8, 2, 6, 5, 4, 0];
    insertion_sort(&mut shuffled);
    assert_eq!(shuffled, vec![0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
}
