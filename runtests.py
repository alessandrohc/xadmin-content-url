#!/usr/bin/env python
# coding=utf-8
"""Entry point for the xadmin-content-url suite, on Django's native test runner.

The package declares three models and ships no migrations for them (the host
project generates those per instance), so ``test_content_url.settings`` maps the app
to None in MIGRATION_MODULES and the runner builds the tables from the models.

xadmin has to be importable. It is not a declared dependency (see pyproject.toml),
so point at the clone:

    PYTHONPATH=../django-xadmin python runtests.py

    python runtests.py                          # whole suite
    python runtests.py test_content_url.test_views  # a single module
    python runtests.py -v 3 --failfast          # runner flags

With coverage:

    coverage run runtests.py && coverage report
"""
import argparse
import os
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the xadmin-content-url suite.")
    parser.add_argument('labels', nargs='*', default=None,
                        help="test labels (default: test_content_url)")
    parser.add_argument('-v', '--verbosity', type=int, default=2, choices=[0, 1, 2, 3])
    parser.add_argument('--failfast', action='store_true')
    parser.add_argument('--keepdb', action='store_true')
    options = parser.parse_args(argv)

    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_content_url.settings')

    import django
    from django.conf import settings
    from django.test.utils import get_runner

    try:
        django.setup()
    except ImportError as exc:  # xadmin missing is the one failure worth explaining
        if 'xadmin' in str(exc):
            sys.stderr.write(
                "xadmin is not importable: {0}\n"
                "It is not a declared dependency -- run with "
                "PYTHONPATH=../django-xadmin\n".format(exc))
            return 2
        raise

    runner_class = get_runner(settings)
    runner = runner_class(verbosity=options.verbosity,
                          interactive=False,
                          failfast=options.failfast,
                          keepdb=options.keepdb)
    failures = runner.run_tests(options.labels or ['test_content_url'])
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
