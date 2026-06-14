# -*- coding: utf-8 -*-
# NOTE: This file is loaded by Maya's scripted-plugin loader (cmds.loadPlugin),
# which on localized Windows fails to decode non-ASCII source. Keep this file
# ASCII-only. User-facing Chinese strings live in modules imported normally
# (selection.py / panel.py), which Python imports as UTF-8 without issue.
#
# It is named ts_plugin.py (not commands.py) on purpose: Maya caches a scripted
# plugin by basename after the first load attempt and will not re-read the file
# from disk on later loads. A fresh basename sidesteps that stale cache.
"""Maya command plugin: tsGenerate / tsUpdate (native undo). Load via cmds.loadPlugin."""
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
        loop, frames = _compute_build_data()       # may raise SelectionError
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
        self._created = path          # set BEFORE store so undoIt can clean a partial orphan
        procedural.store(path, frames, params)
        cmds.select(path, replace=True)
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
