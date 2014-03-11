#!/usr/bin/python
# -*- coding: utf-8 -*-

import ast
import sys

def main():
    source = sys.stdin.read()
    a = ast.parse(source)
    for x in ast.walk(a):
        if isinstance(x, ast.Str):
            print x.s

if __name__ == '__main__':
    main()
