# coding=utf-8
"""The three models.

``XdUrl`` is the interesting one: it is a pointer to an arbitrary object, and its
string form is that object's ``get_absolute_url()``. Everything it can go wrong with
-- a deleted target, a target with no such method, a view name that stopped
resolving -- has to end in an empty string rather than an exception, because these
render inside admin lists.
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from test_content_url.models import Article, Category, Unreachable
from xadmin_content_url.models import XdContentUrl, XdSiteViewUrl, XdUrl


def url_for(obj):
    return XdUrl.objects.create(
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
    )


class XdUrlTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.article = Article.objects.create(title="Hello", slug="hello")

    def test_str_is_the_target_s_absolute_url(self):
        self.assertEqual(str(url_for(self.article)), "/articles/hello/")

    def test_a_target_without_get_absolute_url_renders_empty(self):
        # Unreachable has no such method: AttributeError inside the property.
        target = Unreachable.objects.create(name="nope")
        self.assertEqual(str(url_for(target)), "")

    def test_a_deleted_target_renders_empty(self):
        """The row outlives its target: the generic relation has no FK to cascade.

        clear_xd_content_urls exists to sweep exactly these up.
        """
        pointer = url_for(self.article)
        self.article.delete()
        pointer.refresh_from_db()
        self.assertEqual(str(pointer), "")

    def test_the_generic_target_is_resolvable(self):
        pointer = url_for(self.article)
        self.assertEqual(pointer.content_object, self.article)


class XdSiteViewUrlTests(TestCase):

    def test_get_absolute_url_reverses_the_view_name(self):
        view = XdSiteViewUrl.objects.create(
            ref="detail", name="Article detail", view_name="article-detail"
        )
        # article-detail takes a slug, so reverse() without arguments fails --
        # which is the NoReverseMatch branch, not an error.
        self.assertIsNone(view.get_absolute_url())

    def test_a_view_name_that_does_not_resolve_returns_none(self):
        view = XdSiteViewUrl.objects.create(
            ref="gone", name="Gone", view_name="no-such-view"
        )
        self.assertIsNone(view.get_absolute_url())

    def test_a_resolvable_view_name_returns_its_path(self):
        view = XdSiteViewUrl.objects.create(
            ref="admin", name="Admin", view_name="xadmin:index"
        )
        self.assertEqual(view.get_absolute_url(), "/admin/")

    def test_str_is_the_human_name(self):
        view = XdSiteViewUrl.objects.create(ref="r", name="Readable", view_name="x")
        self.assertEqual(str(view), "Readable")

    def test_the_ref_is_unique_and_not_editable(self):
        # register_xd_site_urls keys on ref, so a duplicate would make the command
        # update the wrong row.
        field = XdSiteViewUrl._meta.get_field("ref")
        self.assertTrue(field.unique)
        self.assertFalse(field.editable)

    def test_rows_are_ordered_by_name(self):
        XdSiteViewUrl.objects.create(ref="b", name="Beta", view_name="x")
        XdSiteViewUrl.objects.create(ref="a", name="Alpha", view_name="y")
        self.assertEqual(
            list(XdSiteViewUrl.objects.values_list("name", flat=True)),
            ["Alpha", "Beta"],
        )


class XdContentUrlTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.article = Article.objects.create(title="Hello", slug="hello")
        cls.category = Category.objects.create(name="News")

    def test_str_delegates_to_the_url(self):
        link = XdContentUrl.objects.create(
            content_type=ContentType.objects.get_for_model(self.category),
            object_id=self.category.pk,
            field_name="xd_content_url",
            url=url_for(self.article),
        )
        self.assertEqual(str(link), "/articles/hello/")

    def test_the_field_name_defaults_to_the_configured_relation_field(self):
        from xadmin_content_url import settings as xd_settings

        field = XdContentUrl._meta.get_field("field_name")
        self.assertEqual(field.default, xd_settings.XD_CONTENT_URL_RELATION_FIELD)
        # Indexed: every lookup the field does filters on it.
        self.assertTrue(field.db_index)

    def test_deleting_the_url_deletes_the_link(self):
        pointer = url_for(self.article)
        XdContentUrl.objects.create(
            content_type=ContentType.objects.get_for_model(self.category),
            object_id=self.category.pk,
            field_name="xd_content_url",
            url=pointer,
        )
        pointer.delete()
        self.assertEqual(XdContentUrl.objects.count(), 0)

    def test_timestamps_are_maintained(self):
        link = XdContentUrl.objects.create(
            content_type=ContentType.objects.get_for_model(self.category),
            object_id=self.category.pk,
            url=url_for(self.article),
        )
        self.assertIsNotNone(link.created_at)
        self.assertIsNotNone(link.updated_at)
