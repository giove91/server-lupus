from django.conf.urls import patterns, url
from django.contrib.auth.decorators import user_passes_test

from game import views


urlpatterns = patterns('',
    url(r'^setup/$', views.setup, name='setup'),
    url(r'^status/$', views.VillageStatusView.as_view(), name='status'),
    url(r'^usepower/$', user_passes_test(views.is_player_check)( views.UsePowerView.as_view() ), name='usepower'),
    url(r'^vote/$', user_passes_test(views.is_player_check)( views.VoteView.as_view() ), name='vote'),
    url(r'^elect/$', user_passes_test(views.is_player_check)( views.ElectView.as_view() ), name='elect'),
    url(r'^personalinfo/$', user_passes_test(views.is_player_check)( views.PersonalInfoView.as_view() ), name='personalinfo'),
)

