#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")
from game.models import *
from game.tests import *

def main():
    for event in Event.objects.all():
        event = event.as_child()
        if event.AUTOMATIC:
            event.delete()

if __name__ == '__main__':
    main()
