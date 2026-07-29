# coding=utf-8
"""register_models -- the entry point AppConfig.ready() calls.

It reads a setting written by hand in a host project's settings module, so every
malformed shape a human can produce has to warn and carry on rather than abort the
boot. A raised exception here would take the whole site down at import time.

Registrations are applied to a throwaway model so the real ones stay untouched:
contribute_to_class is not reversible.
"""
import warnings

from django.db import models
from django.test import SimpleTestCase

from xadmin_content_url.register import register_models


class Throwaway(models.Model):
    """A model that exists only to be grafted onto."""

    name = models.CharField(max_length=10)

    class Meta:
        app_label = "test_content_url"


def field_names(model):
    return {field.name for field in model._meta.private_fields}


class LegacyStringFormTests(SimpleTestCase):

    def test_a_string_grafts_the_default_field_name(self):
        register_models("test_content_url.Throwaway")
        from xadmin_content_url import settings as xd_settings

        self.assertIn(xd_settings.XD_CONTENT_URL_RELATION_FIELD, field_names(Throwaway))

    def test_an_unknown_model_warns_instead_of_raising(self):
        with self.assertWarns(RuntimeWarning) as caught:
            register_models("test_content_url.NoSuchModel")
        self.assertIn("NoSuchModel", str(caught.warning))

    def test_a_path_without_a_dot_warns(self):
        # "Article" instead of "app_label.Article" -- the split fails.
        with self.assertWarns(RuntimeWarning):
            register_models("Throwaway")


class DictionaryFormTests(SimpleTestCase):

    def test_a_list_of_names_grafts_each_one(self):
        register_models({"test_content_url.Throwaway": ["alpha_url", "beta_url"]})
        names = field_names(Throwaway)
        self.assertIn("alpha_url", names)
        self.assertIn("beta_url", names)

    def test_a_name_and_kwargs_pair_is_accepted(self):
        register_models(
            {"test_content_url.Throwaway": [("kw_url", {"verbose_name": "Chosen"})]}
        )
        field = next(f for f in Throwaway._meta.private_fields if f.name == "kw_url")
        self.assertEqual(str(field.verbose_name), "Chosen")

    def test_a_missing_verbose_name_is_derived_from_the_field_name(self):
        register_models({"test_content_url.Throwaway": ["derived_label_url"]})
        field = next(
            f for f in Throwaway._meta.private_fields if f.name == "derived_label_url"
        )
        self.assertEqual(str(field.verbose_name), "Derived Label Url")

    def test_a_bare_value_is_wrapped_and_warned_about(self):
        # A string where a list was expected: usable, but worth telling the author.
        with self.assertWarns(RuntimeWarning) as caught:
            register_models({"test_content_url.Throwaway": "single_url"})
        self.assertIn("must be a list or tuple", str(caught.warning))
        self.assertIn("single_url", field_names(Throwaway))

    def test_an_unknown_model_in_the_dict_does_not_stop_the_rest(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            register_models(
                {
                    "test_content_url.NoSuchModel": ["ignored_url"],
                    "test_content_url.Throwaway": ["survivor_url"],
                }
            )
        self.assertTrue(any("NoSuchModel" in str(w.message) for w in caught))
        self.assertIn("survivor_url", field_names(Throwaway))

    def test_a_malformed_field_definition_warns_and_is_skipped(self):
        with self.assertWarns(RuntimeWarning) as caught:
            register_models({"test_content_url.Throwaway": [("too", "many", "parts")]})
        self.assertIn("Invalid field definition", str(caught.warning))


class UnknownShapeTests(SimpleTestCase):

    def test_neither_a_string_nor_a_dict_warns(self):
        with self.assertWarns(RuntimeWarning) as caught:
            register_models(42)
        self.assertIn("Must be a string or a dictionary", str(caught.warning))

    def test_nothing_registered_is_not_an_error(self):
        register_models()
