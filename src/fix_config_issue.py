#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置问题修复脚本
解决设备配置失败问题
"""

import os
import json
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth


def fix_config_file():
    """修复配置文件"""
    print("🔧 修复配置文件...")
    
    config_path = "config/dahua_config.json"
    
    # 读取当前配置
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return False
    
    # 修复配置项
    fixes = []
    
    # 确保认证方法正确
    if config.get('auth_method') not in ['digest', 'basic']:
        config['auth_method'] = 'digest'
        fixes.append("设置认证方法为digest")
    
    # 确保超时设置合理
    if config.get('timeout', 0) < 1000:
        config['timeout'] = 3000
        fixes.append("增加超时时间到3000ms")
    
    # 确保并发数合理
    if config.get('config_concurrent', 0) > 50:
        config['config_concurrent'] = 10
        fixes.append("降低并发数到10")
    
    # 保存修复后的配置
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
        if fixes:
            print("✅ 配置文件修复完成:")
            for fix in fixes:
                print(f"   - {fix}")
        else:
            print("✅ 配置文件无需修复")
        
        return True
    except Exception as e:
        print(f"❌ 保存配置文件失败: {e}")
        return False


def test_alternative_authentication(ip, port, username, password):
    """测试替代认证方法"""
    print(f"\n🔍 测试替代认证方法: {ip}:{port}")
    
    test_cases = [
        ("Digest认证", "digest"),
        ("Basic认证", "basic"),
        ("无认证", None),
        ("自定义认证头", "custom")
    ]
    
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=General"
    
    for test_name, auth_method in test_cases:
        try:
            if auth_method == "digest":
                auth = HTTPDigestAuth(username, password)
                response = requests.get(url, auth=auth, timeout=5, verify=False)
            elif auth_method == "basic":
                auth = HTTPBasicAuth(username, password)
                response = requests.get(url, auth=auth, timeout=5, verify=False)
            elif auth_method == "custom":
                headers = {'Authorization': f'Basic {username}:{password}'}
                response = requests.get(url, headers=headers, timeout=5, verify=False)
            else:
                response = requests.get(url, timeout=5, verify=False)
            
            if response.status_code == 200:
                print(f"✅ {test_name}: 成功")
                return auth_method
            elif response.status_code == 401:
                print(f"❌ {test_name}: 认证失败")
            else:
                print(f"⚠️ {test_name}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ {test_name}: 错误 - {str(e)}")
    
    return None


def create_custom_config():
    """创建自定义配置"""
    print("\n🔧 创建自定义配置...")
    
    # 获取用户输入
    print("请输入设备配置信息:")
    
    ip = input("设备IP地址 [10.17.1.11]: ").strip() or "10.17.1.11"
    port = input("端口 [80]: ").strip() or "80"
    username = input("用户名 [admin]: ").strip() or "admin"
    password = input("密码 [admin]: ").strip() or "admin"
    
    # 测试认证方法
    best_auth = test_alternative_authentication(ip, port, username, password)
    
    if best_auth:
        print(f"\n✅ 推荐使用 {best_auth} 认证方法")
        
        # 创建自定义配置
        custom_config = {
            "auth_method": best_auth,
            "timeout": 5000,
            "config_concurrent": 5,
            "ping_timeout": 1000,
            "verify_ssl": False,
            "cgi_commands": [
                "VideoWidget[0].CustomTitle[1].EncodeBlend=true",
                "VideoWidget[0].CustomTitle[1].PreviewBlend=true"
            ]
        }
        
        # 保存自定义配置
        try:
            with open("custom_config.json", "w", encoding="utf-8") as f:
                json.dump(custom_config, f, indent=4, ensure_ascii=False)
            
            print("✅ 自定义配置已保存: custom_config.json")
            print("💡 使用方法:")
            print("   复制 custom_config.json 内容到 config/dahua_config.json")
            print("   或直接使用自定义配置进行测试")
            
            return custom_config
        except Exception as e:
            print(f"❌ 保存自定义配置失败: {e}")
    else:
        print("❌ 所有认证方法都失败，请检查设备状态")
    
    return None


def test_with_custom_config():
    """使用自定义配置测试"""
    print("\n🧪 使用自定义配置测试...")
    
    # 检查是否有自定义配置
    if not os.path.exists("custom_config.json"):
        print("❌ 未找到自定义配置，请先运行创建自定义配置")
        return False
    
    try:
        with open("custom_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        
        print("✅ 加载自定义配置成功")
        print(f"   认证方法: {config.get('auth_method', 'digest')}")
        print(f"   超时时间: {config.get('timeout', 3000)}ms")
        print(f"   并发数: {config.get('config_concurrent', 10)}")
        
        # 测试配置
        from utils.log_manager import LogManager
        from utils.device_manager import ConfigExecutor, DeviceInfo
        
        log_manager = LogManager()
        
        # 创建测试设备
        test_device = DeviceInfo(
            index=0, ip="10.17.1.11", port="80", 
            username="admin", password="admin", status="在线"
        )
        test_device.online = True
        test_device.selected = True
        
        # 创建配置执行器
        executor = ConfigExecutor(config, log_manager, use_async=True)
        
        print("\n🚀 开始配置测试...")
        
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
        print(f"❌ 加载自定义配置失败: {e}")
        return False


def main():
    """主函数"""
    print("🔧 设备配置问题修复工具")
    print("=" * 60)
    
    # 显示选项菜单
    print("请选择修复选项:")
    print("1. 自动修复配置文件")
    print("2. 创建自定义配置")
    print("3. 使用自定义配置测试")
    print("4. 完整诊断和修复")
    
    choice = input("\n请输入选项 [1-4]: ").strip()
    
    if choice == "1":
        fix_config_file()
    elif choice == "2":
        create_custom_config()
    elif choice == "3":
        test_with_custom_config()
    elif choice == "4":
        print("\n🔧 执行完整诊断和修复...")
        fix_config_file()
        create_custom_config()
        test_with_custom_config()
    else:
        print("❌ 无效选项")
    
    print("\n💡 后续操作建议:")
    print("1. 如果认证失败，请确认设备用户名密码正确")
    print("2. 检查设备网络连接状态")
    print("3. 尝试不同的认证方法")
    print("4. 运行 'python detailed_diagnose.py' 进行详细诊断")


if __name__ == "__main__":
    main()