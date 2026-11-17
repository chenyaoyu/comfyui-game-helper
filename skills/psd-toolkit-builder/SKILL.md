---
name: psd-toolkit-builder
description: This skill should be used when the user wants to turn a flat concept image (plus separated transparent UI layers) into a layered, editable Photoshop PSD; to upscale an image from 1280x720 to 1920x1080 with clarity enhancement and watermark removal; or to reassemble named, grouped layers into a PSD. Trigger phrases include 生成分层PSD, 拆分图层, 登录页PSD, 高清化背景, 1920x1080 PSD, layered PSD, split UI layers. The underlying tool lives in the comfyui-game-helper repository under psd-toolkit/ and is config-driven via JSON.
agent_created: true
---

# PSD Toolkit Builder

## Overview

把一张平面的游戏登录页概念图，连同拆好的透明 UI 图层，组装成可在 Photoshop 里继续编辑的分层 PSD。也负责前期把 1280×720 的概念图高清化到 1920×1080、清掉平台水印、提清晰细节。

工具本体在 `comfyui-game-helper/psd-toolkit/`（仓库内），是配置驱动的：所有源图、尺寸、坐标、图层清单、分组、输出路径都写在 JSON 里，脚本不认识任何一张具体的图。换图只改配置，不改代码。

定位工具根目录的优先顺序：`scripts/run.py` 里的 `PSD_TOOL_ROOT` 环境变量 → 从脚本位置向上推算的仓库根 → 默认 `<仓库根>/psd-toolkit`。不要假定固定在某个盘符。

## When to use

- 用户要把登录页概念图出成分层 PSD（"生成psd""拆分图层""1920×1080 分层稿"）。
- 用户要把一张生成图放大到 1920×1080、去水印、提清晰。
- 用户要在之前那套 8 组 25 层架构基础上换背景重出 PSD。
- 用户提到 `comfyui-game-helper` 这个仓库里的 PSD / 登录页工具流。

不适用于：从扁平图里自动识别 UI 元素（那是设计判断，脚本做不了）、非登录页的通用 PSD 处理。

## Quick start

工具用系统里带 cv2 的 Python。Windows 上用 `py` launcher；`-X utf8` 不能省，否则中文路径和图层名会乱码。

```bash
# TOOL_ROOT = 仓库根/psd-toolkit（也可由 PSD_TOOL_ROOT 环境变量指定）
cd <仓库根>/psd-toolkit

# 三步全跑（推荐）
py -X utf8 tools/psd_tool.py -c configs/v3.json all
```

四个子命令：`enhance`（背景高清化）、`build`（组装 PSD）、`verify`（校验）、`all`（前三步串起来）。单独跑 `build` 前要先跑过 `enhance`，因为 build 要读高清化后的背景图。

`all` 跑完会打 `[VERIFY] 结果: PASS` 才算成功。PASS 意味着：尺寸 1920×1080、8 组 25 层、中文组名齐全、合成图逐像素差异在容差内（max≤2，V3 实测 0，即"打开即所见"）。

## Standard workflow

用户给一张新背景、要同规格 PSD 时：

1. 复制 `configs/v3.json` 成新配置（如 `configs/新图.json`）。
2. 改 `background.source` 指向新源图，`out` / `plain_out` 和 `output` 里的路径改成新名字。
3. UI 图层不变的话，`layers` 和 `groups` 一个字都别动——这是已验证的 8 组 25 层架构，动容易跑偏。
4. 跑 `py -X utf8 tools/psd_tool.py -c configs/新图.json all`。
5. 确认 verify PASS，再看一眼生成的 preview 图和 clarity 对比板（清晰度没有过曝/光晕）。

## Critical rules（踩过的坑，务必遵守）

1. **路径基准**：配置里的相对路径都相对于项目根目录（`configs/` 的上一级），不是配置文件所在目录。写错会找不到图。
2. **`.libs/` 只放 pytoshop 和 packbits**。装依赖时 pip 会把 numpy 顺带拉进来，而 `.libs` 被加在 `sys.path[0]`，会加载到残缺 numpy 导致 import 失败。numpy/cv2/PIL 一律用系统环境。
3. **中文路径走 PIL**：`cv2.imread` 在 Windows 读中文路径会失败，工具里统一用 `PIL.Image.open`，别改回去。
4. **去水印别克隆贴图**：整块克隆会留下横向暗带接缝。用 HSV 掩膜 + inpaint + 羽化柔化。源图已去水印就把 `dewatermark` 设成 `null`。
5. **图层名末尾的 `\x00` 是正常的**：pytoshop 按 Adobe luni 规范写的空终止符，Photoshop 显示正常。校验器已处理，不要手贱去掉。
6. **别覆盖原交付物**：样例配置输出到 `psd_work/regression/`，正式出图改新路径，别直接盖掉原 PSD。
7. **clear/删除操作要小心**：项目里的源图和 PNG 素材是跑工具的前提。历史上一次 `rm -rf` 误删过这些素材，恢复很麻烦。清理目录前先确认作用域。

## Resources

### references/config-schema.md
JSON 配置的完整字段说明：画布与坐标倍率、背景高清化的 CLAHE/锐化/去水印参数、图层清单每一项的含义、分组下标规则、输出路径。需要改配置或验证字段时读它。详细版用户文档在仓库根的 `doc/PSD工具流说明.md`。

### assets/v3-config-template.json
一份可直接复制的配置模板（通天录 V3 的已验证配置）。创建新配置时先复制它再改。

### scripts/
本 skill 不自带工具代码——工具本体在仓库的 `psd-toolkit/tools/`，由 `psd_tool.py` 统一入口调用。这里只放一个便捷包装脚本 `run.py`，用于在任意目录下快速定位并调用工具。
