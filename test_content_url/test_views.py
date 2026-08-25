# coding=utf-8
"""The content picker view, through the real URLconf.

``ContentUrlAdminView`` is registered on xadmin's site by adminx.py and renders the
modal the JS opens. It is the one place the packaged templates, the crispy helper and
xadmin's static registry all have to line up.
"""
from django.contrib.auth.models import User
from django.test import TestCase

PICKER_URL = "/admin/xd-content-url/"


class PickerViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="root", email="root@example.com", password="secret-for-tests"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_the_view_is_registered_and_renders(self):
        response = self.client.get(PICKER_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "xd_content_url/forms/model_form.html")

    def test_the_form_offers_the_models_that_opted_in(self):
        response = self.client.get(PICKER_URL)
        # Article opted in; Category did not.
        self.assertContains(response, "test_content_url.article")
        self.assertNotContains(response, "test_content_url.category")

    def test_the_form_is_prefixed_so_it_cannot_collide(self):
        # The picker is rendered inside another form's page.
        self.assertContains(self.client.get(PICKER_URL), 'name="xdm-content"')

    def test_the_datatable_language_url_is_published(self):
        """The view resolves xadmin's datatables locale file and hands it to the JS.

        xstatic raises ValueError for the English locale, which the view turns into
        an empty string rather than a 500.
        """
        response = self.client.get(PICKER_URL)
        self.assertIn("dt_language_url", response.context)

    def test_anonymous_users_get_the_login_form_instead(self):
        # xadmin renders its login view in place rather than redirecting.
        self.client.logout()
        response = self.client.get(PICKER_URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="password"')
        self.assertNotContains(response, 'name="xdm-content"')

    def test_an_english_locale_yields_an_empty_language_url(self):
        """xstatic raises ValueError when there is no locale file to serve.

        DataTables ships no en bundle -- English is its default -- so the view has
        to turn that into an empty string. Left unhandled it would be a 500 on the
        picker for every English installation.
        """
        from unittest import mock

        with mock.patch(
            "xadmin_content_url.views.xstatic", side_effect=ValueError("no locale")
        ):
            response = self.client.get(PICKER_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dt_language_url"], "")

    def test_the_crispy_helper_suppresses_the_form_tag(self):
        # The modal supplies its own <form>; a nested one would break the submit.
        response = self.client.get(PICKER_URL)
        helper = response.context["form"].helper
        self.assertFalse(helper.form_tag)
        self.assertFalse(helper.form_show_labels)
        self.assertFalse(helper.include_media)
