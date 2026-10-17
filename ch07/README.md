# 第 7 章 · 代码形态（3rd ed. "Code Shape"）

节号参照第 2 版的编排：§7.3 算术运算（§7.3.1 减少寄存器需求，§7.3.3 表达式里的函数调用与副作用），§7.4 布尔与关系运算（§7.4.1 表示方式，§7.4.2 关系运算的硬件支持），§7.5 数组（§7.5.1 引用向量元素，§7.5.2 存储布局，§7.5.3 引用数组元素，§7.5.4 下标检查），§7.8.3 case 语句。第 3 版第 7 章的结构相近，个别小节的编号可能不同。这里的讲解和例子都是原创的，没有摘录书中文字或图。

本章用一个新的引擎 [`engine/codeshape.aura`](../engine/codeshape.aura)：
- 一个很小的源语言（变量、多维数组、算术、关系与布尔运算、`inc!`、`if`/`while`/`case`），
- 一个树遍历式代码生成器，输出类 ILOC 的三地址码。虚拟寄存器按栈的方式分配，代码里的寄存器个数就是峰值寄存器压力；
- 一个 ILOC 解释器，在按字节寻址的内存上真正执行生成的代码，统计执行的指令、load、乘法、比较、分支和跳转次数；
- 一个直接解释源程序的参考解释器，用来判断生成的代码是否“算对了”（输出里的 matches / DOES NOT MATCH）。

生成器在每个需要决定代码形态的地方都会调用工作区里的一个 define（[`policy.aura`](policy.aura)）。和第 6 章一样，用 `mutate:rebind` + `eval-current` 换掉其中一条，用 `ast:snapshot` / `ast:restore` 回滚，并检查源码逐字节恢复。

| Lab | 演示内容 | 可变异的工作区策略 | 检查项 |
|---|---|---|---|
| [lab1-eval-order](lab1-eval-order/LESSON.md) | Sethi-Ullman 顺序与寄存器需求（3 vs 6）；有副作用时不能重排 | `eval-first`, `su-need`, `may-reorder?` | 6 |
| [lab2-booleans](lab2-booleans/LESSON.md) | 数值编码与位置编码；短路求值；保护条件 | `bool-encoding`, `short-circuit?`, `bool-op-code` | 7 |
| [lab3-arrays](lab3-arrays/LESSON.md) | 行主序、列主序、间接向量、dope vector、下标检查 | `array-layout`, `extent`, `index-origin`, `bounds-check?`, `dope-vector?` | 9 |
| [lab4-case](lab4-case/LESSON.md) | 线性查找、二分查找、跳转表；密度规则；范围检查 | `case-strategy`, `sort-case-keys?`, `jump-range-check?` | 6 |

每个 lab 的命名变异分两类：一类是**合法但代价不同**的选择（比如列主序、全部用跳转表），检查项核对代价；另一类是**错误**的选择，有的让寄存器需求暴涨，有的**静默算错**，检查项核对生成的代码与语言语义不一致。

## 最小闭环
```bash
python3 -m eac loop ch07/lab1-eval-order reorder-across-effects --record
```
1. 用 v0 策略生成 ILOC、执行，与参考解释器对比（matches）。
2. `ast:snapshot` + `mutate:rebind may-reorder?` 换成错误的策略，`eval-current`。
3. 重新生成并执行：寄存器从 3 降到 2，但输出 18 ≠ 17（DOES NOT MATCH）。
4. `ast:restore` + `eval-current`，重新生成，代码、统计和输出都回到原样，工作区源码逐字节恢复。
5. `--record` 记进进度文件；`python3 -m eac --chapter ch07 exercise next` 按掌握情况出下一题。

每个 lab 的闭环记录在 [`results/`](../results/) 下的 `loop-ch07-*.txt`。
