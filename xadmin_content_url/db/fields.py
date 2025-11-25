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
        Captures the field name, uses it to filter the generic relation,
        and adds a helper property to the model.
        """
        super().contribute_to_class(cls, name, **kwargs)
        # Filter the relation for choices in forms/admin.
        self.remote_field.limit_choices_to = {'field_name': name}

        # Dynamically add a property to the model that resolves the filtered URL object.
        # For a field named 'my_field', this adds a property 'my_field_resolved'.
        def url_getter(instance):
            manager = getattr(instance, name)
            # .all() is required to get a filterable queryset from the generic manager.
            # .select_related('url') is an optimization to avoid an extra DB query.
            content_url_obj = manager.all().filter(field_name=name).select_related('url').first()
            return content_url_obj.url if content_url_obj else None

        setattr(cls, f'{name}_content_url_resolved', property(url_getter))


    def xd_save_form_data(self, instance, object_id, content_type: ContentType):
        """
        Creates or gets the XdUrl and XdContentUrl, now including the field_name.
        """
        url, _ = XdUrl.objects.get_or_create(
            content_type=content_type,
            object_id=object_id,
        )

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
        related_manager = super().value_from_object(obj)
        qs = related_manager.filter(field_name=self.name)
        return [o.url for o in qs]

    def formfield(self, **kwargs):
        defaults = {
            'form_class': fields.XdContentUrlField
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)
