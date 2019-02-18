from django.contrib.gis import admin
from .models import Note, ImageNote, TrackFeature #, TileLayer, UserMap

admin.site.register(Note, admin.OSMGeoAdmin)

class ImageNoteAdmin(admin.OSMGeoAdmin):
    date_hierarchy = 'timestamp'
    list_display = ('timestamp', 'owner', )
    list_filter = ('owner',)
#    search_fields = ['document', 'description']
    readonly_fields = ['modifieddate', 'thumbnail_tag', 'webimg_tag']

admin.site.register(ImageNote, ImageNoteAdmin)
admin.site.register(TrackFeature, admin.OSMGeoAdmin)
# admin.site.register(TileLayer, admin.OSMGeoAdmin)
# admin.site.register(UserMap, admin.OSMGeoAdmin)
