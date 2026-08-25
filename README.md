# xadmin-content-url

Lets an editor point a field at **any object registered in the admin** and store its
URL, instead of typing one by hand. A menu entry can target an article, a category or
a site view; the link keeps working when the target's slug changes, because what is
stored is the object, not the string.

It is built on a generic relation, so no model needs a foreign key per content type,
and a single model can carry several such fields.

## Requirements

| | |
| --- | --- |
| Python | 3.10 – 3.13 |
| Django | 4.2 – 5.2 |
| xadmin | the `fabricadigital` fork, 3.6.25 or newer |

Also required, and declared: **djangorestframework** (the picker's datatable is fed by
a DRF serializer and filter backend) and **django-crispy-forms** (the picker view
builds a `FormHelper`). Neither was declared before 1.10.0, so a clean install raised
`ImportError` at boot.

**xadmin is not a declared dependency, on purpose.** Every plugin module imports it,
but the xadmin this package builds on is the fork installed from git (dist name
`xadmin`), while the `xadmin` on PyPI is an unrelated project abandoned at 0.6.1.
Declaring it would make a clean `pip install` resolve to that dead package or fail
outright, so the requirement is stated here and enforced by the test suite, which
imports the real fork.

## Install

```shell
pip install git+https://github.com/alessandrohc/xadmin-content-url.git@v1.10.0
```

## Migrations: the package ships none, by design

There are three models and no migration files — only an empty `migrations` package.
The host project redirects the app at a module it generates per instance:

```python
MIGRATION_MODULES = {'xadmin_content_url': 'myproject_config.xadmin_content_url.migrations'}
```

That is the Publique pattern (`plus_base/settings/content_url.py`). **A project that
does neither gets no tables**: Django sees a migrations package with nothing in it and
concludes the app is fully migrated. Either point `MIGRATION_MODULES` somewhere
writable and run `makemigrations`, or map the app to `None` so the tables are created
straight from the models — which is what this package's own test settings do.

## Setup

```python
INSTALLED_APPS = [
    # ...
    'rest_framework',
    'crispy_forms',
    'xadmin_content_url',
]
```

Then name the models that should carry a field. Two forms are accepted:

```python
XD_CONTENT_URL_FOR_MODELS = [
    # dictionary form: one or more named fields per model
    {'myapp.MenuItem': ['primary_url', ('fallback_url', {'verbose_name': 'Fallback'})]},
    # legacy string form: one field, named by XD_CONTENT_URL_RELATION_FIELD
    'myapp.Category',
]
```

`AppConfig.ready()` reads that setting and grafts the fields on, so no model declares
them in its own source. A malformed entry warns (`RuntimeWarning`) and is skipped
rather than breaking the boot.

Reading a stored URL back, per field:

```python
item = MenuItem.objects.get(pk=1)
item.primary_url_content_url_resolved       # -> XdUrl or None
str(item.primary_url_content_url_resolved)  # -> the target's get_absolute_url()
```

A target model needs `get_absolute_url()`; without one the stored link renders as an
empty string rather than raising.

### Which models the picker offers

Only those whose xadmin admin class opts in:

```python
class ArticleAdmin:
    xd_content_url_enable = True
    xd_content_search_fields = ('title',)   # what the picker's search box filters on
```

`xd_content_search_fields` may be a string or a sequence. Several fields narrow
cumulatively (they AND together). A model without it is listed but not searchable —
its picker returns everything.

### Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `XD_CONTENT_URL_FOR_MODELS` | `[]` | Which models get a field, in either form above. |
| `XD_CONTENT_URL_RELATION_FIELD` | `'xd_content_url'` | Field name used by the legacy string form. |
| `XD_CONTENT_URL_FOR_VIEW_NAME` | `{}` | Named site views to expose as targets; synced by `register_xd_site_urls`. |
| `XD_CONTENT_URL_VIEW_NAME_AUTO_REMOVE` | `True` | Whether that command deletes rows no longer in the setting. |
| `XD_CONTENT_URL_PERMISSIONS` | `()` | Permissions required to read the picker's REST endpoint. |

### Commands

```shell
python manage.py register_xd_site_urls    # sync XdSiteViewUrl from XD_CONTENT_URL_FOR_VIEW_NAME
python manage.py clear_xd_content_urls    # delete links whose host object is gone
```

## Compatibility

