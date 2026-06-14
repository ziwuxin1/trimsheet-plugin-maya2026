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
