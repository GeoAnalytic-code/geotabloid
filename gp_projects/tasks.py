import datetime
from .models import Note, ImageNote, TrackFeature
from geotabloid.taskapp.celery import app
# from celery import shared_task


@app.task
def CleanUpOldData(interval):
    """ this task should be run on a schedule (daily?)
    :param interval: number of days the data will be retained
    :rtype: None
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=interval)

    print("Clean up gp_projects. pruning data older than {0}".format(cutoff))
    cutnotes = Note.objects.filter(modifieddate__lt=cutoff)
    cutimagenotes = ImageNote.objects.filter(modifieddate__lt=cutoff)
    cuttracks = TrackFeature.objects.filter(modifieddate__lt=cutoff)

    print("Deleting {0} Notes, {1} Images and {2} Tracks".format(cutnotes.count(), cutimagenotes.count(), cuttracks.count()))
    cutnotes.delete()  # deleting the notes should automatically delete the imagenotes
    cuttracks.delete()

# @app.on_after_configure.connect
# def setup_periodic_tasks(sender, **kwargs):
#     sender.add_periodic_task(60.0, CleanUpOldData.s(0))
