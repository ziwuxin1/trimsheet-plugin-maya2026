# Trim Strip 面片插件 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Maya 2026.3 里,从一条边线 loop 生成可实时调宽度/法线偏移的紧贴曲面 trim 面片,UV 自动打直成世界比例可平铺矩形,并能一键删历史 + Center Pivot 固化。

**Architecture:** 纯 Python 几何核 (`core/`,零 Maya 依赖) 负责所有数学;Maya I/O 层 (`maya_io/`) 用 OpenMaya API 2.0 读选择、建网格、缓存基准帧;变更操作由 MPxCommand 命令插件 (`commands.py`) 提供原生 undo;`tool.py` 编排,`ui/panel.py` 出 PySide6 停靠面板。调整只移动既有顶点(拓扑不变),故无需自定义 DG 节点。

**Tech Stack:** Maya 2026.3 / Python 3.11 / PySide6 (shiboken6) / maya.api.OpenMaya (API 2.0) / pytest (核测试)。

参考规格: `docs/superpowers/specs/2026-06-13-maya-trim-strip-design.md`

---

## 环境与工具说明 (先读)

- **两层测试:** `core/` 是纯 Python,用普通 `pytest` 在任何机器/沙箱跑;`maya_io/`、`commands.py`、`tool.py`、`ui/` 依赖 Maya,只能在 **装了 Maya 2026.3 的机器上**用 mayapy 或在 Maya 里手动验证。每个 Maya 任务的"测试"步给的是 **Maya 内手动验证步骤 + 预期**。
- **Git:** 当前同步文件夹在沙箱里不支持 git(config 被写成空字节)。下面的 `git commit` 步骤是"有 git 环境时"用的;若直接在此文件夹开发,文件已自动落盘,跳过 commit 即可。
- **运行核测试:** 仓库根目录执行 `python -m pytest trim_strip/tests -v`。
- **包路径:** `trim_strip` 包要在 Maya 的 `PYTHONPATH`/scripts 目录下(Task 13 安装处理)。

## 文件结构 (Decomposition)

```
trim_strip/
  __init__.py            包入口, 暴露 show()
  core/
    __init__.py
    vec.py               纯 Python 3D 向量工具 (无依赖)
    geometry.py          纯 Python: order_loop / compute_frames / compute_arclen / build_rail_points / build_faces / compute_uvs
  maya_io/
    __init__.py
    selection.py         读边线选择 -> 有序顶点 + 世界 P/N + 开闭环
    mesh_build.py        OpenMaya 建网格 / 原地改点 / 改 UV
    procedural.py        缓存基准帧到属性 / 重建点&UV / finalize
  commands.py            MPxCommand: tsGenerate, tsUpdate (原生 undo) + 插件注册
  tool.py                编排层 (UI 调它); 缓存当前 strip 帧做快速预览
  ui/
    __init__.py
    panel.py             PySide6 可停靠面板
  install/
    __init__.py
    install.py           货架按钮 + 确保命令插件加载
  tests/
    __init__.py
    test_vec.py
    test_geometry.py
```

每个文件单一职责;`core/` 不导入 maya,可独立测试。

---

## Task 0: 项目骨架

**Files:**
- Create: `trim_strip/__init__.py`
- Create: `trim_strip/core/__init__.py`, `trim_strip/maya_io/__init__.py`, `trim_strip/ui/__init__.py`, `trim_strip/install/__init__.py`, `trim_strip/tests/__init__.py`
- Create: `pytest.ini`

- [ ] **Step 1: 建包目录与空 `__init__.py`**

`trim_strip/__init__.py`:

```python
"""Trim Strip — 从边线 loop 生成可调 trim 面片的 Maya 工具。"""

__version__ = "1.0.0"


def show():
    """打开/聚焦工具面板 (在 Maya 内调用)。"""
    from trim_strip.ui import panel
    return panel.show()
```

其余 `__init__.py`(`core/`, `maya_io/`, `ui/`, `install/`, `tests/`)均为空文件。

- [ ] **Step 2: pytest 配置**

`pytest.ini`:

```ini
[pytest]
testpaths = trim_strip/tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 3: 验证目录可被发现**

Run: `python -m pytest trim_strip/tests -v`
Expected: `no tests ran`(0 collected,无 import 错误)。

- [ ] **Step 4: Commit (有 git 时)**

```bash
git add trim_strip pytest.ini
git commit -m "chore: scaffold trim_strip package"
```

---

## Task 1: 向量工具 `core/vec.py` (TDD,可在沙箱跑)

**Files:**
- Test: `trim_strip/tests/test_vec.py`
- Create: `trim_strip/core/vec.py`

- [ ] **Step 1: 写失败测试**

`trim_strip/tests/test_vec.py`:

```python
import math
from trim_strip.core import vec


def test_add_sub_scale():
    assert vec.add((1, 2, 3), (4, 5, 6)) == (5, 7, 9)
    assert vec.sub((4, 5, 6), (1, 2, 3)) == (3, 3, 3)
    assert vec.scale((1, -2, 3), 2) == (2, -4, 6)


def test_dot_cross():
    assert vec.dot((1, 0, 0), (0, 1, 0)) == 0
    assert vec.cross((1, 0, 0), (0, 1, 0)) == (0, 0, 1)


def test_length_normalize():
    assert vec.length((3, 4, 0)) == 5
    n = vec.normalize((0, 0, 5))
    assert n == (0.0, 0.0, 1.0)


def test_normalize_zero_returns_fallback():
    assert vec.normalize((0, 0, 0), fallback=(1.0, 0.0, 0.0)) == (1.0, 0.0, 0.0)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest trim_strip/tests/test_vec.py -v`
Expected: FAIL —`ModuleNotFoundError: trim_strip.core.vec`。

- [ ] **Step 3: 实现 `core/vec.py`**

```python
"""零依赖 3D 向量工具。向量用 (x, y, z) 元组表示。"""
import math


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(a):
    return math.sqrt(dot(a, a))


