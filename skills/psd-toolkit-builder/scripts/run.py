#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""便捷包装：从任意位置调用登录页 PSD 工具流。

用法：
    py -X utf8 run.py <config.json> <enhance|build|verify|all>

自动定位仓库内 psd-toolkit/tools/psd_tool.py（可用 PSD_TOOL_ROOT 环境变量覆盖），
用系统里带 cv2 的 py39 解释器执行。配置路径可以是相对或绝对。
"""
import os
import subprocess
import sys

# 从本脚本位置推算仓库根：.../comfyui-game-helper/skills/psd-toolkit-builder/scripts/run.py
# 向上 3 级到 comfyui-game-helper，工具在 psd-toolkit/ 下。
_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_SKILL_DIR)))
TOOL_ROOT = os.environ.get(
    "PSD_TOOL_ROOT",
    os.path.join(_REPO_ROOT, "psd-toolkit"))
ENTRY = os.path.join(TOOL_ROOT, "tools", "psd_tool.py")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    config = os.path.abspath(sys.argv[1])
    command = sys.argv[2]
    if command not in ("enhance", "build", "verify", "all"):
        print("[ERROR] 命令必须是 enhance / build / verify / all")
        return 2
    if not os.path.isfile(config):
        print("[ERROR] 配置不存在:", config)
        return 2

    cmd = [sys.executable, "-X", "utf8", ENTRY, "-c", config, command]
    print("[RUN]", " ".join(cmd))
    return subprocess.call(cmd, cwd=TOOL_ROOT)


if __name__ == "__main__":
    sys.exit(main())
