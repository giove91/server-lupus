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
        self.game = player.game
    
    def render_setting(self):
        template = self.template_setting
        context = {
            'player': self.player,
        }
        # TODO: escape basename
        basename = self.player.user.last_name.replace(' ', '') + '1'
        filename = basename + '.tex'
        
        # Rendering .tex
        render_to_file(template, self.directory + filename, context)
        
        # Compiling
        os.system('pdflatex -output-directory ' + self.directory + ' ' + self.directory + filename)
        
        # Cleaning
        os.system('rm ' + self.directory + basename + '.tex')
        os.system('rm ' + self.directory + basename + '.aux')
        os.system('rm ' + self.directory + basename + '.log')
    
    def render_role(self):
        template = self.template_role
        context = {
            'player': self.player,
        }
        # TODO: escape basename
        basename = self.player.user.last_name.replace(' ', '') + '2'
        filename = basename + '.tex'
        
        # Rendering .tex
        render_to_file(template, self.directory + filename, context)
        
        # Compiling
        os.system('pdflatex -output-directory ' + self.directory + ' ' + self.directory + filename)
        
        # Cleaning
        os.system('rm ' + self.directory + basename + '.tex')
        os.system('rm ' + self.directory + basename + '.aux')
        os.system('rm ' + self.directory + basename + '.log')
    
    def render_all(self):
        self.render_setting()
        self.render_role()


