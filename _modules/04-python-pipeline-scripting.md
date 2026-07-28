---
layout: default
title: Module 4 — Python & Pipeline Scripting
permalink: /modules/python-pipeline/
---

## Module 4 — Python & Pipeline Scripting

**Core job:** solve with standard-library structures (`dict`, `set`, `list`) — Meta's Python round is not a Pandas round.

**Pattern inventory:**
- `dict` for O(1) lookups, JSON parsing, grouping, frequency counting.
- `set` for dedup and relationship operations (intersections/differences).
- `list`/`tuple` for sorting with `key=lambda x: x[1]`, slicing, comprehensions.
- Interval/overlap merges, string/log parsing, native `GROUP BY` via nested dicts, sliding-window rolling metrics.
- Defensive habits: handle `[]`, `None`, malformed rows, and use `dict.get(key, default)` instead of bare indexing.

**Worked problem:** merge overlapping session intervals and compute total non-overlapping active time.

```
Input:   [1,4], [3,6], [8,10], [10,12]
Merged:  [1,6], [8,12]  →  Active time = (6-1) + (12-8) = 9
```

```python
def calculate_total_active_time(intervals: list[list[int]]) -> int:
    """
    Merge overlapping intervals and sum active duration.
    Time: O(N log N) from the sort. Space: O(N).
    """
    if not intervals:
        return 0

    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]

    for start, end in sorted_intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1][1] = max(prev_end, end)
        else:
            merged.append([start, end])

    return sum(end - start for start, end in merged)


if __name__ == "__main__":
    print(calculate_total_active_time([[1, 4], [3, 6], [8, 10], [10, 12]]))  # 9
```

Say the complexity out loud unprompted (`O(N log N)`, driven by the sort) — it signals you're not pattern-matching from memory.

