from django.urls import path
from django.contrib.auth.decorators import user_passes_test

from django.views.generic.base import RedirectView

from game.views import *

app_name = 'game'

urlpatterns = [
    path('', RedirectView.as_view(url='status', permanent=False)),
    
    path('status/', VillageStatusView.as_view(), name='status'),
    path('announcements/', AnnouncementsView.as_view(), name='announcements'),
    
    path('usepower/', UsePowerView.as_view(), name='usepower'),
    path('vote/', VoteView.as_view(), name='vote'),
    path('elect/', ElectView.as_view(), name='elect'),
    path('personalinfo/', PersonalInfoView.as_view(), name='personalinfo'),
    path('appoint/', AppointView.as_view(), name='appoint'),
    path('contacts/', ContactsView.as_view(), name='contacts'),
    path('comment/', CommentView.as_view(), name='comment'),

    path('join/', JoinGameView.as_view(), name='join'), # Aggiunge il giocatore
    path('leave/', LeaveGameView.as_view(), name='leave'), # Rimuove il giocatore

    path('addmaster/', not_implemented, name='addmaster'), # Aggiunge un master alla partita
    path('setup/', SetupGameView.as_view(), name='setup'), # Prepara l'inizio
    path('seed/', SeedView.as_view(), name='seed'), # Cambia o crea il seed
    path('composition/', not_implemented, name='composition'), # Imposta la composizione del villaggio
    path('propositions/', not_implemented, name='propositions'), # Cambia le proposizioni iniziali
    path('soothsayer/', not_implemented, name='soothsayer'), # Cambia le frasi dei divinatori
    path('settings/', GameSettingsView.as_view(), name='settings'), # Cambia le impostazioni della partita
    path('restart/', RestartGameView.as_view(), name='restart'), # Elimina tutti gli eventi e riapre le iscrizioni
    path('delete/', not_implemented, name='delete'), # Cancella la partita
    
    path('adminstatus/', AdminStatusView.as_view(), name='adminstatus'),
    path('advanceturn/', advance_turn, name='advanceturn'),
    path('pointofview/', PointOfView.as_view(), name='pointofview'),
    path('dump/', DumpView.as_view(), name='dump'),
]

