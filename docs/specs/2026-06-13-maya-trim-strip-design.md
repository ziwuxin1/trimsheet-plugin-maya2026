# Maya 边线生成 Trim 面片插件 — 设计文档

- 日期: 2026-06-13
- 状态: 待用户审阅
- 作者: Junliang + Claude (brainstorming)
- 代号: `trim_strip`

## 1. 目标 (Overview)

一个 Maya Python 工具:用户双击选中一条边线 loop,点一个按钮,沿这条边线生成一片紧贴曲面的多边形面片 (strip / ribbon);生成后可实时调整 **宽度 (width)** 和 **沿法线浮起距离 (offset)**;再一键把 UV "打直"成笔直矩形 (保持世界比例、可横向平铺),用来贴预先做好的 trim sheet;最后一键收尾:删历史 + Center Pivot,得到干净的静态网格。

典型用途:在硬表面/场景模型的转折边上快速贴出 trim 条带细节。

## 2. 目标环境 (Target Environment)

- Maya **2026.3**
- Python **3.11**
- UI: **PySide6 / Qt6** (shiboken6),停靠窗用 `maya.app.general.mayaMixin.MayaQWidgetDockableMixin`
- 几何: **OpenMaya API 2.0** (`maya.api.OpenMaya`,简称 `om`)
- 撤销: 变更操作实现为 **API 2.0 MPxCommand**(原生 undo/redo);因此本工具是一个可加载的 Maya **command 插件**
- 单元测试: Maya 2026 自带 **mayapy** + pytest

> 说明:这里的 "插件 (plugin)" 指注册 MPxCommand 的命令插件,**不是** 自定义 DG 节点 (MPxNode)。"实时/procedural" 来自缓存帧 + 重算,不依赖 DG 求值。

## 3. 用户操作流程 (Workflow)

1. 在视口双击选中一条边线 loop(Maya 原生 loop 选择,开环或闭环均可)。
2. 打开工具面板,点【从所选边线生成面片】。→ 生成 strip,自动写好初始 UV,并选中新面片。
3. 拖动【宽度】【法线偏移】滑块,面片实时更新。
4. (可选)调【UV 平铺密度】、勾【翻转法线】。
5. 点【打直 UV】→ 重新写一遍笔直、世界比例的 UV,并把 UV 壳归位到原点。
6. 在 UV 编辑器里把 UV 壳挪到 trim sheet 对应条带上(用户手动,或后续版本辅助)。
7. 点【完成:删历史 + Center Pivot】→ 固化为静态网格。

## 4. 架构决策 (Architecture Decision)

**采用方案 B:缓存帧 + 原地改点。**

生成时,对边线 loop 上每个顶点算一次"基准帧" `{P, N, W, 弧长}` 并缓存(存为面片 transform 上的隐藏属性 + UI 内存)。之后调整宽度/偏移时,拓扑不变,只用纯向量数学重算 `2×N` 个顶点坐标并原地写回 → 毫秒级、丝滑。

被否决的备选:

- **方案 A:自定义 MPxNode(真 DG 历史)** — 最正统但开发量大、跨机要加载节点插件、更脆。本工具调整只涉及移动既有顶点(拓扑不变),不需要 DG 节点也能做到真正实时,故不采用。若日后需要通道盒里可见可删的真实历史节点,可升级到 A。
- **方案 C:每次改都删了重建** — 会刷爆 undo、闪烁、强依赖源网格,不采用。

**"清除历史" 的语义(重要):** 方案 B 下没有 Maya 原生构造历史节点。所以【完成】按钮做三件事:① `delete(ch=True)` 删掉任何残留构造历史;② 移除插件存的 `ts*` 隐藏属性(结束实时编辑、面片变纯静态);③ `Center Pivot`。

## 5. 核心几何算法 (Core Geometry)

沿边线把顶点排成有序链 `P[0..N-1]`(开环 N 个点,闭环额外首尾相接)。逐顶点构造局部坐标系:

- `P_i` = 顶点世界坐标(取自源网格)
- `N_i` = 源网格在该点的平滑顶点法线(世界空间,单位化)
- `T_i` = 沿线切向 = `normalize(P[i+1] − P[i−1])`;开环端点用单侧差分;闭环首尾用环绕邻居
- `W_i` = `normalize(cross(N_i, T_i))` — 贴着曲面的"横向"方向

两条轨道点(宽度居中对称 + 沿法线浮起):

