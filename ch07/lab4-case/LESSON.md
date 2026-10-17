# Lab 4 · case 语句的三种实现（§7.8.3）

## 要点
- **线性查找**：按顺序把选择子和每个键比较一遍，命中就跳。代码最短，命中第 i 个键要比较 i 次，落到 else 要比较全部。分支少（比如 ≤ 3 个）时最划算。
- **二分查找**：键排好序，每次和中间的键比较，再决定去左半还是右半。比较次数是 O(log n)。**前提是键有序**，乱序时会被引到错误的一半。
- **跳转表**：键落在 `lo..hi` 里且足够密时，建一张 `hi - lo + 1` 个字的表，第 `k - lo` 项存分支 k 的地址，没有的键填 else 的地址。只需要一次范围检查、一次 load、一次间接跳转，与分支数无关。代价是表的大小随**键的跨度**而不是分支数增长。
- **范围检查不能省。** 选择子不在 `lo..hi` 里时，`(k - lo) * w` 会落在表外，读到的可能是别的数据，也可能正好是另一张表里的一个合法地址。
- 编译器通常按**密度**选：分支很少用线性查找，键密集用跳转表，其余用二分。本仓库 v0 的 `case-strategy` 是：≤ 3 个分支用 linear；跨度 ≤ 2 × 分支数用 jump；否则用 binary。

## 实验程序
`program.csl` 有三类 case：键 1..6 全有（密）、只有 3 个键（小）、6 个键分散在 1..5000（稀，源码里故意乱序）。`adjacent.csl` 有两条紧挨着的密集 case，第一张表后面就是第二张表。

| 变异 | 改了什么 | 现象 |
|---|---|---|
| `always-linear` | 全部线性查找 | 结果对；比较 109 → 141 次 |
| `always-jump` | 全部跳转表 | 结果对；比较降到 77 次，但表从 6 个字涨到 **15011 个字** |
| `binary-unsorted` | 二分查找不排序 | k = 1 和查 10 的那次**静默落进 else** |
| `no-range-check` | 跳转表不做范围检查（跑 `adjacent.csl`） | k = 5 读到第二张表的第一项，**跳进第二条 case 的分支**，中间的输出被跳过 |

```bash
python3 -m eac run ch07/lab4-case                         # 每条 case 选了哪种实现，比较次数，表大小
python3 -m eac loop ch07/lab4-case always-jump
python3 -m eac loop ch07/lab4-case no-range-check
```

## 练习
`case-cost`：随机的键集合和选择子，问线性查找或二分查找各执行几条比较指令，或者 v0 的密度规则会选哪种实现。答成另一种查找方式的次数记为 `linear-vs-binary`，选错实现记为 `density`。

## English summary
A case statement compiles to a linear search, a binary search over sorted keys, or a jump table indexed by
`k - lo`. The choice trades comparisons against table size, which grows with the key span. Here, using jump tables
everywhere cuts comparisons from 109 to 77 but needs 15011 table words. Binary search over unsorted keys and a jump
table without a range check both miscompile silently. The latter jumps into a neighbouring statement's table.
