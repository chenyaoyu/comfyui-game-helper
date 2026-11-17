# -*- coding: utf-8 -*-
"""通用分层 PSD 组装：读 JSON 图层配置 -> 按 z-order 叠加 -> 写出分组 PSD。

只依赖 numpy / Pillow / pytoshop（+ packbits）。不含写死的画布尺寸、
坐标、图层清单或分组——全部来自配置字典。

配置字段见 configs/v3.json，字段含义见 doc/PSD工具流说明.md。
"""
import os

import numpy as np
from PIL import Image
from pytoshop.user import nested_layers as nl
from pytoshop import enums, core
from pytoshop import codecs

# pytoshop 的 RLE 依赖可选 Cython 扩展 packbits；缺失时注入纯 Python 实现。
if not hasattr(codecs, 'packbits'):
    import packbits as _pb

    class _PackbitsShim:
        @staticmethod
        def encode(row):
            return _pb.encode(bytes(np.ascontiguousarray(row, dtype=np.uint8).tobytes()))

        @staticmethod
        def decode(data, *args, **kwargs):
            return _pb.decode(bytes(data))

    codecs.packbits = _PackbitsShim


def _abs(path, base):
    return path if os.path.isabs(path) else os.path.join(base, path)


def _read_rgba(base, path, resize=None):
    im = Image.open(_abs(path, base)).convert('RGBA')
    if resize:
        im = im.resize((int(resize[0]), int(resize[1])), Image.LANCZOS)
    return np.array(im)


def _make_layer(name, rgba, left, top, W, H):
    """把一张 RGBA 贴到画布坐标系，裁掉画布外部分，返回 pytoshop Image 层。"""
    left, top = int(round(left)), int(round(top))
    h, w = rgba.shape[:2]
    x0, y0 = max(0, -left), max(0, -top)
    x1, y1 = min(w, W - left), min(h, H - top)
    if x1 <= x0 or y1 <= y0:
        return None
    c = rgba[y0:y1, x0:x1]
    L, T = left + x0, top + y0
    return nl.Image(
        name=name, top=T, left=L, bottom=T + c.shape[0], right=L + c.shape[1],
        channels={
            0: np.ascontiguousarray(c[:, :, 0]),
            1: np.ascontiguousarray(c[:, :, 1]),
            2: np.ascontiguousarray(c[:, :, 2]),
            -1: np.ascontiguousarray(c[:, :, 3]),
        })


def _blend(canvas, rgba, left, top):
    """PIL alpha_composite 语义的源-over 混合，更新 canvas。"""
    H, W = canvas.shape[:2]
    left, top = int(round(left)), int(round(top))
    h, w = rgba.shape[:2]
    x0, y0 = max(0, -left), max(0, -top)
    x1, y1 = min(w, W - left), min(h, H - top)
    if x1 <= x0 or y1 <= y0:
        return
    src = rgba[y0:y1, x0:x1].astype(np.float32)
    dst = canvas[top + y0:top + y1, left + x0:left + x1].astype(np.float32)
    sa = src[:, :, 3:4] / 255.0
    da = dst[:, :, 3:4] / 255.0
    oa = sa + da * (1 - sa)
    oc = np.where(oa > 0,
                  (src[:, :, :3] * sa + dst[:, :, :3] * da * (1 - sa)) /
                  np.maximum(oa, 1e-6), 0)
    out = np.concatenate([oc, oa * 255], axis=2)
    canvas[top + y0:top + y1, left + x0:left + x1] = np.clip(out, 0, 255).astype(np.uint8)


def _validate_groups(cfg):
    """严格校验分组下标：全为合法整数、无重复、并集恰好覆盖所有图层。"""
    n = len(cfg['layers'])
    seen = []
    for g in cfg['groups']:
        for i in g['layers']:
            if not isinstance(i, int) or isinstance(i, bool):
                raise ValueError("分组 '%s' 的下标必须是整数，收到 %r" % (g['name'], i))
            if i < 0 or i >= n:
                raise ValueError("分组 '%s' 的下标 %d 越界（图层总数 %d）" % (g['name'], i, n))
            seen.append(i)
    dup = sorted({i for i in seen if seen.count(i) > 1})
    if dup:
        raise ValueError("分组下标重复: %s（一个图层只能属于一个组）" % dup)
    missing = sorted(set(range(n)) - set(seen))
    if missing:
        raise ValueError("有图层未被任何分组覆盖: %s" % missing)


def build(cfg, base):
    """按配置组装 PSD，返回写出路径与合成图数组。"""
    _validate_groups(cfg)
    canvas_cfg = cfg['canvas']
    W, H = int(canvas_cfg['width']), int(canvas_cfg['height'])
    scale = float(cfg.get('coordinate_scale', 1.0))

    built = []
    composite = np.zeros((H, W, 4), np.uint8)

    for spec in cfg['layers']:
        rgba = _read_rgba(base, spec['file'], spec.get('resize'))
        # pad 是额外外扩边距（阴影导出用），与 x/y 同单位；换算到画布像素
        left = (float(spec['x']) - float(spec.get('pad', 0))) * scale
        top = (float(spec['y']) - float(spec.get('pad', 0))) * scale
        built.append(_make_layer(spec['name'], rgba, left, top, W, H))
        _blend(composite, rgba, left, top)

    out_cfg = cfg['output']
    preview_path = _abs(out_cfg['preview'], base)
    os.makedirs(os.path.dirname(preview_path) or '.', exist_ok=True)
    Image.fromarray(composite[:, :, :3], 'RGB').save(preview_path)

    if out_cfg.get('background_copy'):
        bg_path = _abs(out_cfg['background_copy'], base)
        os.makedirs(os.path.dirname(bg_path) or '.', exist_ok=True)
        Image.open(_abs(cfg['layers'][0]['file'], base)).convert('RGB').save(bg_path)

    hierarchy = []
    for g in cfg['groups']:
        kids = [built[i] for i in g['layers'] if i < len(built) and built[i] is not None]
        hierarchy.append(nl.Group(name=g['name'], layers=kids))

    psd = nl.nested_layers_to_psd(hierarchy, enums.ColorMode.rgb,
                                  size=(W, H), compression=enums.Compression.rle)

    chans = np.stack([
        np.ascontiguousarray(composite[:, :, 0]),
        np.ascontiguousarray(composite[:, :, 1]),
        np.ascontiguousarray(composite[:, :, 2]),
        np.full((H, W), 255, np.uint8),
    ], axis=0)
    chans = chans[:psd.num_channels]
    psd.image_data = core.ImageData(channels=chans, compression=enums.Compression.rle)

    psd_path = _abs(out_cfg['psd'], base)
    os.makedirs(os.path.dirname(psd_path) or '.', exist_ok=True)
    with open(psd_path, 'wb') as fh:
        psd.write(fh)
    return psd_path, composite
