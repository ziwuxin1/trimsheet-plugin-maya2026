"""安装货架按钮并确保命令插件已加载。"""
import os
import maya.cmds as cmds
import maya.mel as mel

_PLUGIN = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "ts_plugin.py"))


def ensure_plugin_loaded():
    # 命令已经可用 -> 无需任何操作。
    if hasattr(cmds, "tsGenerate"):
        return
    # 可能上次加载失败/中途出错,Maya 仍把 "ts_plugin" 记为已加载,
    # 这会让普通 loadPlugin 变成空操作。所以先强制干净卸载再重载。
    try:
        if cmds.pluginInfo("ts_plugin", query=True, loaded=True):
            cmds.flushUndo()
            cmds.unloadPlugin("ts_plugin")
    except Exception:
        pass
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
