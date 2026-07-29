# coding=utf-8
"""The distribution's own metadata.

Packaging bugs stay invisible until an install goes wrong somewhere else, so the
things 1.4.0 fixed are pinned here -- above all the README that never shipped.
"""
import pathlib
import re
import unittest

from django.test import SimpleTestCase

try:  # tomllib is stdlib from 3.11; tomli covers 3.10 (see optional deps)
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - depends on the interpreter
    try:
        import tomli as tomllib
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None

ROOT = pathlib.Path(__file__).resolve().parent.parent


@unittest.skipIf(tomllib is None, 'no TOML reader available')
class MetadataTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(ROOT / 'pyproject.toml', 'rb') as handle:
            cls.pyproject = tomllib.load(handle)
        cls.project = cls.pyproject['project']

    def test_declares_a_pep_517_build_backend(self):
        self.assertEqual(self.pyproject['build-system']['build-backend'],
                         'setuptools.build_meta')

    def test_name_and_version(self):
        self.assertEqual(self.project['name'], 'xadmin-content-url')
        self.assertRegex(self.project['version'], r'^\d+\.\d+\.\d+$')

    def test_states_the_minimum_python(self):
        self.assertEqual(self.project['requires-python'], '>=3.10')

    def test_django_is_bounded_on_both_ends(self):
        # Three requirements start with "django" here -- django itself,
        # djangorestframework and django-crispy-forms -- so match the bare one.
        django = [item for item in self.project['dependencies']
                  if item.lower().startswith('django>')]
        self.assertEqual(len(django), 1, msg=self.project['dependencies'])
        self.assertIn('>=4.2', django[0])
        self.assertIn('<6.0', django[0])

    def test_the_other_runtime_dependencies_are_bounded_too(self):
        """Both are imported at module level, and neither was declared before.

        filters.py subclasses a DRF filter backend and views.py builds a crispy
        FormHelper, so a clean install without them raises ImportError at boot.
        """
        requirements = ' '.join(self.project['dependencies'])
        self.assertIn('djangorestframework>=3.15,<4.0', requirements)
        self.assertIn('django-crispy-forms>=2.0,<3.0', requirements)

    def test_xadmin_is_not_a_declared_dependency(self):
        """Deliberate: the xadmin on PyPI is a different, dead project.

        The real one is the fork installed from git under the same dist name.
        """
        offenders = [item for item in self.project['dependencies']
                     if re.match(r'^\s*xadmin', item, re.I)]
        self.assertEqual(offenders, [])

    def test_classifiers_cover_the_tested_matrix(self):
        classifiers = self.project['classifiers']
        for version in ('4.2', '5.0', '5.1', '5.2'):
            self.assertIn('Framework :: Django :: {0}'.format(version), classifiers)
        for version in ('3.10', '3.11', '3.12', '3.13'):
            self.assertIn('Programming Language :: Python :: {0}'.format(version), classifiers)

    def test_the_licence_is_declared_and_shipped(self):
        self.assertEqual(self.project['license'], 'MIT')
        self.assertEqual(self.project['license-files'], ['LICENSE'])
        self.assertTrue((ROOT / 'LICENSE').is_file())

    def test_the_spdx_expression_is_not_doubled_by_a_classifier(self):
        """setuptools>=77 (PEP 639) refuses to build if both are present.

        The failure is at build time only -- the metadata looks fine in the file and
        the suite passes -- so it surfaces when a release is being cut. It is what
        broke django-tabular-permissions v3.1.0.
        """
        offenders = [item for item in self.project['classifiers']
                     if item.startswith('License ::')]
        self.assertEqual(offenders, [],
                         msg='remove the classifier or the license expression, not both')

    def test_the_readme_points_at_the_file_that_exists(self):
        self.assertEqual(self.project['readme'], 'README.md')
        self.assertTrue((ROOT / self.project['readme']).is_file())

    def test_the_urls_point_at_the_maintained_repository(self):
        """Homepage was the former employee's fork until 1.4.0.

        The provenance stays, under Upstream, because that is where the code came
        from -- it just is not where the package lives.
        """
        urls = self.project['urls']
        self.assertNotIn('alexsilva', urls['Homepage'])
        self.assertEqual(urls['Homepage'], urls['Source'])
        self.assertIn('alexsilva', urls['Upstream'])

    def test_subpackages_are_declared(self):
        include = self.pyproject['tool']['setuptools']['packages']['find']['include']
        self.assertIn('xadmin_content_url*', include)

    def test_package_data_is_switched_on(self):
        # Templates, the JS and the compiled catalogue reach the wheel through this.
        self.assertTrue(self.pyproject['tool']['setuptools']['include-package-data'])


class LegacyBuildTests(SimpleTestCase):

    def test_setup_py_is_gone(self):
        self.assertFalse((ROOT / 'setup.py').exists())

    def test_no_setup_cfg_metadata(self):
        self.assertFalse((ROOT / 'setup.cfg').exists())


class ManifestTests(SimpleTestCase):
    """Every path MANIFEST.in names has to exist."""

    def _entries(self):
        for line in (ROOT / 'MANIFEST.in').read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                yield line.split()

    def test_included_files_exist(self):
        missing = [parts[1] for parts in self._entries()
                   if parts[0] == 'include' and not (ROOT / parts[1]).exists()]
        self.assertEqual(missing, [], msg='MANIFEST.in includes missing files: {0}'.format(missing))

    def test_recursive_includes_point_at_real_directories(self):
        missing = [parts[1] for parts in self._entries()
                   if parts[0] == 'recursive-include' and not (ROOT / parts[1]).is_dir()]
        self.assertEqual(missing, [], msg='MANIFEST.in walks missing dirs: {0}'.format(missing))

    def test_the_compiled_catalogue_is_included(self):
        # locale/ is listed wholesale, which is what carries django.mo.
        walked = [parts[1] for parts in self._entries() if parts[0] == 'recursive-include']
        self.assertIn('xadmin_content_url/locale', walked)
