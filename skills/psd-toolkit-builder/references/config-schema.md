# JSON 配置字段说明

所有相对路径相对于**项目根目录**（`psd-toolkit/`，即 `configs/` 的上一级）。用绝对路径也可以。

## 顶层结构

```json
{
  "name": "配置名（仅备注）",
  "canvas": { "width": 1920, "height": 1080 },
  "coordinate_scale": 1.5,
  "background": { ... },
  "layers": [ ... ],
  "groups": [ ... ],
  "output": { ... }
}
```

| 字段 | 说明 |
|---|---|
| `canvas.width/height` | 最终 PSD 的画布尺寸，通常 1920×1080 |
| `coordinate_scale` | 逻辑坐标 → 画布像素的倍率。1280→1920 是 1.5；坐标已按最终画布写就设 1.0 |

## background（背景高清化）

```json
{
  "source": "通天录...png",
  "out": "psd_work/regression/bg_enhanced.png",
  "plain_out": "psd_work/regression/bg_plain.png",
  "width": 1920,
  "height": 1080,
  "clahe": { "clip": 1.30, "tile": [8, 8] },
  "sharpen": [
    { "radius": 1.1, "percent": 118, "threshold": 2 },
    { "radius": 2.8, "percent": 32, "threshold": 6 }
  ],
  "color": 1.06,
  "dewatermark": null,
  "compare": {
    "out": "psd_work/regression/clarity_compare.png",
    "box_out": [250, 150, 650, 400],
    "cell": [800, 500]
  }
}
```

| 字段 | 说明 |
|---|---|
| `source` | 源图路径 |
| `out` | 高清化成品（会被 layer[0] 引用） |
| `plain_out` | 可选，只放大不增强的对照图 |
| `width/height` | 放大目标尺寸 |
| `clahe` | 可选。亮度通道局部对比，拉开暗部层次。`clip` 建议 1.2~1.4，`tile` 一般 [8,8]。不要就删掉字段 |
| `sharpen` | 数组，可多档。细档 `radius≈1.1/percent≈118` 提笔画，粗档 `radius≈2.8/percent≈32` 提轮廓，都带 threshold 防噪点放大 |
| `color` | 饱和度补偿，1.05~1.08 |
| `dewatermark` | `null` 表示源图已去水印；否则见下表 |
| `compare` | 可选。出"左简单放大/右增强后"局部对比板。`box_out` 是画布坐标下的裁剪框，`cell` 是每格尺寸 |

### dewatermark 子字段

```json
{
  "x0": 1150, "y0": 640,
  "v_min": 62, "s_max": 135,
  "dilate_kernel": 7, "dilate_iter": 3, "mask_blur": 9,
  "inpaint_radius1": 9, "inpaint_radius2": 5,
  "feather_x": 0.45, "feather_y": 0.35,
  "feather_blur": 10, "feather_strength": 0.55, "soft_blur": 2.2
}
```

原理：在 `[x0,y0]→[x1,y1]` 矩形内（x1/y1 不写默认到图边），HSV 挑出亮且不太饱和的水印字，膨胀成掩膜，TELEA+NS 两次 inpaint，最后羽化柔化修补区。矩形位置按水印实际位置调，一般右下角。

## layers（图层清单，从下到上）

```json
{
  "name": "02-1 纸人 · 符纸光晕",
  "file": "psd_work/x_7_2.png",
  "x": 196, "y": 378,
  "pad": 0,
  "resize": [552, 609]
}
```

| 字段 | 说明 |
|---|---|
| `name` | 图层名，原样写入 PSD，用中文 |
| `file` | 透明底 PNG 路径 |
| `x/y` | 逻辑坐标（乘 coordinate_scale 得到画布位置） |
| `pad` | 外扩边距，和 x/y 同单位。有投影的图层（如登录面板）导出多带边距，填对应值归位；没有就不写 |
| `resize` | 可选 `[w,h]`。导出图按 2x 时，这里写目标尺寸先缩放再摆放，文字重新栅格化所以锐利 |

顺序 = PSD 里的 z-order（数组第一个在最底）。第一层必须是铺满画布的背景。

## groups（分组）

```json
{ "name": "01 · 背景", "layers": [0] },
{ "name": "02 · 角色", "layers": [1, 2] }
```

`layers` 是图层在 `layers` 数组里的下标。所有下标合起来正好覆盖每一层，不漏不重。分组只影响 PSD 组织，不影响叠加顺序。

已验证的 8 组架构（25 层）：
- 01 背景 [0]
- 02 角色 [1,2]
- 03 氛围 [3,4,5]
- 04 页眉与标识 [6,7,8,9]
- 05 登录面板 [10]
- 06 页脚 [11,12,13]
- 07 卷轴装饰 [14,15,16,17,18,19]
- 08 符印封印 [20,21,22,23,24]

## output（输出）

```json
{
  "psd": "psd_work/regression/v3_回归_分层.psd",
  "preview": "psd_work/regression/v3_回归_preview.png",
  "background_copy": "psd_work/regression/v3_回归_背景.png"
}
```

- `psd`：分层 PSD 路径
- `preview`：内置合成图导出的预览 PNG
- `background_copy`：可选，把 `layers[0]` 单独存成纯背景图

## verify 判定

- 尺寸 == canvas
- 分组数、图层数达标
- 组名齐全（自动剥离 `\x00`）
- 合成图逐像素 max diff ≤ 2（实测 0）

全部满足打 PASS。
