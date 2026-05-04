"""
数据库初始化脚本
创建测试数据库和示例数据
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from database.connection import initialize_demo_db


if __name__ == "__main__":
    print("Initializing demo database...")
    initialize_demo_db()
    print("Done!")
