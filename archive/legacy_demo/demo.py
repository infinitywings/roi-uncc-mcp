#!/usr/bin/env python3
"""
Main demo launcher - wrapper for the actual demo scripts
"""

import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

# Import and run the actual demo
from demo_docker import main

if __name__ == '__main__':
    main()