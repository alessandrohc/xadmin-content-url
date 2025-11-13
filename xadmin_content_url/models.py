from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse, NoReverseMatch
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from . import settings as xd_settings


class XdSiteViewUrl(models.Model):
    ref = models.CharField(verbose_name=_("Ref"), max_length=256,
                           unique=True, editable=False)
    name = models.CharField(verbose_name=_("Name"), max_length=256)
    view_name = models.CharField(verbose_name=_("URL name"), max_length=350)

    def get_absolute_url(self):
        try:
            return reverse(self.view_name)
        except NoReverseMatch:
            return

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['view_name']),
            models.Index(fields=['ref'])
        ]
        verbose_name = _("Site view")
        verbose_name_plural = _("Site views")


class XdUrl(models.Model):
    object_id = models.PositiveIntegerField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    content_object = GenericForeignKey("content_type", "object_id")

    def _get_object_url(self):
        # noinspection PyBroadException
        try:
            obj = self.content_object
        except Exception as exc:
            url = None
        else:
            url = obj and obj.get_absolute_url()
        return force_str(url or '')

    def __str__(self):
        return self._get_object_url()

    class Meta:
        verbose_name = _("URL")
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]


class XdContentUrl(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    object_id = models.PositiveIntegerField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    content_object = GenericForeignKey("content_type", "object_id")

    field_name = models.CharField(
        _("Field Name"),
        max_length=255,
        db_index=True,
        default=xd_settings.XD_CONTENT_URL_RELATION_FIELD
    )
    url = models.ForeignKey(XdUrl, on_delete=models.CASCADE, verbose_name=_("URL"))

    def __str__(self):
        return str(self.url)

    class Meta:
        ordering = ("content_type",)
        verbose_name = _("Content URL")
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]
