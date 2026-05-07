"""
tests/conftest.py — pytest için proje kök dizinini path'e ekler.
"""
import sys
import os

# Proje kökünü path'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
