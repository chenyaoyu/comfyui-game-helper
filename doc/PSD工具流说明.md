# 登录页 PSD 工具流 · 使用说明

这套工具干一件事：把一张平面的游戏登录页概念图，加上拆好的透明 UI 图层，组装成一份能在 Photoshop 里继续编辑的分层 PSD。

它从两件事里长出来的。第一件是高清化——概念图通常是 1280×720 的生成图，要放大到 1920×1080，还得清掉平台自动盖的水印、把细节提清晰。第二件是组装——把登录框、按钮、符印、装饰线这些元素按原来的前后遮挡顺序叠回去，分组分好，中文命名，让用户打开 PSD 就能直接改某一层。

原来的做法是每次写死一个 Python 脚本，换个背景就把坐标、尺寸、图层清单全改一遍，既容易错又没法复用。现在把这些全抽到一个 JSON 配置里，脚本本身不认识任何一张具体的图——你给它什么配置，它就出什么 PSD。

---

## 目录长什么样

```
psd-toolkit/
├─ tools/                    工具本体，一般不用动
│  ├─ psd_tool.py           统一入口，四个命令都从这走
│  ├─ enhancer.py           背景高清化
│  ├─ psd_builder.py        分层 PSD 组装
│  └─ verifier.py           产物校验
├─ configs/
│  └─ v3.json               配置样例，改这个就能出新的 PSD
├─ psd_work/                 素材：源图 + 拆好的透明 PNG
├─ generated-images/         旧版高清化的源图
├─ .libs/                    本地依赖（pytoshop / packbits），跟环境解耦
├─ requirements.txt          依赖清单
└─ 通天录_...png             V3 源图
```

`doc/` 里是这份说明，`skills/` 里是可被智能体直接调用的 skill 包。

---

## 装环境

用的是系统里带 cv2 的那套 Python（Windows 上是 `py` launcher）。核心依赖 cv2 / numpy / Pillow 那套环境里通常已经有了，缺的是写 PSD 用的两个库，已经放进项目本地的 `.libs/`，不用你管。

如果换台机器，先确认：

```bash
py -c "import cv2, numpy, PIL; print('ok')"
```

能打印 ok 就行。然后需要的话再装 PDB 写入依赖：

```bash
py -m pip install -r requirements.txt
```

注意别把 numpy 装进 `.libs/`。之前踩过一次：pip 装 pytoshop 时顺带拉了个 numpy 副本进来，结果 `.libs` 被加到 `sys.path` 最前面，加载到一个残缺的 numpy，直接 import 失败。现在 `.libs/` 里只保留 pytoshop 和 packbits，numpy/cv2/PIL 一律用系统环境的。

---

## 四个命令

所有命令都从 `psd_tool.py` 进，用 `-c` 指定配置：

```bash
cd psd-toolkit

# 1. 只做背景高清化
py -X utf8 tools/psd_tool.py -c configs/v3.json enhance

# 2. 只组装 PSD（要求背景高清图已经存在）
py -X utf8 tools/psd_tool.py -c configs/v3.json build

# 3. 只校验已有 PSD
py -X utf8 tools/psd_tool.py -c configs/v3.json verify

# 4. 三步全跑，推荐用这个
py -X utf8 tools/psd_tool.py -c configs/v3.json all
```

`-X utf8` 是 Windows 上让中文路径和中文图层名不出乱码，别省。

`all` 的顺序是 enhance → build → verify。build 会读 enhance 生成的背景图，所以单独跑 build 前得先跑过 enhance。

---

## 配置文件怎么写

打开 `configs/v3.json`，照着改就行。所有相对路径都相对于**项目根目录**（也就是 `configs/` 的上一级），不是相对于配置文件本身。这点容易搞混，记一下。

### 画布与坐标

```json
"canvas": { "width": 1920, "height": 1080 },
"coordinate_scale": 1.5
```

`coordinate_scale` 是逻辑坐标到画布像素的换算倍率。原来的设计稿是 1280×720，出到 1920×1080 正好 1.5 倍，所以图层位置写的是 1280 坐标系里的值，工具自动乘 1.5 摆到画布上。

如果你所有坐标直接按最终画布写，把这个设成 1.0 就行。

### 背景高清化

```json
"background": {
  "source": "通天录_C调整_V3_密录千眼 · 朱砂满卷.png",
  "out": "psd_work/regression/bg_enhanced.png",
  "width": 1920, "height": 1080,
  "clahe": { "clip": 1.30, "tile": [8, 8] },
  "sharpen": [
    { "radius": 1.1, "percent": 118, "threshold": 2 },
    { "radius": 2.8, "percent": 32, "threshold": 6 }
  ],
  "color": 1.06,
  "dewatermark": null
}
```

- `source` 是源图，`out` 是高清化后的成品。
- `clahe` 是亮度通道局部对比，把暗部符文层次拉开，不动色相。不想增强就删掉这个字段。
- `sharpen` 可以写多档。细档提笔画，粗档提轮廓，都带 threshold 防止把噪点一起放大。这是针对"满卷细字"调出来的配方，实测没有光晕、暗部也不会被洗亮。
- `color` 是饱和度，锐化后颜色会偏灰，稍微补一点回来。
- `dewatermark` 是去水印设置。**源图已经去过水印就写 `null`**。没去过的话给一个矩形区域，走 HSV 亮色掩膜 + 两次 inpaint + 羽化柔化，具体字段在后面附录。