def normalize(a, fallback=(0.0, 0.0, 0.0)):
    l = length(a)
    if l < 1e-9:
        return fallback
    return (a[0] / l, a[1] / l, a[2] / l)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest trim_strip/tests/test_vec.py -v`
Expected: PASS(4 passed)。

- [ ] **Step 5: Commit (有 git 时)**

```bash
git add trim_strip/core/vec.py trim_strip/tests/test_vec.py
git commit -m "feat(core): add vec math helpers"
```

---

## Task 2: 边线排序 `order_loop` (TDD)

**Files:**
- Test: `trim_strip/tests/test_geometry.py`
- Create: `trim_strip/core/geometry.py`

- [ ] **Step 1: 写失败测试**

`trim_strip/tests/test_geometry.py`:

```python
import pytest
from trim_strip.core import geometry


def test_order_open_chain():
    edges = [(12, 13), (10, 11), (11, 12)]   # 乱序输入
    ordered, is_closed = geometry.order_loop(edges)
    assert ordered == [10, 11, 12, 13]
    assert is_closed is False


def test_order_closed_loop():
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    ordered, is_closed = geometry.order_loop(edges)
    assert ordered == [0, 1, 2, 3]
    assert is_closed is True


def test_branching_raises():
    edges = [(0, 1), (1, 2), (1, 3)]          # 顶点 1 度为 3
    with pytest.raises(ValueError):
        geometry.order_loop(edges)


def test_two_separate_loops_raises():
    edges = [(0, 1), (1, 2), (2, 0), (5, 6), (6, 7), (7, 5)]
    with pytest.raises(ValueError):
        geometry.order_loop(edges)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest trim_strip/tests/test_geometry.py -v`
Expected: FAIL —`ModuleNotFoundError: trim_strip.core.geometry`。

- [ ] **Step 3: 实现 `core/geometry.py`(先只放 `order_loop`)**

```python
"""零依赖几何核:边线排序、局部帧、弧长、轨道点、面、UV。"""
from trim_strip.core import vec


def order_loop(edge_pairs):
    """把一组边(顶点 id 对)排成有序顶点链。返回 (ordered_ids, is_closed)。
    分叉(度>2)或非单条连续链时抛 ValueError。"""
    adj = {}
    for a, b in edge_pairs:
        if a == b:
            continue
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    if not adj:
        raise ValueError("没有选中任何边线。")
    if any(len(ns) > 2 for ns in adj.values()):
        raise ValueError("选择有分叉,请只选一条边线 loop。")
    ends = sorted(v for v, ns in adj.items() if len(ns) == 1)
    if len(ends) not in (0, 2):
        raise ValueError("选择不是单条连续的边线。")
    is_closed = len(ends) == 0
    start = ends[0] if ends else min(adj)
    ordered = [start]
    prev, cur = None, start
    while True:
        nxts = sorted(n for n in adj[cur] if n != prev)
        if not nxts:
            break                       # 开环:到达另一端
        nxt = nxts[0]
        if nxt == start:
            break                       # 闭环:绕回起点
        ordered.append(nxt)
        prev, cur = cur, nxt
    if len(ordered) != len(adj):
        raise ValueError("选择不是单条连续的边线。")
    return ordered, is_closed
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest trim_strip/tests/test_geometry.py -v`
Expected: PASS(4 passed)。

- [ ] **Step 5: Commit (有 git 时)**

```bash
git add trim_strip/core/geometry.py trim_strip/tests/test_geometry.py
git commit -m "feat(core): order edge loop into vertex chain"
```

---

## Task 3: 局部帧 + 弧长 (TDD)

**Files:**
- Modify: `trim_strip/tests/test_geometry.py`(追加)
- Modify: `trim_strip/core/geometry.py`(追加 `compute_frames`, `compute_arclen`)

- [ ] **Step 1: 追加失败测试**

追加到 `trim_strip/tests/test_geometry.py`:

```python
def test_compute_frames_orthogonal():
    P = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
    N = [(0, 1, 0), (0, 1, 0), (0, 1, 0)]
    tangents, widths = geometry.compute_frames(P, N, is_closed=False)
    for t, w, n in zip(tangents, widths, N):
        assert abs(vec.dot(w, n)) < 1e-6      # W ⟂ N
        assert abs(vec.dot(w, t)) < 1e-6      # W ⟂ T
        assert abs(vec.length(w) - 1.0) < 1e-6


def test_compute_arclen_monotonic():
    P = [(0, 0, 0), (3, 0, 0), (3, 4, 0)]
    arclen = geometry.compute_arclen(P, is_closed=False)
    assert arclen == [0.0, 3.0, 7.0]
```

(顶部需 `from trim_strip.core import vec`,若未导入则加上。)

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest trim_strip/tests/test_geometry.py -k "frames or arclen" -v`
Expected: FAIL —`AttributeError: module ... has no attribute 'compute_frames'`。

- [ ] **Step 3: 追加实现到 `core/geometry.py`**

```python
def compute_frames(positions, normals, is_closed):
    """逐顶点算切向 T 与贴面横向 W=normalize(cross(N, T))。返回 (tangents, widths)。"""
    n = len(positions)
    tangents, widths = [], []
    for i in range(n):
        if is_closed:
            p_prev = positions[(i - 1) % n]
            p_next = positions[(i + 1) % n]
        else:
            p_prev = positions[i - 1] if i > 0 else positions[i]
            p_next = positions[i + 1] if i < n - 1 else positions[i]
        t = vec.normalize(vec.sub(p_next, p_prev))
        w = vec.normalize(vec.cross(vec.normalize(normals[i]), t))
        tangents.append(t)
        widths.append(w)
    # 退化点(N ∥ T -> W=0):借相邻有效帧,再不行用世界 X
    for i in range(n):
        if widths[i] == (0.0, 0.0, 0.0):
            found = None
            for j in list(range(i + 1, n)) + list(range(i - 1, -1, -1)):
                if widths[j] != (0.0, 0.0, 0.0):
                    found = widths[j]
                    break
            widths[i] = found if found else (1.0, 0.0, 0.0)
    return tangents, widths


def compute_arclen(positions, is_closed):
    """逐顶点累计弧长 (起点 0)。"""
    arclen = [0.0]
    for i in range(1, len(positions)):
        arclen.append(arclen[-1] + vec.length(vec.sub(positions[i], positions[i - 1])))
    return arclen
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest trim_strip/tests/test_geometry.py -v`
Expected: PASS(6 passed)。

