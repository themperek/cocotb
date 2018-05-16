#!/usr/bin/env python

import os

os.environ['SPHINX_BUILD'] = '1'
import cocotb

def main():
    print(os.path.dirname(os.path.dirname(cocotb.__file__)))

if __name__ == "__main__":
    main()