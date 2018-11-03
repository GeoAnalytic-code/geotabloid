import os
import json
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.safestring import mark_safe
from django.db.models.signals import post_delete
from django.dispatch import receiver


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
        fd = json.loads(self.form)
        fs = ''
        for f in fd['forms']:
            for fi in f['formitems']:
                if fi['value']:
                    fs = fs + '<p class="card-title">' + fi['key'] + " : "
                    fs = fs + fi['value'] + "</p>"
        return fs

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

    def thumbnail_tag(self):
        return mark_safe('<img src="%s" width="256" />' % self.thumbnail.url)

    thumbnail_tag.short_description = 'Thumbnail'

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

    class Meta:
        ordering = ['-timestamp_start']
        unique_together = (("timestamp_start", "owner"),)
