# tests/conftest.py
"""
Shared pytest fixtures and configuration.
Ensures the project root is on sys.path for all test modules.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