- [ ] **Step 5: Commit (有 git 时)**

```bash
git add trim_strip/core/geometry.py trim_strip/tests/test_geometry.py
git commit -m "feat(core): per-vertex frames and arc length"
```

---

## Task 4: 轨道点 + 面 (TDD)

**Files:**
- Modify: `trim_strip/tests/test_geometry.py`(追加)
- Modify: `trim_strip/core/geometry.py`(追加 `build_rail_points`, `build_faces`)

- [ ] **Step 1: 追加失败测试**

```python
def test_build_rail_points_symmetric():
    P = [(0, 0, 0), (1, 0, 0)]
    N = [(0, 1, 0), (0, 1, 0)]
    W = [(0, 0, -1), (0, 0, -1)]
    pts = geometry.build_rail_points(P, N, W, width=2.0, offset=0.5)
    # 顺序 L0, R0, L1, R1
    L0, R0 = pts[0], pts[1]
    mid = vec.scale(vec.add(L0, R0), 0.5)
    assert mid == (0.0, 0.5, 0.0)               # 中点 = P + N*offset
    assert abs(vec.length(vec.sub(L0, R0)) - 2.0) < 1e-6   # |L-R| = width


def test_build_faces_open_and_closed():
    counts, connects = geometry.build_faces(num_pts=2, is_closed=False)
    assert counts == [4]
    assert connects == [0, 1, 3, 2]
    counts_c, connects_c = geometry.build_faces(num_pts=3, is_closed=True)
    assert counts_c == [4, 4, 4]                # 闭环 3 段含绕回
    assert connects_c[-4:] == [4, 5, 1, 0]      # 最后一段 2->0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest trim_strip/tests/test_geometry.py -k "rail or faces" -v`
Expected: FAIL —`AttributeError ... build_rail_points`。

- [ ] **Step 3: 追加实现**

```python
def build_rail_points(positions, normals, widths, width, offset):
    """每个顶点生成两条轨道点 L/R(居中对称 + 沿法线偏移)。顺序 L0,R0,L1,R1,…"""
    half = width * 0.5
    pts = []
    for i in range(len(positions)):
        base = vec.add(positions[i], vec.scale(vec.normalize(normals[i]), offset))
        pts.append(vec.add(base, vec.scale(widths[i], half)))   # L_i
        pts.append(vec.sub(base, vec.scale(widths[i], half)))   # R_i
    return pts


def build_faces(num_pts, is_closed, flip=False):
    """网格顶点索引: L_i=2i, R_i=2i+1。每段连四边形 (L_i,R_i,R_{i+1},L_{i+1})。"""
    counts, connects = [], []
    segments = num_pts if is_closed else num_pts - 1
    for i in range(segments):
        a, b = i, (i + 1) % num_pts
        face = [2 * a, 2 * a + 1, 2 * b + 1, 2 * b]
        if flip:
            face = list(reversed(face))
        counts.append(4)
        connects.extend(face)
    return counts, connects
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest trim_strip/tests/test_geometry.py -v`
Expected: PASS(8 passed)。

- [ ] **Step 5: Commit (有 git 时)**

```bash
git add trim_strip/core/geometry.py trim_strip/tests/test_geometry.py
git commit -m "feat(core): rail points and strip faces"
```

---

## Task 5: UV 打直 (TDD)

**Files:**
- Modify: `trim_strip/tests/test_geometry.py`(追加)
- Modify: `trim_strip/core/geometry.py`(追加 `compute_uvs`)

- [ ] **Step 1: 追加失败测试**

```python
def test_compute_uvs_world_scale():
    arclen = [0.0, 1.0, 2.0]
    us, vs = geometry.compute_uvs(arclen, width=2.0, density=3.0)
    # 顺序与顶点一致: 2i = L_i, 2i+1 = R_i
    assert us == [0.0, 0.0, 3.0, 3.0, 6.0, 6.0]
    assert vs == [6.0, 0.0, 6.0, 0.0, 6.0, 0.0]
    u_span = max(us) - min(us)
    v_span = max(vs) - min(vs)
    assert abs(u_span - arclen[-1] * 3.0) < 1e-6   # U 跨度 = 世界长 * density
    assert abs(v_span - 2.0 * 3.0) < 1e-6          # V 跨度 = 世界宽 * density
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest trim_strip/tests/test_geometry.py -k uvs -v`
Expected: FAIL —`AttributeError ... compute_uvs`。

- [ ] **Step 3: 追加实现**

```python
def compute_uvs(arclen, width, density):
    """解析式直 UV: U=弧长*density, L 边 V=width*density, R 边 V=0。
    按网格顶点顺序返回 (us, vs),索引 2i=L_i, 2i+1=R_i。"""
    us, vs = [], []
    v_top = width * density
    for i in range(len(arclen)):
        u = arclen[i] * density
        us.append(u); vs.append(v_top)   # L_i
        us.append(u); vs.append(0.0)     # R_i
    return us, vs
```

- [ ] **Step 4: 跑全部核测试确认通过**

Run: `python -m pytest trim_strip/tests -v`
Expected: PASS(9 passed)。核到此 100% 可测、全绿。

- [ ] **Step 5: Commit (有 git 时)**

```bash
git add trim_strip/core/geometry.py trim_strip/tests/test_geometry.py
git commit -m "feat(core): analytic straight world-scale UVs"
```

---

## Task 6: 读边线选择 `maya_io/selection.py` (Maya)

**Files:**
- Create: `trim_strip/maya_io/selection.py`

- [ ] **Step 1: 实现整文件**

