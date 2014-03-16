# -*- coding: utf-8 -*-

import os, codecs, random, string
from django.template.loader import render_to_string

from models import *
from events import *
from constants import *


def render_to_file(template, filename, context):
    codecs.open(filename, 'w', 'utf-8').write(render_to_string(template, context))

def generate_password(length):
    chars = string.ascii_letters
    return ''.join(random.choice(chars) for i in range(length))


class LetterRenderer:
    template_setting = 'letters/setting.tex'
    template_role = 'letters/role.tex'
    
    directory = 'letters/'
    
    password_length = 8
    
    def __init__(self, player):
        self.player = player
        self.game = player.game
        self.players = self.game.get_players()
        self.numplayers = len(self.players)
        self.column_height = (self.numplayers+1)/2
        self.mayor = self.game.mayor
        
        self.password = generate_password(self.password_length)
        
        self.initial_propositions = InitialPropositionEvent.objects.filter(turn__game=self.game)
        
        knowledge_events = RoleKnowledgeEvent.objects.filter(player=player).filter(cause=KNOWLEDGE_CLASS)
        self.initial_knowledge = []
        for event in knowledge_events:
            message = event.to_player_string(player)
            if message is not None:
                self.initial_knowledge.append(message)
        
        soothsayer_events = RoleKnowledgeEvent.objects.filter(player=player).filter(cause=SOOTHSAYER)
        self.soothsayer_knowledge = []
        for event in soothsayer_events:
            message = event.to_soothsayer_proposition()
            assert message is not None
            self.soothsayer_knowledge.append(message)
        
        self.context = {
            'player': self.player,
            'password': self.password,
            'game': self.game,
            'players': self.players,
            'numplayers': self.numplayers,
            'column_height': self.column_height,
            'mayor': self.mayor,
            'initial_propositions': self.initial_propositions,
            'initial_knowledge': self.initial_knowledge,
            'soothsayer_knowledge': self.soothsayer_knowledge,
        }
    
    def escape_name(self, name):
        # TODO: fare l'escape in un modo più elegante
        return name.replace(u' ', u'').replace(u'à', u'a').replace(u'ò', u'o')
    
    def render_setting(self):
        template = self.template_setting
        
        basename = self.escape_name(self.player.user.last_name) + '1'
        filename = basename + '.tex'
        
        # Rendering .tex
        render_to_file(template, self.directory + filename, self.context)
        
        # Compiling
        os.system('pdflatex -output-directory ' + self.directory + ' ' + self.directory + filename)
        
        # Cleaning
        os.system('rm ' + self.directory + basename + '.tex')
        os.system('rm ' + self.directory + basename + '.aux')
        os.system('rm ' + self.directory + basename + '.log')
    
    def render_role(self):
        template = self.template_role
        
        basename = self.escape_name(self.player.user.last_name) + '2'
        filename = basename + '.tex'
        
        # Rendering .tex
        render_to_file(template, self.directory + filename, self.context)
        
        # Compiling
        os.system('pdflatex -output-directory ' + self.directory + ' ' + self.directory + filename)
        
        # Cleaning
        os.system('rm ' + self.directory + basename + '.tex')
        os.system('rm ' + self.directory + basename + '.aux')
        os.system('rm ' + self.directory + basename + '.log')
    
    def set_password(self):
        user = self.player.user
        user.set_password(self.password)
        user.save()
    
    def render_all(self):
        self.set_password()
        self.render_setting()
        self.render_role()


