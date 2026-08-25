# coding=utf-8
"""URLs for the suite: xadmin's site, plus a target for get_absolute_url."""
import xadmin
from django.http import HttpResponse
from django.urls import path


def article_detail(request, slug):
    return HttpResponse('article {0}'.format(slug))


urlpatterns = [
    # site.urls is the (patterns, app_name, namespace) triple, which path()
    # unpacks on its own; include() refuses a 3-tuple.
    path('admin/', xadmin.site.urls),
    path('articles/<slug:slug>/', article_detail, name='article-detail'),
]
