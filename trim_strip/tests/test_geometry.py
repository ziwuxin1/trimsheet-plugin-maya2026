import pytest
from trim_strip.core import geometry
from trim_strip.core import vec


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
