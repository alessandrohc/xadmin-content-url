# coding=utf-8
"""The REST layer the picker's datatable talks to: filter, serializer, permission."""
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase, override_settings

from test_content_url.models import Article, Unreachable
from xadmin_content_url.filters import SearchFilterBackend
from xadmin_content_url.rest.permissions import HasContentUrlPermission
from xadmin_content_url.rest.serializers.content import GenericContentUrlSerializer


class FakeView:
    def __init__(self, search_fields=None, model=Article):
        if search_fields is not None:
            self.xd_content_search_fields = search_fields
        self.opts = model._meta


def request_with(**params):
    request = RequestFactory().get("/", params)
    request.query_params = request.GET
    return request


class SearchFilterTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        Article.objects.create(title="Django release", slug="django")
        Article.objects.create(title="Python release", slug="python")

    def _filter(self, view, **params):
        return SearchFilterBackend().filter_queryset(
            request_with(**params), Article.objects.all(), view
        )

    def test_filters_on_the_declared_field(self):
        # DataTables posts its term as search[value].
        result = self._filter(FakeView(("title",)), **{"search[value]": "django"})
        self.assertEqual([a.slug for a in result], ["django"])

    def test_a_bare_string_field_name_is_accepted(self):
        # UnreachableAdmin declares xd_content_search_fields as a plain string.
        result = self._filter(FakeView("title"), **{"search[value]": "python"})
        self.assertEqual([a.slug for a in result], ["python"])

    def test_the_match_is_case_insensitive(self):
        result = self._filter(FakeView(("title",)), **{"search[value]": "DJANGO"})
        self.assertEqual(len(result), 1)

    def test_no_term_means_no_filtering(self):
        self.assertEqual(len(self._filter(FakeView(("title",)))), 2)

    def test_a_whitespace_only_term_means_no_filtering(self):
        result = self._filter(FakeView(("title",)), **{"search[value]": "   "})
        self.assertEqual(len(result), 2)

    def test_a_view_without_search_fields_is_left_alone(self):
        """No xd_content_search_fields means the model is not searchable.

        Returning everything is the right answer -- the alternative would be
        guessing which field to search.
        """
        result = self._filter(FakeView(), **{"search[value]": "django"})
        self.assertEqual(len(result), 2)

    def test_multiple_fields_narrow_cumulatively(self):
        # Successive .filter() calls AND together, so a term has to match both.
        result = self._filter(
            FakeView(("title", "slug")), **{"search[value]": "django"}
        )
        self.assertEqual([a.slug for a in result], ["django"])


class SerializerTests(TestCase):

    def _serialize(self, instance):
        serializer_class = type(
            "Bound",
            (GenericContentUrlSerializer,),
            {"Meta": type("Meta", (GenericContentUrlSerializer.Meta,), {"model": type(instance)})},
        )
        return serializer_class(instance).data

    def test_reports_the_pk_the_title_and_the_url(self):
        article = Article.objects.create(title="Hello", slug="hello")
        data = self._serialize(article)
        self.assertEqual(data["id"], article.pk)
        self.assertEqual(data["title"], "Hello")
        self.assertEqual(data["url"], "/articles/hello/")

    def test_the_title_is_html_escaped(self):
        """The title goes into a datatable cell as HTML.

        The escaping is in the serializer rather than the template, so it has to
        survive here.
        """
        article = Article.objects.create(title='<img src=x onerror=alert(1)>', slug="x")
        self.assertEqual(
            self._serialize(article)["title"],
            "&lt;img src=x onerror=alert(1)&gt;",
        )

    def test_only_the_three_declared_fields_are_exposed(self):
        article = Article.objects.create(title="Hello", slug="hello")
        self.assertEqual(set(self._serialize(article)), {"id", "title", "url"})


class PermissionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="staff", password="x")
        cls.article = Article.objects.create(title="Hello", slug="hello")

    def _check(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return HasContentUrlPermission().has_permission(request, FakeView())

    @override_settings(XD_CONTENT_URL_PERMISSIONS=())
    def test_no_configured_permission_means_open(self):
        self.assertTrue(self._check(self.user))

    @override_settings(XD_CONTENT_URL_PERMISSIONS=["view_content_url"])
    def test_a_missing_permission_denies(self):
        self.assertFalse(self._check(self.user))

    @override_settings(XD_CONTENT_URL_PERMISSIONS=["view"])
    def test_the_codename_is_built_from_the_model(self):
        """get_permission_codename joins the action with the model name.

        So "view" against Article means auth on test_content_url.view_article --
        the permission Django creates for the model itself.
        """
        content_type = ContentType.objects.get_for_model(Article)
        self.user.user_permissions.add(
            Permission.objects.get(content_type=content_type, codename="view_article")
        )
        self.assertTrue(self._check(User.objects.get(pk=self.user.pk)))

    @override_settings(XD_CONTENT_URL_PERMISSIONS=["view", "change"])
    def test_every_configured_permission_is_required(self):
        content_type = ContentType.objects.get_for_model(Article)
        self.user.user_permissions.add(
            Permission.objects.get(content_type=content_type, codename="view_article")
        )
        # change_article is missing, so the conjunction fails.
        self.assertFalse(self._check(User.objects.get(pk=self.user.pk)))
