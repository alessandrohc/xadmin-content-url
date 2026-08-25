# coding=utf-8
"""Minimal settings for the xadmin-content-url suite.

Two choices here are worth reading before changing anything.

**MIGRATION_MODULES sets this app to None.** The package deliberately ships an empty
``migrations`` package: the host project redirects
``MIGRATION_MODULES['xadmin_content_url']`` at a per-instance module it generates
(``plus_base/settings/content_url.py``), so there is no migration to ship. Mapping
the app to None here tells Django it has no migrations at all, which makes the test
runner create its three tables straight from the models.

**XD_CONTENT_URL_FOR_MODELS is filled in.** The field is not declared on any model
by hand -- ``AppConfig.ready`` reads this setting and grafts it on. So this setting
*is* the package's public surface, and the suite has to exercise both of its forms:
the legacy string and the dictionary with explicit field names.
"""
from pathlib import Path

from django import forms

# ---------------------------------------------------------------------------
# Django >= 5.0 compat shim for xadmin -- test-only, on purpose.
#
# xadmin/views/dashboard.py:298 builds `property(_get_choices,
# forms.ChoiceField._set_choices)`. Django 5.0 turned ChoiceField.choices into a
# real property and dropped the old pair, so importing xadmin.views raises
# AttributeError on 5.0+ and django.setup() never finishes. Reusing the new
# property's setter gives back exactly the callable xadmin wants, with Django's own
# semantics. The permanent fix belongs to xadmin (#7093); nothing ships this.
# ---------------------------------------------------------------------------
if not hasattr(forms.ChoiceField, '_set_choices'):
    forms.ChoiceField._set_choices = forms.ChoiceField.choices.fset

BASE_DIR = Path(__file__).resolve().parent.parent

# Fixed key: this is a test suite, there is nothing here to protect.
SECRET_KEY = 'xadmin-content-url-test-only-not-a-secret'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',

    # xadmin's own dependencies. crispy_forms is also this package's: the content
    # picker view builds a FormHelper.
    'crispy_forms',
    'crispy_bootstrap4',
    'reversion',
    'import_export',
    'formtools',
    'rest_framework',

    'xadmin',
    'xadmin_content_url',
    'test_content_url',
]

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Restores HttpRequest.is_ajax() for xadmin's benefit, not this package's --
    # xadmin/plugins/ajax.py calls it on every admin view. Mirrors what the host
    # project installs; see the module docstring in middleware.py.
    'test_content_url.middleware.RequestToolsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ROOT_URLCONF = 'test_content_url.urls'

STATIC_URL = '/static/'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_TEMPLATE_PACK = 'bootstrap4'
CRISPY_ALLOWED_TEMPLATE_PACKS = ('bootstrap4',)

# See the module docstring: the package ships no migrations by design.
MIGRATION_MODULES = {'xadmin_content_url': None}

# The graft AppConfig.ready() performs. Article uses the dictionary form with two
# named fields, which is what proves several fields can coexist on one model;
# Category uses the legacy string form and gets the default field name.
XD_CONTENT_URL_FOR_MODELS = [
    {'test_content_url.Article': ['primary_url', ('secondary_url', {})]},
    'test_content_url.Category',
]

XD_CONTENT_URL_PERMISSIONS = ['view_content_url']
