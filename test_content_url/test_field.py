# coding=utf-8
"""XdContentUrlField -- the graft, and the field_name scoping that makes it safe.

No model declares this field in its own source: AppConfig.ready() reads
XD_CONTENT_URL_FOR_MODELS and calls contribute_to_class. The suite therefore asserts
against the models as the running app left them, which is the only state that
matters.

The scoping is the part worth guarding. Every link row lives in one shared table and
is distinguished by ``field_name``; if a filter forgets it, saving one field wipes
the other field's link on the same object.
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from test_content_url.models import Article, Category
from xadmin_content_url.db.fields import XdContentUrlField
from xadmin_content_url.forms import fields as form_fields
from xadmin_content_url.models import XdContentUrl, XdUrl


def pointer_to(obj):
    """An unsaved XdUrl the way the form field builds it from submitted data."""
    return XdUrl(
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
    )


class GraftTests(TestCase):

    def test_the_dictionary_form_grafts_every_named_field(self):
        names = {field.name for field in Article._meta.private_fields}
        self.assertIn("primary_url", names)
        self.assertIn("secondary_url", names)

    def test_the_legacy_string_form_grafts_the_default_field_name(self):
        from xadmin_content_url import settings as xd_settings

        names = {field.name for field in Category._meta.private_fields}
        self.assertIn(xd_settings.XD_CONTENT_URL_RELATION_FIELD, names)

    def test_each_field_limits_choices_to_its_own_name(self):
        # This is what keeps two fields on one model from seeing each other's rows.
        field = Article._meta.get_field("primary_url")
        self.assertEqual(field.remote_field.limit_choices_to, {"field_name": "primary_url"})

    def test_the_field_is_editable_so_forms_render_it(self):
        # GenericRelation is editable=False by default, which would hide it.
        self.assertTrue(Article._meta.get_field("primary_url").editable)

    def test_a_resolver_property_is_added_per_field(self):
        self.assertTrue(hasattr(Article, "primary_url_content_url_resolved"))
        self.assertTrue(hasattr(Article, "secondary_url_content_url_resolved"))

    def test_the_form_field_class_is_the_packaged_one(self):
        formfield = Article._meta.get_field("primary_url").formfield()
        self.assertIsInstance(formfield, form_fields.XdContentUrlField)

    def test_the_default_target_model_is_xdcontenturl(self):
        self.assertIs(XdContentUrlField().remote_field.model, XdContentUrl)


class SaveFormDataTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.host = Article.objects.create(title="Host", slug="host")
        cls.target_a = Article.objects.create(title="A", slug="a")
        cls.target_b = Article.objects.create(title="B", slug="b")

    def _save(self, field_name, targets):
        field = Article._meta.get_field(field_name)
        field.save_form_data(self.host, [pointer_to(t) for t in targets])

    def _links(self, field_name):
        return XdContentUrl.objects.filter(
            content_type=ContentType.objects.get_for_model(Article),
            object_id=self.host.pk,
            field_name=field_name,
        )

    def test_saving_creates_the_pointer_and_the_link(self):
        self._save("primary_url", [self.target_a])
        self.assertEqual(self._links("primary_url").count(), 1)
        self.assertEqual(str(self._links("primary_url").get().url), "/articles/a/")

    def test_saving_again_replaces_rather_than_accumulates(self):
        self._save("primary_url", [self.target_a])
        self._save("primary_url", [self.target_b])
        self.assertEqual(self._links("primary_url").count(), 1)
        self.assertEqual(str(self._links("primary_url").get().url), "/articles/b/")

    def test_saving_an_empty_list_clears_the_field(self):
        self._save("primary_url", [self.target_a])
        self._save("primary_url", [])
        self.assertEqual(self._links("primary_url").count(), 0)

    def test_none_is_a_no_op_rather_than_a_clear(self):
        """A field absent from the submitted form must not wipe stored data.

        save_form_data(None) happens when the form did not include the field at all.
        """
        self._save("primary_url", [self.target_a])
        Article._meta.get_field("primary_url").save_form_data(self.host, None)
        self.assertEqual(self._links("primary_url").count(), 1)

    def test_falsy_entries_are_skipped(self):
        field = Article._meta.get_field("primary_url")
        field.save_form_data(self.host, [None, pointer_to(self.target_a)])
        self.assertEqual(self._links("primary_url").count(), 1)

    def test_two_fields_on_one_object_do_not_clobber_each_other(self):
        """The reason field_name is in every filter.

        Without it, saving secondary_url deletes primary_url's link, because both
        rows share content_type and object_id.
        """
        self._save("primary_url", [self.target_a])
        self._save("secondary_url", [self.target_b])

        self.assertEqual(self._links("primary_url").count(), 1)
        self.assertEqual(self._links("secondary_url").count(), 1)
        self.assertEqual(str(self._links("primary_url").get().url), "/articles/a/")
        self.assertEqual(str(self._links("secondary_url").get().url), "/articles/b/")

    def test_clearing_one_field_leaves_the_other_alone(self):
        self._save("primary_url", [self.target_a])
        self._save("secondary_url", [self.target_b])
        self._save("secondary_url", [])
        self.assertEqual(self._links("primary_url").count(), 1)
        self.assertEqual(self._links("secondary_url").count(), 0)

    def test_the_pointer_row_is_reused_across_hosts(self):
        # get_or_create on (content_type, object_id): two hosts pointing at the same
        # target share one XdUrl.
        other_host = Article.objects.create(title="Other", slug="other")
        self._save("primary_url", [self.target_a])
        Article._meta.get_field("primary_url").save_form_data(
            other_host, [pointer_to(self.target_a)]
        )
        self.assertEqual(XdUrl.objects.count(), 1)


class ValueFromObjectTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.host = Article.objects.create(title="Host", slug="host")
        cls.target_a = Article.objects.create(title="A", slug="a")
        cls.target_b = Article.objects.create(title="B", slug="b")

    def test_reads_back_only_this_field_s_links(self):
        Article._meta.get_field("primary_url").save_form_data(
            self.host, [pointer_to(self.target_a)]
        )
        Article._meta.get_field("secondary_url").save_form_data(
            self.host, [pointer_to(self.target_b)]
        )
        primary = Article._meta.get_field("primary_url").value_from_object(self.host)
        self.assertEqual([str(url) for url in primary], ["/articles/a/"])

    def test_an_unset_field_reads_back_empty(self):
        self.assertEqual(
            Article._meta.get_field("primary_url").value_from_object(self.host), []
        )

    def test_the_resolver_property_returns_the_pointer(self):
        Article._meta.get_field("primary_url").save_form_data(
            self.host, [pointer_to(self.target_a)]
        )
        host = Article.objects.get(pk=self.host.pk)
        self.assertEqual(str(host.primary_url_content_url_resolved), "/articles/a/")

    def test_the_resolver_property_is_none_when_unset(self):
        host = Article.objects.get(pk=self.host.pk)
        self.assertIsNone(host.primary_url_content_url_resolved)

    def test_the_resolver_property_is_scoped_to_its_own_field(self):
        Article._meta.get_field("secondary_url").save_form_data(
            self.host, [pointer_to(self.target_b)]
        )
        host = Article.objects.get(pk=self.host.pk)
        self.assertIsNone(host.primary_url_content_url_resolved)
        self.assertEqual(str(host.secondary_url_content_url_resolved), "/articles/b/")
