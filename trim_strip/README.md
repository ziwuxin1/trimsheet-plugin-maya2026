# Trim Strip (Maya 2026.3)

## 安装
1. 把 `trim_strip` 父目录加入 Maya 的 PYTHONPATH(或放到 Maya `scripts` 目录)。
2. Script Editor 运行:
   ```python
   from trim_strip.install import install
   install.install_shelf_button()
   ```

## 使用
1. 双击选中一条边线 loop。
2. 点货架 **Trim** 按钮打开面板,点【从所选边线生成面片】。
3. 拖【宽度】【法线偏移】实时调;【UV 密度】控制平铺;【打直 UV】重写直 UV。
4. 需要时点【翻转法线】。
5. 贴好 trim 后点【完成: 删历史 + Center Pivot】固化。
