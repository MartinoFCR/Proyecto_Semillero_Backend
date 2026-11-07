from django.contrib import admin

from .models import Bus, BusType, Driver, GPSDevice, Seat


@admin.register(BusType)
class BusTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "max_capacity")
    search_fields = ("name", "code")


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ("id", "plate", "bus_type", "capacity", "state")
    search_fields = ("plate",)
    list_filter = ("state",)


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "license_number")
    search_fields = ("full_name", "license_number")


@admin.register(GPSDevice)
class GPSDeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "device_id", "bus", "state", "last_ping_at")
    search_fields = ("name", "device_id")
    list_filter = ("state",)


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("id", "bus", "seat_number")
    list_filter = ("bus",)
