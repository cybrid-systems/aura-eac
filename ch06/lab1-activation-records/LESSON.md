# Lab 1 · 活动记录与调用栈（§6.2, §6.3.1）

## 要点（自己的话）
- **过程调用 = 一次激活。** 每次调用都要有一块私有存储，放这次激活自己的东西：形参、局部变量、返回地址、指向别的激活的链接。这块存储就是**活动记录（AR）**。
- **递归时，同一个过程会有多个 AR 同时存活。** `fact(4)` 正在等 `fact(3)` 的结果时，两份 `k`（4 和 3）必须同时存在，所以 `k` 不能放在固定地址。
- **调用和返回严格配对、后进先出。** 最后进去的调用最先返回，所以 AR 可以放在栈上，返回时直接弹掉。
- AR 的布局由**链接约定**决定，见 Lab 4。这里用默认布局：`ret | dynamic | static | params | locals | saved`。

## 在 Aura 里看到什么
```bash
python3 -m eac run ch06/lab1-activation-records --trace      # call/return 配对 + 每帧的 k
python3 -m eac loop ch06/lab1-activation-records no-param-area
python3 -m eac loop ch06/lab1-activation-records no-return-address
```
- 执行历史中，每条 `call #n` 都对应一条 `return #n`，嵌套次序就是栈的形状。
- `(break "fact entered")` 会对所有活着的帧拍快照。第一次快照里只有 `main` 和 `fact(k=4)`。最深的那次（k=1）有 5 个帧。
- `no-param-area`：把 `frame-areas` 改成没有参数区。调用方在 precall 序列里找不到 `k` 的槽位，Aura 会报 `has no 'p:k' slot`。
- `no-return-address`：去掉返回地址槽。被调用者执行完之后，在 epilog 里不知道该跳回哪里。

## 自测
`python3 -m eac exercise next`，概念 `ar-recursion`：最大栈深度是多少，某一帧返回什么值。

## English summary
One activation record per call. Recursive calls keep several ARs of the same procedure alive at once, so locals
cannot live at fixed addresses. Calls and returns nest LIFO, so ARs go on a stack. The two mutations take away
the parameter area and the return-address slot, and show which part of the linkage each one serves.
