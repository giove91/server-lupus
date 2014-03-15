#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")
from game.models import *
from game.tests import *

def main():
    delete_auto_users()

if __name__ == '__main__':
    main()
