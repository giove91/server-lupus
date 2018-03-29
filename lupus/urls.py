from django.urls import path, include
from django.contrib import admin
from django.conf import settings

from django.views.generic.base import RedirectView
#from django.core.urlresolvers import reverse_lazy
from game import views
from game.views import *


admin.autodiscover()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('index/', home, name='home'),
    path('', RedirectView.as_view(pattern_name='home', permanent=False)),
    
    path('ruleset/', ruleset, name='ruleset'),
    path('credits/', credits, name='credits'),
    path('trailer/', trailer, name='trailer'),
    path('prototypes/', prototypes, name='prototypes'),
    path('error/', errorpage, name='error'),

    path('creategame/', CreateGameView.as_view(), name='creategame'),

    path('game/<str:game_name>/', include('game.urls', namespace='game'))
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

