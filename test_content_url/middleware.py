# coding=utf-8
"""Test-only middleware that restores HttpRequest.is_ajax().

**Not for this package** -- xadmin_content_url never calls it (test_compat.py
asserts so). xadmin does, in five places, and ``xadmin/plugins/ajax.py:17`` runs on
every admin view through the plugin manager. Django removed the method in 4.0, so
any xadmin view raises AttributeError on 4.0+ unless something puts it back; the
host project does exactly that, in
``plus_base.xpublique.middleware.request.RequestToolsMiddleware``.

The predicate is the host's, verbatim. The permanent fix belongs to xadmin (#7093).
"""
from functools import partial


def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


class RequestToolsMiddleware:
    """Mirror of the host project's middleware of the same name."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not hasattr(request, 'is_ajax'):
            request.is_ajax = partial(is_ajax, request)
        return self.get_response(request)
