import os
import json
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.safestring import mark_safe
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse


# Geopaparazzi user projects data


def userdata_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/<owner>/userdata/<filename>
    return '{0}/userdata/{1}'.format(instance.owner, os.path.basename(filename))


class PointFeature(models.Model):
    """ abstract model for a point location feature
    """
    location = models.PointField(dim=2)
    lat = models.FloatField(verbose_name="Latitude (WGS84)")
    lon = models.FloatField(verbose_name="Longitude (WGS84)")
    altitude = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    modifieddate = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey('users.user', to_field='id', on_delete=models.CASCADE)

    class Meta:
        abstract = True

    def __str__(self):
        return '{0} {1}'.format(self.owner, self.timestamp)


class Note(PointFeature):
    """ a Note, which is the main form item
    """
    description = models.TextField(null=True, blank=True, verbose_name="Note type")
    text = models.TextField(null=True, blank=True, verbose_name="Text note")
    form = JSONField(null=True, blank=True, verbose_name="Form element")

    def form_selection(self):
        try:
            fd = json.loads(self.form)
        except json.JSONDecodeError:
            return ''
        fs = ''
        for f in fd['forms']:
            for fi in f['formitems']:
                if fi['value']:
                    fs = fs + '<p class="card-title">' + fi['key'] + " : "
                    fs = fs + fi['value'] + "</p>"
        return fs

    def url(self):
        return reverse('note-detail', args=[self.pk])

    class Meta:
        ordering = ['-timestamp']
        unique_together = (("timestamp", "owner"),)


class ImageNote(PointFeature):
    """ an image, sketch or map note
    """
    image = models.ImageField(upload_to=userdata_directory_path)
    thumbnail = models.ImageField(upload_to=userdata_directory_path)
    azimuth = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    note = models.ForeignKey(Note, related_name='images', on_delete=models.CASCADE)

    # @property
    def thumbnail_tag(self):
        return mark_safe('<img src="%s" width="256" />' % self.thumbnail.url)

    thumbnail_tag.short_description = 'Thumbnail'

    def url(self):
        return reverse('imagenote-detail', args=[self.pk])

    class Meta:
        ordering = ['-timestamp']
        unique_together = (("timestamp", "owner"),)


@receiver(post_delete, sender=ImageNote)
def imagenote_post_delete(sender, instance, **kwargs):
    """
    Deletes files from filesystem
    when corresponding `ImageNote` object is deleted.
    TODO:  test that this works when files are stored on remote server (S3)
    """
    instance.image.delete(False)
    instance.thumbnail.delete(False)


class TrackFeature(models.Model):
    """ a GPS track with optional text
    linestring is stored as lat,lon - ht is ignored because the geodjango admin widgets don't support it
    """
    linestring = models.LineStringField(dim=2)
    timestamp_start = models.DateTimeField(null=True, blank=True, verbose_name="Timestamp at start")
    timestamp_end = models.DateTimeField(null=True, blank=True, verbose_name="Timestamp at end")
    modifieddate = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey('users.user', to_field='id', on_delete=models.CASCADE)
    text = models.TextField(null=True, blank=True, verbose_name="Text note")
    lengthm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True,
                                  verbose_name="Track length in metres")

    def __str__(self):
        return '{0} {1}'.format(self.owner, self.timestamp_start)

    def url(self):
        return reverse('track-detail', args=[self.pk])

    class Meta:
        ordering = ['-timestamp_start']
        unique_together = (("timestamp_start", "owner"),)


# Additional classes for custom leaflet maps

class TileLayer(models.Model):
    description = models.CharField(max_length=50)
    url_template = models.CharField(
        max_length=200,
        help_text="URL template using OSM tile format"
    )
    minZoom = models.IntegerField(default=0)
    maxZoom = models.IntegerField(default=18)
    attribution = models.CharField(max_length=300)
    rank = models.SmallIntegerField(
        blank=True,
        null=True,
        help_text='Order of the tilelayers in the edit box'
    )
    # See https://wiki.openstreetmap.org/wiki/TMS#The_Y_coordinate
    tms = models.BooleanField(default=False)

    def js_create(self):
        js = "L.tileLayer('{0}', {{attribution: '{1}', maxZoom: {2}, minZoom: {3}}});".format(self.url_template,
                                                                                            self.attribution,
                                                                                            self.maxZoom,
                                                                                            self.minZoom)
        return mark_safe(js)

    js_create.short_description = 'Tilelayer script'

    def __str__(self):
        return self.description


class UserMap(models.Model):
    ANONYMOUS = 1
    EDITORS = 2
    OWNER = 3
    PUBLIC = 1
    OPEN = 2
    PRIVATE = 3
    EDIT_STATUS = (
        (ANONYMOUS, 'Everyone can edit'),
        (EDITORS, 'Only editors can edit'),
        (OWNER, 'Only owner can edit'),
    )
    SHARE_STATUS = (
        (PUBLIC, 'everyone (public)'),
        (OPEN, 'anyone with link'),
        (PRIVATE, 'editors only'),
    )
    slug = models.SlugField(db_index=True)
    description = models.TextField(blank=True, null=True, verbose_name="description")
    center = models.PointField(verbose_name="center")
    zoom = models.IntegerField(default=7, verbose_name="zoom")
    modifieddate = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey('users.user', to_field='id', on_delete=models.CASCADE)
    edit_status = models.SmallIntegerField(choices=EDIT_STATUS, default=OWNER, verbose_name="edit status")
    share_status = models.SmallIntegerField(choices=SHARE_STATUS, default=PUBLIC, verbose_name="share status")
    tracks = models.ManyToManyField(TrackFeature, blank=True)
    notes = models.ManyToManyField(Note, blank=True)
    images = models.ManyToManyField(ImageNote, blank=True)
    tilelayer = models.ManyToManyField(TileLayer)

    def track_json(self):
        return reverse('track-json-usermap',  kwargs={'pk': self.pk})

    def image_json(self):
        return reverse('image-json-usermap',  kwargs={'pk': self.pk})

    def __str__(self):
        return self.description
