#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大华摄像机批量配置工具 - 优化版 v9.5 (基于 v9.4.8)
此版本为 V9.5，初始复制自 V9.4.1 并添加异步执行器骨架。
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
import time
import re  # 添加re模块导入

# 使用已迁移的 full_app 作为主界面入口
try:
    from full_app import DahuaConfigApp
except Exception as e:
    print(f"无法导入 full_app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 其余 main.py 内容保持与 v9.4.1 相同，用作 V9.5 的起点。
# 为简洁起见，此文件已在 V9.4.1 中验证并复制到 V9.5。

# 如果需要，我可以在 V9.5 中逐步替换 ConfigExecutor 的实现以使用 async_executor。

# 移除对第三方库的依赖，使用内置的DIGEST认证实现
print("使用内置的DIGEST认证实现")

def main():
    try:
        print("=" * 60)
        print("大华摄像机批量配置工具 v9.5")
        print("基于 v9.4.x 复制并添加异步执行器骨架")
        print("=" * 60)
        
        # 不再创建额外的tk.Tk()实例，因为DahuaConfigApp已经继承自tk.Tk
        # root = tk.Tk()
        # try:
        #     if os.path.exists("icon.ico"):
        #         root.iconbitmap("icon.ico")
        # except:
        #     pass
        
        # 直接启动已迁移的完整主界面
        app = DahuaConfigApp()
        app.mainloop()
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("按Enter键退出...")

if __name__ == "__main__":
    main()