from django.conf.urls import patterns, url
from django.contrib.auth.decorators import user_passes_test

from game.views import *


urlpatterns = patterns('',
    url(r'^setup/$', setup, name='setup'),
    url(r'^ruleset/$', ruleset, name='ruleset'),
    url(r'^status/$', VillageStatusView.as_view(), name='status'),
    url(r'^usepower/$', user_passes_test(is_player_check)( UsePowerView.as_view() ), name='usepower'),
    url(r'^vote/$', user_passes_test(is_player_check)( VoteView.as_view() ), name='vote'),
    url(r'^elect/$', user_passes_test(is_player_check)( ElectView.as_view() ), name='elect'),
    url(r'^personalinfo/$', user_passes_test(is_player_check)( PersonalInfoView.as_view() ), name='personalinfo'),
    url(r'^contacts/$', user_passes_test(is_player_check)( ContactsView.as_view() ), name='contacts'),
)

