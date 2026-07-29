# coding=utf-8
"""The two xadmin plugins.

The media plugin runs on every model form in the admin, and the REST plugin answers
the picker's datatable. The REST one is read-only by construction, and that is the
part worth guarding: it is reachable by URL parameter on any registered model.
"""
from django.core.exceptions import PermissionDenied
from django.forms import Media
from django.test import RequestFactory, SimpleTestCase, TestCase
from xadmin.views import ModelAdminView

from test_content_url.models import Article
from xadmin_content_url.filters import SearchFilterBackend
from xadmin_content_url.rest.serializers.content import GenericContentUrlSerializer
from xadmin_content_url.xplugin import (
    XdContentUrlAdminPlugin,
    XdContentUrlAdminRestPlugin,
)


class FakeAdminSite:
    name = "xadmin"


def make_admin_view(request=None, method="get", model=Article):
    """A ModelAdminView instance without xadmin's setup chain.

    __new__ keeps the class identity that the plugin registration depends on while
    skipping setup(), which wants a plugin manager and a resolved URL.
    """
    view = ModelAdminView.__new__(ModelAdminView)
    view.request = request or RequestFactory().get("/admin/")
    view.request_method = method
    view.user = None
    view.args = ()
    view.kwargs = {}
    view.admin_site = FakeAdminSite()
    view.model = model
    view.opts = model._meta
    return view


class MediaPluginTests(SimpleTestCase):

    def test_it_is_always_active(self):
        # It only adds assets, so there is nothing to gate on.
        plugin = XdContentUrlAdminPlugin(make_admin_view())
        self.assertTrue(plugin.init_request())

    def test_it_adds_the_packaged_js_and_css(self):
        plugin = XdContentUrlAdminPlugin(make_admin_view())
        media = plugin.get_media(Media())
        self.assertIn("xd_content_url/js/xd_sel_url.js", [str(js) for js in media._js])
        self.assertIn(
            "xd_content_url/css/xd_sel_url.css",
            [str(css) for css in media._css["screen"]],
        )

    def test_it_pulls_the_datatable_vendor_assets(self):
        # The picker is a DataTable inside a Bootstrap modal; without these it is an
        # empty <table>.
        plugin = XdContentUrlAdminPlugin(make_admin_view())
        rendered = str(plugin.get_media(Media()))
        self.assertIn("datatables", rendered)
        self.assertIn("xadmin.bs.modal.js", rendered)


class RestPluginActivationTests(SimpleTestCase):

    def _plugin(self, params=None, method="get", **attrs):
        request = RequestFactory().get("/admin/", params or {})
        plugin = XdContentUrlAdminRestPlugin(make_admin_view(request, method=method))
        for name, value in attrs.items():
            setattr(plugin, name, value)
        return plugin

    def test_inactive_without_the_plugin_parameter(self):
        self.assertFalse(self._plugin().init_request())

    def test_active_with_the_plugin_parameter(self):
        self.assertTrue(self._plugin({"plugin": "xd_ct_url"}).init_request())

    def test_another_plugin_name_does_not_activate_it(self):
        self.assertFalse(self._plugin({"plugin": "something_else"}).init_request())

    def test_it_can_be_switched_off_per_model_admin(self):
        plugin = self._plugin({"plugin": "xd_ct_url"}, xd_content_url_enable=False)
        self.assertFalse(plugin.init_request())

    def test_a_write_method_is_refused_outright(self):
        """Read-only by construction, and this is the only thing enforcing it.

        The endpoint is reachable on any registered model by adding a query
        parameter, so a POST reaching the serializer would be a write path nobody
        reviewed.
        """
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                plugin = self._plugin({"plugin": "xd_ct_url"}, method=method)
                with self.assertRaises(PermissionDenied):
                    plugin.init_request()

    def test_safe_methods_are_allowed(self):
        for method in ("get", "options", "head"):
            with self.subTest(method=method):
                plugin = self._plugin({"plugin": "xd_ct_url"}, method=method)
                self.assertTrue(plugin.init_request())

    def test_a_write_method_is_ignored_while_the_plugin_is_inactive(self):
        # No query parameter: the plugin must not interfere with ordinary admin POSTs.
        self.assertFalse(self._plugin(method="post").init_request())


class RestPluginWiringTests(TestCase):

    def _plugin(self):
        request = RequestFactory().get("/admin/", {"plugin": "xd_ct_url"})
        return XdContentUrlAdminRestPlugin(make_admin_view(request))

    def test_the_serializer_is_bound_to_the_view_s_model(self):
        # The packaged serializer declares no model; the plugin subclasses it per
        # request so one serializer serves every registered model.
        serializer_class = self._plugin().get_serializer_class(None)
        self.assertIs(serializer_class.Meta.model, Article)
        self.assertTrue(issubclass(serializer_class, GenericContentUrlSerializer))

    def test_binding_does_not_mutate_the_packaged_serializer(self):
        self._plugin().get_serializer_class(None)
        self.assertFalse(hasattr(GenericContentUrlSerializer.Meta, "model"))

    def test_permissions_are_instantiated_from_the_declared_classes(self):
        from xadmin_content_url.rest.permissions import HasContentUrlPermission

        permissions = self._plugin().get_permissions(None)
        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], HasContentUrlPermission)

    def test_the_queryset_goes_through_the_search_backend(self):
        Article.objects.create(title="Django", slug="django")
        Article.objects.create(title="Python", slug="python")

        plugin = XdContentUrlAdminRestPlugin(
            make_admin_view(
                RequestFactory().get(
                    "/admin/", {"plugin": "xd_ct_url", "search[value]": "django"}
                )
            )
        )
        plugin.admin_view.request.query_params = plugin.admin_view.request.GET
        plugin.admin_view.xd_content_search_fields = ("title",)

        result = plugin.filter_queryset(Article.objects.all())
        self.assertEqual([a.slug for a in result], ["django"])

    def test_the_search_backend_is_replaceable(self):
        self.assertIs(
            XdContentUrlAdminRestPlugin.xd_content_url_search_filter,
            SearchFilterBackend,
        )
