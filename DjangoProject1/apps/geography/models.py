from django.db import models

# Create your models here.
class Department(models.Model):
    department_name = models.CharField(max_length=100, null=False)

    class Meta:
        verbose_name_plural = 'Departamentos'
        verbose_name = 'Departamento'

class City(models.Model):
    city_name = models.CharField(max_length=100, null=False)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='cities'
    )

    class Meta:
        verbose_name_plural = 'Ciudades'
        verbose_name = 'Ciudad'

class Place(models.Model):
    place_name = models.CharField(max_length=50, null=False)
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name='places'
    )
    place_point = models.PointField(srid=4326)

    class Meta:
        verbose_name_plural = 'Ubicaciones'
        verbose_name = 'Ubicación'

