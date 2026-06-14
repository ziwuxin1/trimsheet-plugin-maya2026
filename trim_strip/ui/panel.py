"""PySide6 独立工具窗(无边框 + 自绘深色标题栏,EnvIt 风格)。

用 wrapInstance(MQtUtil.mainWindow()) 把 Maya 主窗口当父窗口;窗口设为
Qt.Window | Qt.FramelessWindowHint,整窗由 Qt 绘制 —— 没有任何 Maya/原生边框色。
代价:不可停靠进 Maya 布局(浮动工具窗)。
"""
from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance, isValid
import maya.OpenMayaUI as omui
import maya.cmds as cmds

from trim_strip import tool
from trim_strip import __version__ as _VERSION
from trim_strip.maya_io import procedural
from trim_strip.maya_io.selection import SelectionError

_win = None

STYLE = """
QWidget { background-color: #1c1c1c; color: #c9c9c9; font-size: 12px; }
#root { background-color: #1c1c1c; border: 1px solid #3a3a3a; }

#titleBar { background-color: #141414; }
#titleBarLabel { color: #ededed; font-weight: 500; }
#winBtn, #closeBtn { background: transparent; border: none; color: #9a9a9a; font-size: 13px; }
#winBtn:hover { background-color: #2a2a2a; color: #ffffff; }
#closeBtn:hover { background-color: #c0392b; color: #ffffff; }

#subtitle { color: #7c7c7c; font-size: 10px; }
#divLine  { background-color: #333333; border: none; }
#divLabel { color: #c7d63b; font-weight: 500; letter-spacing: 1px; }
#rowLabel { color: #b0b0b0; }
#paramGroup { border: 1px solid #333333; border-radius: 4px; }
#statusFrame { background-color: #181818; border-top: 1px solid #2a2a2a; }
#statusBar { color: #7c7c7c; }
#verLabel  { color: #6a6a6a; }

QPushButton {
    background-color: #2b2b2b; border: 1px solid #3d3d3d; border-radius: 3px;
    padding: 7px 10px; color: #d8d8d8; min-height: 16px;
}
QPushButton:hover    { background-color: #343434; border-color: #4a4a4a; }
QPushButton:pressed  { background-color: #262626; }
QPushButton:disabled { background-color: #242424; color: #5a5a5a; border-color: #333333; }

QPushButton#accentFill { background-color: #c7d63b; color: #1c1c1c; border: none; font-weight: 500; }
QPushButton#accentFill:hover    { background-color: #d4e24a; }
QPushButton#accentFill:pressed  { background-color: #b3c12f; }
QPushButton#accentFill:disabled { background-color: #3a3d2a; color: #7a7d60; }

QPushButton#accentOutline { background-color: #1c1c1c; color: #c7d63b; border: 1px solid #c7d63b; font-weight: 500; }
QPushButton#accentOutline:hover    { background-color: #26261a; }
QPushButton#accentOutline:pressed  { background-color: #202014; }
QPushButton#accentOutline:disabled { background-color: #1c1c1c; color: #5a5d40; border-color: #3a3d2a; }

QDoubleSpinBox {
    background-color: #262626; border: 1px solid #3a3a3a; border-radius: 2px;
    color: #d7d59a; padding: 2px 4px; selection-background-color: #c7d63b; selection-color: #1c1c1c;
}
QDoubleSpinBox:disabled { color: #5f5f5f; background-color: #232323; }

QSlider::groove:horizontal { height: 4px; background: #121212; border-radius: 2px; }
QSlider::handle:horizontal { background: #dcea61; width: 12px; height: 12px; margin: -5px 0; border-radius: 6px; }
QSlider::handle:horizontal:hover     { background: #e6f27a; }
QSlider::sub-page:horizontal         { background: #c7d63b; border-radius: 2px; }
QSlider::sub-page:horizontal:disabled{ background: #3c3c3c; }
QSlider::handle:horizontal:disabled  { background: #4f4f4f; }

QCheckBox { color: #cfcfcf; spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #555555; background: #262626; border-radius: 2px; }
QCheckBox::indicator:hover   { border-color: #777777; }
QCheckBox::indicator:checked { background: #c7d63b; border-color: #c7d63b; }
QCheckBox:disabled { color: #5a5a5a; }
QCheckBox::indicator:disabled { background: #242424; border-color: #383838; }
"""

_STATUS_COLOR = {"info": "#7c7c7c", "ok": "#c7d63b", "warn": "#e0a14a"}


