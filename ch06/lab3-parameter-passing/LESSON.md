# Lab 3 · 参数传递机制（§6.4.1）

同一段调用代码，只改工作区里的 `pass-mode` 策略，观察调用者能看到的副作用。

| 机制 | 形参槽里放什么 | swap(a,b) | bump(i,i) | sum(i,1,5,i*i) |
|---|---|---|---|---|
| value | 实参的值（拷贝） | 不交换 `1 2` | `1` | 只求值一次：`5` |
| reference | 实参的地址 | 交换 `2 1` | 两个形参是同一地址：`12` | `term` 是表达式，传的是临时变量的地址：`720` |
| value-result | 进入时拷贝，返回时按顺序写回 | `2 1` | 后写回的覆盖先写回的：`11` | `605` |
| name | thunk：表达式加上调用者的 AR，每次使用都重新求值 | `2 1` | `12` | Jensen's device：`55` |

要点：
- 传引用时，如果实参是表达式而不是变量，编译器会先分配一个临时变量再传它的地址（引擎里显示为 `%temp`）。
- 传值-结果和传引用的区别只在**别名**出现时才看得出来，比如 `bump(i,i)`。
- 传名是在调用者的环境里求值。thunk 求值的次数可以从 `stats.thunk-evals` 看到。
- 策略可以按过程、按形参分别设置，例如 `jensen-only` 只让 `sum` 的 `k` 和 `term` 按名传递。

```bash
python3 -m eac run ch06/lab3-parameter-passing -m all-name
python3 -m eac loop ch06/lab3-parameter-passing all-value-result
```

## English summary
One program, four binding policies selected by rebinding `pass-mode`. Aliasing (`bump(i,i)`) separates reference from
value-result, and Jensen's device separates name from everything else.
