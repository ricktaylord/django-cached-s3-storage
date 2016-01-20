try:
	from django.conf.urls.defaults import url
except ImportError:
	from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^thumbnail/$', views.ThumbnailImage.as_view(),name="thumbnail"),
]