```
half = width / 2
L_i = P_i + N_i * offset + W_i * half
R_i = P_i + N_i * offset - W_i * half
```

面 (quad):对每段 `i → i+1` 连 `(L_i, R_i, R_{i+1}, L_{i+1})`;闭环时最后一段 `N-1 → 0` 也连。绕序保证面法线朝 `+N`(可被【翻转法线】反向)。

几何意义:`W` 垂直于法线 → 面片贴合曲面弯曲走向(翻过圆角也跟着弯);`offset` 沿法线整体抬起,避免与源网格穿插 / z-fighting。

退化处理:当 `N_i` 与 `T_i` 近似平行(`cross` 趋零),用邻帧的 `W` 或世界 up 作回退。

## 6. UV 打直 (UV Authoring)

不使用 Unfold;**解析式直接写 UV**,因为 strip 拓扑就是规整的 `2×N` 网格:

```
arclen_i = Σ |P_k − P_{k-1}|   (k=1..i, arclen_0 = 0)
density  = UV单位 / 世界单位   (一个旋钮, 默认 1.0)
U(L_i)=U(R_i)= arclen_i * density
V(L_i)= width * density        V(R_i)= 0
```

结果:弯曲的 loop 在 UV 空间里变成一条 **笔直水平矩形**(这就是"打直");U、V 用同一世界→UV 比例 → 贴图不拉伸,且沿弯折在 U 方向连续平铺,符合 "保持世界比例可平铺"。

生成时自动写一遍;【打直 UV】按钮重写这套规范 UV 并把壳移到 UV 原点。宽度变化会按上式同步更新 V。

## 7. 实时调整机制 (Live Adjustment)

- 生成时缓存 `{P, N, W, arclen}` + 拓扑 + 当前参数 `(width, offset, density, flip, closed)`,存为 transform 隐藏属性(见 §9)并在 UI 内存留副本。
- 滑块变化 → 纯向量重算 `2N` 个轨道点(及 UV)→ 原地写回。
- 拖动期间用 `MFnMesh.setPoints` 做**瞬时预览**(不入 undo);松开滑块时提交一次 MPxCommand → **整段拖动 = 一步 undo**。
- 源网格在生成后即使被删除/修改,也不影响后续调整(基准帧已缓存)。

## 8. 一键完成 (Finalize)

`finalize(transform)`:

1. `cmds.delete(transform, constructionHistory=True)`
2. 移除所有 `ts*` 隐藏属性(结束实时编辑)
3. `cmds.xform(transform, centerPivots=True)`

得到轴心居中、无历史、可直接贴图的静态网格。实现为可撤销的 MPxCommand。

## 9. 数据模型 (Cached Attributes)

生成的面片 transform 上写入隐藏属性(`finalize` 时清除):

| 属性 | 类型 | 含义 |
|---|---|---|
| `tsIsStrip` | bool | 标记:这是本工具生成的可调面片 |
| `tsVersion` | int | 数据 schema 版本 |
| `tsClosed` | bool | 是否闭环 |
| `tsWidth` / `tsOffset` / `tsDensity` | float | 当前参数 |
| `tsFlip` | bool | 是否翻转法线 |
| `tsBaseP` / `tsBaseN` / `tsBaseW` | doubleArray | 展平的逐顶点 P / N / W(各 `3*N`) |
| `tsArcLen` | doubleArray | 逐顶点累计弧长(`N`) |

## 10. 模块结构 (Module Structure)

各单元单一职责、接口清晰、可独立理解与测试。`core/` 不导入 `cmds`、无场景副作用。

```
trim_strip/
  __init__.py
  core/
    geometry.py     纯函数: order_loop / compute_frames / arclen / rail_points / faces / uvs
  maya_io/
    selection.py    读当前边选 → 有序顶点 id、世界 P/N、判开闭环、校验; 友好报错
    mesh_build.py   MFnMesh 建网格 / setPoints 原地更新 / 写 UV
    procedural.py   存读缓存帧(§9)、recompute_and_update、finalize
  commands.py       注册 MPxCommand: tsGenerate / tsUpdate / tsFinalize (原生 undo)
  tool.py           编排层(UI 调它): generate / set_width / set_offset / set_density / set_flip / straighten_uv / finalize
  ui/
    panel.py        PySide6 可停靠面板; 滑块/按钮; 拖动预览 + 松手提交
  install/
    install.py      安装货架按钮; 加载命令插件
  tests/
    test_geometry.py  纯几何单测 (mayapy + pytest)
```

### 关键接口 (草拟)

