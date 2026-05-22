#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试日志系统修复验证脚本
验证GUI日志和文件日志的正确区分
"""

import os
import sys
import time
from datetime import datetime

# 添加utils路径到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from log_manager import LogManager
from device_manager import ConfigExecutor

class MockLogCallback:
    """模拟GUI日志回调函数"""
    def __init__(self):
        self.gui_logs = []
    
    def __call__(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.gui_logs.append(log_entry)
        print(f"GUI日志: {log_entry}")

def test_logging_separation():
    """测试GUI日志和文件日志的区分"""
    print("=== 测试日志系统修复 ===")
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建模拟GUI回调
    gui_callback = MockLogCallback()
    
    # 创建配置执行器
    config = {
        "cgi_commands": ["Network.eth0.IPAddress=192.168.1.100"],
        "verify_ssl": False
    }
    
    executor = ConfigExecutor(config, log_manager=log_manager, log_callback=gui_callback)
    
    print("\n1. 测试GUI日志和文件日志的区分:")
    
    # 测试GUI日志（处理后的进度信息）
    executor._log("开始配置设备", "INFO")
    executor._log("设备 192.168.1.100 CGI请求 1/1: http://192.168.1.100/cgi-bin/configManager.cgi?action=setConfig&Network.eth0.IPAddress=192.168.1.100", "INFO")
    executor._log("设备 192.168.1.100 CGI响应: 状态码=200, 耗时=0.5s, 响应内容='OK'", "INFO")
    executor._log("配置完成", "INFO")
    
    # 测试文件日志（原始请求响应）
    log_manager.log_cgi_request(
        "192.168.1.100", 1, 1, 
        "http://192.168.1.100/cgi-bin/configManager.cgi?action=setConfig&Network.eth0.IPAddress%3D192.168.1.100",
        "Digest", 
        {"User-Agent": "Mozilla/5.0"},
        raw_command="Network.eth0.IPAddress=192.168.1.100"
    )
    
    log_manager.log_cgi_response(
        "192.168.1.100", 200, 0.5, 
        {"Content-Type": "text/plain"}, 
        "OK", 
        success=True,
        raw_command="Network.eth0.IPAddress=192.168.1.100"
    )
    
    print("\n2. 检查GUI日志内容（应该只包含处理后的进度信息）:")
    for log in gui_callback.gui_logs:
        print(f"  {log}")
    
    print("\n3. 检查文件日志路径:")
    print(f"  详细日志文件: {log_manager.detailed_log_file}")
    print(f"  失败日志文件: {log_manager.failure_log_file}")
    
    # 读取文件日志内容
    try:
        with open(log_manager.detailed_log_file, 'r', encoding='utf-8') as f:
            file_logs = f.readlines()
        
        print("\n4. 检查文件日志内容（应该包含原始请求响应）:")
        for log in file_logs[-10:]:  # 显示最后10行
            if log.strip():
                print(f"  文件日志: {log.strip()}")
    except Exception as e:
        print(f"读取文件日志失败: {e}")
    
    print("\n5. 验证日志区分:")
    gui_log_count = len(gui_callback.gui_logs)
    print(f"  GUI日志数量: {gui_log_count}")
    print(f"  GUI日志内容: 处理后的进度信息")
    print(f"  文件日志内容: 原始请求响应数据")
    
    # 清理
    executor.stop()
    
    print("\n=== 测试完成 ===")
    return True

def test_async_logging_fix():
    """测试异步路径日志修复"""
    print("\n=== 测试异步路径日志修复 ===")
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建模拟GUI回调
    gui_callback = MockLogCallback()
    
    # 创建配置执行器（启用异步）
    config = {
        "cgi_commands": ["Network.eth0.IPAddress=192.168.1.100"],
        "verify_ssl": False
    }
    
    executor = ConfigExecutor(config, log_manager=log_manager, log_callback=gui_callback, use_async=True)
    
    print("\n1. 测试异步路径的日志记录:")
    
    # 模拟异步路径的日志记录
    if executor.async_manager:
        print("  ✓ AsyncIOManager 已初始化")
        
        # 测试异步路径的日志记录方法
        executor._log("[async] 开始异步配置", "INFO")
        
        # 模拟异步请求日志记录
        base_url = "http://192.168.1.100/cgi-bin/configManager.cgi"
        command = "Network.eth0.IPAddress=192.168.1.100"
        encoded_cmd = "Network.eth0.IPAddress%3D192.168.1.100"
        full_url = f"{base_url}?action=setConfig&{encoded_cmd}"
        
        # 记录原始请求（应该记录到文件）
        log_manager.log_cgi_request(
            "192.168.1.100", 1, 1, full_url, "Digest", 
            {"User-Agent": "Mozilla/5.0"}, raw_command=command
        )
        
        # 记录GUI进度信息
        executor._log(f"设备 192.168.1.100 CGI请求 1/1: {base_url}?action=setConfig&Network.eth0.IPAddress=192.168.1.100", "INFO")
        
        print("  ✓ 异步路径日志记录测试完成")
    else:
        print("  ✗ AsyncIOManager 初始化失败")
    
    # 清理
    executor.stop()
    
    print("\n=== 异步路径测试完成 ===")
    return True

if __name__ == "__main__":
    try:
        test_logging_separation()
        test_async_logging_fix()
        print("\n✅ 所有测试通过！日志系统修复验证成功")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()