from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from ..models import Note, ImageNote, TrackFeature
from ..serializers import NGImageNoteSerializer, NGNoteSerializer, \
    NGTrackFeatureSerializer, NGTrackFeatureSerializer, NoteSerializer
from django.core.exceptions import ObjectDoesNotExist
import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from geotabloid.users.tests.factories import UserFactory


# Some tests of the various REST endpoints for the geopaparazzi user project services


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ImageNoteAPITestCase(APITestCase):
    def setUp(self):
        self.user1 = UserFactory.build()
        self.user1.save()
        self.client.login(username=self.user1.username, password=self.user1.password)
        self.tempfile = tempfile.NamedTemporaryFile()
        self.document = SimpleUploadedFile(self.tempfile.name, b'some example data for our file')
        self.imagenote = ImageNote.objects.create(lat=52, lon=-113 )
