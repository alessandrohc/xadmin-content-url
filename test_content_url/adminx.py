# coding=utf-8
"""Admin registrations for the suite, discovered by xadmin's autodiscover.

``xd_content_url_enable`` is the opt-in the content picker reads: only models whose
admin sets it appear in the picker's dropdown, and only those answer the REST plugin.
Category deliberately leaves it off, which is how the suite proves the filter works.
"""
from xadmin.sites import site

from test_content_url.models import Article, Category, Unreachable


class ArticleAdmin:
    xd_content_url_enable = True
    xd_content_search_fields = ('title',)
    list_display = ('title', 'slug')


class CategoryAdmin:
    list_display = ('name',)


class UnreachableAdmin:
    xd_content_url_enable = True
    xd_content_search_fields = 'name'  # a bare string, not a tuple


site.register(Article, ArticleAdmin)
site.register(Category, CategoryAdmin)
site.register(Unreachable, UnreachableAdmin)
