# -*- coding: utf-8 -*-
"""LanShare Android 入口（Chaquopy 自动执行本模块的 main()）"""

import os
import sys

# 确保能 import 同目录的 LanShare.py / templates.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import LanShare  # noqa: E402


def main():
    ok, info = LanShare.launch_android()
    print("[LanShare-Android] 启动结果:", ok, info)


if __name__ == "__main__":
    main()
