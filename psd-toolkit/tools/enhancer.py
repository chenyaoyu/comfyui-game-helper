# -*- coding: utf-8 -*-
"""通用背景高清化：放大 + 清晰度增强 + 可选去水印。

只依赖 numpy / opencv-python / Pillow。所有参数由配置字典驱动，
不含任何写死的源图名、尺寸或水印坐标。

配置字段见 configs/v3.json 的 background 段，字段含义见 doc/PSD工具流说明.md。
"""
import os

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def _abs(path, base):
    """相对路径按 base 解析，绝对路径原样返回。"""
    return path if os.path.isabs(path) else os.path.join(base, path)


def _read_rgb(path):
    """用 PIL 读图，规避 cv2.imread 在 Windows 中文路径下失败的问题。"""
    return np.array(Image.open(path).convert('RGB'))


def _remove_watermark(rgb, spec):
    """HSV 亮色掩膜 + 膨胀 + TELEA/NS 两次 inpaint + 羽化柔化。

    spec 为 None 或空字典时跳过（源图已去水印的情况，如通天录 V3）。
    """
    if not spec:
        return rgb
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    # 矩形先 clamp 到图像边界，避免负索引 / 越界切片导致颜色转换或广播崩溃
    x0 = max(0, int(spec.get('x0', 0)))
    y0 = max(0, int(spec.get('y0', 0)))
    x1 = min(w, int(spec.get('x1', w)))
    y1 = min(h, int(spec.get('y1', h)))
    if x1 <= x0 or y1 <= y0:
        return rgb

    roi = bgr[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    v, s = hsv[:, :, 2], hsv[:, :, 1]
    sel = ((v > int(spec.get('v_min', 62))) &
           (s < int(spec.get('s_max', 135)))).astype(np.uint8) * 255
    k = int(spec.get('dilate_kernel', 7))
    it = int(spec.get('dilate_iter', 3))
    sel = cv2.dilate(sel, np.ones((k, k), np.uint8), iterations=it)
    bk = int(spec.get('mask_blur', 9))
    if bk > 1:
        sel = cv2.GaussianBlur(sel, (bk, bk), 0)

    mask = np.zeros((h, w), np.uint8)
    mask[y0:y1, x0:x1] = sel
    clean = cv2.inpaint(bgr, mask, float(spec.get('inpaint_radius1', 9)),
                        cv2.INPAINT_TELEA)
    clean = cv2.inpaint(clean, (mask > 40).astype(np.uint8) * 255,
                        float(spec.get('inpaint_radius2', 5)), cv2.INPAINT_NS)

    # 只在修补 footprint 内羽化柔化，不整块克隆贴图（克隆会留下横向接缝）
    ph, pw = y1 - y0, x1 - x0
    yy, xx = np.mgrid[0:ph, 0:pw]
    fx = np.clip(xx / (pw * float(spec.get('feather_x', 0.45))), 0, 1)
    fy = np.clip(yy / (ph * float(spec.get('feather_y', 0.35))), 0, 1)
    f = cv2.GaussianBlur((fx * fy).astype(np.float32), (0, 0),
                         float(spec.get('feather_blur', 10)))[:, :, None]
    strength = float(spec.get('feather_strength', 0.55))
    roi_now = clean[y0:y1, x0:x1].astype(np.float32)
    soft = cv2.GaussianBlur(roi_now.astype(np.uint8), (0, 0),
                            float(spec.get('soft_blur', 2.2))).astype(np.float32)
    clean[y0:y1, x0:x1] = (roi_now * (1 - f * strength) +
                           soft * (f * strength)).astype(np.uint8)
    return cv2.cvtColor(clean, cv2.COLOR_BGR2RGB)


def _sharpen_and_color(rgb, spec):
    """Lanczos 放大 -> LAB 的 L 通道 CLAHE -> 分档 UnsharpMask -> 增色。"""
    w, h = int(spec['width']), int(spec['height'])
    big = Image.fromarray(rgb).resize((w, h), Image.LANCZOS)
    arr = np.array(big)

    clahe = spec.get('clahe')
    if clahe and float(clahe.get('clip', 0)) > 0:
        lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
        L, a, b = cv2.split(lab)
        L = cv2.createCLAHE(
            clipLimit=float(clahe.get('clip', 1.3)),
            tileGridSize=tuple(clahe.get('tile', [8, 8]))
        ).apply(L)
        arr = cv2.cvtColor(cv2.merge([L, a, b]), cv2.COLOR_LAB2RGB)

    im = Image.fromarray(arr)
    for sh in spec.get('sharpen', []):
        im = im.filter(ImageFilter.UnsharpMask(
            radius=float(sh.get('radius', 1.2)),
            percent=int(sh.get('percent', 110)),
            threshold=int(sh.get('threshold', 2))))
    color = float(spec.get('color', 1.0))
    if color != 1.0:
        im = ImageEnhance.Color(im).enhance(color)
    return im


def enhance(background_cfg, base):
    """执行背景高清化，返回主输出路径。"""
    src = _abs(background_cfg['source'], base)
    out = _abs(background_cfg['out'], base)

    rgb = _read_rgb(src)
    rgb = _remove_watermark(rgb, background_cfg.get('dewatermark'))

    plain_rel = background_cfg.get('plain_out')
    plain_im = None
    if plain_rel:
        plain_im = Image.fromarray(rgb).resize(
            (int(background_cfg['width']), int(background_cfg['height'])),
            Image.LANCZOS)
        plain_path = _abs(plain_rel, base)
        os.makedirs(os.path.dirname(plain_path) or '.', exist_ok=True)
        plain_im.save(plain_path)

    im = _sharpen_and_color(rgb, background_cfg)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    im.save(out)

    # 可选：左=简单放大 / 右=增强后 的局部对照板，用于视觉验收
    cmp = background_cfg.get('compare')
    if cmp and cmp.get('out'):
        cell = tuple(cmp.get('cell', [800, 500]))
        box_out = tuple(cmp['box_out'])
        sx = int(background_cfg['width']) / rgb.shape[1]
        sy = int(background_cfg['height']) / rgb.shape[0]
        box_src = (int(box_out[0] / sx), int(box_out[1] / sy),
                   int(box_out[2] / sx), int(box_out[3] / sy))
        left = Image.fromarray(rgb).crop(box_src).resize(cell, Image.LANCZOS)
        right = im.crop(box_out).resize(cell, Image.LANCZOS)
        board = Image.new('RGB', (cell[0] * 2, cell[1]))
        board.paste(left, (0, 0))
        board.paste(right, (cell[0], 0))
        cmp_out = _abs(cmp['out'], base)
        os.makedirs(os.path.dirname(cmp_out) or '.', exist_ok=True)
        board.save(cmp_out)

    return out
