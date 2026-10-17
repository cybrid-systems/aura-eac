# Lab 2 · 静态链与动态链（§6.3.1, §6.4.3）

## 要点
- **动态链**指向**调用者**的 AR，表示"谁调用了我"，返回时用它恢复调用者的环境。
- **静态链（access link）**指向**词法父过程最近一次激活**的 AR，表示"我是在哪里声明的"。在 Algol/Pascal 这类允许嵌套过程的语言里，非局部变量要靠它找到。
- **建立静态链：** 调用者在第 `c` 层，被调用者在第 `e` 层，从调用者的 AR 出发沿静态链走 `c - e + 1` 跳，就到了被调用者父过程的 AR。
  - 调用自己的子过程时走 0 跳，也就是指向调用者自己。
  - 调用兄弟过程或递归调用自己时走 1 跳。
  - 顶层过程不需要静态链，因为它的非局部名字都是全局变量，地址固定。
- **访问非局部变量：** 在第 `u` 层使用、第 `d` 层声明的名字，要走 `u - d` 跳。跳数在编译时就能算出来，与运行时调用了多少层无关。这对坐标 ⟨层差, 偏移⟩ 一般叫做静态坐标。

## 实验程序
`main` 声明了 `x`。`p` 也声明了自己的 `x`，遮住了 `main` 的。`r` 嵌套在 `q` 里，用的是 `main` 的 `x`。`p` 会调用 `q`。
- 按调用者往回走（动态链）：`r → q → p → main`
- 按声明位置往回走（静态链）：`r → q → main`

| 变异 | 改了什么 | 现象 |
|---|---|---|
| `link-to-caller` | `static-link-hops` 恒为 0 | 输出 `[100, 7, 8]`，**静默出错**：`r` 读到的是 `p` 的 `x` |
| `access-dynamic-chain` | 非局部访问沿动态链走 | 输出相同，其实就是动态作用域 |
| `access-off-by-one` | 跳数少算 1 | 停在 `q`，`q` 没有 `x`，**直接报错** |

```bash
python3 -m eac loop ch06/lab2-static-links link-to-caller      # 帧快照：变异前后 q 的静态链分别指向 main / p
```
要注意的是，最危险的变异不会报错。程序照常跑完，只是悄悄读错了变量，所以要看快照里的静态链，或者对照输出。

## 更深的嵌套
练习 `static-link-target` 和 `nonlocal-hops` 会随机生成 3 到 5 层嵌套的程序，难度随掌握程度上升。答错时如果你给出的是调用者，会被记为 `static-vs-dynamic` 混淆，下一题会专门出静态链和动态链指向不同 AR 的对比题。

## English summary
The dynamic link points to the caller and the static link to the lexical parent's latest AR. Setting up the static link takes
`caller_level - callee_level + 1` hops, and a non-local access takes `use_level - decl_level` hops. Linking to the
caller (or walking the dynamic chain) gives dynamic scoping: the program still runs, but it reads the wrong variable.
