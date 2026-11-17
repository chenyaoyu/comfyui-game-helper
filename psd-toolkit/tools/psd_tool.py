#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通用登录页 PSD 工具流统一入口。

用法：
    python tools/psd_tool.py --config configs/v3.json enhance   # 背景高清化
    python tools/psd_tool.py --config configs/v3.json build     # 组装分层 PSD
    python tools/psd_tool.py --config configs/v3.json verify    # 校验产物
    python tools/psd_tool.py --config configs/v3.json all       # 三步全跑（推荐）

配置里的所有相对路径都相对于「配置文件所在目录的父目录」解析，
也就是项目根（configs/ 的上一级），见 doc/PSD工具流说明.md。
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 项目本地依赖目录（pytoshop / packbits），保证工具自包含
sys.path.insert(0, os.path.join(ROOT, '.libs'))
sys.path.insert(0, HERE)


def load_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    return cfg


def config_base(path):
    """配置相对路径的基准 = configs 目录的父目录（项目根）。"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    return base


def main():
    ap = argparse.ArgumentParser(
        description='通用登录页 PSD 工具流：背景高清化 / 分层 PSD 组装 / 校验')
    ap.add_argument('--config', '-c', required=True, help='JSON 配置文件路径')
    ap.add_argument('command', choices=['enhance', 'build', 'verify', 'all'],
                    help='要执行的步骤；all = enhance + build + verify')
    args = ap.parse_args()

    cfg_path = os.path.abspath(args.config)
    if not os.path.isfile(cfg_path):
        print('[ERROR] 配置文件不存在:', cfg_path)
        return 2
    cfg = load_config(cfg_path)
    base = config_base(cfg_path)
    print('[INFO] 配置:', cfg_path)
    print('[INFO] 路径基准:', base)

    cmd = args.command
    composite = None

    if cmd in ('enhance', 'all'):
        from enhancer import enhance
        out = enhance(cfg['background'], base)
        print('[OK] 背景高清化完成:', out)
        # 消除 background.out 与 layers[0].file 的双真相源：
        # all 模式把实际输出路径注入第 0 层，build 不再依赖两处字符串恰好相同
        if cmd == 'all':
            rel = os.path.relpath(out, base).replace('\\', '/')
            cfg['layers'][0]['file'] = rel

    if cmd in ('build', 'all'):
        from psd_builder import build
        psd_path, composite = build(cfg, base)
        print('[OK] PSD 组装完成:', psd_path, os.path.getsize(psd_path), 'bytes')

    if cmd in ('verify', 'all'):
        from verifier import verify
        # all 模式用刚算出的合成图比对；单独 verify 时读预览图当期望值
        if composite is None:
            from PIL import Image
            preview = os.path.join(base, cfg['output']['preview'])
            composite = np.asarray(Image.open(preview).convert('RGBA'))
        passed, report = verify(cfg, base, composite)
        print('[VERIFY] 尺寸:', report['size'],
              '| 组数:', len(report['groups']),
              '| 图层数:', report['layer_count'])
        print('[VERIFY] 组名:', [g['name'] for g in report['groups']])
        if report['composite']:
            print('[VERIFY] 合成图差异: mean=%.6f max=%d' % (
                report['composite']['mean_diff'], report['composite']['max_diff']))
        print('[VERIFY] 结果:', 'PASS' if passed else 'FAIL')
        return 0 if passed else 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
