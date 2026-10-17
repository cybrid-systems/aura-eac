# Lab 6 · 对象记录与方法向量（§6.3.2，简要对比）

- **对象记录（object record）：** 第 0 槽是指向所属类的方法向量的指针，后面依次是继承来的字段和本类新增的字段。所以子类对象的前缀布局和父类相同，父类的代码按同样的偏移访问字段不会出错。
- **方法向量：** 继承来的方法保持原来的槽位。子类覆盖一个方法时，替换的是同一个槽里的实现，新增的方法追加在末尾。
- **虚方法调用：** 先从对象记录的第 0 槽取出方法向量，再按槽位号取出实现。它查的是对象**运行时类**的向量，和变量的声明类型无关。
- 与 Algol 风格对比：方法里访问的"非局部名字"主要是对象字段，靠 `self` 加上字段偏移找到，不靠静态链。

变异 `dispatch-declared` 改成按声明类型取方法向量，相当于静态绑定。`(send-as Counter d bump)` 于是绕过了 `Loud` 覆盖的 `bump`，输出从 20 变成 11。

## English summary
An object record starts with a method-vector pointer, followed by the inherited fields and then the class's own fields.
An override keeps the slot of the method it replaces. Virtual dispatch indexes the runtime class's vector, and the mutation shows what static binding would do instead.
