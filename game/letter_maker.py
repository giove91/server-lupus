# -*- coding: utf-8 -*-

from django.template.loader import render_to_string
import codecs

from models import *


def render_to_file(template, filename, context):
    codecs.open(filename, 'w', 'utf-8').write(render_to_string(template, context))


def prova():
    template = 'letter.tex'
    filename = 'prova.tex'
    context = {'variabile': 'Pippo è'}
    
    render_to_file(template, filename, context)
