#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试增强日志记录功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.log_manager import LogManager
from utils.device_manager import ConfigExecutor, DeviceInfo
import time

def test_enhanced_logging():
    """测试增强的日志记录功能"""
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建测试设备
    test_device = DeviceInfo(
        index=0, 
        ip="192.168.1.100", 
        port="80", 
        username="admin", 
        password="password"
    )
    
    # 测试原始请求记录
    print("测试原始请求记录...")
    raw_command = "cgi-bin/configManager.cgi?action=getConfig&name=VideoStandard"
    
    # 记录CGI请求
    full_url = f"http://{test_device.ip}:{test_device.port}/{raw_command}"
    log_manager.log_cgi_request(
        test_device.ip, 1, 1, full_url, "digest", 
        {"User-Agent": "TestClient/1.0"}, "GET", raw_command
    )
    
    # 记录原始请求
    log_manager.log_raw_request(
        test_device.ip, 1, 1, full_url, raw_command, "digest", 
        {"User-Agent": "TestClient/1.0"}, "GET"
    )
    
    # 测试原始响应记录
    print("测试原始响应记录...")
    response_text = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <result>0</result>
    <VideoStandard>PAL</VideoStandard>
</Response>"""
    
    # 记录CGI响应
    log_manager.log_cgi_response(
        test_device.ip, 200, 1.5, 
        {"Content-Type": "application/xml"}, 
        response_text, success=True, raw_command=raw_command
    )
    
    # 记录原始响应
    log_manager.log_raw_response(
        test_device.ip, 200, 1.5, 
        {"Content-Type": "application/xml"}, 
        response_text, raw_command=raw_command
    )
    
    # 测试错误响应记录
    print("测试错误响应记录...")
    error_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <result>401</result>
    <error>Unauthorized</error>
</Response>"""
    
    # 记录错误响应
    log_manager.log_cgi_response(
        test_device.ip, 401, 0.8, 
        {"Content-Type": "application/xml"}, 
        error_response, success=False, raw_command=raw_command
    )
    
    log_manager.log_raw_response(
        test_device.ip, 401, 0.8, 
        {"Content-Type": "application/xml"}, 
        error_response, raw_command=raw_command
    )
    
    # 测试异常情况记录
    print("测试异常情况记录...")
    
    # 记录超时错误
    log_manager.log_cgi_response(
        test_device.ip, "TIMEOUT", 5.0, {}, 
        "请求超时 (超时设置: 5.0s)", success=False, raw_command=raw_command
    )
    
    log_manager.log_raw_response(
        test_device.ip, "TIMEOUT", 5.0, {}, 
        "请求超时 (超时设置: 5.0s)", raw_command=raw_command
    )
    
    # 记录连接错误
    log_manager.log_cgi_response(
        test_device.ip, "CONNECTION_ERROR", 0, {}, 
        "连接失败: Connection refused", success=False, raw_command=raw_command
    )
    
    log_manager.log_raw_response(
        test_device.ip, "CONNECTION_ERROR", 0, {}, 
        "连接失败: Connection refused", raw_command=raw_command
    )
    
    print("日志记录测试完成！")
    print("日志文件位置:", log_manager.log_dir)
    
    # 显示日志目录内容
    print("\n日志目录内容:")
    for file in os.listdir(log_manager.log_dir):
        if file.endswith('.log'):
            file_path = os.path.join(log_manager.log_dir, file)
            file_size = os.path.getsize(file_path)
            print(f"  {file} ({file_size} bytes)")

def test_device_manager_logging():
    """测试设备管理器中的日志记录功能"""
    
    print("\n测试设备管理器日志记录...")
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建配置执行器
    config = {
        "config_concurrent": 50,
        "timeout": 1000,
        "auth_method": "digest",
        "verify_ssl": False,
        "cgi_commands": [
            "VideoStandard=PAL",
            "VideoColor=Color",
            "VideoResolution=1920*1080"
        ]
    }
    
    config_executor = ConfigExecutor(config, log_manager)
    
    # 添加测试设备
    test_device = DeviceInfo(
        index=0, 
        ip="192.168.1.101", 
        port="80", 
        username="admin", 
        password="password123"
    )
    test_device.online = True  # 设置为在线状态
    test_device.status = "在线"  # 设置设备状态
    test_device.selected = True  # 设置为选中状态
    
    # 实际执行配置（这会触发_send_command方法中的日志记录）
    print("执行实际配置操作...")
    
    try:
        # 使用同步模式执行配置
        results = config_executor.execute_batch(
            [test_device], 
            mode="standard", 
            exec_strategy="device_first"
        )
        
        print(f"配置完成，结果: {len(results)} 台设备")
        
    except Exception as e:
        print(f"配置过程中出现错误: {e}")
        # 这是预期的，因为测试设备不存在，但会触发日志记录
    
    print("设备管理器日志记录测试完成！")

if __name__ == "__main__":
    print("开始测试增强日志记录功能...")
    
    try:
        test_enhanced_logging()
        test_device_manager_logging()
        
        print("\n所有测试完成！")
        print("请检查日志目录中的日志文件，确认原始请求和响应信息已正确记录。")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()