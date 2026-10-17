# Lab 1 · 求值顺序与寄存器压力（§7.3.1, §7.3.3）

## 要点
- 树遍历式的代码生成器对每个结点做两件事：先为两个操作数生成代码，再发一条运算指令。**先生成哪个操作数**不影响结果，但会影响同时活着的寄存器有多少。
- 一个子树的寄存器需求可以自底向上标出来（Sethi-Ullman 标号）：
  - 叶子需要 1 个寄存器（先 load 进来）；
  - 内部结点：两边需求 `l`、`r` 不等时取较大者，相等时是 `l + 1`。
- **先算需求大的子树。** 它算完后只剩 1 个寄存器存着结果，再算另一边时只多占这一个。反过来先算需求小的，它的结果要一直占着寄存器，等需求大的那边算完。
- 右深的表达式（`a + (b * (c - (d / (e + f))))`）是最极端的例子：从左往右算，每进一层就多一个活着的寄存器，6 个叶子要 6 个寄存器；先算右边只要 2 个。真实机器的寄存器有限，多出来的那些就要溢出到内存。
- **重排有前提。** 本仓库的语言规定操作数从左到右求值。只有两边都没有副作用时，调换顺序才看不出来。`(+ x (* (inc! x) 2))` 里右边需求更大，但它会改 `x`，先算它就改变了左边读到的值。

## 实验程序
- `program.csl`：两个表达式。e1 是“茂密”的树（需求 3），e2 是右深的链（需求 2）。
- `effects.csl`：右操作数带 `inc!` 副作用。

生成器把虚拟寄存器按栈的方式分配和释放，所以生成的代码里出现的不同寄存器个数，就是峰值寄存器压力。生成的 ILOC 在 ILOC 解释器上真正执行，再和直接解释源程序的结果比较（“matches / DOES NOT MATCH”）。

| 变异 | 改了什么 | 现象 |
|---|---|---|
| `left-first` | `eval-first` 总是 `"left"` | 输出正确，寄存器 3 → **6** |
| `smaller-first` | 先算需求**小**的一边 | 输出正确，寄存器 6 |
| `flat-labels` | `su-need` 漏掉相等时的 +1 | 所有结点需求都是 1，排序退化成从左到右，寄存器 6 |
| `reorder-across-effects` | `may-reorder?` 恒为真 | 寄存器 3 → 2，但打印 **18 而不是 17**：静默错误 |

```bash
python3 -m eac run ch07/lab1-eval-order --code                    # 看 ILOC：e2 先 load e、f，最后才 load a
python3 -m eac loop ch07/lab1-eval-order left-first               # 寄存器 3 -> 6 -> 回滚 3
python3 -m eac loop ch07/lab1-eval-order reorder-across-effects   # 省了一个寄存器，结果错了
```

## 练习
- `su-registers`：随机生成表达式树，问按某种顺序生成代码要几个寄存器。答成另一种顺序的数会记为 `left-first-registers`，答成叶子个数记为 `leaf-count`。对比题专门用右深树，两种顺序的差别最大。
- `reorder-effects`：带 `inc!` 的表达式打印什么。答成重排后的结果记为 `reorder-side-effects`。

## English summary
Sethi-Ullman labels give each subtree's register need: a leaf needs 1; an interior node needs max(l, r), or l + 1
when l = r. Generating the needier operand first keeps peak pressure at the root's label. Here a right-deep chain
needs 2 registers that way and 6 when generated left to right. Reordering is legal only when neither operand has a
side effect. The `reorder-across-effects` mutation saves a register and silently prints 18 instead of 17.