```python
"""读取当前激活的边线选择,返回有序 loop 数据(世界空间)。"""
import maya.api.OpenMaya as om
from trim_strip.core import geometry


class SelectionError(Exception):
    """选择非法时抛出,message 直接给用户看。"""


def get_loop_from_selection():
    sel = om.MGlobal.getActiveSelectionList()
    if sel.length() == 0:
        raise SelectionError("请先双击选中一条边线 loop。")
    try:
        dag, comp = sel.getComponent(0)
    except Exception:
        raise SelectionError("请选择网格的边线(edge)。")
    if comp.isNull() or comp.apiType() != om.MFn.kMeshEdgeComponent:
        raise SelectionError("当前选择不是边线。请双击选中一条 edge loop。")

    edge_comp = om.MFnSingleIndexedComponent(comp)
    edge_ids = list(edge_comp.getElements())
    if not edge_ids:
        raise SelectionError("没有选中任何边线。")

    edge_it = om.MItMeshEdge(dag)
    edge_pairs = []
    for eid in edge_ids:
        edge_it.setIndex(eid)
        edge_pairs.append((edge_it.vertexId(0), edge_it.vertexId(1)))

    try:
        ordered, is_closed = geometry.order_loop(edge_pairs)
    except ValueError as exc:
        raise SelectionError(str(exc))

    mesh = om.MFnMesh(dag)
    positions, normals = [], []
    for vid in ordered:
        p = mesh.getPoint(vid, om.MSpace.kWorld)
        positions.append((p.x, p.y, p.z))
        nrm = mesh.getVertexNormal(vid, False, om.MSpace.kWorld)
        normals.append((nrm.x, nrm.y, nrm.z))

    return {
        "ordered": ordered,
        "positions": positions,
        "normals": normals,
        "is_closed": is_closed,
        "source": dag.fullPathName(),
    }
```

- [ ] **Step 2: 在 Maya 内验证**

在 Maya 2026.3 Script Editor (Python):

```python
import sys; sys.path.append(r"<trim_strip 父目录>")
from trim_strip.maya_io import selection
# 选一个 poly 物体,双击选中一条 edge loop,然后:
print(selection.get_loop_from_selection())
```

Expected: 打印 dict,`positions`/`normals` 数量相等、`ordered` 顺序连续、开环 `is_closed=False`。无选择时抛 `SelectionError("请先双击选中一条边线 loop。")`。

- [ ] **Step 3: Commit (有 git 时)**

```bash
git add trim_strip/maya_io/selection.py
git commit -m "feat(maya_io): read ordered edge loop with world P/N"
```

---

## Task 7: 建网格 / 改点 / 改 UV `maya_io/mesh_build.py` (Maya)

**Files:**
- Create: `trim_strip/maya_io/mesh_build.py`

- [ ] **Step 1: 实现整文件**

```python
"""用 OpenMaya 创建 strip 网格并原地更新点/UV。"""
import maya.api.OpenMaya as om
import maya.cmds as cmds


def create_strip(points, poly_counts, poly_connects, us, vs, uv_counts, uv_ids, name="trimStrip#"):
    mfn = om.MFnMesh()
    mpoints = om.MPointArray([om.MPoint(p[0], p[1], p[2]) for p in points])
    counts = om.MIntArray(poly_counts)
    connects = om.MIntArray(poly_connects)
    transform_obj = mfn.create(mpoints, counts, connects)   # 无 parent -> 返回 transform

    mfn.setUVs(om.MFloatArray(us), om.MFloatArray(vs))
    mfn.assignUVs(om.MIntArray(uv_counts), om.MIntArray(uv_ids))

    dag = om.MFnDagNode(transform_obj)
    dag.setName(name)
    path = dag.fullPathName()
    cmds.sets(path, edit=True, forceElement="initialShadingGroup")
    return path


def _mesh_fn(mesh_path):
    sel = om.MSelectionList()
    sel.add(mesh_path)
    return om.MFnMesh(sel.getDagPath(0))


def update_points(mesh_path, points):
    mfn = _mesh_fn(mesh_path)
    mfn.setPoints(om.MPointArray([om.MPoint(p[0], p[1], p[2]) for p in points]), om.MSpace.kObject)


def update_uvs(mesh_path, us, vs):
    mfn = _mesh_fn(mesh_path)
    mfn.setUVs(om.MFloatArray(us), om.MFloatArray(vs))


def snapshot(mesh_path):
    """读当前 object 空间点 + UV,用于精确 undo。返回 (points, us, vs)。"""
    mfn = _mesh_fn(mesh_path)
    pts = [(p.x, p.y, p.z) for p in mfn.getPoints(om.MSpace.kObject)]
    us, vs = mfn.getUVs()
    return pts, list(us), list(vs)
```

- [ ] **Step 2: 在 Maya 内验证(直接拿核函数喂数据)**

```python
from trim_strip.core import geometry
from trim_strip.maya_io import mesh_build
P = [(0,0,0),(1,0,0),(2,0,0)]; N=[(0,1,0)]*3
_, W = geometry.compute_frames(P, N, False)
A = geometry.compute_arclen(P, False)
pts = geometry.build_rail_points(P, N, W, 1.0, 0.0)
cnt, con = geometry.build_faces(3, False)
us, vs = geometry.compute_uvs(A, 1.0, 1.0)
path = mesh_build.create_strip(pts, cnt, con, us, vs, cnt, con)
print(path)
```

Expected: 视口出现一条 3 段、2 宽的平面带子;UV 编辑器里是一条笔直水平矩形;`mesh_build.update_points(path, geometry.build_rail_points(P,N,W,3.0,0.5))` 后带子变宽并抬起。

- [ ] **Step 3: Commit (有 git 时)**

```bash
git add trim_strip/maya_io/mesh_build.py
git commit -m "feat(maya_io): create/update strip mesh via OpenMaya"
```

---

## Task 8: 缓存帧与重建 `maya_io/procedural.py` (Maya)

**Files:**
- Create: `trim_strip/maya_io/procedural.py`

- [ ] **Step 1: 实现整文件**