def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        return None
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def _kill_panel_jobs():
    """杀掉所有引用本面板选择回调的 scriptJob(跨 sys.modules 重载安全)。"""
    try:
        for entry in cmds.scriptJob(listJobs=True) or []:
            if "_on_selection_changed" in entry:
                try:
                    cmds.scriptJob(kill=int(entry.split(":", 1)[0]), force=True)
                except Exception:
                    pass
    except Exception:
        pass


class _TitleBar(QtWidgets.QFrame):
    """自绘标题栏:标题 + 最小化 + 关闭,可拖动整窗。"""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(30)
        self._window = window
        self._drag_offset = None
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 4, 0)
        lay.setSpacing(2)
        lbl = QtWidgets.QLabel("Trim Strip")
        lbl.setObjectName("titleBarLabel")
        lay.addWidget(lbl)
        lay.addStretch(1)
        btn_min = QtWidgets.QPushButton("–")
        btn_min.setObjectName("winBtn")
        btn_min.setFixedSize(34, 28)
        btn_min.setCursor(QtCore.Qt.ArrowCursor)
        btn_min.clicked.connect(self._window.showMinimized)
        btn_close = QtWidgets.QPushButton("✕")
        btn_close.setObjectName("winBtn")
        btn_close.setProperty("class", "closeBtn")
        btn_close.setObjectName("closeBtn")
        btn_close.setFixedSize(34, 28)
        btn_close.setCursor(QtCore.Qt.ArrowCursor)
        btn_close.clicked.connect(self._window.close)
        lay.addWidget(btn_min)
        lay.addWidget(btn_close)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & QtCore.Qt.LeftButton):
            self._window.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_offset = None


class _FloatRow(QtWidgets.QWidget):
    valueChanged = QtCore.Signal()
    committed = QtCore.Signal()

    def __init__(self, label, mn, mx, val, parent=None):
        super().__init__(parent)
        self._mn, self._mx = mn, mx
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lbl = QtWidgets.QLabel(label)
        lbl.setObjectName("rowLabel")
        lbl.setMinimumWidth(56)
        lay.addWidget(lbl)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.spin = QtWidgets.QDoubleSpinBox()
        self.spin.setRange(mn, mx)
        self.spin.setDecimals(3)
        self.spin.setSingleStep((mx - mn) / 200.0)
        self.spin.setFixedWidth(62)
        self.spin.setAlignment(QtCore.Qt.AlignCenter)
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


def _divider(text):
    w = QtWidgets.QWidget()
    h = QtWidgets.QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)

    def line():
        f = QtWidgets.QFrame()
        f.setObjectName("divLine")
        f.setFixedHeight(1)
        f.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        return f

    lbl = QtWidgets.QLabel(text)
    lbl.setObjectName("divLabel")
    h.addWidget(line(), 1)
    h.addWidget(lbl)
    h.addWidget(line(), 1)
    return w


class TrimStripPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("root")
        self.setWindowTitle("Trim Strip")
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setMinimumWidth(316)
        self.setStyleSheet(STYLE)
        self._build_ui()
        _kill_panel_jobs()
        self._sel_job = cmds.scriptJob(event=["SelectionChanged", self._on_selection_changed], protected=True)
        self._on_selection_changed()

    # ---------- UI ----------
    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(_TitleBar(self))

        body = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(body)
        root.setContentsMargins(14, 10, 14, 0)
        root.setSpacing(8)
        outer.addWidget(body, 1)

        sub = QtWidgets.QLabel("边线 Trim 面片工具 · v%s" % _VERSION)
        sub.setObjectName("subtitle")
        root.addWidget(sub)
        root.addSpacing(4)

        root.addWidget(_divider("生成"))
        self.btn_gen = QtWidgets.QPushButton("从所选边线生成面片")
        self.btn_gen.setObjectName("accentFill")
        self.btn_gen.setMinimumHeight(34)
        root.addWidget(self.btn_gen)
        root.addSpacing(4)

        root.addWidget(_divider("实时调整"))
        grp = QtWidgets.QFrame()
        grp.setObjectName("paramGroup")
        gl = QtWidgets.QVBoxLayout(grp)
        gl.setContentsMargins(10, 10, 10, 10)
        gl.setSpacing(10)
        self.row_w = _FloatRow("宽度", 0.0, 10.0, 1.0)
        self.row_o = _FloatRow("法线偏移", -1.0, 1.0, 0.05)
        self.row_d = _FloatRow("UV 密度", 0.01, 10.0, 1.0)
        for r in (self.row_w, self.row_o, self.row_d):
            gl.addWidget(r)
        root.addWidget(grp)
        root.addSpacing(4)

        root.addWidget(_divider("UV / 法线"))
        self.btn_uv = QtWidgets.QPushButton("打直 UV")
        root.addWidget(self.btn_uv)
        self.chk_flip = QtWidgets.QCheckBox("翻转法线")
        root.addWidget(self.chk_flip)
        root.addSpacing(4)

        root.addWidget(_divider("收尾"))
        self.btn_fin = QtWidgets.QPushButton("完成:删历史 + Center Pivot")
        self.btn_fin.setObjectName("accentOutline")
        self.btn_fin.setMinimumHeight(34)
        root.addWidget(self.btn_fin)

        root.addStretch(1)

        # 状态栏 + 右下角缩放手柄
        self.statusFrame = QtWidgets.QFrame()
        self.statusFrame.setObjectName("statusFrame")
        sh = QtWidgets.QHBoxLayout(self.statusFrame)
        sh.setContentsMargins(14, 4, 4, 4)
        sh.setSpacing(6)
        self.status = QtWidgets.QLabel("就绪")
        self.status.setObjectName("statusBar")
        ver = QtWidgets.QLabel("v%s" % _VERSION)
        ver.setObjectName("verLabel")
        sh.addWidget(self.status, 1)
        sh.addWidget(ver)
        sh.addWidget(QtWidgets.QSizeGrip(self), 0, QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight)
        outer.addWidget(self.statusFrame)

        # 接线
        self.btn_gen.clicked.connect(self._on_generate)
        for r in (self.row_w, self.row_o, self.row_d):
            r.valueChanged.connect(self._on_preview)
            r.committed.connect(self._on_commit)
        self.btn_uv.clicked.connect(self._on_straighten)
        self.chk_flip.toggled.connect(self._on_flip)
        self.btn_fin.clicked.connect(self._on_finalize)

    def _set_status(self, text, kind="info"):
        self.status.setText(text)
        self.status.setStyleSheet("#statusBar { color: %s; }" % _STATUS_COLOR.get(kind, "#7c7c7c"))

    def _editable(self, on):
        for w in (self.row_w, self.row_o, self.row_d, self.btn_uv, self.chk_flip, self.btn_fin):
            w.setEnabled(on)

    def _load_params(self, params):
        self.row_w.set_value(params["width"])
        self.row_o.set_value(params["offset"])
        self.row_d.set_value(params["density"])

    # ---------- 行为 ----------
    def _on_generate(self):
        try:
            _path, params = tool.generate()
        except SelectionError as exc:
            cmds.warning(str(exc))
            self._set_status(str(exc), "warn")
            return
        self._load_params(params)
        self._editable(True)
        self._set_status("已生成面片 — 拖滑块实时调整", "ok")

    def _on_selection_changed(self, *args):
        try:
            if not isValid(self):
                return
        except Exception:
            pass
        xforms = set()
        for s in cmds.ls(selection=True, long=True, objectsOnly=True) or []:
            if cmds.objectType(s, isType="transform"):
                xforms.add(s)
            else:
                par = cmds.listRelatives(s, parent=True, fullPath=True, type="transform") or []
                xforms.update(par)
        strips = [x for x in xforms if procedural.is_strip(x)]
        params = tool.set_active(strips[0]) if len(strips) == 1 else None
        if params:
            self._load_params(params)
            self._editable(True)
            self._set_status("已选中本工具面片", "ok")
        else:
            self._editable(False)
            self._set_status("请生成面片,或选中一条本工具生成的面片", "info")

    def _on_preview(self):
        tool.preview(self.row_w.value(), self.row_o.value(), self.row_d.value())

    def _on_commit(self):
        tool.commit(self.row_w.value(), self.row_o.value(), self.row_d.value())

    def _on_straighten(self):
        tool.straighten_uv()
        self._set_status("已打直 UV", "ok")

    def _on_flip(self, *args):
        tool.reverse_normals()
        self._set_status("已翻转法线", "ok")

    def _on_finalize(self):
        tool.finalize()
        self._editable(False)
        self._set_status("已完成:删历史 + Center Pivot", "ok")

    def closeEvent(self, event):
        if getattr(self, "_sel_job", None) is not None and cmds.scriptJob(exists=self._sel_job):
            cmds.scriptJob(kill=self._sel_job, force=True)
        super().closeEvent(event)


def show():
    global _win
    from trim_strip.install import install
    install.ensure_plugin_loaded()
    _kill_panel_jobs()
    if _win is not None:
        try:
            _win.close()
        except Exception:
            pass
        _win = None
    parent = maya_main_window()
    _win = TrimStripPanel(parent=parent)
    _win.resize(330, 540)
    if parent is not None:
        c = parent.geometry().center()
        _win.move(c.x() - 165, c.y() - 270)
    _win.show()
    _win.raise_()
    return _win
