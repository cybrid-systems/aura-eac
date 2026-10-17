# Lab 3 · 数组寻址（§7.5.1–7.5.4）

## 要点
- 一维数组 `V[lo..hi]`，元素宽度 `w`：`V[i]` 的地址是 `base + (i - lo) * w`。
- 二维 `A[lo1..hi1, lo2..hi2]`，记 `len2 = hi2 - lo2 + 1`：
  - **行主序**（同一行相邻）：`base + ((i - lo1) * len2 + (j - lo2)) * w`
  - **列主序**（同一列相邻）：把两维对调，`base + ((j - lo2) * len1 + (i - lo1)) * w`
  - 更多维时用 Horner 法则逐维“乘上下一维的长度再加下一个下标”。
- **间接向量**：先有一个行指针向量，每个指针指向一行。访问 `A[i,j]` 时先取出第 i 行的指针，再加上 `(j - lo2) * w`。不用乘行长，但每次访问多一次 load，而且各行可以不等长。
- **dope vector**：数组作为参数传进来、形状在编译时不知道时，下界、上界和长度都放在一个描述符里，代码在运行时从里面读。本仓库每个数组都带一个 dope vector（每维 4 个字：lo, hi, origin, extent），`dope-vector?` 决定代码是读它还是把常数直接编进指令。
- **下标检查**：每个下标和 lo、hi 各比一次，越界就跳到陷阱。代价是每个下标两次比较和两次分支。去掉检查后，越界访问会静默读写别的元素甚至别的数组。

## 实验程序
`A[1..3, 1..4]` 和紧跟在后面的 `B[0..3]`，`A[i,j] = 10*i + j`，打印几个元素。`oob.csl` 访问不存在的 `A[2,5]`。

本仓库里变量从地址 0 开始，数组从 256 开始；A 的 dope vector 占 32 字节，所以 A 的数据从 288 开始。

| 变异 | 改了什么 | 现象 |
|---|---|---|
| `column-major` | 列主序 | 输出相同；`A[2,3]` 的地址 312 → 316 |
| `indirection` | 间接向量 | 输出相同；load 次数 87 → 102 |
| `dope-vector` | 运行时读 dope vector | 输出相同；load 次数 87 → 204 |
| `no-bounds-check` | 去掉下标检查（跑 `oob.csl`） | `A[2,5]` **静默读到 `A[3,1]` = 31**，语言规定应报越界 |
| `forget-lower-bound` | `index-origin` 恒为 0 | 每个地址偏后 20 字节，`A[3,4]` 写进了 **B[0]**：静默错误 |
| `extent-off-by-one` | `extent = hi - lo` | 行长少 1，`A[1,4]` 和 `A[2,1]` 地址相同，**后写的覆盖先写的** |

```bash
python3 -m eac addr ch07/lab3-arrays A 2 3                 # 地址和计算它的 ILOC
python3 -m eac addr ch07/lab3-arrays A 2 3 -m column-major
python3 -m eac loop ch07/lab3-arrays forget-lower-bound
python3 -m eac loop ch07/lab3-arrays no-bounds-check
```

## 练习
`array-address`：随机的上下界（高等级会出现 0、负数的下界）和布局，给出首元素地址，问某个元素的地址。答成另一种布局的地址记为 `row-vs-column`，忘了减下界记为 `lower-bound-omitted`，行长少 1 记为 `extent-off-by-one`。

## English summary
Row-major address = base + ((i - lo1) * len2 + (j - lo2)) * w; column-major swaps the roles of the dimensions.
Indirection vectors replace the multiply by a row length with an extra load per dimension. Dope vectors move
bounds and extents to run time. Forgetting the lower bound or the +1 in the extent produces addresses that alias
other elements, or even another array, with no error. Removing range checks lets A[2,5] read A[3,1].
