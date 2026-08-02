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