```python
"""把基准帧缓存到 strip transform 的隐藏属性,并从参数重建点/UV;收尾固化。"""
import maya.cmds as cmds
from trim_strip.core import geometry
from trim_strip.maya_io import mesh_build

_DOUBLE_ARRAYS = ("tsBaseP", "tsBaseN", "tsBaseW", "tsArcLen")
_SCALAR_ATTRS = ("tsIsStrip", "tsVersion", "tsClosed", "tsWidth", "tsOffset", "tsDensity")


def _flatten(vecs):
    out = []
    for v in vecs:
        out.extend((float(v[0]), float(v[1]), float(v[2])))
    return out


def _unflatten(flat):
    return [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat), 3)]


def _set_da(attr, vals):
    cmds.setAttr(attr, len(vals), *vals, type="doubleArray")


def ensure_attrs(t):
    if cmds.attributeQuery("tsIsStrip", node=t, exists=True):
        return
    cmds.addAttr(t, longName="tsIsStrip", attributeType="bool", hidden=True)
    cmds.addAttr(t, longName="tsVersion", attributeType="long", hidden=True)
    cmds.addAttr(t, longName="tsClosed", attributeType="bool", hidden=True)
    for a in ("tsWidth", "tsOffset", "tsDensity"):
        cmds.addAttr(t, longName=a, attributeType="double", hidden=True)
    for a in _DOUBLE_ARRAYS:
        cmds.addAttr(t, longName=a, dataType="doubleArray", hidden=True)


def store(t, frames, params):
    ensure_attrs(t)
    cmds.setAttr(t + ".tsIsStrip", 1)
    cmds.setAttr(t + ".tsVersion", 1)
    cmds.setAttr(t + ".tsClosed", int(params["is_closed"]))
    cmds.setAttr(t + ".tsWidth", float(params["width"]))
    cmds.setAttr(t + ".tsOffset", float(params["offset"]))
    cmds.setAttr(t + ".tsDensity", float(params["density"]))
    _set_da(t + ".tsBaseP", _flatten(frames["positions"]))
    _set_da(t + ".tsBaseN", _flatten(frames["normals"]))
    _set_da(t + ".tsBaseW", _flatten(frames["widths"]))
    _set_da(t + ".tsArcLen", [float(x) for x in frames["arclen"]])


def is_strip(t):
    return bool(cmds.attributeQuery("tsIsStrip", node=t, exists=True)) and bool(cmds.getAttr(t + ".tsIsStrip"))


def read(t):
    frames = {
        "positions": _unflatten(cmds.getAttr(t + ".tsBaseP")),
        "normals": _unflatten(cmds.getAttr(t + ".tsBaseN")),
        "widths": _unflatten(cmds.getAttr(t + ".tsBaseW")),
        "arclen": list(cmds.getAttr(t + ".tsArcLen")),
    }
    params = {
        "is_closed": bool(cmds.getAttr(t + ".tsClosed")),
        "width": cmds.getAttr(t + ".tsWidth"),
        "offset": cmds.getAttr(t + ".tsOffset"),
        "density": cmds.getAttr(t + ".tsDensity"),
    }
    return frames, params


def apply(t, frames, params):
    """根据参数重算并原地写回点 + UV(不含 undo,调用方负责)。"""
    pts = geometry.build_rail_points(frames["positions"], frames["normals"], frames["widths"], params["width"], params["offset"])
    us, vs = geometry.compute_uvs(frames["arclen"], params["width"], params["density"])
    mesh_build.update_points(t, pts)
    mesh_build.update_uvs(t, us, vs)


def write_params(t, params):
    cmds.setAttr(t + ".tsWidth", float(params["width"]))
    cmds.setAttr(t + ".tsOffset", float(params["offset"]))
    cmds.setAttr(t + ".tsDensity", float(params["density"]))


def finalize(t):
    """删历史 + 移除 ts* 属性 + Center Pivot。整块包成一次 undo。"""
    cmds.undoInfo(openChunk=True)
    try:
        cmds.delete(t, constructionHistory=True)
        for a in _SCALAR_ATTRS + _DOUBLE_ARRAYS:
            if cmds.attributeQuery(a, node=t, exists=True):
                cmds.deleteAttr(t + "." + a)
        cmds.xform(t, centerPivots=True)
    finally:
        cmds.undoInfo(closeChunk=True)
```

- [ ] **Step 2: 在 Maya 内验证**

接 Task 7 的 `path`:

```python
from trim_strip.maya_io import procedural
from trim_strip.core import geometry
frames = {"positions":P, "normals":N, "widths":W, "arclen":A}
params = {"is_closed":False, "width":1.0, "offset":0.0, "density":1.0}
procedural.store(path, frames, params)
print(procedural.is_strip(path))                 # True
f2, p2 = procedural.read(path); print(p2)         # 取回参数
procedural.apply(path, f2, {"is_closed":False,"width":4.0,"offset":0.3,"density":1.0})  # 变宽抬起
procedural.finalize(path)
print(cmds.attributeQuery("tsIsStrip", node=path, exists=True))  # False;轴心已居中
```

Expected: `is_strip` True;`apply` 后带子变宽抬起;`finalize` 后 ts* 属性消失、历史清空、Center Pivot 生效。

- [ ] **Step 3: Commit (有 git 时)**

```bash
git add trim_strip/maya_io/procedural.py
git commit -m "feat(maya_io): cache frames on transform, rebuild and finalize"
```

---

## Task 9: 命令插件 `commands.py` (Maya,原生 undo)

**Files:**
- Create: `trim_strip/commands.py`

- [ ] **Step 1: 实现整文件**

