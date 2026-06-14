"""用 OpenMaya 创建 strip 网格并原地更新点/UV。"""
import maya.api.OpenMaya as om
import maya.cmds as cmds


def create_strip(points, poly_counts, poly_connects, us, vs, uv_counts, uv_ids, name="trimStrip#"):
    mfn = om.MFnMesh()
    mpoints = om.MPointArray([om.MPoint(p[0], p[1], p[2]) for p in points])
    counts = om.MIntArray(poly_counts)
    connects = om.MIntArray(poly_connects)
    created = mfn.create(mpoints, counts, connects)   # 无 parent -> 应返回 transform

    mfn.setUVs(om.MFloatArray(us), om.MFloatArray(vs))
    mfn.assignUVs(om.MIntArray(uv_counts), om.MIntArray(uv_ids))

    # 兜底:确保拿到的是 transform 路径(create 在某些情况下可能给 shape)。
    created_path = om.MFnDagNode(created).fullPathName()
    if cmds.objectType(created_path) != "transform":
        created_path = cmds.listRelatives(created_path, parent=True, fullPath=True)[0]
    # 用 cmds.rename:它支持 "#" 自动编号;MFnDagNode.setName 不支持,
    # 且 "#" 是非法节点名字符,setName 会抛异常导致后续 store 不执行。
    new_name = cmds.rename(created_path, name)
    path = cmds.ls(new_name, long=True, type="transform")[0]   # 显式取 transform,标记必落在 transform 上
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
