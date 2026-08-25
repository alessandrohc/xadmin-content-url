# coding=utf-8
"""The form field, its widget, and the content picker form.

The wire format is a comma-separated list of ``app_label:model:object_id`` triples,
produced by the JS and parsed back here. It is the contract between the browser and
the field, so round-tripping it is the thing to pin.
"""
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from xadmin.sites import AdminSite

from test_content_url.models import Article, Category, Unreachable
from xadmin_content_url.forms.content import ContentUrlForm, get_models_registry
from xadmin_content_url.forms.fields import XdContentUrlField
from xadmin_content_url.forms.widgets import XdContentUrlInput
from xadmin_content_url.models import XdUrl


def wire(obj):
    opts = obj._meta
    return "{0}:{1}:{2}".format(opts.app_label, opts.model_name, obj.pk)


class ToPythonTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.article = Article.objects.create(title="A", slug="a")
        cls.category = Category.objects.create(name="News")

    def setUp(self):
        self.field = XdContentUrlField(required=False)

    def test_a_single_triple_becomes_one_pointer(self):
        value = self.field.to_python(wire(self.article))
        self.assertEqual(len(value), 1)
        self.assertIsInstance(value[0], XdUrl)
        self.assertEqual(value[0].object_id, self.article.pk)
        self.assertEqual(
            value[0].content_type, ContentType.objects.get_for_model(Article)
        )

    def test_several_triples_are_comma_separated(self):
        raw = ",".join([wire(self.article), wire(self.category)])
        self.assertEqual(len(self.field.to_python(raw)), 2)

    def test_an_empty_value_becomes_the_empty_list(self):
        # empty_value defaults to [] rather than None, so save_form_data clears.
        self.assertEqual(self.field.to_python(""), [])
        self.assertEqual(self.field.to_python(None), [])

    def test_the_object_id_is_coerced_through_the_model_pk(self):
        value = self.field.to_python(wire(self.article))
        self.assertIsInstance(value[0].object_id, int)

    def test_a_malformed_triple_raises(self):
        # Not a ValidationError: the JS is the only producer of this value, so a
        # broken payload is a bug rather than user input. Recorded as it behaves.
        with self.assertRaises(ValueError):
            self.field.to_python("only:two")

    def test_the_empty_value_defaults_to_a_list(self):
        # [] rather than None so that clearing the widget clears the stored links:
        # save_form_data reads None as "field not submitted" and skips.
        self.assertEqual(XdContentUrlField(required=False).to_python(""), [])
        self.assertEqual(
            XdContentUrlField(required=False, empty_value=None).to_python(""), []
        )

    def test_an_explicit_empty_value_is_honoured(self):
        """Fixed in 1.10.0; before that the argument was inert.

        The assignment sat inside ``if empty_value is None``, so any other value was
        dropped -- and since forms.Field defines no empty_value, to_python("") raised
        AttributeError instead of returning anything.
        """
        sentinel = ["nothing selected"]
        field = XdContentUrlField(required=False, empty_value=sentinel)
        self.assertIs(field.to_python(""), sentinel)
        self.assertIs(field.to_python(None), sentinel)

    def test_prepare_value_passes_lists_through(self):
        pointers = [XdUrl(object_id=1, content_type=None)]
        self.assertIs(self.field.prepare_value(pointers), pointers)

    def test_prepare_value_parses_a_raw_string(self):
        self.assertEqual(len(self.field.prepare_value(wire(self.article))), 1)


class HasChangedTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.article = Article.objects.create(title="A", slug="a")
        cls.other = Article.objects.create(title="B", slug="b")

    def setUp(self):
        self.field = XdContentUrlField(required=False)

    def _initial(self, obj):
        return [
            XdUrl(
                content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
            )
        ]

    def test_the_same_target_is_not_a_change(self):
        self.assertFalse(
            self.field.has_changed(self._initial(self.article), wire(self.article))
        )

    def test_a_different_target_is_a_change(self):
        self.assertTrue(
            self.field.has_changed(self._initial(self.article), wire(self.other))
        )

    def test_selecting_something_where_there_was_nothing_is_a_change(self):
        self.assertTrue(self.field.has_changed([], wire(self.article)))

    def test_clearing_a_selection_is_reported_as_unchanged(self):
        """Documented, and it is why save_form_data cannot rely on has_changed.

        With no submitted values the loop has nothing to compare, so it falls through
        to False even though the stored value is being removed. The field still saves
        correctly, because ModelForm calls save_form_data regardless.
        """
        self.assertFalse(self.field.has_changed(self._initial(self.article), ""))

    def test_a_disabled_field_never_reports_a_change(self):
        self.field.disabled = True
        self.assertFalse(self.field.has_changed([], wire(self.article)))

    def test_an_unparseable_payload_counts_as_changed(self):
        # to_python raising ValidationError means "we cannot tell" -> assume changed.
        field = XdContentUrlField(required=False)
        field.to_python = lambda value: (_ for _ in ()).throw(ValidationError("bad"))
        self.assertTrue(field.has_changed([], "whatever"))


class WidgetTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.article = Article.objects.create(title="A", slug="a")

    def _pointer(self):
        return XdUrl.objects.create(
            content_type=ContentType.objects.get_for_model(Article),
            object_id=self.article.pk,
        )

    def test_the_value_is_rendered_as_the_wire_format(self):
        context = XdContentUrlInput().get_context("field", [self._pointer()], {})
        self.assertEqual(context["widget"]["value"], wire(self.article))

    def test_the_input_is_hidden_and_carries_a_readable_twin(self):
        # The user sees the resolved URL; the form posts the triples.
        context = XdContentUrlInput().get_context("field", [self._pointer()], {})
        widget = context["widget"]
        self.assertTrue(widget["is_hidden"])
        self.assertEqual(widget["type"], "hidden")
        self.assertEqual(widget["sel"]["value"], "/articles/a/")
        self.assertEqual(widget["sel"]["type"], "text")

    def test_an_empty_value_renders_empty_on_both_halves(self):
        # Django's Widget.format_value turns "" into None, which is what suppresses
        # the value attribute in the rendered input.
        context = XdContentUrlInput().get_context("field", [], {})
        self.assertIsNone(context["widget"]["value"])
        self.assertEqual(context["widget"]["sel"]["value"], "")

    def test_none_is_tolerated(self):
        context = XdContentUrlInput().get_context("field", None, {})
        self.assertIsNone(context["widget"]["value"])
        self.assertEqual(context["widget"]["sel"]["value"], "")

    def test_the_packaged_template_renders(self):
        # The widget points at its own template; a missing one is a 500 on any form
        # carrying the field.
        html = XdContentUrlInput().render("field", [self._pointer()], {})
        self.assertIn(wire(self.article), html)


class ContentPickerFormTests(TestCase):

    def test_only_models_that_opted_in_are_offered(self):
        """xd_content_url_enable is the opt-in.

        Category's admin does not set it, so it must not appear -- otherwise the
        picker would offer models whose REST endpoint refuses to answer.
        """
        choices = dict(ContentUrlForm().fields["content"].choices)
        self.assertIn("test_content_url.article", choices)
        self.assertIn("test_content_url.unreachable", choices)
        self.assertNotIn("test_content_url.category", choices)

    def test_the_labels_are_the_models_verbose_names(self):
        choices = dict(ContentUrlForm().fields["content"].choices)
        self.assertEqual(str(choices["test_content_url.article"]), "article")

    def test_the_registry_walk_can_target_another_site(self):
        # get_models_registry defaults to the global site but accepts one, which is
        # what makes it testable without touching global state.
        self.assertEqual(list(get_models_registry(admin_site=AdminSite())), [])
