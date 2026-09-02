# -*- coding: utf-8 -*-
"""LanShare Android 入口。

兼容 Chaquopy 两种入口触发方式（顶层执行 或 自动调用 main()），
用 _STATE 保证 launch_android() 只执行一次。
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import LanShare  # noqa: E402

_ERROR = ""
_STATE = "starting"


def _run():
    global _ERROR, _STATE
    try:
        ok, info = LanShare.launch_android()
        if ok:
            _STATE = "running"
        else:
            _STATE = "error"
            _ERROR = "launch 返回失败: %r" % (info,)
    except Exception:
        _STATE = "error"
        _ERROR = traceback.format_exc()


def _ensure_run():
    if _STATE == "starting":
        _run()
    return _STATE


def main():
    _ensure_run()


def get_status():
    """供 App 界面读取：返回 'running' 或错误详情"""
    _ensure_run()
    return _ERROR if _STATE == "error" else _STATE


def set_share(path, is_file=False):
    """App 系统文件选择器选定目录/文件后调用（path 为真实路径）"""
    _ensure_run()
    return LanShare.add_share(path)


# 双保险：若 Chaquopy 入口是“执行顶层代码”，这里会立即触发
if os.environ.get("_LANSHARE_MAIN_RUN") != "1":
    os.environ["_LANSHARE_MAIN_RUN"] = "1"
    _ensure_run()

if __name__ == "__main__":
    main()