还有两个可选字段：`plain_out` 会额外存一张"只放大不增强"的对照图，`compare` 会出一张"左简单放大 / 右增强后"的局部对比板，用来肉眼验收清晰度。

### 图层清单

这是核心，`layers` 数组按从下到上的顺序写，顺序就是 PSD 里的遮挡顺序：

```json
{ "name": "02-1 纸人 · 符纸光晕",
  "file": "psd_work/x_7_2.png",
  "x": 196, "y": 378,
  "pad": 0,
  "resize": [552, 609] }
```

- `name`：图层名，会原样写进 PSD，直接用中文。
- `file`：透明底 PNG 路径。
- `x` / `y`：逻辑坐标。
- `pad`：额外外扩边距。登录面板那个图层有投影，导出时多带了 100px（2x）的边距，所以填 50 把它归位。没有投影就写 0 或干脆不写。
- `resize`：导出图尺寸。原来 UI 是按 2x 导出的，这里写成目标尺寸让工具先缩放再摆放，文字会重新栅格化所以是锐利的。不写就按原尺寸。

第一层必须是背景，而且尺寸要铺满画布。组装时会把 `layers[0]` 单独复制一份当纯背景交付图（`output.background_copy`），方便单独使用。

### 分组

```json
"groups": [
  { "name": "01 · 背景", "layers": [0] },
  { "name": "02 · 角色", "layers": [1, 2] }
]
```

`layers` 里写的是图层在数组里的下标。所有下标合起来应该正好覆盖每一层，别漏也别重。分组只是 PSD 里的组织方式，不影响叠加顺序——顺序永远看 `layers` 数组。

### 输出

```json
"output": {
  "psd": "psd_work/regression/v3_回归_分层.psd",
  "preview": "psd_work/regression/v3_回归_preview.png",
  "background_copy": "psd_work/regression/v3_回归_背景.png"
}
```

样例里输出都放在 `psd_work/regression/`，这是为了回归测试时不覆盖原交付物。正式用的时候改成你要的路径。

---

## 校验看什么

`verify` 会查四件事：

1. **尺寸**对不对，1920×1080。
2. **分组数**和**图层数**够不够。
3. **组名**齐不齐。psd_tools 读回来的名字末尾会带一个 `\x00`（Adobe 的规范，正常现象），工具已经处理掉了，不用担心。
4. **合成图一致性**：把 PSD 的合成结果和组装时自己算的叠加图逐像素比。容差是 max≤2（舍入差异），实测 V3 是 0，说明"打开即所见"，没有渲染偏差。

最后打 `[VERIFY] 结果: PASS` 才算过。

---

## 修改流程（最常用）

拿到一张新背景，想出同规格的 PSD：

1. 复制 `configs/v3.json` 成 `configs/我的新图.json`。
2. 改 `background.source` 指向新源图，`out` / `plain_out` / 输出路径改成新名字。
3. UI 图层不动的话，`layers` 和 `groups` 一个字都不用改。
4. 跑 `py -X utf8 tools/psd_tool.py -c configs/我的新图.json all`。
5. 看 verify 是不是 PASS，再看一眼 `preview` 图和对比板。

就这么简单。原来那套"改脚本"的做法，现在变成"改配置"。

---

## 附录：去水印字段

如果源图右下角有平台盖的 `AI生成 / WORKBUDDY` 水印，在 `background.dewatermark` 里给一个矩形：

```json
"dewatermark": {
  "x0": 1150, "y0": 640,
  "v_min": 62, "s_max": 135,
  "dilate_kernel": 7, "dilate_iter": 3,
  "mask_blur": 9,
  "inpaint_radius1": 9, "inpaint_radius2": 5,
  "feather_x": 0.45, "feather_y": 0.35,
  "feather_blur": 10, "feather_strength": 0.55,
  "soft_blur": 2.2
}
```

原理是：在矩形内用 HSV 挑出亮且不太饱和的像素（就是水印字），膨胀成掩膜，inpaint 两次填掉，最后只在修补区域羽化柔化。

一个坑：**别整块克隆贴图去盖水印**，会留下横向的暗带接缝。羽化才是正解。

另外，同一个平台生成的一批图，水印位置基本固定。更省事的做法是从一张暗底图提一次精确掩膜，膨胀后复用到所有图上，比逐张在浅底上做阈值误伤纸纹要稳。

---

## 已知边界

- 图层清单和坐标得人工给。这套工具负责"按清单组装",不负责"从一张扁平图里自动认出哪些是按钮、哪些是装饰"——那个识别是设计判断，不是脚本活。
- 中文路径在 Windows 上靠 PIL 读图规避（cv2.imread 对中文路径会失败），所以图都走 PIL。
- 图层名末尾的 `\x00` 是 `pytoshop` 按 Adobe luni 规范写的，Photoshop 显示正常，psd_tools 也会原样带出。别手贱去掉，去掉反而破坏规范。
