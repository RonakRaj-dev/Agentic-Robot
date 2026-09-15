import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import compatibility layer to monkeypatch agentscope message and models classes
import models.compat
