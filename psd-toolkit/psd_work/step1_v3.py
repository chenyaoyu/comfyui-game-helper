# -*- coding: utf-8 -*-
"""V3 背景高清化：1280x720 -> 1920x1080，针对暗调 + 密符文做分档清晰度增强。
源图已完成像素级去水印，这里不再动水印区域，只做放大/对比/锐化。"""
import os, cv2, numpy as np
from PIL import Image, ImageFilter, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '通天录_C调整_V3_密录千眼 · 朱砂满卷.png')
OUT = os.path.join(ROOT, 'psd_work', 'v3_clean_1920.png')
PLAIN = os.path.join(ROOT, 'psd_work', 'v3_plain_1920.png')
PREVIEW = os.path.join(ROOT, 'psd_work', 'v3_clarity_compare.png')

# 用 PIL 读取，避开 cv2.imread 在 Windows 上的中文路径问题
rgb = np.array(Image.open(SRC).convert('RGB'))
print('src', rgb.shape, 'mean', round(rgb.mean(), 1))

big = Image.fromarray(rgb).resize((1920, 1080), Image.LANCZOS)
big.save(PLAIN)                      # 纯放大对照
arr = np.array(big)

# 1) LAB 亮度通道局部对比：把暗部符文层次拉开，不动色相
lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
L, a, b = cv2.split(lab)
L = cv2.createCLAHE(clipLimit=1.30, tileGridSize=(8, 8)).apply(L)
arr = cv2.cvtColor(cv2.merge([L, a, b]), cv2.COLOR_LAB2RGB)

# 2) 分档锐化：细档提符文笔画，粗档提竹简/眼纹轮廓，都带 threshold 防噪点放大
im = Image.fromarray(arr)
im = im.filter(ImageFilter.UnsharpMask(radius=1.1, percent=118, threshold=2))
im = im.filter(ImageFilter.UnsharpMask(radius=2.8, percent=32,  threshold=6))

# 3) 轻微色饱和，补回放大+锐化后偏灰的朱砂
im = ImageEnhance.Color(im).enhance(1.06)
im.save(OUT)
print('saved', OUT, im.size)

# 4) 清晰度对照板：同一区域，左=简单放大，右=增强后（各 2x 局部）
box = (250, 150, 650, 400)          # 符文/眼纹密集区（1920 坐标）
box2 = (int(box[0] / 1.5), int(box[1] / 1.5), int(box[2] / 1.5), int(box[3] / 1.5))
left = Image.open(SRC).crop(box2).resize((800, 500), Image.LANCZOS)
right = im.crop(box).resize((800, 500), Image.LANCZOS)
cv = Image.new('RGB', (1600, 500))
cv.paste(left, (0, 0)); cv.paste(right, (800, 0))
cv.save(PREVIEW)
print('compare saved')