```python
"""Maya 命令插件: tsGenerate / tsUpdate(原生 undo)。用 cmds.loadPlugin 加载。"""
import maya.api.OpenMaya as om
import maya.cmds as cmds

from trim_strip.core import geometry
from trim_strip.maya_io import selection, mesh_build, procedural

DEFAULT_WIDTH = 1.0
DEFAULT_OFFSET = 0.05
DEFAULT_DENSITY = 1.0


def maya_useNewAPI():
    pass


def _compute_build_data():
    loop = selection.get_loop_from_selection()
    _, widths = geometry.compute_frames(loop["positions"], loop["normals"], loop["is_closed"])
    frames = {
        "positions": loop["positions"],
        "normals": loop["normals"],
        "widths": widths,
        "arclen": geometry.compute_arclen(loop["positions"], loop["is_closed"]),
    }
    return loop, frames


class TsGenerateCmd(om.MPxCommand):
    NAME = "tsGenerate"

    def __init__(self):
        super().__init__()
        self._build = None
        self._created = None

    @staticmethod
    def creator():
        return TsGenerateCmd()

    def isUndoable(self):
        return True

    def doIt(self, args):
        loop, frames = _compute_build_data()       # 可能抛 SelectionError
        params = {"is_closed": loop["is_closed"], "width": DEFAULT_WIDTH,
                  "offset": DEFAULT_OFFSET, "density": DEFAULT_DENSITY}
        self._build = (frames, params)
        self.redoIt()

    def redoIt(self):
        frames, params = self._build
        pts = geometry.build_rail_points(frames["positions"], frames["normals"], frames["widths"], params["width"], params["offset"])
        counts, connects = geometry.build_faces(len(frames["positions"]), params["is_closed"])
        us, vs = geometry.compute_uvs(frames["arclen"], params["width"], params["density"])
        path = mesh_build.create_strip(pts, counts, connects, us, vs, counts, connects)
        procedural.store(path, frames, params)
        cmds.select(path, replace=True)
        self._created = path
        self.clearResult()
        self.setResult(path)

    def undoIt(self):
        if self._created and cmds.objExists(self._created):
            cmds.delete(self._created)
        self._created = None


class TsUpdateCmd(om.MPxCommand):
    NAME = "tsUpdate"

    def __init__(self):
        super().__init__()
        self._t = None
        self._frames = None
        self._old_params = None
        self._new_params = None
        self._old_pts = None
        self._old_us = None
        self._old_vs = None

    @staticmethod
    def creator():
        return TsUpdateCmd()

    @staticmethod
    def syntax():
        s = om.MSyntax()
        s.addArg(om.MSyntax.kString)
        s.addFlag("-w", "-width", om.MSyntax.kDouble)
        s.addFlag("-o", "-offset", om.MSyntax.kDouble)
        s.addFlag("-d", "-density", om.MSyntax.kDouble)
        return s

    def isUndoable(self):
        return True

    def doIt(self, args):
        parser = om.MArgParser(self.syntax(), args)
        self._t = parser.commandArgumentString(0)
        self._frames, params = procedural.read(self._t)
        self._old_params = dict(params)
        self._old_pts, self._old_us, self._old_vs = mesh_build.snapshot(self._t)
        new = dict(params)
        if parser.isFlagSet("-w"):
            new["width"] = parser.flagArgumentDouble("-w", 0)
        if parser.isFlagSet("-o"):
            new["offset"] = parser.flagArgumentDouble("-o", 0)
        if parser.isFlagSet("-d"):
            new["density"] = parser.flagArgumentDouble("-d", 0)
        self._new_params = new
        self.redoIt()

    def redoIt(self):
        procedural.apply(self._t, self._frames, self._new_params)
        procedural.write_params(self._t, self._new_params)

    def undoIt(self):
        mesh_build.update_points(self._t, self._old_pts)
        mesh_build.update_uvs(self._t, self._old_us, self._old_vs)
        procedural.write_params(self._t, self._old_params)


def initializePlugin(plugin):
    pf = om.MFnPlugin(plugin, "Junliang", "1.0.0", "Any")
    pf.registerCommand(TsGenerateCmd.NAME, TsGenerateCmd.creator)
    pf.registerCommand(TsUpdateCmd.NAME, TsUpdateCmd.creator, TsUpdateCmd.syntax)


def uninitializePlugin(plugin):
    pf = om.MFnPlugin(plugin)
    pf.deregisterCommand(TsUpdateCmd.NAME)
    pf.deregisterCommand(TsGenerateCmd.NAME)
```

- [ ] **Step 2: 在 Maya 内验证 undo/redo**

```python
import maya.cmds as cmds
cmds.loadPlugin(r"<trim_strip 父目录>/trim_strip/commands.py")
# 选一条 edge loop:
path = cmds.tsGenerate()
cmds.tsUpdate(path, width=3.0, offset=0.3)
cmds.undo()    # 回到生成时的宽度/偏移
cmds.redo()    # 再次变宽
cmds.undo(); cmds.undo()   # 第二次 undo 应删除生成的面片
```

Expected: `tsGenerate` 返回新 transform 名并选中;`tsUpdate` 改变形态;`undo` 精确回退一步;连续 undo 到生成那步会删掉面片。整段拖动在 UI 里会是一次 commit = 一步 undo。

- [ ] **Step 3: Commit (有 git 时)**

```bash
git add trim_strip/commands.py
git commit -m "feat: tsGenerate/tsUpdate MPxCommands with native undo"
```

---

## Task 10: 编排层 `tool.py` (Maya)

**Files:**
- Create: `trim_strip/tool.py`

- [ ] **Step 1: 实现整文件**

```python
"""UI 调用的高层编排。缓存当前 strip 的帧做快速实时预览。"""
import maya.cmds as cmds
from trim_strip.maya_io import procedural, mesh_build
from trim_strip.core import geometry

_active = {"transform": None, "frames": None}


def generate():
    """读当前边线选择生成面片(undoable)。返回 (transform, params)。"""
    path = cmds.tsGenerate()
    frames, params = procedural.read(path)
    _active["transform"], _active["frames"] = path, frames
    return path, params


def set_active(path):
    """选择变化时调用:若是本工具的面片则载入,返回 params,否则 None。"""
    if path and cmds.objExists(path) and procedural.is_strip(path):
        frames, params = procedural.read(path)
        _active["transform"], _active["frames"] = path, frames
        return params
    _active["transform"], _active["frames"] = None, None
    return None


def preview(width, offset, density):
    """拖滑块时的快速、非 undo 预览。"""
    t, frames = _active["transform"], _active["frames"]
    if not t:
        return
    procedural.apply(t, frames, {"is_closed": False, "width": width, "offset": offset, "density": density})


def commit(width, offset, density):
    """松开滑块时的一步 undo 提交。"""
    t = _active["transform"]
    if t:
        cmds.tsUpdate(t, width=width, offset=offset, density=density)


def straighten_uv():
    t = _active["transform"]
    if not t:
        return
    frames, params = procedural.read(t)
    us, vs = geometry.compute_uvs(frames["arclen"], params["width"], params["density"])
    cmds.undoInfo(openChunk=True)
    try:
        mesh_build.update_uvs(t, us, vs)
    finally:
        cmds.undoInfo(closeChunk=True)


def reverse_normals():
    t = _active["transform"]
    if t:
        cmds.polyNormal(t, normalMode=0, constructionHistory=False)


def finalize():
    t = _active["transform"]
    if not t:
        return
    procedural.finalize(t)
    _active["transform"], _active["frames"] = None, None
```

