import django.forms as django_forms
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from xadmin_content_url.forms import widgets
from xadmin_content_url.models import XdUrl


class XdContentUrlField(django_forms.Field):
	widget = widgets.XdContentUrlInput
	widget_model = XdUrl

	def __init__(self, *args, empty_value=None, **kwargs):
		super().__init__(*args, **kwargs)
		# Assigned unconditionally. Until 1.10.0 the assignment sat inside
		# `if empty_value is None`, so passing anything else dropped the argument --
		# and because forms.Field defines no empty_value, to_python("") then raised
		# AttributeError instead of returning it.
		# The default stays [] rather than None so that clearing the widget clears
		# the stored links: save_form_data treats None as "field not submitted".
		self.empty_value = [] if empty_value is None else empty_value

	def prepare_value(self, value):
		if value in self.empty_values or isinstance(value, list):
			return value
		else:
			return self.to_python(value)

	def has_changed(self, initial, data):
		"""Return True if data differs from initial."""
		# Always return False if the field is disabled since self.bound_data
		# always uses the initial value in this case.
		if self.disabled:
			return False
		try:
			data = self.to_python(data)
			if hasattr(self, '_coerce'):
				return self._coerce(data) != self._coerce(initial)
		except ValidationError:
			return True
		# For purposes of seeing whether something has changed, None is
		# the same as an empty string, if the data or initial value we get
		# is None, replace it with ''.
		initial_values: list[XdUrl] = initial if initial is not None else ()
		data_values: list[XdUrl] = data if data is not None else ()
		changed = False
		for data_val in data_values:
			for initial_val in initial_values:
				if (data_val.pk and data_val.pk == initial_val.pk or
						data_val.content_type == initial_val.content_type and
						data_val.object_id == initial_val.object_id):
					break
			else:
				changed = True
				break
		return changed

	def to_python(self, value):
		if value in self.empty_values:
			return self.empty_value
		items = []
		for index, item in enumerate(value.split(',')):
			app_label, model_name, object_id = item.split(":")
			model = apps.get_model(app_label, model_name)
			object_id = model._meta.pk.to_python(object_id)
			ctype = ContentType.objects.get_for_model(model)
			items.append(self.widget_model(object_id=object_id, content_type=ctype))
		return items
