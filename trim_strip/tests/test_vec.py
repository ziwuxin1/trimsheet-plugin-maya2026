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
