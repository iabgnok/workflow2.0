"""将 new_src 加入 sys.path，使 agent.engine.* 可正确导入。"""
import sys
import os

new_src = os.path.join(os.path.dirname(__file__), "..", "..")
if new_src not in sys.path:
    sys.path.insert(0, os.path.abspath(new_src))
