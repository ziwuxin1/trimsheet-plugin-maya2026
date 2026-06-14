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
