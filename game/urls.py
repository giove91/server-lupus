from django.conf.urls import patterns, url
from django.contrib.auth.decorators import user_passes_test

from game.views import *


urlpatterns = patterns('',
    
    url(r'^ruleset/$', ruleset, name='ruleset'),
    url(r'^credits/$', credits, name='credits'),
    
    url(r'^status/$', VillageStatusView.as_view(), name='status'),
    url(r'^announcements/$', AnnouncementsView.as_view(), name='announcements'),
    
    url(r'^usepower/$', UsePowerView.as_view(), name='usepower'),
    url(r'^vote/$', VoteView.as_view(), name='vote'),
    url(r'^elect/$', ElectView.as_view(), name='elect'),
    url(r'^personalinfo/$', PersonalInfoView.as_view(), name='personalinfo'),
    url(r'^appoint/$', AppointView.as_view(), name='appoint'),
    url(r'^contacts/$', ContactsView.as_view(), name='contacts'),
    url(r'^comment/$', CommentView.as_view(), name='comment'),
    
    url(r'^adminstatus/$', AdminStatusView.as_view(), name='adminstatus'),
    url(r'^setup/$', setup, name='setup'),
    url(r'^advanceturn/$', advance_turn, name='advanceturn'),
    url(r'^createletters/$', create_letters, name='createletters'),
    url(r'^pointofview/$', PointOfView.as_view(), name='pointofview'),
)

