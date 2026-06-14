"""Trim Strip — 从边线 loop 生成可调 trim 面片的 Maya 工具。"""

__version__ = "1.0.0"


def show():
    """打开/聚焦工具面板 (在 Maya 内调用)。"""
    from trim_strip.ui import panel
    return panel.show()
