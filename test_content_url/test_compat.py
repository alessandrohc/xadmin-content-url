# coding=utf-8
"""No dependency on Django APIs that have been removed.

The point of these tests is that they read the shipped source rather than
exercising it: a code path that is only reached on an AJAX request, or only when a
particular plugin is installed, would otherwise carry a removed API for years
without anyone noticing.
"""
import ast
import pathlib

from django.test import SimpleTestCase

import xadmin_content_url

PACKAGE = pathlib.Path(xadmin_content_url.__file__).parent


def sources():
    for path in sorted(PACKAGE.rglob('*.py')):
        yield path, path.read_text(encoding='utf-8')


class RemovedApiTests(SimpleTestCase):

    def test_nothing_calls_request_is_ajax(self):
        """HttpRequest.is_ajax() was removed in Django 4.0.

        This package is clean, and the test exists to keep it that way: xadmin
        itself still calls the method in five places and only works because the
        host project restores it in middleware (mirrored in
        test_content_url/middleware.py). It would be easy to copy that habit from the
        surrounding code.

        The walk is AST-based, so a docstring naming the method is not a hit.
        """
        offenders = []
        for path, source in sources():
            for node in ast.walk(ast.parse(source)):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'is_ajax'):
                    offenders.append('{0}:{1}'.format(path.relative_to(PACKAGE), node.lineno))
        self.assertEqual(offenders, [])

    def test_no_removed_translation_helpers(self):
        # ugettext* went in Django 4.0; the package uses gettext/gettext_lazy.
        removed = ('ugettext', 'ugettext_lazy', 'ungettext', 'ungettext_lazy')
        offenders = [(str(path.relative_to(PACKAGE)), name)
                     for path, source in sources()
                     for name in removed if name in source]
        self.assertEqual(offenders, [])

    def test_no_removed_encoding_helpers(self):
        # smart_text/force_text went in Django 4.0.
        removed = ('smart_text', 'force_text')
        offenders = [(str(path.relative_to(PACKAGE)), name)
                     for path, source in sources()
                     for name in removed if name in source]
        self.assertEqual(offenders, [])

    def test_no_stdlib_modules_removed_in_python_3_12(self):
        """distutils and friends went with PEP 594 / PEP 632.

        This is the failure mode that stops a package from importing at all on
        3.12+, so it is worth a guard even when the current source is clean.
        """
        removed = ('distutils', 'telnetlib', 'imp', 'pipes', 'cgi', 'asynchat', 'asyncore')
        offenders = []
        for path, source in sources():
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Import):
                    names = [alias.name.split('.')[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or '').split('.')[0]]
                else:
                    continue
                for name in names:
                    if name in removed:
                        offenders.append('{0}:{1} {2}'.format(
                            path.relative_to(PACKAGE), node.lineno, name))
        self.assertEqual(offenders, [])

    def test_urls_are_not_built_with_the_removed_conf_helper(self):
        # django.conf.urls.url was removed in Django 4.0. The package registers its
        # routes as regex strings through site.register_view, so there is nothing
        # to import -- this pins that.
        offenders = [str(path.relative_to(PACKAGE)) for path, source in sources()
                     if 'from django.conf.urls import' in source]
        self.assertEqual(offenders, [])


class ImportTests(SimpleTestCase):

    def test_every_module_imports(self):
        """Cheap, and it is what a packaging mistake breaks first.

        adminx is excluded: importing it twice would register the views and the
        XdSiteViewUrl admin on the site a second time. xadmin's autodiscover already
        imported it, which is what the view tests rely on.
        """
        import importlib

        for path, _source in sources():
            module = '.'.join(path.relative_to(PACKAGE.parent).with_suffix('').parts)
            if module.endswith('adminx'):
                continue
            importlib.import_module(module)
