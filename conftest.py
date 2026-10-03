"""
conftest.py — pytest shared fixtures for SmartRoute test suite
"""
import os
import sys

# Ensure the project root is on the Python path for all tests
sys.path.insert(0, os.path.dirname(__file__))
