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
