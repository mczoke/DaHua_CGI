#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解决认证问题的专用脚本
针对密码相同但认证失败的情况
"""

import os
import json
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth


def get_actual_password():
    """获取实际使用的密码"""
    print("🔑 请输入设备实际使用的密码:")
    print("   (如果所有设备使用相同密码，请输入一次即可)")
    
    password = input("密码: ").strip()
    
    if not password:
        print("⚠️ 密码不能为空，使用默认密码 'admin'")
        password = "admin"
    
    return password


def test_with_actual_password(ip, port, username, password):
    """使用实际密码测试"""
    print(f"\n🧪 测试设备: {ip}:{port}")
    print(f"   用户名: {username}")
    print(f"   密码: {password}")
    
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=General"
    
    # 测试Digest认证
    try:
        auth = HTTPDigestAuth(username, password)
        response = requests.get(url, auth=auth, timeout=5, verify=False)
        
        if response.status_code == 200:
            print("✅ Digest认证: 成功")
            return "digest"
        elif response.status_code == 401:
            print("❌ Digest认证: 失败 (用户名/密码错误)")
        else:
            print(f"⚠️ Digest认证: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Digest认证: 错误 - {str(e)}")
    
    # 测试Basic认证
    try:
        auth = HTTPBasicAuth(username, password)
        response = requests.get(url, auth=auth, timeout=5, verify=False)
        
        if response.status_code == 200:
            print("✅ Basic认证: 成功")
            return "basic"
        elif response.status_code == 401:
            print("❌ Basic认证: 失败 (用户名/密码错误)")
        else:
            print(f"⚠️ Basic认证: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Basic认证: 错误 - {str(e)}")
    
    # 测试无认证
    try:
        response = requests.get(url, timeout=5, verify=False)
        
        if response.status_code == 200:
            print("✅ 无认证: 成功 (设备无需认证)")
            return "none"
        elif response.status_code == 401:
            print("❌ 无认证: 失败 (设备需要认证)")
        else:
            print(f"⚠️ 无认证: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ 无认证: 错误 - {str(e)}")
    
    return None


def update_config_with_correct_auth(auth_method, password):
    """更新配置文件使用正确的认证方法"""
    print(f"\n🔧 更新配置文件...")
    
    config_path = "config/dahua_config.json"
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 更新认证方法
        config['auth_method'] = auth_method
        
        # 增加超时时间
        config['timeout'] = 5000
        
        # 降低并发数以提高稳定性
        config['config_concurrent'] = 5
        config['ping_concurrent'] = 5
        
        # 保存更新后的配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
        print("✅ 配置文件已更新:")
        print(f"   认证方法: {auth_method}")
        print(f"   超时时间: 5000ms")
        print(f"   并发数: 5")
        
        return True
        
    except Exception as e:
        print(f"❌ 更新配置文件失败: {e}")
        return False


def create_device_file_with_correct_password(password):
    """创建设备文件使用正确的密码"""
    print(f"\n📋 创建设备文件...")
    
    # 创建设备列表
    devices = [
        {"IP地址": "10.17.1.11", "端口": "80", "用户名": "admin", "密码": password},
        {"IP地址": "10.17.1.12", "端口": "80", "用户名": "admin", "密码": password},
        {"IP地址": "10.17.1.13", "端口": "80", "用户名": "admin", "密码": password},
        {"IP地址": "10.17.1.14", "端口": "80", "用户名": "admin", "密码": password},
        {"IP地址": "10.17.1.15", "端口": "80", "用户名": "admin", "密码": password},
        {"IP地址": "10.17.1.16", "端口": "80", "用户名": "admin", "密码": password},
        {"IP地址": "10.17.1.17", "端口": "80", "用户名": "admin", "密码": password},
        {"IP地址": "10.17.1.18", "端口": "80", "用户名": "admin", "密码": password},
        {"IP地址": "10.17.1.19", "端口": "80", "用户名": "admin", "密码": password},
        {"IP地址": "10.17.1.20", "端口": "80", "用户名": "admin", "密码": password},
    ]
    
    # 保存为CSV文件
    try:
        import pandas as pd
        df = pd.DataFrame(devices)
        df.to_excel("correct_devices.xlsx", index=False)
        
        print("✅ 设备文件已创建: correct_devices.xlsx")
        print(f"   包含 {len(devices)} 台设备")
        print(f"   密码: {password}")
        
        return True
        
    except Exception as e:
        print(f"❌ 创建设备文件失败: {e}")
        
        # 如果pandas不可用，创建简单的文本文件
        try:
            with open("correct_devices.txt", "w", encoding="utf-8") as f:
                f.write("IP地址,端口,用户名,密码\n")
                for device in devices:
                    f.write(f"{device['IP地址']},{device['端口']},{device['用户名']},{device['密码']}\n")
            
            print("✅ 设备文件已创建: correct_devices.txt")
            return True
            
        except Exception as e2:
            print(f"❌ 创建设备文本文件也失败: {e2}")
            return False


def test_fixed_configuration():
    """测试修复后的配置"""
    print(f"\n🚀 测试修复后的配置...")
    
    try:
        from utils.log_manager import LogManager
        from utils.device_manager import ConfigExecutor, DeviceInfo
        
        # 创建日志管理器
        log_manager = LogManager()
        
        # 加载配置
        from utils.config_manager import ConfigManager
        config = ConfigManager.load_config()
        
        print("✅ 配置加载成功:")
        print(f"   认证方法: {config.get('auth_method', 'digest')}")
        print(f"   超时时间: {config.get('timeout', 3000)}ms")
        
        # 创建测试设备
        test_device = DeviceInfo(
            index=0, ip="10.17.1.11", port="80", 
            username="admin", password="admin", status="在线"
        )
        test_device.online = True
        test_device.selected = True
        
        # 创建配置执行器
        executor = ConfigExecutor(config, log_manager, use_async=True)
        
        print("\n开始配置测试...")
        
        try:
            results = executor.execute_batch(
                [test_device], 
                mode="standard", 
                exec_strategy="device_first"
            )
            
            if results and len(results) > 0:
                print("✅ 配置测试成功！")
                return True
            else:
                print("❌ 配置测试失败")
                return False
                
        except Exception as e:
            print(f"❌ 配置执行错误: {e}")
            return False
            
    except Exception as e:
        print(f"❌ 测试准备失败: {e}")
        return False


def main():
    """主函数"""
    print("🔧 认证问题解决方案")
    print("=" * 60)
    print("针对密码相同但认证失败的情况")
    print()
    
    # 获取实际密码
    actual_password = get_actual_password()
    
    # 测试第一个设备
    print(f"\n📡 测试第一个设备 (10.17.1.11)...")
    best_auth = test_with_actual_password("10.17.1.11", "80", "admin", actual_password)
    
    if best_auth:
        print(f"\n✅ 找到有效的认证方法: {best_auth}")
        
        # 更新配置文件
        if update_config_with_correct_auth(best_auth, actual_password):
            # 创建设备文件
            if create_device_file_with_correct_password(actual_password):
                # 测试修复后的配置
                if test_fixed_configuration():
                    print("\n🎉 问题解决完成！")
                    print("💡 下一步操作:")
                    print("   1. 使用 correct_devices.xlsx 文件加载设备")
                    print("   2. 运行配置程序进行批量配置")
                    print("   3. 如果仍有问题，运行 'python detailed_diagnose.py'")
                else:
                    print("\n⚠️ 配置测试失败，但基础设置已完成")
            else:
                print("\n⚠️ 创建设备文件失败")
        else:
            print("\n⚠️ 更新配置文件失败")
    else:
        print("\n❌ 所有认证方法都失败")
        print("💡 可能的原因:")
        print("   1. 设备不在线或网络不通")
        print("   2. 用户名/密码确实不正确")
        print("   3. 设备不支持CGI配置")
        print("   4. 防火墙或网络限制")
        print("\n🔧 建议:")
        print("   1. 确认设备IP地址正确")
        print("   2. 确认设备在线且可访问")
        print("   3. 尝试使用浏览器直接访问设备")
        print("   4. 运行 'python detailed_diagnose.py' 进行详细诊断")


if __name__ == "__main__":
    main()