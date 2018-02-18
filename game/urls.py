from django.urls import path
from django.contrib.auth.decorators import user_passes_test

from django.views.generic.base import RedirectView

from game.views import *


urlpatterns = [
    path('', RedirectView.as_view(url='index', permanent=False)),
    path('index/', home, name='home'),
    
    path('ruleset/', ruleset, name='ruleset'),
    path('credits/', credits, name='credits'),
    path('trailer/', trailer, name='trailer'),
    path('prototypes/', prototypes, name='prototypes'),
    path('error/', errorpage, name='error'),
    
    path('status/', VillageStatusView.as_view(), name='status'),
    path('announcements/', AnnouncementsView.as_view(), name='announcements'),
    
    path('usepower/', UsePowerView.as_view(), name='usepower'),
    path('vote/', VoteView.as_view(), name='vote'),
    path('elect/', ElectView.as_view(), name='elect'),
    path('personalinfo/', PersonalInfoView.as_view(), name='personalinfo'),
    path('appoint/', AppointView.as_view(), name='appoint'),
    path('contacts/', ContactsView.as_view(), name='contacts'),
    path('comment/', CommentView.as_view(), name='comment'),
    
    path('adminstatus/', AdminStatusView.as_view(), name='adminstatus'),
    path('setup/', setup, name='setup'),
    path('advanceturn/', advance_turn, name='advanceturn'),
    path('pointofview/', PointOfView.as_view(), name='pointofview'),
    path('dump/', DumpView.as_view(), name='dump'),
]

