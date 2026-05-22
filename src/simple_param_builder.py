#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化参数构造器
将复杂JSON参数转换为标准CGI格式
"""

class SimpleParamBuilder:
    """简化参数构造器"""
    
    @staticmethod
    def build_dahua_params(command: dict) -> str:
        """
        将复杂命令转换为大华设备标准参数格式
        
        Args:
            command: 原始命令字典
            
        Returns:
            标准CGI参数字符串
        """
        action = command.get("action", "")
        
        if action != "setConfig":
            # 非setConfig命令直接返回
            import urllib.parse
            return urllib.parse.urlencode(command, doseq=True)
        
        param = command.get("param", {})
        params = ["action=setConfig"]
        
        # 递归处理参数
        SimpleParamBuilder._process_params(param, "", params)
        
        return "&".join(params)
    
    @staticmethod
    def _process_params(data, prefix, params):
        """递归处理参数"""
        if isinstance(data, dict):
            for key, value in data.items():
                new_prefix = f"{prefix}[{key}]" if prefix else key
                SimpleParamBuilder._process_params(value, new_prefix, params)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_prefix = f"{prefix}[{i}]" if prefix else str(i)
                SimpleParamBuilder._process_params(item, new_prefix, params)
        else:
            # 基本类型
            param_str = f"{prefix}={data}"
            params.append(param_str)

# 使用示例
if __name__ == "__main__":
    builder = SimpleParamBuilder()
    
    # 复杂命令示例
    complex_command = {
        "action": "setConfig",
        "param": {
            "VideoWidget": [
                {
                    "Name": "VideoWidget",
                    "VideoWidgetTitle": {
                        "enabled": True,
                        "text": "Test Title"
                    }
                }
            ]
        }
    }
    
    simple_params = builder.build_dahua_params(complex_command)
    print("简化后的参数:")
    print(simple_params)
    
    # 输出: action=setConfig&VideoWidget[0][Name]=VideoWidget&VideoWidget[0][VideoWidgetTitle][enabled]=True&VideoWidget[0][VideoWidgetTitle][text]=Test Title
