import cv2, numpy as np
from PIL import Image, ImageFilter, ImageEnhance

SRC = 'generated-images/Edit_this_exact_image__There_i_2026-11-01T04-38-18.png'
OUT = 'psd_work/bg_clean_1920.png'

bgr = cv2.imread(SRC, cv2.IMREAD_COLOR)
h, w = bgr.shape[:2]

# --- 1) watermark mask: wider ROI + looser threshold, dilate generously ---
mask = np.zeros((h, w), np.uint8)
x0, y0 = 1150, 640
roi = bgr[y0:h, x0:w]
hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
v, s = hsv[:, :, 2], hsv[:, :, 1]
sel = ((v > 62) & (s < 135)).astype(np.uint8) * 255
sel = cv2.dilate(sel, np.ones((7, 7), np.uint8), iterations=3)
sel = cv2.GaussianBlur(sel, (9, 9), 0)      # soft mask edge
mask[y0:h, x0:w] = sel
print('mask pixels', int((mask > 0).sum()))

# --- 2) inpaint, twice for stubborn glyph interiors ---
clean = cv2.inpaint(bgr, mask, 9, cv2.INPAINT_TELEA)
clean = cv2.inpaint(clean, (mask > 40).astype(np.uint8) * 255, 5, cv2.INPAINT_NS)

# --- 3) soften ONLY the repaired watermark footprint, feathered, no cloning ---
ph, pw = h - y0, w - x0
yy, xx = np.mgrid[0:ph, 0:pw]
feather = np.clip(np.minimum.reduce([yy/16.0, (ph-1-yy)/16.0, (pw-1-xx)/16.0]) * 0 + 1, 0, 1)
# use a soft radial-ish feather that is 1 in the watermark core, 0 at top/left edges
f = np.clip((xx / (pw*0.45)), 0, 1) * np.clip((yy / (ph*0.35)), 0, 1)
f = cv2.GaussianBlur(f.astype(np.float32), (0,0), 10)[:, :, None]
roi_now = clean[y0:h, x0:w].astype(np.float32)
blur_roi = cv2.GaussianBlur(roi_now.astype(np.uint8), (0,0), 2.2).astype(np.float32)
clean[y0:h, x0:w] = (roi_now*(1-f*0.55) + blur_roi*(f*0.55)).astype(np.uint8)

cv2.imwrite('psd_work/bg_clean_1280.png', clean)

# --- 4) upscale 1.5x Lanczos + gentle clarity ---
rgb = cv2.cvtColor(clean, cv2.COLOR_BGR2RGB)
big = Image.fromarray(rgb).resize((1920, 1080), Image.LANCZOS)
arr = np.array(big)
lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
L, a, b = cv2.split(lab)
L = cv2.createCLAHE(clipLimit=1.35, tileGridSize=(8, 8)).apply(L)
arr = cv2.cvtColor(cv2.merge([L, a, b]), cv2.COLOR_LAB2RGB)
sharp = Image.fromarray(arr).filter(ImageFilter.UnsharpMask(radius=1.4, percent=115, threshold=3))
ImageEnhance.Color(sharp).enhance(1.05).save(OUT)
print('saved', OUT)
