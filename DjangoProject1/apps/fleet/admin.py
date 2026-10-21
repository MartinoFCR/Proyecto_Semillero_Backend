from django.contrib import admin

from .models import Bus, Driver, Seat


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ("id", "plate", "capacity", "state")
    search_fields = ("plate",)
    list_filter = ("state",)


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "license_number")
    search_fields = ("full_name", "license_number")


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("id", "bus", "seat_number")
    list_filter = ("bus",)
