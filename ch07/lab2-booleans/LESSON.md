# Lab 2 · 布尔值与关系运算的编码（§7.4.1, §7.4.2）

## 要点
- 布尔表达式出现在两种地方：
  - **值上下文**：结果要存进变量或打印，`(set! p (< a b))`。
  - **分支上下文**：结果只用来决定往哪走，`(if (< a b) ...)`。
- 两种编码：
  - **数值编码**：把真假算成寄存器里的 0/1（`cmp_LT r1, r2 => r3`），`and`/`or`/`not` 变成对 0/1 的运算。
  - **位置编码（控制流编码）**：不产生 0/1，“值”就是控制流到达的位置：`cbr r -> L真, L假`。
- 合理的组合是：值上下文用数值编码，分支上下文用位置编码（本仓库的 v0）。在分支上下文里硬算出 0/1 再分支，或者在值上下文里绕一圈分支再写 1/0，都会多出指令。
- **短路求值**：`(and a b)` 在 `a` 为假时不算 `b`，`(or a b)` 在 `a` 为真时不算 `b`。当 `b` 有副作用或可能出错（除零、越界）时，短路是语言语义的一部分，编译器必须遵守；`b` 是纯的、不会出错时，直接算两边、不加分支往往更快。v0 的 `short-circuit?` 就按这个规则决定。
- 数值编码要保证结果仍是合法的 0/1。用乘法实现 `and` 没问题，用加法实现 `or` 在两边都为真时得到 2。

## 实验程序
- `program.csl`：值上下文的 `or`/`and`，分支上下文的 `and`，以及一个右操作数带 `(inc! n)` 的 `or` 循环（只有 k 为奇数时才该执行 inc!）。
- `guard.csl`：`(and (!= d 0) (> (/ x d) 4))`，左边是除法的保护条件。

| 变异 | 改了什么 | 现象 |
|---|---|---|
| `or-as-add` | 数值 `or` 用 `add` | `p` 打印 **2**：静默错误 |
| `no-short-circuit` | 从不短路 | `n` 是 **6 而不是 3**：静默错误 |
| `no-short-circuit-guard` | 同上，跑 `guard.csl` | d = 0 时照样做除法，**运行时除零** |
| `all-positional` | 值上下文也用位置编码 | 结果对；执行的分支 17 → 25，代码 69 → 100 条 |
| `always-short-circuit` | 纯操作数也短路 | 结果对；分支 17 → 20，执行的指令 173 → 171 |

```bash
python3 -m eac run ch07/lab2-booleans --code
python3 -m eac loop ch07/lab2-booleans no-short-circuit
python3 -m eac loop ch07/lab2-booleans no-short-circuit-guard
```

## 练习
`short-circuit`：循环里 `(and/or 条件 (> (inc! n) 0))`，问最后 n 是多少。答成不短路的结果记为 `no-short-circuit`，下一题会出一道两种理解答案不同的对比题。

## English summary
Booleans are encoded numerically (0/1 in a register) where the value is needed, and positionally (which label
control reaches) where it only picks a branch. Short-circuit evaluation is mandatory when the right operand has a
side effect or can trap, and optional otherwise. Dropping it silently changes `n` from 3 to 6 and turns a guarded
division into a divide-by-zero. Implementing `or` as integer add yields 2, which is not a boolean.
