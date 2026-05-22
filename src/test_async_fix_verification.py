
#!/usr/bin/env python3
"""
测试异步执行器修复效果
验证线程池环境中的事件循环问题是否已解决
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from utils.async_executor import AsyncIOManager
from utils.device_manager import DeviceInfo

def test_async_in_thread_pool():
    """在线程池中测试异步执行"""
    
    async def run_async_test():
        """异步测试函数"""
        # 创建测试设备
        device = DeviceInfo(
            index=1,
            ip="10.17.1.11",
            port=80,
            username="admin",
            password="admin123",
            online=True
        )
        
        # 创建异步管理器
        async_manager = AsyncIOManager()
        
        # 测试命令
        command = "VideoWidget[0].CustomTitle[1].EncodeBlend=true"
        
        try:
            # 发送异步命令
            result = await async_manager.send_command_async(device, command)
            print(f"异步命令执行结果: {result}")
            
            # 检查返回格式
            if isinstance(result, tuple) and len(result) == 5:
                print("✅ 返回格式正确：5元素元组")
                ok, text, status, headers, error = result
                print(f"  成功标志: {ok}")
                print(f"  响应文本: {text[:100]}..." if text else "  响应文本: 空")
                print(f"  状态: {status}")
                print(f"  错误信息: {error}")
            else:
                print(f"❌ 返回格式错误: {type(result)}, 长度: {len(result) if hasattr(result, '__len__') else 'N/A'}")
                
        except Exception as e:
            print(f"❌ 异步命令执行异常: {e}")
            import traceback
            traceback.print_exc()
    
    # 在线程池中运行异步测试
    def run_in_thread_pool():
        """在线程池中运行异步代码"""
        try:
            # 在线程池中创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行异步测试
            loop.run_until_complete(run_async_test())
            loop.close()
            
        except Exception as e:
            print(f"❌ 线程池执行异常: {e}")
            import traceback
            traceback.print_exc()
    
    # 使用线程池执行
    print("=== 测试线程池中的异步执行 ===")
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        for i in range(3):
            future = executor.submit(run_in_thread_pool)
            futures.append(future)
        
        # 等待所有任务完成
        for future in futures:
            future.result()

def test_direct_async():
    """直接测试异步执行"""
    
    async def run_direct_test():
        """直接异步测试"""
        device = DeviceInfo(
            index=1,
            ip="10.17.1.11",
            port=80,
            username="admin",
            password="admin123",
            online=True
        )
        
        async_manager = AsyncIOManager()
        command = "VideoWidget[0].CustomTitle[1].EncodeBlend=true"
        
        try:
            result = await async_manager.send_command_async(device, command)
            print(f"直接异步执行结果: {result}")
            
            if isinstance(result, tuple) and len(result) == 5:
                print("✅ 直接异步执行成功")
            else:
                print("❌ 直接异步执行失败")
                
        except Exception as e:
            print(f"❌ 直接异步执行异常: {e}")
    
    print("\n=== 测试直接异步执行 ===")
    asyncio.run(run_direct_test())

if __name__ == "__main__":
    print("开始测试异步执行器修复...")
    
    # 测试直接异步执行
    test_direct_async()
    
    # 测试线程池中的异步执行
    test_async_in_thread_pool()
    
    print("\n=== 测试完成 ===")