`core/geometry.py`(纯函数,输入/输出为数组或 `om.MVector/MPoint`):

- `order_loop(edge_pairs: list[(int,int)]) -> (ordered_vertex_ids: list[int], is_closed: bool)` — 图遍历排序,可单测
- `compute_frames(P, N, is_closed) -> (T, W)`
- `compute_arclen(P, is_closed) -> list[float]`
- `build_rail_points(P, N, W, width, offset) -> list[MPoint]`(顺序 `L0,R0,L1,R1,…`)
- `build_faces(num_pts, is_closed, flip) -> (polyCounts, polyConnects)`
- `compute_uvs(arclen, width, density) -> (uArray, vArray, uvCounts, uvIds)`

`maya_io/selection.py`:

- `get_loop_from_selection() -> {ordered_ids, worldP, worldN, is_closed, source_dag}`;选区非法时抛带提示的异常

`maya_io/procedural.py`:

- `store(transform, frames, params)` / `read(transform) -> (frames, params)` / `is_strip(transform) -> bool`
- `recompute_and_update(transform, *, width, offset, density, flip, transient: bool)` — `transient=True` 走 setPoints 预览,否则提交
- `finalize(transform)`

## 11. UI 规格 (Maya 2026 · PySide6)

`MayaQWidgetDockableMixin` 停靠窗,控件:

- 按钮【从所选边线生成面片】
- 滑块+数值框:宽度 Width(世界单位)
- 滑块+数值框:法线偏移 Normal Offset
- 滑块+数值框:UV 平铺密度 Density
- 复选框:翻转法线 Flip Normals
- 按钮【打直 UV】
- 按钮【完成:删历史 + Center Pivot】

行为:

- 仅当当前选中的是本工具生成的面片(`tsIsStrip`)时,滑块/打直/完成可用;否则灰显,提示先生成或选中。
- 滑块 `sliderPressed` → 开始;`valueChanged` → 瞬时预览;`sliderReleased` → 提交一次 undo。
- 货架按钮唤出/聚焦面板。

## 12. 错误处理与边界 (Edge Cases)

- 未选边 / 选的不是边 → 提示"请先双击选中一条边线 loop",中止。
- 选区不是单条连续链(分叉 / 多条独立 loop)→ v1 提示"请只选一条连续边线",中止。
- 闭环 (ring) → 自动判环、首尾封口、UV 弧长绕回。
- 极短选区(< 2 段)→ 提示边线太短。
- 退化帧(法线 ∥ 切向)→ 邻帧 / 世界 up 回退。
- 源网格带非冻结缩放/变换 → 全程世界空间运算;新面片建在世界空间(独立物体)。
- 选中已 finalize 或非本工具物体时点调整 → 灰显/提示。

## 13. 测试策略 (Testing)

**单元测试(mayapy + pytest,`tests/test_geometry.py`):**

- `order_loop`:已知边表 → 正确顺序与开/闭判定(含乱序输入、闭环)。
- 帧正交性:`W·N ≈ 0`、`W·T ≈ 0`、各向量单位长。
- 轨道对称:`(L_i + R_i)/2 ≈ P_i + N_i*offset`;`|L_i − R_i| ≈ width`。
- 弧长单调递增;闭环末段正确绕回。
- UV:`U` 跨度/`V` 跨度 ≈ 世界 长/宽 比;`density` 缩放线性。

**Maya 内手动 QA 清单:**

- 用参考图那种曲面,分别测开环、闭环。
- `offset > 0` 时面片不与源网格穿插。
- UV 编辑器中 UV 壳为一条笔直水平矩形。
- 拖滑块流畅、单步 undo 可整段回退。
- 【完成】后:无构造历史、`ts*` 属性已清、轴心位于包围盒中心。

## 14. 范围 (Scope / YAGNI)

**v1 包含:** 单条连续 loop(开/闭)、对称宽度、法线浮起偏移、实时滑块、解析直 UV(世界比例可平铺)、翻转法线、删历史+Center Pivot 收尾、PySide6 停靠 UI、货架安装、命令插件 undo。

**明确推迟(先不做):** 一次处理多条 loop、单侧宽度、宽度射线投影贴合曲面、转角斜接、自动赋材质、多段剖面 (profile)、跨会话恢复实时编辑(超出属性缓存范围)、UV 自动吸附到 trim 条带。

## 15. 待解决问题 (Open Questions)

无(架构、版本、几何/UV/收尾行为均已在 brainstorming 中确认)。
