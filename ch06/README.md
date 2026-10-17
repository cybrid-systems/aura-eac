# 第 6 章 · 过程的实现（3rd ed. "Implementing Procedures"；2nd ed. "The Procedure Abstraction"）

节号按第 3 版：§6.2 背景，§6.3.1 Algol 类语言的运行时支持，§6.3.2 面向对象语言的运行时支持，§6.4.1 参数传递，§6.4.2 返回值，§6.4.3 非局部变量的可寻址性，§6.5 标准化链接。第 2 版的编号略有不同。这里的讲解和例子都是原创的，没有摘录书中文字或图。

| Lab | 演示内容 | 可变异的工作区策略 | 检查项 |
|---|---|---|---|
| [lab1-activation-records](lab1-activation-records/LESSON.md) | 递归 `fact` 的执行历史：call/return 配对、每帧的 `k` 和返回值、最多 5 帧同时存活 | `frame-areas`（去掉参数区或返回地址） | 4 |
| [lab2-static-links](lab2-static-links/LESSON.md) | Pascal 风格的嵌套过程：静态链和动态链分别指向哪里；把静态链改错后静默读错变量；跳数少算 1 时报错 | `static-link-hops`, `access-chain`, `access-hops` | 5 |
| [lab3-parameter-passing](lab3-parameter-passing/LESSON.md) | 同一程序在传值、传引用、传值-结果、传名下的输出；别名；Jensen's device | `pass-mode` | 5 |
| [lab4-linkage](lab4-linkage/LESSON.md) | 链接约定分 5 个阶段搭建；每阶段检查哪些程序能跑、字段偏移、链跳转次数 | `frame-areas`, `callee-saves` | 5 阶段 |
| [lab5-procedure-params](lab5-procedure-params/LESSON.md) | 过程参数要带静态链（闭包），这是最小闭环的"更难变体" | `closure-link`, `access-chain` | 3 |
| [lab6-objects](lab6-objects/LESSON.md) | 对象记录、方法向量、覆盖时保持原槽位、虚方法分派 | `dispatch-class` | 2 |

所有策略的初始版本（v0，即教科书上的正确做法）都在 [`policy.aura`](policy.aura) 里。

## 最小闭环
```bash
python3 -m eac loop ch06/lab2-static-links link-to-caller --record
```
1. 用正确的约定运行程序，`(break ...)` 处会对所有活着的 AR 拍快照。
2. 用 `ast:snapshot` 加 `mutate:rebind static-link-hops` 换上一个错误的约定，再 `eval-current`。
3. 重新运行，观察输出变化或错误，以及快照里静态链指向哪里。
4. 用 `ast:restore` 加 `eval-current` 回滚，再运行，并检查工作区源码逐字节恢复。
5. 用 `--record` 把这次实验记进进度文件，然后 `python3 -m eac exercise next` 会根据掌握情况出下一题，比如更深的嵌套或过程参数。
