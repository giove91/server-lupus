from django.urls import path, include
from django.contrib import admin
from django.conf import settings

from django.views.generic.base import RedirectView
#from django.core.urlresolvers import reverse_lazy
from game import views

admin.autodiscover()

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='home', permanent=False)),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('game/', include('game.urls'))
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

