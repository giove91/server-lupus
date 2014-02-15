from django.conf.urls import patterns, url
from django.contrib.auth.decorators import user_passes_test

from game.views import *


urlpatterns = patterns('',
    url(r'^setup/$', setup, name='setup'),
    url(r'^advance_turn/$', advance_turn, name='advance_turn'),
    url(r'^ruleset/$', ruleset, name='ruleset'),
    
    url(r'^status/$', VillageStatusView.as_view(), name='status'),
    
    url(r'^usepower/$', UsePowerView.as_view(), name='usepower'),
    url(r'^vote/$', VoteView.as_view(), name='vote'),
    url(r'^elect/$', ElectView.as_view(), name='elect'),
    url(r'^personalinfo/$', PersonalInfoView.as_view(), name='personalinfo'),
    url(r'^contacts/$', ContactsView.as_view(), name='contacts'),
    
    url(r'^pointofview/$', PointOfView.as_view(), name='pointofview'),
)

