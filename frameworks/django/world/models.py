from django.db import models


class World(models.Model):
    """The benchmark's existing `world` table (not managed by migrations)."""

    id = models.IntegerField(primary_key=True)
    randomnumber = models.IntegerField()

    class Meta:
        db_table = 'world'
        managed = False
