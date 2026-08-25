# coding=utf-8
"""The two management commands.

``register_xd_site_urls`` syncs the XdSiteViewUrl table from a settings dict --
it runs on deploy, so its update and removal behaviour decides what a site's menus
point at.

``clear_xd_content_urls`` sweeps links whose *host* object is gone. Not the target:
that distinction is the subject of two tests below, and it is narrower than the
command's own help text claims.
"""
from contextlib import redirect_stdout
from io import StringIO

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase, override_settings

from test_content_url.models import Article, Category, Unreachable
from xadmin_content_url.models import XdContentUrl, XdSiteViewUrl, XdUrl

VIEWS = {
    "articles": {"name": "Articles", "view_name": "article-detail"},
    "admin": {"name": "Admin", "view_name": "xadmin:index"},
}


def register(**kwargs):
    """Run the command and return what it wrote.

    call_command(stdout=...) captures it because 1.10.0 routed the output through
    self.stdout; before that the command wrote to sys.stdout directly, ignoring both
    the stream Django offers and --verbosity. redirect_stdout guards that: anything
    still bypassing self.stdout would land there and fail the assertion below.
    """
    out = StringIO()
    stray = StringIO()
    with redirect_stdout(stray):
        call_command("register_xd_site_urls", stdout=out, **kwargs)
    assert stray.getvalue() == "", "command wrote past self.stdout: {0!r}".format(
        stray.getvalue()
    )
    return out.getvalue()


class RegisterSiteUrlsTests(TestCase):

    @override_settings(XD_CONTENT_URL_FOR_VIEW_NAME=VIEWS)
    def test_creates_one_row_per_configured_view(self):
        # The command reads the setting captured at import time, so the module
        # attribute is what it consults -- see the note in test_the_setting_is_read.
        XdSiteViewUrl.objects.all().delete()
        with self._patched(VIEWS):
            register()
        self.assertEqual(
            set(XdSiteViewUrl.objects.values_list("ref", flat=True)),
            {"articles", "admin"},
        )

    def _patched(self, views, auto_remove=True):
        """Point the command class at a given configuration.

        register_xd_site_urls copies the settings onto class attributes at import
        time, so override_settings alone does not reach it. Patching the attributes
        is what the command actually reads -- and it documents that coupling.
        """
        from unittest import mock

        from xadmin_content_url.management.commands import register_xd_site_urls

        command = register_xd_site_urls.Command
        return mock.patch.multiple(
            command,
            site_view_name_setting=views,
            site_view_auto_remove_setting=auto_remove,
        )

    def test_running_twice_is_idempotent(self):
        with self._patched(VIEWS):
            register()
            register()
        self.assertEqual(XdSiteViewUrl.objects.count(), 2)

    def test_a_changed_name_is_updated_in_place(self):
        with self._patched(VIEWS):
            register()
        changed = {"articles": {"name": "Renamed", "view_name": "article-detail"}}
        with self._patched(changed):
            output = register()
        self.assertEqual(
            XdSiteViewUrl.objects.get(ref="articles").name, "Renamed"
        )
        self.assertIn("Updated", output)

    def test_a_changed_view_name_is_updated_in_place(self):
        with self._patched(VIEWS):
            register()
        changed = {"articles": {"name": "Articles", "view_name": "xadmin:index"}}
        with self._patched(changed):
            register()
        self.assertEqual(
            XdSiteViewUrl.objects.get(ref="articles").view_name, "xadmin:index"
        )

    def test_rows_no_longer_configured_are_removed(self):
        with self._patched(VIEWS):
            register()
        with self._patched({"admin": VIEWS["admin"]}):
            register()
        self.assertEqual(
            set(XdSiteViewUrl.objects.values_list("ref", flat=True)), {"admin"}
        )

    def test_removal_can_be_switched_off(self):
        """Auto-removal deletes rows a site's menus may still reference.

        XD_CONTENT_URL_VIEW_NAME_AUTO_REMOVE exists for instances that register some
        views outside the setting.
        """
        with self._patched(VIEWS):
            register()
        with self._patched({"admin": VIEWS["admin"]}, auto_remove=False):
            register()
        self.assertEqual(XdSiteViewUrl.objects.count(), 2)

    def test_nothing_configured_clears_the_table(self):
        with self._patched(VIEWS):
            register()
        with self._patched({}):
            register()
        self.assertEqual(XdSiteViewUrl.objects.count(), 0)


class ClearContentUrlsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.host = Category.objects.create(name="News")

    def _link(self, target):
        pointer = XdUrl.objects.create(
            content_type=ContentType.objects.get_for_model(target),
            object_id=target.pk,
        )
        return XdContentUrl.objects.create(
            content_type=ContentType.objects.get_for_model(self.host),
            object_id=self.host.pk,
            field_name="xd_content_url",
            url=pointer,
        )

    def _run(self):
        out = StringIO()
        call_command("clear_xd_content_urls", stdout=out)
        return out.getvalue()

    def test_a_live_link_is_kept(self):
        article = Article.objects.create(title="Alive", slug="alive")
        self._link(article)
        output = self._run()
        self.assertEqual(XdContentUrl.objects.count(), 1)
        self.assertIn("No orphaned links found", output)

    def test_deleting_a_registered_host_needs_no_command_at_all(self):
        """The grafted field is a GenericRelation, and those do cascade.

        So for any model registered through this package, the orphan class the
        command looks for cannot arise: the rows are gone before it runs.
        """
        article = Article.objects.create(title="Doomed", slug="doomed")
        self._link(article)
        self.host.delete()
        self.assertEqual(XdContentUrl.objects.count(), 0)
        self.assertIn("No orphaned links found", self._run())

    def test_a_link_on_an_unregistered_host_is_removed(self):
        """Where the command does earn its keep.

        A model with no XdContentUrlField has no GenericRelation, so nothing
        cascades and the link outlives its host. In practice that means rows left
        behind after a model was dropped from XD_CONTENT_URL_FOR_MODELS, or written
        by hand.
        """
        host = Unreachable.objects.create(name="no field here")
        article = Article.objects.create(title="Target", slug="target")
        pointer = XdUrl.objects.create(
            content_type=ContentType.objects.get_for_model(article),
            object_id=article.pk,
        )
        XdContentUrl.objects.create(
            content_type=ContentType.objects.get_for_model(host),
            object_id=host.pk,
            field_name="xd_content_url",
            url=pointer,
        )
        host.delete()
        self.assertEqual(XdContentUrl.objects.count(), 1)

        output = self._run()
        self.assertEqual(XdContentUrl.objects.count(), 0)
        self.assertIn("Marked for deletion", output)
        self.assertIn("1 orphaned links were removed", output)

    def test_a_link_whose_target_is_gone_is_kept(self):
        """The gap, pinned rather than fixed -- reported for a decision.

        The command's help says it removes "URL links that point to deleted
        objects", which reads like this case: the menu entry still exists but the
        content it pointed at is gone. It is not what the code checks. The target
        lives on XdUrl, one hop further, and the link's own content_object is the
        host, which is still very much alive.

        The consequence is visible rather than silent -- ``XdUrl._get_object_url``
        swallows the missing target and renders an empty URL -- so the menu entry
        stays and leads nowhere. Widening the sweep means deleting more rows than it
        does today, which is a call for the maintainer, not a packaging change.
        """
        article = Article.objects.create(title="Doomed", slug="doomed")
        self._link(article)
        article.delete()
        output = self._run()
        self.assertEqual(XdContentUrl.objects.count(), 1)
        self.assertIn("No orphaned links found", output)

    def test_the_pointer_row_is_never_swept(self):
        # XdUrl has no cleanup at all: once its target is gone the row simply stays.
        article = Article.objects.create(title="Doomed", slug="doomed")
        self._link(article)
        article.delete()
        self._run()
        self.assertEqual(XdUrl.objects.count(), 1)

    def test_live_and_orphaned_links_are_told_apart(self):
        alive = Article.objects.create(title="Alive", slug="alive")
        self._link(alive)

        orphan_host = Unreachable.objects.create(name="no field here")
        pointer = XdUrl.objects.create(
            content_type=ContentType.objects.get_for_model(alive), object_id=alive.pk
        )
        XdContentUrl.objects.create(
            content_type=ContentType.objects.get_for_model(orphan_host),
            object_id=orphan_host.pk,
            field_name="xd_content_url",
            url=pointer,
        )
        orphan_host.delete()

        self._run()
        self.assertEqual(XdContentUrl.objects.count(), 1)
        self.assertEqual(XdContentUrl.objects.get().object_id, self.host.pk)

    def test_an_empty_table_is_reported_as_clean(self):
        self.assertIn("No orphaned links found", self._run())
