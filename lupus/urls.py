from django.conf.urls import patterns, include, url
from django.contrib import admin

from game import views

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', views.home, name='home'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^login/$', 'django.contrib.auth.views.login', name='login'),
    url(r'^logout/$', views.logout_view, name='logout'),
    url(r'^game/', include('game.urls')),
)

