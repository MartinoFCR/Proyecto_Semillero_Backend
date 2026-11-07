import json
import logging
import os
import sys
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Inicia el consumidor MQTT para escuchar telemetría de dispositivos ESP32 "
        "en el tópico 'buses/+/telemetry' e ingresarla automáticamente a la base de datos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            type=str,
            default=os.environ.get("MQTT_BROKER_HOST", "localhost"),
            help="Host del broker MQTT (por defecto: env MQTT_BROKER_HOST o localhost).",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.environ.get("MQTT_BROKER_PORT", 1883)),
            help="Puerto del broker MQTT (por defecto: 1883).",
        )
        parser.add_argument(
            "--topic",
            type=str,
            default="buses/+/telemetry",
            help="Tópico MQTT a suscribir (por defecto: buses/+/telemetry).",
        )

    def handle(self, *args, **options):
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.stdout.write(self.style.ERROR(
                "La librería 'paho-mqtt' no está instalada. Ejecuta 'pip install paho-mqtt' "
                "para usar el listener nativo de MQTT."
            ))
            return

        from DjangoProject1.apps.trips.telemetry_services import ingest_device_telemetry

        host = options["host"]
        port = options["port"]
        topic = options["topic"]

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.stdout.write(self.style.SUCCESS(f"Conectado exitosamente al broker MQTT {host}:{port}."))
                client.subscribe(topic)
                self.stdout.write(self.style.NOTICE(f"Suscrito al tópico '{topic}'."))
            else:
                self.stdout.write(self.style.ERROR(f"Fallo al conectar al broker MQTT. Código de retorno: {rc}"))

        def on_message(client, userdata, msg):
            try:
                payload_str = msg.payload.decode("utf-8")
                payload = json.loads(payload_str)
                result = ingest_device_telemetry(payload)
                self.stdout.write(
                    f"Telemetría procesada para {result.get('device_id')} "
                    f"(Bus: {result.get('bus_plate')}, Viaje: {result.get('active_trip_id')})"
                )
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Error procesando mensaje en {msg.topic}: {exc}"))

        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message

        username = os.environ.get("MQTT_USERNAME")
        password = os.environ.get("MQTT_PASSWORD")
        if username and password:
            client.username_pw_set(username, password)

        self.stdout.write(self.style.NOTICE(f"Iniciando conexión MQTT a {host}:{port}..."))
        try:
            client.connect(host, port, 60)
            client.loop_forever()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nListener MQTT detenido por el usuario."))
            client.disconnect()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error de conexión MQTT: {exc}"))
