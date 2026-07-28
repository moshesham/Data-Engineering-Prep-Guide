---
layout: default
title: Module 4 — Python & Pipeline Scripting
permalink: /modules/python-pipeline/
---

## Module 4 — Python & Pipeline Scripting

**Core job:** solve with standard-library structures (`dict`, `set`, `heapq`, `re`, `list`) — Meta's Python round is usually about data manipulation and algorithmic clarity, not Pandas fluency.

## Table of Contents

1. [Data Structure Patterns](#1-data-structure-patterns)
   1. [Dict-based grouping/aggregation](#11-dict-based-groupingaggregation)
   2. [Set-based relationship problems](#12-set-based-relationship-problems-mutual-connections)
   3. [Heap / priority queue for top-K](#13-heappriority-queue-for-top-k-problems)
2. [String & Log Parsing](#2-string--log-parsing)
   1. [Regex-based extraction](#21-regex-based-extraction-from-raw-log-lines)
   2. [Malformed/missing-field handling](#22-malformedmissing-field-handling)
3. [Interval Problems](#3-interval-problems)
   1. [Merge intervals](#31-merge-intervals)
   2. [Counting concurrent overlaps](#32-counting-concurrent-overlaps-at-a-point-in-time)
4. [Sliding Window](#4-sliding-window)
   1. [Fixed-size window](#41-fixed-size-window)
   2. [Variable-size window](#42-variable-size-window)
5. [Complexity Communication](#5-complexity-communication)
   1. [Stating Big-O unprompted](#51-stating-big-o-unprompted)

## 1. Data Structure Patterns

### 1.1 Dict-based grouping/aggregation

Use `dict` when the prompt sounds like SQL in Python:
- count per user
- sum watch time per creator
- group events by day
- build adjacency lists

Canonical pattern:

```python
from collections import defaultdict

watch_by_creator = defaultdict(int)
for user_id, creator_id, watch_seconds in events:
    watch_by_creator[creator_id] += watch_seconds
```

Why interviewers like this:
- linear scan
- constant-time updates on average
- very readable

### 1.2 Set-based relationship problems (mutual connections)

#### Worked problem: mutual friends between two users

Prompt: Given a social graph as a dictionary `{user_id: set(friend_ids)}`, find mutual friends between two users.

```python
def mutual_friends(graph: dict[int, set[int]], user_a: int, user_b: int) -> set[int]:
    """
    Return the set of mutual friends between user_a and user_b.
    Time: O(min(len(friends_a), len(friends_b))) average-case for set intersection.
    Space: O(m) for the result, where m is the number of mutual friends.
    """
    friends_a = graph.get(user_a, set())
    friends_b = graph.get(user_b, set())
    return friends_a & friends_b


if __name__ == "__main__":
    graph = {
        1: {2, 3, 4, 8},
        5: {3, 4, 6, 8},
    }
    print(mutual_friends(graph, 1, 5))  # {3, 4, 8}
```

Why this is the right answer:
- `set` intersection is both simpler and faster than nested loops
- missing users are handled safely with `graph.get(..., set())`

### 1.3 Heap/priority-queue for top-K problems

#### Worked problem: top-5 most-watched creators from a stream

Prompt: Given a stream of watch events `(user_id, creator_id, watch_seconds)`, find the top-5 most-watched creators.

This is a two-step pattern:
1. aggregate watch seconds per creator
2. keep a heap of size `k`

```python
import heapq
from collections import defaultdict
from typing import Iterable


def top_k_creators(
    watch_events: Iterable[tuple[int, int, int]],
    k: int = 5,
) -> list[tuple[int, int]]:
    """
    Return the top-k creators by total watch seconds.

    Output format: [(creator_id, total_watch_seconds), ...] sorted descending.

    Time:
        O(n) to aggregate + O(c log k) to maintain heap,
        where n = number of events and c = number of distinct creators.
    Space:
        O(c) for the aggregation map + O(k) for the heap.
    """
    total_watch_by_creator = defaultdict(int)

    for _user_id, creator_id, watch_seconds in watch_events:
        total_watch_by_creator[creator_id] += watch_seconds

    min_heap: list[tuple[int, int]] = []

    for creator_id, total_watch in total_watch_by_creator.items():
        item = (total_watch, creator_id)
        if len(min_heap) < k:
            heapq.heappush(min_heap, item)
        else:
            heapq.heappushpop(min_heap, item)

    return [
        (creator_id, total_watch)
        for total_watch, creator_id in sorted(min_heap, reverse=True)
    ]


if __name__ == "__main__":
    sample_events = [
        (1, 101, 40),
        (2, 101, 25),
        (3, 102, 80),
        (4, 103, 15),
        (5, 104, 50),
        (6, 105, 65),
        (7, 106, 35),
        (8, 102, 45),
        (9, 104, 55),
        (10, 105, 20),
    ]
    print(top_k_creators(sample_events, k=5))
```

Key interview note:
- `heapq.nlargest()` is perfectly fine if all totals are already materialized
- the fixed-size min-heap is more scalable and demonstrates better streaming intuition

## 2. String & Log Parsing

### 2.1 Regex-based extraction from raw log lines

Use `re` when the input is semi-structured text and fields are not guaranteed to be positionally stable.

Example pattern:

```python
import re

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\S+\s+\S+)\s+user_id=(?P<user_id>\d+)\s+"
    r"event=(?P<event>\w+)\s+watch_ms=(?P<watch_ms>\d+)$"
)
```

Named capture groups improve readability and reduce indexing mistakes.

### 2.2 Malformed/missing-field handling

#### Worked example: parse log lines defensively

Prompt: Parse Apache-style log lines such as:

`"2026-07-20 14:32:01 user_id=98401293 event=reel_view watch_ms=14200"`

One line is malformed and missing a field.

```python
import re

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"user_id=(?P<user_id>\d+)\s+"
    r"event=(?P<event>[a-zA-Z_]+)\s+"
    r"watch_ms=(?P<watch_ms>\d+)$"
)


def parse_log_lines(lines: list[str]) -> tuple[list[dict], list[dict]]:
    """
    Returns:
        parsed_rows: valid rows
        bad_rows: rows that could not be parsed, with a reason

    Time: O(n * m), where n is number of lines and m is average line length.
    Space: O(n) for output storage.
    """
    parsed_rows: list[dict] = []
    bad_rows: list[dict] = []

    for line_number, line in enumerate(lines, start=1):
        try:
            match = LOG_PATTERN.match(line.strip())
            if not match:
                raise ValueError("line does not match expected format")

            row = {
                "timestamp": match.group("timestamp"),
                "user_id": int(match.group("user_id")),
                "event": match.group("event"),
                "watch_ms": int(match.group("watch_ms")),
            }
            parsed_rows.append(row)

        except Exception as exc:
            bad_rows.append(
                {
                    "line_number": line_number,
                    "raw_line": line,
                    "error": str(exc),
                }
            )

    return parsed_rows, bad_rows


if __name__ == "__main__":
    sample_lines = [
        "2026-07-20 14:32:01 user_id=98401293 event=reel_view watch_ms=14200",
        "2026-07-20 14:32:09 user_id=555 event=reel_like watch_ms=0",
        "2026-07-20 14:32:15 user_id=777 event=reel_view",  # malformed: missing watch_ms
    ]

    parsed, bad = parse_log_lines(sample_lines)
    print("PARSED:", parsed)
    print("BAD:", bad)
```

Why this is strong:
- regex enforces format
- `try/except` prevents one bad row from crashing the whole batch
- malformed rows are preserved for audit/debugging

## 3. Interval Problems

### 3.1 Merge intervals

#### Worked problem: merge overlapping session intervals and compute total non-overlapping active time

```text
Input:   [1,4], [3,6], [8,10], [10,12]
Merged:  [1,6], [8,12]  →  Active time = (6-1) + (12-8) = 9
```

```python
def calculate_total_active_time(intervals: list[list[int]]) -> int:
    """
    Merge overlapping intervals and sum active duration.
    Time: O(n log n) due to sorting.
    Space: O(n) in the worst case.
    """
    if not intervals:
        return 0

    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0][:]]

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

### 3.2 Counting concurrent overlaps at a point in time

#### Worked problem: maximum number of concurrent sessions

Prompt: Given session intervals `(start_time, end_time)`, find the maximum number of concurrent sessions at any instant.

This is **not** the same as merging for total active time. Use a sweep line.

```python
def max_concurrent_sessions(intervals: list[tuple[int, int]]) -> int:
    """
    Treat intervals as half-open: [start, end).
    If one session ends at time t and another starts at time t,
    they are not counted as overlapping.

    Time: O(n log n) due to sorting event points.
    Space: O(n).
    """
    if not intervals:
        return 0

    events: list[tuple[int, int]] = []
    for start, end in intervals:
        events.append((start, 1))   # session starts
        events.append((end, -1))    # session ends

    # Sort by time, then process end events before start events at same timestamp.
    events.sort(key=lambda item: (item[0], item[1]))

    current = 0
    max_seen = 0

    for _time, delta in events:
        current += delta
        max_seen = max(max_seen, current)

    return max_seen


if __name__ == "__main__":
    sessions = [(1, 5), (2, 6), (4, 8), (7, 9), (8, 10)]
    print(max_concurrent_sessions(sessions))  # 3
```

## 4. Sliding Window

### 4.1 Fixed-size window

Use fixed-size windows when the prompt says:
- last `k` events
- average over the last `n` minutes/items
- longest subarray of exact size `k`

Example: moving average over the last 3 watch durations

```python
def moving_average(nums: list[int], k: int) -> list[float]:
    if k <= 0 or k > len(nums):
        return []

    window_sum = sum(nums[:k])
    result = [window_sum / k]

    for right in range(k, len(nums)):
        window_sum += nums[right] - nums[right - k]
        result.append(window_sum / k)

    return result
```

Time: `O(n)`  
Space: `O(1)` extra, excluding output.

### 4.2 Variable-size window

Use variable-size windows when the condition depends on the contents of the current window:
- smallest subarray with sum at least target
- longest substring with at most `k` distinct chars
- longest streak with at most one anomaly

Example: shortest subarray with sum at least `target`

```python
def min_subarray_len(target: int, nums: list[int]) -> int:
    left = 0
    current_sum = 0
    best = float("inf")

    for right, value in enumerate(nums):
        current_sum += value

        while current_sum >= target:
            best = min(best, right - left + 1)
            current_sum -= nums[left]
            left += 1

    return 0 if best == float("inf") else best
```

Time: `O(n)`  
Space: `O(1)`

## 5. Complexity Communication

### 5.1 Stating Big-O unprompted

Say the complexity out loud without waiting to be asked. It signals control, not memorization.

Good examples:
- "This uses a hash map, so the scan is `O(n)` time and `O(c)` space for distinct creators."
- "The heap version is `O(c log k)` after aggregation."
- "The interval solution is `O(n log n)` because sorting dominates."

When relevant, also mention:
- what drives the complexity
- whether the solution is streaming-friendly
- how edge cases are handled (`[]`, missing keys, malformed rows)
