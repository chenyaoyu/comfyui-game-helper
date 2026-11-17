# -*- coding: utf-8 -*-
"""PSD 校验：尺寸 / 分组 / 图层数 / 中文名 / 合成图逐像素一致性。

依赖 psd_tools（只读）。验收时把 verify 结果与 build 时的合成图比对。
"""
import os

import numpy as np
from psd_tools import PSDImage


def _abs(path, base):
    return path if os.path.isabs(path) else os.path.join(base, path)


def verify(cfg, base, expected_composite=None):
    """校验 PSD，返回 (是否通过, 报告字典)。"""
    out_cfg = cfg['output']
    psd_path = _abs(out_cfg['psd'], base)
    W, H = int(cfg['canvas']['width']), int(cfg['canvas']['height'])

    psd = PSDImage.open(psd_path)
    report = {
        'path': psd_path,
        'size_ok': (psd.width, psd.height) == (W, H),
        'size': (psd.width, psd.height),
        'groups': [],
        'layer_count': 0,
        'names_ok': True,
        'composite': None,
    }

    def walk(node, depth=0):
        count = 0
        for child in node:
            if child.is_group():
                sub = walk(child, depth + 1)
                report['groups'].append({
                    'name': child.name.rstrip('\x00'), 'depth': depth, 'children': sub})
                count += sub
            else:
                count += 1
                # Adobe luni 规范：图层名末尾带 \x00 空终止符，属正常，不算错误
        return count

    report['layer_count'] = walk(psd)

    expected_names = {g['name'] for g in cfg['groups']}
    # psd_tools 读回的组名带 Adobe luni 规范的 \x00 空终止符，比较前先剥掉
    actual_names = {g['name'].rstrip('\x00') for g in report['groups']}
    # 精确相等：不允许少组、多组或组名不符
    report['names_ok'] = expected_names == actual_names

    if expected_composite is not None:
        flat = np.asarray(psd.composite().convert('RGB')).astype(np.int16)
        exp = expected_composite[:, :, :3].astype(np.int16)
        diff = np.abs(flat - exp)
        report['composite'] = {
            'mean_diff': round(float(diff.mean()), 6),
            'max_diff': int(diff.max()),
        }

    # 精确层数：重复层 / 多余层都要判失败（build 已用 _validate_groups 保证，这里是双保险）
    passed = (report['size_ok'] and report['names_ok'] and
              report['layer_count'] == len(cfg['layers']) and
              len(report['groups']) == len(cfg['groups']) and
              (report['composite'] is None or report['composite']['max_diff'] <= 2))
    return passed, report
