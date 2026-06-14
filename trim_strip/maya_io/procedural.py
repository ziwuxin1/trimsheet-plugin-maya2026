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
    flat = flat or []
    return [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat), 3)]


def _set_da(attr, vals):
    # 直接把列表作为单个值传入;Maya 自己数长度。
    # 旧写法 setAttr(attr, len(vals), *vals, type="doubleArray") 在 Maya 2026
    # 会报 "Too much data was provided",所以改成列表形式。
    cmds.setAttr(attr, list(vals), type="doubleArray")


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
