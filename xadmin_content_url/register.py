import warnings

from django.apps import apps
from django.utils.translation import gettext_lazy as _

from xadmin_content_url import settings
from xadmin_content_url.db.fields import XdContentUrlField
from xadmin_content_url.models import XdContentUrl


def _process_legacy_item(model_path):
    """Processes a legacy, string-based registration."""
    try:
        app_label, model_name = model_path.split(".", 1)
        model = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as exc:
        warnings.warn(f"Invalid model path '{model_path}'. Error: {exc}", RuntimeWarning)
        return

    field = XdContentUrlField(XdContentUrl, verbose_name=_("URL Content"))
    field.contribute_to_class(model, settings.XD_CONTENT_URL_RELATION_FIELD)


def _process_dict_item(item_dict):
    """Processes a new, dictionary-based registration."""
    for model_path, field_names in item_dict.items():
        try:
            app_label, model_name = model_path.split(".", 1)
            model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as exc:
            warnings.warn(f"Invalid model path '{model_path}' in dictionary. Error: {exc}", RuntimeWarning)
            continue  # Continue to the next item in the dict

        if not isinstance(field_names, (list, tuple)):
            warnings.warn(f"Value for '{model_path}' must be a list or tuple of field names.", RuntimeWarning)
            field_names = [field_names]  # Be lenient

        for field_name in field_names:
            # Use the field name to generate a user-friendly verbose_name
            verbose_name = _(field_name.replace("_", " ").title())
            field = XdContentUrlField(XdContentUrl, verbose_name=verbose_name)
            field.contribute_to_class(model, field_name)


def register_models(*items):
    """
    Registers models to receive the content URL field(s).

    It iterates through the configured items from XD_CONTENT_URL_FOR_MODELS.
    Each item can be a string (for legacy, single-field registration) or a
    dictionary (for the new, multi-field registration).
    """
    for item in items:
        if isinstance(item, str):
            # Legacy mode: item is 'app_label.ModelName'
            _process_legacy_item(item)
        elif isinstance(item, dict):
            # New mode: item is {'app_label.ModelName': ['field1', 'field2']}
            _process_dict_item(item)
        else:
            warnings.warn(f"Invalid item in XD_CONTENT_URL_FOR_MODELS: {item}. Must be a string or a dictionary.",
                          RuntimeWarning)

