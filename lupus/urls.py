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
    path('accounts/signup/', SignUpView.as_view(), name='signup'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('index/', HomeView.as_view(), name='home'),
    path('', RedirectView.as_view(pattern_name='home', permanent=False)),
    path('ruleset/', RulesetView.as_view(), name='ruleset'),
    path('credits/', CreditsView.as_view(), name='credits'),
    path('trailer/', TrailerView.as_view(), name='trailer'),
    path('prototypes/', PrototypesView.as_view(), name='prototypes'),
    path('error/', ErrorView.as_view(), name='error'),

    path('creategame/', CreateGameView.as_view(), name='creategame'),

    path('game/<str:game_name>/', include('game.urls', namespace='game'))
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
