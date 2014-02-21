# -*- coding: utf-8 -*-

import os, codecs
from django.template.loader import render_to_string

from models import *


def render_to_file(template, filename, context):
    codecs.open(filename, 'w', 'utf-8').write(render_to_string(template, context))


class LetterRenderer:
    template_setting = 'letters/setting.tex'
    template_role = 'letters/role.tex'
    
    directory = 'letters/'
    
    def __init__(self, player):
        self.player = player
    
    def render_setting(self):
        template = self.template_setting
        directory = self.directory
        context = {
            'player': self.player,
        }
        # TODO: escape basename
        basename = self.player.user.last_name.replace(' ', '')
        filename = basename + '.tex'
        
        render_to_file(template, directory + filename, context)
        os.system('pdflatex -output-directory ' + directory + ' ' + directory + filename)
        # os.system('rm ' + directory + basename + '.{tex,aux,log}')


