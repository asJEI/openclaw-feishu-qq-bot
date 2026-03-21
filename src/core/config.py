import yaml
import os
from pathlib import Path

class Config:
    def __init__(self):
        # 获取项目根目录路径
        self.base_path = Path(__file__).parent.parent.parent
        self.config_path = self.base_path / "config" / "config.yaml"
        
        # 如果没有真实配置文件，尝试读示例文件（仅用于容错）
        if not self.config_path.exists():
            self.config_path = self.base_path / "config" / "config-example.yaml"
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._data = yaml.safe_load(f)

    def get(self, key, default=None):
        keys = key.split('.')
        value = self._data
        try:
            for k in keys:
                value = value[k]
            return value
        except KeyError:
            return default

# 实例化，方便其他模块直接 import settings
settings = Config()