- [ ] **Step 2: 在 Maya 内验证**

```python
from trim_strip import tool
# 选 edge loop:
path, params = tool.generate(); print(params)
tool.preview(2.5, 0.2, 1.0)     # 视口实时变(无 undo 记录)
tool.commit(2.5, 0.2, 1.0)      # 记一步 undo
tool.straighten_uv(); tool.reverse_normals()
tool.finalize()                 # 固化
```

Expected: 各步对应视口变化正确;`preview` 不污染 undo,`commit` 可 undo;`finalize` 后属性清空、轴心居中。

- [ ] **Step 3: Commit (有 git 时)**

```bash
git add trim_strip/tool.py
git commit -m "feat: tool orchestration with cached-frame live preview"
```

---

## Task 11: PySide6 停靠面板 `ui/panel.py` (Maya)

**Files:**
- Create: `trim_strip/ui/panel.py`

- [ ] **Step 1: 实现整文件**

```python
"""PySide6 可停靠面板。"""
from PySide6 import QtWidgets, QtCore
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import maya.cmds as cmds

from trim_strip import tool
from trim_strip.maya_io.selection import SelectionError

_win = None


class _FloatRow(QtWidgets.QWidget):
    valueChanged = QtCore.Signal()
    committed = QtCore.Signal()

    def __init__(self, label, mn, mx, val, parent=None):
        super().__init__(parent)
        self._mn, self._mx = mn, mx
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QtWidgets.QLabel(label))
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.spin = QtWidgets.QDoubleSpinBox()
        self.spin.setRange(mn, mx)
        self.spin.setDecimals(3)
        self.spin.setSingleStep((mx - mn) / 200.0)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.set_value(val)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)
        self.slider.sliderReleased.connect(self.committed.emit)
        self.spin.editingFinished.connect(self.committed.emit)

    def _to_slider(self, v):
        return int(round((v - self._mn) / (self._mx - self._mn) * 1000))

    def _from_slider(self, s):
        v = self._mn + (s / 1000.0) * (self._mx - self._mn)
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self.valueChanged.emit()

    def _from_spin(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(self._to_slider(v))
        self.slider.blockSignals(False)
        self.valueChanged.emit()

    def set_value(self, v):
        self.spin.blockSignals(True)
        self.slider.blockSignals(True)
        self.spin.setValue(v)
        self.slider.setValue(self._to_slider(v))
        self.spin.blockSignals(False)
        self.slider.blockSignals(False)

    def value(self):
        return self.spin.value()


class TrimStripPanel(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Trim Strip")
        self.setObjectName("trimStripPanel")
        self._build_ui()
        self._sel_job = cmds.scriptJob(event=["SelectionChanged", self._on_selection_changed], protected=True)
        self._on_selection_changed()

    def _build_ui(self):
        lay = QtWidgets.QVBoxLayout(self)
        self.btn_gen = QtWidgets.QPushButton("从所选边线生成面片")
        self.row_w = _FloatRow("宽度", 0.0, 10.0, 1.0)
        self.row_o = _FloatRow("法线偏移", -1.0, 1.0, 0.05)
        self.row_d = _FloatRow("UV 密度", 0.01, 10.0, 1.0)
        self.btn_uv = QtWidgets.QPushButton("打直 UV")
        self.btn_flip = QtWidgets.QPushButton("翻转法线")
        self.btn_fin = QtWidgets.QPushButton("完成: 删历史 + Center Pivot")
        for w in (self.btn_gen, self.row_w, self.row_o, self.row_d, self.btn_uv, self.btn_flip, self.btn_fin):
            lay.addWidget(w)
        lay.addStretch(1)
        self.btn_gen.clicked.connect(self._on_generate)
        for r in (self.row_w, self.row_o, self.row_d):
            r.valueChanged.connect(self._on_preview)
            r.committed.connect(self._on_commit)
        self.btn_uv.clicked.connect(lambda: tool.straighten_uv())
        self.btn_flip.clicked.connect(lambda: tool.reverse_normals())
        self.btn_fin.clicked.connect(self._on_finalize)

    def _editable(self, on):
        for w in (self.row_w, self.row_o, self.row_d, self.btn_uv, self.btn_flip, self.btn_fin):
            w.setEnabled(on)

    def _load_params(self, params):
        self.row_w.set_value(params["width"])
        self.row_o.set_value(params["offset"])
        self.row_d.set_value(params["density"])

    def _on_generate(self):
        try:
            _path, params = tool.generate()
        except SelectionError as exc:
            cmds.warning(str(exc))
            return
        self._load_params(params)
        self._editable(True)

    def _on_selection_changed(self):
        sel = cmds.ls(selection=True, long=True, objectsOnly=True) or []
        transforms = [s for s in sel if "transform" in (cmds.nodeType(s, inherited=True) or [])]
        params = tool.set_active(transforms[0]) if len(transforms) == 1 else None
        if params:
            self._load_params(params)
            self._editable(True)
        else:
            self._editable(False)

    def _on_preview(self):
        tool.preview(self.row_w.value(), self.row_o.value(), self.row_d.value())

    def _on_commit(self):
        tool.commit(self.row_w.value(), self.row_o.value(), self.row_d.value())

    def _on_finalize(self):
        tool.finalize()
        self._editable(False)

    def closeEvent(self, event):
        if self._sel_job is not None and cmds.scriptJob(exists=self._sel_job):
            cmds.scriptJob(kill=self._sel_job, force=True)
        super().closeEvent(event)


def show():
    global _win
    if _win is None:
        _win = TrimStripPanel()
    _win.show(dockable=True)
    return _win
```

