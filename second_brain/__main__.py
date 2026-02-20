#!/usr/bin/env python3
"""
支持 python -m second_brain 方式调用
"""

from .cli import main

if __name__ == '__main__':
    import sys
    sys.exit(main())
