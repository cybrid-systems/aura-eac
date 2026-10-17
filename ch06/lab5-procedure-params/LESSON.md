# Lab 5 · 过程参数（§6.4.1, §6.4.3）——最小闭环的"更难变体"

把过程当参数传出去时，光传代码地址不够，还必须带上**它声明处的环境**，也就是将来调用它时要用的静态链。在本引擎里，`(proc-ref addn)` 生成一个 `("closure" addn AR)`，其中的 AR 是创建闭包时沿静态链找到的 `outer` 的 AR。

- 正确的约定（`closure-link = env`）：`apply` 里调用 `f` 时，`addn` 的静态链指向 `outer` 的 AR，`n = 5`，输出 11。
- `closure-links-caller`：静态链指向调用者 `apply`，而 `apply` 恰好也有一个局部变量 `n = 1000`，输出 2001，静默出错。
- `access-dynamic-chain` 的结果一样，原因也一样，都是取到了调用者的变量。

## English summary
A procedure-valued parameter has to carry the AR it was created in. If it is linked to its caller instead, the call
silently reads the caller's `n`.
