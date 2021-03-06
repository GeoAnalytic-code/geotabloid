# Create your tasks here
from __future__ import absolute_import, unicode_literals
import os
from datetime import datetime, timezone, timedelta
# from celery import shared_task
from geotabloid.taskapp.celery import app
import sqlite3
import tempfile
from PIL import Image, ExifTags
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from gp_projects.models import ImageNote, Note, TrackFeature
from django.contrib.gis.geos import Point, LineString
from django.core.files import File
from django.core.files.storage import default_storage


@app.task
def LoadUserProject(userproject_file, ownerid):
    """ given an uploaded Geopaparazzi UserProject
    extract the useful bits and load them to the database
    :param userproject_file: name of the sqlite3 file to be read
    :param ownerid: id of the file owner
    :type arg1: string
    :type arg2: int
    :rtype: None

    Since the userproject file and the images extracted from it may be managed by the Django-storages module (Boto)
    we have to take care to make local copies of all files accessed.

    Also, since this task is intended for asynchronous execution via Celery, the calling parameters cannot be
    model instances (they are not JSON serializable!), so any model references have to be passed using primary keys
    """
    # before we can open the database file, it must be copied locally!
    document = default_storage.open(userproject_file, 'rb')
    userproject = tempfile.NamedTemporaryFile(delete=False)
    # this might be a memory problem!
    data = document.read()
    userproject.write(data)
    userproject.close()

    # get the owner from the ownerid
    User = get_user_model()
    owner = User.objects.get(id=ownerid)

    # connect to the database
    conn = sqlite3.connect(userproject.name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # import gpstracks if any
    for gpslog in c.execute('SELECT * FROM gpslogs;'):
        log_dict = dict(gpslog)
        rcd = TrackFeature(owner=owner, text=log_dict['text'])
        rcd.timestamp_start = datetime.utcfromtimestamp(log_dict['startts']/1000).replace(tzinfo=timezone.utc)
        rcd.timestamp_end = datetime.utcfromtimestamp(log_dict['endts']/1000).replace(tzinfo=timezone.utc)
        rcd.lengthm = log_dict['lengthm']
        d = conn.cursor()
        plist = []
        for pt in d.execute('SELECT * FROM gpslogsdata WHERE logid=? ORDER BY ts ASC', (log_dict['_id'],)):
            pt_dict = dict(pt)
            plist.append(Point(pt_dict['lon'], pt_dict['lat']))
        rcd.linestring = LineString(plist)
        try:
            with transaction.atomic():
                rcd.save()
        except IntegrityError:  # if the track is already in the database, catch the error and continue
            pass
        d.close()

    # import notes and images together in order to preserve relationships
    for nt in c.execute('SELECT * FROM notes;'):
        nt_dict = dict(nt)
        rcd = Note(owner=owner, text= nt_dict['text'], form = nt_dict['form'])
        ts = datetime.utcfromtimestamp(nt_dict['ts']/1000).replace(tzinfo=timezone.utc)
        print("processing note at {0}".format(ts))
        rcd.timestamp = ts
        rcd.description = nt_dict['description']
        rcd.lat = nt_dict['lat']
        rcd.lon = nt_dict['lon']
        rcd.location = Point(rcd.lon, rcd.lat)
        rcd.altitude = nt_dict['altim']
        try:
            with transaction.atomic():
                rcd.save()  # save the Note here so that we can refer to it when creating ImageNote records
        except IntegrityError:  # if the Note is already in the database, catch the error and continue
            print("Error saving note - already exists")
            continue

        d = conn.cursor()
        # Import all Images linked to the current Note
        # Design Note:  presumes ImageNote records are _always_ referenced by a Note
        #               unreferenced records will not be imported
        for im in d.execute('SELECT * FROM images WHERE note_id=?;', (nt_dict['_id'],)):
            im_dict = dict(im)
            imgrcd = ImageNote(owner=owner, note=rcd, azimuth=im_dict['azim'])
            # Note that ImageNote records have time and location distinct from the Note
            imgrcd.timestamp = datetime.utcfromtimestamp(im_dict['ts']/1000).replace(tzinfo=timezone.utc)
            imgrcd.lat = im_dict['lat']
            imgrcd.lon = im_dict['lon']
            imgrcd.location = Point(imgrcd.lon, imgrcd.lat)
            imgrcd.altitude = im_dict['altim']
            e = conn.cursor()
            e.execute('SELECT * FROM imagedata WHERE _id=?;', (im_dict['_id'],))
            img = e.fetchone()
            img_dict = dict(img)
            # save the full image locally - this should probably be put in a temp directory
            blob = img_dict['data']
            local_filename = im_dict['text']
            with open(local_filename, 'wb') as output_file:
                output_file.write(blob)  # deleting the notes should automatically delete the imagenotes

            # Rotate the image if an orientation tag is available
            try:
                print("opening image file {0}".format(local_filename))
                image = Image.open(local_filename)
                # this is a dumb way to find an integer from a dict but it works...
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break
                exif = dict(image._getexif().items())

                if exif[orientation] == 3:
                    image = image.rotate(180, expand=True)
                elif exif[orientation] == 6:
                    image = image.rotate(270, expand=True)
                elif exif[orientation] == 8:
                    image = image.rotate(90, expand=True)
                image.save(local_filename)
                image.close()

            except (AttributeError, KeyError, IndexError):
                # cases: image don't have getexif
                pass

            # create a web suitable resized image here
            # TODO:  put the size and save options in the settings file
            webimg_filename = 'web_{0}'.format(local_filename)
            image = Image.open(local_filename)
            websize = 480, 480
            image.thumbnail(websize)
            image.save(webimg_filename, optimize=True, quality=85)
            image.close()

            qf = open(local_filename, 'rb')
            imgrcd.image = File(qf)
            # the thumbnail - also should be placed in a temp directory
            blob = img_dict['thumbnail']
            thmname = 'thm_{0}'.format(local_filename)
            with open(thmname, 'wb') as output_file:
                output_file.write(blob)
            qt = open(thmname, 'rb')
            qw = open(webimg_filename, 'rb')
            imgrcd.thumbnail = File(qt)
            imgrcd.webimg = File(qw)
            # save the newly created image record
            try:
                with transaction.atomic():
                    imgrcd.save()
            except IntegrityError:  # if the image is already in the database, catch the error and continue
                pass
            # clean up temporary image files
            qf.close()
            try:
                os.remove(local_filename)
            except OSError as err:
                pass

            qt.close()
            try:
                os.remove(thmname)
            except OSError as err:
                pass

            qw.close()
            try:
                os.remove(webimg_filename)
            except OSError as err:
                pass

    # clean up the temporary sqlite3 file
    userproject.close()
    try:
        os.remove(userproject.name)
    except OSError as err:
        pass


@app.task
def CleanUpOldProjects(interval):
    """ this task should be run on a schedule (daily?)
    :param interval: number of days the data will be retained
    :rtype: None
    """
    from profiles.models import UserProject # import here to avoid circular dependency
    cutoff = datetime.now(timezone.utc) - timedelta(days=interval)

    print("Clean up projects. pruning data older than {0}".format(cutoff))
    cut_user_projects = UserProject.objects.filter(modifieddate__lt=cutoff)

    print("Deleting {0} user projects".format(cut_user_projects.count()))
    cut_user_projects.delete()

