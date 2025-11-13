from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from xadmin_content_url.forms import fields
from xadmin_content_url.models import XdContentUrl, XdUrl


class XdContentUrlField(GenericRelation):
    """
    A GenericRelation to XdContentUrl that is aware of its own field name,
    allowing multiple such fields to exist on a single model.
    """
    description = "Field that allows selecting url for generic content."

    def __init__(self, to=None, **kwargs):
        super().__init__(to or XdContentUrl, **kwargs)
        self.editable = True

    def contribute_to_class(self, cls, name, **kwargs):
        """
        Captures the field name and uses it to filter the generic relation.
        """
        super().contribute_to_class(cls, name, **kwargs)
        # Filter the relation to only include XdContentUrl objects
        # where the field_name matches the name of this field.
        self.remote_field.limit_choices_to = {'field_name': name}

    def xd_save_form_data(self, instance, object_id, content_type: ContentType):
        """
        Creates or gets the XdUrl and XdContentUrl, now including the field_name.
        """
        url = XdUrl.objects.get_or_create(
            content_type=content_type,
            object_id=object_id,
        )[0]

        # Ensure the field_name is saved along with the link.
        obj, created = self.remote_field.model.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.pk,
            field_name=self.name,  # self.name is the name of the field on the parent model
            defaults={'url': url}
        )
        return obj

    def save_form_data(self, instance, data: list[XdUrl]):
        """
        Saves the form data, ensuring that only links managed
        by this specific field are affected.
        """
        if data is None:
            return

        saved_pks = []
        # The widget usually returns a list with one item, but we iterate for safety.
        for url in data:
            if not url:
                continue
            obj = self.xd_save_form_data(instance, url.object_id, url.content_type)
            saved_pks.append(obj.pk)

        # DELETES only the links managed by THIS field that are no longer selected.
        # Adding `field_name=self.name` to the filter is the crucial fix.
        qs = self.remote_field.model.objects.filter(
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.pk,
            field_name=self.name
        )
        qs.exclude(pk__in=saved_pks).delete()

    def value_from_object(self, obj):
        """Return the value of this field in the given model instance."""
        # The filtering by field_name is already handled automatically by limit_choices_to
        return [o.url for o in super().value_from_object(obj).all()]

    def formfield(self, **kwargs):
        defaults = {
            'form_class': fields.XdContentUrlField
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)
