from django.db import models
from DjangoProject1.apps.geography.models import Place

# Create your models here.
class Route(models.Model):
    origin = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name='routes_from'
    )
    destination = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name='routes_to'
    )
    distance_km = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )

    class Meta:
        verbose_name_plural = 'Rutas'
        verbose_name = 'Ruta'