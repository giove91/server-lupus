# -*- coding: utf-8 -*-

import os, codecs, string
from django.template.loader import render_to_string

from .models import *
from .events import *
from .constants import *
from datetime import timedelta
from .utils import get_now

def render_to_file(template, filename, context):
    codecs.open(filename, 'w', 'utf-8').write(render_to_string(template, context))

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
        
        self.directory += self.game.name + "/"
        self.initial_propositions = InitialPropositionEvent.objects.filter(turn__game=self.game)
        
        knowledge_events = [event for event in self.game.get_dynamics().events if event.subclass == 'RoleKnowledgeEvent' and event.player.pk == player.pk and event.cause == KNOWLEDGE_CLASS]
        self.initial_knowledge = []
        for event in knowledge_events:
            message = event.to_player_string(player)
            if message is not None:
                self.initial_knowledge.append(message)
        
        soothsayer_events = [ev for ev in self.game.get_dynamics().events if isinstance(ev, SoothsayerModelEvent) and ev.soothsayer == player]
        self.soothsayer_knowledge = []
        for event in soothsayer_events:
            message = event.to_soothsayer_proposition()
            assert message is not None
            self.soothsayer_knowledge.append(message)
        
        self.context = {
            'player': self.player,
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
        # TODO: fare l'escape in un modo più elegante (e possibilmente
        # che funzioni anche)
        return name.replace(u' ', u'').replace(u'à', u'a').replace(u'ò', u'o').replace(u"'", u'')
    
    def render_setting(self):
        template = self.template_setting
        
        basename = self.escape_name(self.player.user.last_name) + '_' + self.escape_name(self.player.user.first_name) + '1'
        filename = basename + '.tex'
        
        # Rendering .tex
        os.system('mkdir -p templates/' + self.directory)
        render_to_file(template, 'templates/' + self.directory + filename, self.context)
        
        # Compiling
        time = get_now()
        ret = os.system('pdflatex -output-directory templates/' + self.directory + ' templates/' + self.directory + filename + ' | grep "!"')
        assert get_now() - time <= timedelta(seconds=1)

        # Cleaning
        if ret == 0:
            os.system('rm templates/' + self.directory + basename + '.tex')
            os.system('rm templates/' + self.directory + basename + '.aux')
            os.system('rm templates/' + self.directory + basename + '.log')
    
    def render_role(self):
        template = self.template_role
        
        basename = self.escape_name(self.player.user.last_name) + '_' + self.escape_name(self.player.user.first_name) + '2'
        filename = basename + '.tex'
        
        # Rendering .tex
        render_to_file(template, 'templates/' + self.directory + filename, self.context)
        
        # Compiling
        time = get_now()
        ret = os.system('pdflatex -output-directory templates/' + self.directory + ' templates/' + self.directory + filename + '| grep "!"')
        assert get_now() - time <= timedelta(seconds=1)
        
        # Cleaning
        if ret == 0:
            os.system('rm templates/' + self.directory + basename + '.tex')
            os.system('rm templates/' + self.directory + basename + '.aux')
            os.system('rm templates/' + self.directory + basename + '.log')
    
    def render_all(self):
        self.render_setting()
        self.render_role()


