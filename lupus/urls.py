from django.conf.urls import patterns, include, url
from django.contrib import admin

from django.views.generic.base import RedirectView
from django.core.urlresolvers import reverse_lazy
from game import views

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', RedirectView.as_view(pattern_name='home', permanent=False)),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^login/$', 'django.contrib.auth.views.login', name='login'),
    url(r'^logout/$', views.logout_view, name='logout'),
	url(r'^password_change/$', 'django.contrib.auth.views.password_change', 
		{'template_name':'registration/password_change_form.html'}, name='password_change'),
	url(r'^password_change/done/$', 'django.contrib.auth.views.password_change_done', 
		{'template_name':'registration/password_change_done.html'}, name='password_change_done'),
    url(r'^game/', include('game.urls')),
)