Every cell below was run against the real xadmin fork — whole suite, no skips:

| | Django 4.2 | Django 5.0 | Django 5.1 | Django 5.2 |
| --- | --- | --- | --- | --- |
| Python 3.10 | pass | pass | pass | pass |
| Python 3.11 | pass | pass | pass | pass |
| Python 3.12 | pass | pass | pass | pass |
| Python 3.13 | n/a | n/a | pass | pass |

`n/a` is Django's own limit: 4.2 and 5.0 do not support 3.13.

This package's own code uses no API Django has removed — `test_compat.py` pins that.
Two things it needs from its environment on Django 5.x are xadmin's gaps, not its own,
and the test settings supply both so the suite can run:

- **`ChoiceField._set_choices`**, dropped in Django 5.0 and monkeypatched by
  `xadmin/views/dashboard.py`, which makes `django.setup()` fail on 5.0+.
- **`HttpRequest.is_ajax()`**, removed in Django 4.0. xadmin calls it in five places,
  one of which runs on every admin view, so the whole admin depends on the host
  project's `RequestToolsMiddleware` restoring it.

Neither shim ships.

## Translations

Source strings are English, with a compiled `pt_BR` catalogue in **two** domains:
`django` (Python and templates, 14 messages) and `djangojs` (the picker's JavaScript,
2 messages). The JS one only reaches the browser if the host project lists
`xadmin_content_url` in `XADMIN_I18N_JAVASCRIPT_PACKAGES`.

## Running the tests

```shell
PYTHONPATH=../django-xadmin python runtests.py
PYTHONPATH=../django-xadmin python runtests.py test_content_url.test_field
```

With coverage (currently 99%):

```shell
pip install -e ".[test]"
PYTHONPATH=../django-xadmin coverage run runtests.py && coverage report -m
```

`test_locale.py` needs `msgfmt` to compare each committed `.mo` against its `.po`; it
skips without it. There is no CI on this repository.

## Known issues

Found while packaging 1.10.0 and reported rather than changed, because each one either
deletes more data than it does today or changes what an editor reads on screen:

- **`clear_xd_content_urls` sweeps the narrower orphan class.** Its help says it
  removes "links that point to deleted objects", but what it checks is whether the
  link's *host* is gone — the target lives one hop away, on `XdUrl`. And because the
  grafted field is a `GenericRelation`, deleting a registered host already cascades,
  so for any model registered through this package the case it looks for cannot
  arise. What does happen — the target being deleted, leaving a menu entry that
  renders an empty URL — is not swept, and `XdUrl` rows are never swept at all.
  Widening it means deleting more rows, which is a maintainer's call. Pinned by
  `test_a_link_whose_target_is_gone_is_kept`.
- **One pt_BR string is wrong**: `"URL name"` (the label of `XdSiteViewUrl.view_name`)
  is translated as *"URL de conteúdo"*, repeating the translation of `"Content URL"`.
  It should read "Nome da URL". Left to a translation pass so a packaging release does
  not change admin labels.

## 1.10.0

- Packaging moved to `pyproject.toml` (PEP 517/621); `setup.py` is gone. It declared
  no build backend, no `python_requires`, no dependencies and no Django classifiers,
  and pointed `url` at a former employee's fork as the project home. The provenance is
  now recorded under `Upstream` instead.
- **`djangorestframework` and `django-crispy-forms` are declared.** Both are imported
  at module level and neither was listed, so a clean install was broken.
- Both catalogue headers filled in: `Language:` was empty and the rest was still
  gettext's `SOME DESCRIPTIVE TITLE` boilerplate, in both domains. Messages untouched;
  both `.mo` files recompiled and verified against their `.po` by a test.
- **Fixed: `XdContentUrlField`'s `empty_value` argument was inert.** The assignment
  sat inside `if empty_value is None`, so any other value was dropped — and since
  `forms.Field` defines no `empty_value`, `to_python("")` then raised `AttributeError`
  instead of returning it. The default is still `[]`, which is what makes clearing the
  widget clear the stored links.
- **Fixed: `register_xd_site_urls` wrote straight to `sys.stdout`.** It now uses
  `self.stdout`, so `call_command(stdout=...)` captures its output and `--verbosity`
  applies. The text is unchanged.
- Test suite added: 153 tests, 99% coverage, run across 14 Python × Django cells.
