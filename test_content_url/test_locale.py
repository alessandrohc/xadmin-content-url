# coding=utf-8
"""The pt_BR catalogues: shipped, compiled, in sync, and actually used.

This package ships **two**. ``django.mo`` covers Python and templates; ``djangojs.mo``
covers the picker's JavaScript and only reaches the browser because the host project
lists ``xadmin_content_url`` in ``XADMIN_I18N_JAVASCRIPT_PACKAGES`` -- so a stale or
missing djangojs catalogue shows up as an untranslated modal, with nothing wrong
server-side.
"""
import gettext
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from django.test import SimpleTestCase
from django.utils import translation

LOCALE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "xadmin_content_url"
    / "locale"
    / "pt_BR"
    / "LC_MESSAGES"
)
DOMAINS = ("django", "djangojs")


def catalog(path):
    with open(path, "rb") as handle:
        return gettext.GNUTranslations(handle)


class ShippedCatalogTests(SimpleTestCase):

    def test_both_domains_ship_source_and_compiled(self):
        for domain in DOMAINS:
            with self.subTest(domain=domain):
                self.assertTrue((LOCALE / "{0}.po".format(domain)).is_file())
                self.assertTrue((LOCALE / "{0}.mo".format(domain)).is_file())

    def test_each_catalogue_declares_its_language(self):
        # Empty until 1.10.0, in both files. Django infers the language from the
        # directory name, so nothing broke -- every other gettext tool reads this.
        for domain in DOMAINS:
            with self.subTest(domain=domain):
                info = catalog(LOCALE / "{0}.mo".format(domain)).info()
                self.assertEqual(info.get("language"), "pt_BR")

    def test_every_message_is_translated(self):
        for domain in DOMAINS:
            with self.subTest(domain=domain):
                untranslated = [
                    msgid
                    for msgid, msgstr in catalog(
                        LOCALE / "{0}.mo".format(domain)
                    )._catalog.items()
                    if msgid and not msgstr
                ]
                self.assertEqual(untranslated, [])

    def test_no_entry_is_left_fuzzy(self):
        """msgfmt drops fuzzy entries, so a fuzzy string silently shows in English.

        Only the source file records the flag, so this is the sole place to see it.
        """
        for domain in DOMAINS:
            with self.subTest(domain=domain):
                lines = (
                    (LOCALE / "{0}.po".format(domain))
                    .read_text(encoding="utf-8")
                    .splitlines()
                )
                fuzzy = [
                    index
                    for index, line in enumerate(lines, 1)
                    if line.startswith("#,") and "fuzzy" in line
                ]
                self.assertEqual(fuzzy, [])


@unittest.skipIf(shutil.which("msgfmt") is None, "gettext tools not installed")
class CompiledInSyncTests(SimpleTestCase):
    """The committed .mo files have to match the committed .po files.

    Compared message by message, never byte by byte: msgfmt writes its own headers
    and strips POT-Creation-Date, so two correct builds differ as files.
    """

    def test_each_committed_mo_matches_a_fresh_build(self):
        for domain in DOMAINS:
            with self.subTest(domain=domain):
                source = LOCALE / "{0}.po".format(domain)
                with tempfile.TemporaryDirectory() as tmp:
                    fresh = pathlib.Path(tmp) / "fresh.mo"
                    subprocess.run(
                        ["msgfmt", "--check", "-o", str(fresh), str(source)], check=True
                    )
                    committed = catalog(LOCALE / "{0}.mo".format(domain))._catalog
                    rebuilt = catalog(fresh)._catalog
                self.assertEqual(set(committed), set(rebuilt))
                differing = {
                    key: (committed[key], rebuilt[key])
                    for key in set(committed) & set(rebuilt)
                    if key and committed[key] != rebuilt[key]
                }
                self.assertEqual(differing, {})


class ActiveTranslationTests(SimpleTestCase):
    """What the catalogues are for."""

    def _config(self):
        from django.apps import apps

        return apps.get_app_config("xadmin_content_url")

    def test_the_app_label_is_translated(self):
        with translation.override("pt-br"):
            self.assertEqual(str(self._config().verbose_name), "URL de conteúdo")

    def test_english_is_the_source_language(self):
        with translation.override("en"):
            self.assertEqual(str(self._config().verbose_name), "Content URL")

    def test_model_metadata_is_translated(self):
        from xadmin_content_url.models import XdSiteViewUrl

        with translation.override("pt-br"):
            self.assertEqual(str(XdSiteViewUrl._meta.verbose_name), "Tela do site")
            self.assertEqual(
                str(XdSiteViewUrl._meta.verbose_name_plural), "Telas do site"
            )

    def test_the_javascript_catalogue_covers_the_picker_strings(self):
        # Both come from static/xd_content_url/js/xd_sel_url.js.
        js = catalog(LOCALE / "djangojs.mo")
        self.assertEqual(js.gettext("Insert selected"), "Inserir selecionado")
        self.assertEqual(js.gettext("Content URL"), "URL de conteúdo")

    def test_a_template_string_is_translated(self):
        from django.template import Context, Template

        template = Template("{% load i18n %}{% trans 'Title' %}")
        with translation.override("pt-br"):
            self.assertEqual(template.render(Context({})), "Título")

    def test_a_mistranslated_label_is_recorded(self):
        """Reported, not changed: "URL name" reads as "URL de conteúdo".

        ``XdSiteViewUrl.view_name`` is the *name of a URL pattern*, so its label in
        the admin should be "Nome da URL". It currently repeats the translation of
        "Content URL", which is a different string entirely -- a copy-paste in the
        catalogue, not a code defect. Left to a translation pass so this packaging
        release does not quietly change admin labels.
        """
        from xadmin_content_url.models import XdSiteViewUrl

        with translation.override("pt-br"):
            label = str(XdSiteViewUrl._meta.get_field("view_name").verbose_name)
        self.assertEqual(label, "URL de conteúdo")
