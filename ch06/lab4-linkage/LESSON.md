# Lab 4 · 逐步搭建链接约定（§6.3.1, §6.5）

一个调用分成四段代码：调用前（precall）、序言（prolog）、尾声（epilog）、返回后（postreturn）。链接约定规定这四段各自负责什么，以及 AR 怎样布局。这一节从最小的约定开始，每次加一个区。每一步都用 `mutate:rebind frame-areas` 换掉布局，然后跑同一组测试程序：

| 阶段 | 布局 | 能跑通的程序 |
|---|---|---|
| S1 | `ret` | t1（只有调用和返回） |
| S2 | `ret params` | + t2（带参数的递归） |
| S3 | `ret params locals` | + t3（局部变量） |
| S4 | `ret dynamic static params locals` | + t4（访问两层外的变量，计数恰好 2 次静态链跳转） |
| S5 | `… saved` 并且 `callee-saves = (r1)` | + t5（调用者放在 r1 里的值在调用后还在） |

检查项：每一阶段的程序必须"该过的过、不该过的不过"，`tri` 的各字段偏移和表中一致，t4 的静态链跳转次数为 2。每一阶段做完都会 `ast:restore`，并检查工作区源码逐字节恢复。

说明：引擎返回时用自己的栈弹出 AR，所以 `dynamic` 槽在这里只用于展示和动态链实验，`ret` 槽则是必需的。

```bash
python3 -m eac check ch06/lab4-linkage
```

## English summary
The linkage convention is built one area at a time (return address, then params, locals, links, and the callee-saved area).
At every stage the lab asserts which test programs run, what the frame offsets are, and how many links are followed.