- [ ] **Step 2: 在 Maya 内验证**

```python
import maya.cmds as cmds
cmds.loadPlugin(r"<父目录>/trim_strip/commands.py")
from trim_strip.ui import panel
panel.show()
# 双击选边 loop -> 点[生成] -> 拖[宽度][法线偏移]看实时 -> [打直UV] -> [翻转法线] -> [完成]
```

Expected: 面板可停靠;选中本工具面片时滑块/按钮亮起,否则灰显;拖动实时更新且松手一步 undo;选择非 strip 物体时控件灰显。

- [ ] **Step 3: Commit (有 git 时)**

```bash
git add trim_strip/ui/panel.py
git commit -m "feat(ui): PySide6 dockable trim strip panel"
```

---

## Task 12: 安装 `install/install.py` (Maya)

**Files:**
- Create: `trim_strip/install/install.py`

- [ ] **Step 1: 实现整文件**

```python
"""安装货架按钮并确保命令插件已加载。"""
import os
import maya.cmds as cmds
import maya.mel as mel

_PLUGIN = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "commands.py"))


def ensure_plugin_loaded():
    try:
        loaded = cmds.pluginInfo("commands", query=True, loaded=True)
    except Exception:
        loaded = False
    if not loaded:
        cmds.loadPlugin(_PLUGIN)


def install_shelf_button():
    ensure_plugin_loaded()
    shelf = mel.eval("$tmp = $gShelfTopLevel")
    current = cmds.tabLayout(shelf, query=True, selectTab=True)
    cmds.shelfButton(
        parent=current,
        label="TrimStrip",
        annotation="Trim Strip 面片工具",
        image="polyExtrudeEdge.png",
        imageOverlayLabel="Trim",
        sourceType="python",
        command="from trim_strip.ui import panel; panel.show()",
    )
```

- [ ] **Step 2: 在 Maya 内验证**

```python
import sys; sys.path.append(r"<trim_strip 父目录>")
from trim_strip.install import install
install.install_shelf_button()
```

Expected: 当前货架出现 "Trim" 按钮;点它能加载插件并弹出面板。

- [ ] **Step 3: 写使用说明 `trim_strip/README.md`**

```markdown
# Trim Strip (Maya 2026.3)

## 安装
1. 把 `trim_strip` 父目录加入 Maya 的 PYTHONPATH(或放到 Maya `scripts` 目录)。
2. Script Editor 运行:
   ```python
   from trim_strip.install import install
   install.install_shelf_button()
   ```

## 使用
1. 双击选中一条边线 loop。
2. 点货架 **Trim** 按钮打开面板,点【从所选边线生成面片】。
3. 拖【宽度】【法线偏移】实时调;【UV 密度】控制平铺;【打直 UV】重写直 UV。
4. 需要时点【翻转法线】。
5. 贴好 trim 后点【完成: 删历史 + Center Pivot】固化。
```

- [ ] **Step 4: Commit (有 git 时)**

```bash
git add trim_strip/install/install.py trim_strip/README.md
git commit -m "feat(install): shelf button installer and README"
```

---

## Task 13: 端到端 QA (Maya 手动,对照规格 §13)

**Files:** 无(纯验证)

- [ ] **Step 1: 核测试全绿**

Run: `python -m pytest trim_strip/tests -v`
Expected: 9 passed。

- [ ] **Step 2: 用参考图那类曲面跑全流程**

在 Maya 2026.3 中,对一个有圆角转折的硬表面模型:

- 开环 loop:双击选中翻过圆角的一条 loop → 生成 → 面片贴合弯曲走向。
- 闭环 loop:选一圈闭合 loop → 生成 → 首尾封口、无破面。
- `法线偏移 > 0`:面片浮起,与源网格 **不穿插**、无 z-fighting。
- UV 编辑器:UV 壳为 **一条笔直水平矩形**;改宽度时 V 跨度按比例变(不拉伸贴图)。
- 拖滑块流畅;一次拖动 = 一步 `Ctrl+Z` 整段回退。
- 【完成】后:`无` 构造历史、`ts*` 属性已清除、轴心位于包围盒中心(Modify > Center Pivot 等效)。
- 错误处理:空选择 / 选面非边 / 分叉选择 → 弹出对应中文提示且不崩。

Expected: 全部符合;不符合的项回到对应 Task 修。

- [ ] **Step 3: Commit (有 git 时)**

```bash
git add -A
git commit -m "test: end-to-end QA pass for trim strip v1"
```

---

## 自检结论 (Spec Coverage / Placeholder / Type)

- **规格覆盖:** §3 流程→Task 10/11;§5 几何→Task 3/4;§6 UV→Task 5;§7 实时机制→Task 9(tsUpdate)+Task 10(preview/commit);§8 finalize→Task 8;§9 属性 schema→Task 8;§10 模块→Task 0-12;§11 UI→Task 11;§12 边界→Task 6(selection)+ Task 13 QA;§13 测试→Task 1-5 单测 + Task 13 清单;§14 范围→本计划仅做 v1。
- **与规格的有意偏差(已在本计划落实):** ①`core/geometry.py` 用纯 Python(非 `om.MVector`)以便沙箱可测;②`tsFlip` 属性取消,翻转法线改为【翻转法线】按钮调 `polyNormal`(更简、可独立 undo),`build_faces` 保留 `flip` 形参默认 False。两处不改变规格意图。
- **占位符扫描:** 无 TBD/TODO;每个代码步均给完整代码与可执行命令/预期。
- **类型/命名一致性:** `frames` 字典键 `positions/normals/widths/arclen` 全程一致;`params` 键 `is_closed/width/offset/density` 全程一致;命令名 `tsGenerate/tsUpdate`、函数 `build_rail_points/build_faces/compute_uvs/apply/finalize/preview/commit` 跨任务调用一致。
```
