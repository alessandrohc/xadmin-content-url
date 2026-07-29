# coding=utf-8
"""Models for the suite.

The package declares no model that carries its own field: ``AppConfig.ready`` reads
XD_CONTENT_URL_FOR_MODELS and grafts ``XdContentUrlField`` onto whatever models the
host project names. These two stand in for that host.

``get_absolute_url`` matters: it is what ``XdUrl.__str__`` and the REST serializer
resolve, so a model without one is a URL that renders empty.
"""
from django.db import models
from django.urls import reverse


class Article(models.Model):
    """Registered through the dictionary form, with two named fields."""

    title = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def get_absolute_url(self):
        return reverse('article-detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.title


class Category(models.Model):
    """Registered through the legacy string form: one field, the default name."""

    name = models.CharField(max_length=100)

    def get_absolute_url(self):
        return '/categories/{0}/'.format(self.pk)

    def __str__(self):
        return self.name


class Unreachable(models.Model):
    """No get_absolute_url at all -- the branch XdUrl._get_object_url swallows."""

    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
