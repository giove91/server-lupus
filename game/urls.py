from django.urls import path
from django.contrib.auth.decorators import user_passes_test

from django.views.generic.base import RedirectView

from game.views import *

app_name = 'game'

urlpatterns = [
    path('', RedirectView.as_view(url='status', permanent=False)),
    
    path('status/', VillageStatusView.as_view(), name='status'),
    path('announcements/', AnnouncementsListView.as_view(), name='announcements'),
    
    path('usepower/', UsePowerView.as_view(), name='usepower'),
    path('vote/', VoteView.as_view(), name='vote'),
    path('elect/', ElectView.as_view(), name='elect'),
    path('personalinfo/', PersonalInfoView.as_view(), name='personalinfo'),
    path('appoint/', AppointView.as_view(), name='appoint'),
    path('comment/', CommentView.as_view(), name='comment'),

    path('join/', JoinGameView.as_view(), name='join'), # Aggiunge il giocatore
    path('leave/', LeaveGameView.as_view(), name='leave'), # Rimuove il giocatore
    path('newplayer/', NewPlayerView.as_view(), name='newplayer'), # Crea un nuovo utente e lo aggiunge alla partita

    path('as_gm/', as_gm, name='as_gm'), # Assume i poteri da GM
    path('as_normal_user/', as_normal_user, name='as_normal_user'), # Lascia i poteri da GM

    path('managemasters/', ManageGameMastersView.as_view(), name='managemasters'), # Aggiunge un master alla partita
    path('deletemaster/<int:pk>', DeleteGameMasterView.as_view(), name='deletemaster'), # Toglie un master dalla partita
    path('publishannouncement/', PublishAnnouncementView.as_view(), name='publishannouncement'), # Pubblica un annuncio
    path('deleteannouncement/<int:pk>', DeleteAnnouncementView.as_view(), name='deleteannouncement'), # Cancella un annuncio
    path('setup/', SetupGameView.as_view(), name='setup'), # Prepara l'inizio
    path('seed/', SeedView.as_view(), name='seed'), # Cambia o crea il seed
    path('composition/', VillageCompositionView.as_view(), name='composition'), # Imposta la composizione del villaggio
    path('spectralsequence/', SpectralSequenceView.as_view(), name='spectralsequence'), # Imposta la successione spettrale
    path('propositions/', InitialPropositionsView.as_view(), name='propositions'), # Pubblica le proposizioni iniziali
    path('deleteproposition/<int:pk>/', DeletePropositionView.as_view(), name='deleteproposition'), # Cancella una proposizione iniziale
    path('soothsayer/<int:pk>/', SoothsayerView.as_view(), name='soothsayer'), # Cambia le frasi dei divinatori
    path('deletesoothsayer/<int:pk>/', DeleteSoothsayerView.as_view(), name='deletesoothsayer'), # Cancella una proposizione per il divinatore
    path('settings/', GameSettingsView.as_view(), name='settings'), # Cambia le impostazioni della partita

    path('rollbackturn/', RollbackLastTurnView.as_view(), name='rollbackturn'), # Riporta la partita alla fine del turno precedente, cancellando gli eventi di quello in corso.
    path('restart/', RestartGameView.as_view(), name='restart'), # Elimina tutti gli eventi e riapre le iscrizioni
    path('load/', LoadGameView.as_view(), name='load'), # Elimina tutti gli eventi e carica da file
    
    path('delete/', not_implemented, name='delete'), # Cancella la partita
    
    path('adminstatus/', AdminStatusView.as_view(), name='adminstatus'),
    path('advanceturn/', AdvanceTurnView.as_view(), name='advanceturn'),
    path('forcevictory/', ForceVictoryView.as_view(), name='forcevictory'),
    path('pointofview/', PointOfView.as_view(), name='pointofview'),
    path('dump/', DumpView.as_view(), name='dump'),
]

