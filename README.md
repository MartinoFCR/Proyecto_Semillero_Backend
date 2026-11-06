# Proyecto Semillero Backend

Backend para la gestión de transporte, viajes, ventas y tiquetes. Está
construido con Django y Django REST Framework, con soporte geoespacial
mediante PostGIS.

## Funcionalidades implementadas

- Usuarios con roles de cliente, conductor y administrador.
- Autenticación mediante JWT.
- Gestión de buses, conductores y sillas.
- Gestión geográfica de departamentos, ciudades y lugares.
- Gestión de rutas.
- Gestión de viajes y su asignación a bus, conductor y ruta.
- Lecturas, eventos y estados de sillas asociados a viajes.
- Ventas administrativas y ventas online.
- Tiquetes con silla asignada y código único.
- Recuperación de contraseña y cambio obligatorio de la contraseña inicial.
- Solicitudes de soporte y contactos públicos configurables.
- Confirmaciones de compra por correo.
- Carné digital vigente mientras la cuenta del cliente permanezca activa.
- Integración preparada para Wompi Sandbox.

## Estructura principal

```text
manage.py
DjangoProject1/
├── settings.py
├── urls.py
└── apps/
    ├── accounts/    Usuarios y roles
    ├── fleet/       Buses, conductores y sillas
    ├── geography/   Departamentos, ciudades y lugares
    ├── routes/      Rutas
    ├── trips/       Viajes, lecturas y eventos
    ├── sales/       Ventas, pagos y tiquetes
    └── support/     Solicitudes de soporte
```

## Requisitos

- Python 3.12 o compatible con las dependencias del proyecto.
- Django 5.2.
- PostgreSQL con PostGIS.
- GDAL y GEOS cuando el sistema operativo los requiera.
- Las dependencias de `requirements.txt`.

Instalación local:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

En Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Variables de entorno

Crear un archivo `.env` en la misma carpeta que `manage.py`. No subirlo al
repositorio ni compartir sus valores.

```env
SECRET_KEY=clave-aleatoria-larga
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:4200

DB_NAME=nombre_de_la_base
DB_USER=usuario_de_la_base
DB_PASSWORD=contraseña_de_la_base
DB_HOST=127.0.0.1
DB_PORT=5432

# Wompi Sandbox
WOMPI_BASE_URL=https://sandbox.wompi.co/v1
WOMPI_PUBLIC_KEY=pub_test_...
WOMPI_PRIVATE_KEY=prv_test_...
WOMPI_INTEGRITY_SECRET=test_integrity_...
WOMPI_EVENTS_SECRET=test_events_...

# Cuenta, correo y soporte
FRONTEND_BASE_URL=https://portalbic.site
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=no-reply@portalbic.site
MEDIA_ROOT=/app/media
CUSTOMER_SERVICE_EMAIL=soporte@example.com
CUSTOMER_SERVICE_PHONE=...
CUSTOMER_SERVICE_WHATSAPP=...
CUSTOMER_SERVICE_HOURS=Lunes a viernes de 8:00 a 17:00
CHANGES_POLICY_URL=https://portalbic.site/politicas/cambios
REFUNDS_POLICY_URL=https://portalbic.site/politicas/reembolsos
PRIVACY_POLICY_URL=https://portalbic.site/politicas/privacidad
TERMS_URL=https://portalbic.site/terminos
TICKET_VERIFICATION_MAX_AGE_SECONDS=2592000
LOGIN_FAILURE_LIMIT=5
LOGIN_FAILURE_WINDOW_SECONDS=900
```

Las fotos se guardan dentro de `MEDIA_ROOT/profile_photos/` y `/media/` se
publica también cuando `DEBUG=False`. En Docker, `/app/media` debe montarse en
un volumen persistente o en una carpeta del host; de lo contrario, una
reconstrucción del contenedor elimina los archivos subidos aunque la base de
datos conserve el nombre de la foto. Por ejemplo, el servicio backend debe
tener un volumen equivalente a:

```yaml
volumes:
  - ./backend/media:/app/media
```

En producción `SECRET_KEY` es obligatoria; Django no inicia si falta o conserva
el valor de ejemplo. Los límites de login usan la base de datos compartida.
El caché de recuperación, activación y soporte usa `django_cache`, por lo que
debe crearse con `createcachetable` después de migrar.

En este despliegue Compose se ejecuta desde `/home/devadhan/semillero`, por
lo que el archivo `docker-compose.yml` está usando:

```yaml
services:
  backend:
    volumes:
      - ./backend/media:/app/media
```

La `SECRET_KEY` no debe conservar el valor de ejemplo
`cambia_esta_clave`. En producción se debe usar una clave aleatoria y
mantener el archivo con permisos restrictivos, por ejemplo:

```bash
chmod 600 .env
```

El archivo `.env.example` contiene nombres de variables y valores de ejemplo,
pero nunca debe contener credenciales reales.

## Migraciones y comprobaciones

Desde la carpeta que contiene `manage.py`:

```bash
python manage.py check
python manage.py migrate
```

Después de publicar cambios que agreguen modelos o campos, las migraciones
también deben ejecutarse dentro del contenedor que usa la base de datos de
producción. Por ejemplo:

```bash
docker exec semillero-backend python3 manage.py migrate
docker exec semillero-backend python3 manage.py createcachetable django_cache
docker exec semillero-backend python3 manage.py showmigrations accounts sales fleet
docker compose restart backend
```

Las migraciones nuevas de esta versión incluyen:

```text
accounts 0004_user_password_changed_at_accountactiontoken
accounts 0005_user_password_change_required
sales    0009_sale_email_confirmation_sent_at
sales    0010_adminsaleidempotency
sales    0011_ticketcheckin_ticketcheckinidempotency
support  0001_initial
```

Para esta versión deben aparecer aplicadas, como mínimo, estas migraciones:

```text
accounts 0003_user_photo_card_id
accounts 0004_user_password_changed_at_accountactiontoken
accounts 0005_user_password_change_required
sales    0005_saleitem_sale_idempotency_key
sales    0006_passenger_document_codes
sales    0007_alter_sale_status
sales    0009_sale_email_confirmation_sent_at
sales    0010_adminsaleidempotency
sales    0011_ticketcheckin_ticketcheckinidempotency
fleet    0004_bustype_bus_bus_type
support  0001_initial
```

Si `/api/token/` devuelve `500` después de desplegar esta versión, revisar
primero `showmigrations`. Un `OPTIONS /api/token/` con respuesta `200` solo
confirma que la ruta está publicada; no confirma que el esquema de la base de
datos esté actualizado. No se deben borrar usuarios ni reinicializar la base
de datos: aplicar las migraciones conserva los datos existentes.

La migración `accounts.0003_user_photo_card_id` crea un UUID distinto para
cada usuario existente antes de aplicar la restricción única de `card_id`.
Si una imagen anterior de la migración falló con `UniqueViolation` sobre
`accounts_user_card_id_key`, se debe reconstruir el contenedor con esta
versión corregida y ejecutar nuevamente `migrate`; la migración fallida se
revierte y no debe marcarse manualmente como aplicada.

La migración de viajes permite dejar como opcionales los datos operativos que
aún no están implementados:

- `fuel_start`
- `fuel_end`
- `odometer_start`
- `odometer_end`

En cambio, un viaje requiere:

- Bus.
- Conductor.
- Ruta.

## Autenticación

Obtener token:

```http
POST /api/token/
Content-Type: application/json
```

```json
{
  "username": "usuario",
  "password": "contraseña"
}
```

Usar el token en los endpoints protegidos:

```http
Authorization: Bearer <access_token>
```

El token de acceso dura 30 minutos y el de renovación 7 días, según la
configuración actual de Simple JWT.

## Endpoints principales

### Usuarios

```text
/api/accounts/users/
```

### Flota

```text
/api/fleet/buses/
/api/fleet/drivers/
/api/fleet/seats/
```

### Geografía

```text
/api/geography/departments/
/api/geography/cities/
/api/geography/places/
```

### Rutas

```text
/api/routes/routes/
```

Una ruta relaciona un origen, un destino y una distancia en kilómetros.

Para la página principal hay una consulta pública de rutas, sin token:

```text
/api/public/routes/
```

### Viajes

```text
/api/trips/trips/
/api/trips/readings/
/api/trips/events/
/api/trips/current-seat-states/
/api/trips/seat-state-history/
```

Un viaje relaciona obligatoriamente un bus, un conductor y una ruta.

Los viajes programados próximos también pueden consultarse públicamente desde:

```text
/api/public/trips/
```

### Documentación de API

```text
/api/schema/
/api/schema/swagger-ui/
/api/schema/redoc/
```

La guía detallada de todos los endpoints, payloads y permisos está en
[API_ENDPOINTS.md](./API_ENDPOINTS.md).

## Ventas y tiquetes

La aplicación de ventas está en
`DjangoProject1/apps/sales/`.

Modelos principales:

- `Sale`: venta conjunta, estado comercial, comprador y total.
- `SaleItem`: pasajero y silla incluidos en una venta.
- `Payment`: información del pago y referencia del proveedor.
- `Ticket`: tiquete emitido por silla, pasajero, viaje, estado y código único.

Una compra puede incluir hasta 10 pasajeros y sillas. Todas las sillas se
reservan de forma atómica y no se puede emitir otro tiquete activo para la
misma combinación de viaje y silla.

### Consulta de ventas y tiquetes

```text
GET /api/sales/sales/
GET /api/sales/tickets/
```

Un cliente solo puede consultar sus propias ventas y tiquetes. Un
administrador puede consultar todas las ventas y tiquetes.

Cada tiquete incluye un token y una URL de verificación firmados por el
servidor:

```text
GET /api/sales/tickets/verify/?token=VERIFICATION_TOKEN
```

La verificación es pública y devuelve `valid` junto con el estado `issued`,
`used` o `cancelled`. El token de verificación es independiente del JWT.
El frontend puede usar esa URL como contenido del QR al generar un PDF con
una boleta por página.

El endpoint de factura propia es:

```text
GET /api/sales/sales/{sale_id}/invoice/
```

### Venta administrativa

Un administrador puede registrar una venta con:

- Transferencia: `transfer`
- Efectivo: `cash`
- Tarjeta: `card`

Endpoint:

```text
POST /api/sales/admin-sales/
```

Ejemplo:

```json
{
  "identification_number": "1000000000",
  "name": "Juan Perez",
  "email": "juan@example.com",
  "telephone": "3001234567",
  "trip": 1,
  "seat": 5,
  "payment_method": "cash"
}
```

El valor no se recibe del cliente: el backend lo obtiene de la tarifa
administrada para ese viaje (`/api/trips/fares/`).

Las ventas administrativas se marcan como pagadas y generan el tiquete
inmediatamente. Si el cliente no existe, se crea como cliente y su contraseña
provisional es su número de identificación. Esta contraseña debe reemplazarse
posteriormente por un flujo seguro de cambio de contraseña.

## Wompi Sandbox

El cliente autenticado inicia una compra online con:

```text
POST /api/sales/wompi/checkout/
```

Ejemplo:

```json
{
  "trip": 1,
  "passengers": [
    {
      "seat": 5,
      "name": "Ana Perez",
      "identification_document_code": "13",
      "identification_number": "100000001",
      "email": "ana@example.com",
      "telephone": "3001234567"
    }
  ]
}
```

El backend calcula el valor usando la tarifa asociada al viaje. El cliente no
puede modificar `amount_cents`.

El backend crea una venta pendiente y devuelve:

- `sale_id`
- `reference`
- `public_key`
- `currency`
- `amount_in_cents`
- `signature_integrity`

El frontend debe usar `public_key` y `signature_integrity` con el Widget de
Wompi. Los datos de tarjeta no deben pasar por el backend ni guardarse en la
base de datos.

Las compras online aceptan hasta 10 pasajeros, reservan todas las sillas de
forma atómica durante 5 minutos y requieren el encabezado
`Idempotency-Key`. Si el pago no se confirma dentro de ese plazo, la venta
queda `expired` y las sillas vuelven a estar disponibles. Una venta
administrativa recibe `409 Conflict` mientras exista una reserva online
vigente.

## Facturación electrónica con Factus

Las ventas pagadas crean una factura Factus asociada a la venta. La factura
no bloquea la venta ni la emisión del tiquete: si faltan datos fiscales o
Factus no responde, queda en estado `error` para reintentar posteriormente.

Variables adicionales requeridas:

```env
FACTUS_BASE_URL=https://api-sandbox.factus.com.co
FACTUS_USERNAME=...
FACTUS_PASSWORD=...
FACTUS_CLIENT_ID=...
FACTUS_CLIENT_SECRET=...
FACTUS_NUMBERING_RANGE_ID=...
FACTUS_PRODUCT_CODE=...
FACTUS_PRODUCT_NAME=...
FACTUS_MUNICIPALITY_CODE=...
```

El reintento administrativo se realiza con:

```text
POST /api/sales/factus/invoices/<sale_id>/retry/
```

El CUFE, número, XML y PDF deben ser suministrados por Factus; el backend no
los inventa.

### Confirmación temporal sin webhook

Mientras no se pueda configurar el webhook en el panel de Wompi, el frontend
puede enviar el resultado del Widget al backend:

```text
POST /api/sales/wompi/status/
```

```json
{
  "sale_id": 10,
  "transaction_id": "ID_DEVUELTO_POR_WOMPI"
}
```

El backend consulta la transacción directamente con Wompi usando
`WOMPI_PRIVATE_KEY` y valida:

- Referencia.
- Valor.
- Moneda.
- Estado de la transacción.

Solo una transacción `APPROVED` marca la venta como pagada y genera el
tiquete. Los estados `DECLINED` y `ERROR` marcan la venta como fallida.

### Webhook de Wompi

Cuando se recupere el acceso al panel de Wompi, se podrá configurar:

```text
POST https://portalbic.site/api/sales/wompi/webhook/
```

El webhook es el mecanismo recomendado para producción porque evita depender
de una confirmación iniciada por el frontend.

Para pruebas Sandbox se pueden usar las tarjetas documentadas por Wompi:

```text
4242 4242 4242 4242  -> aprobada
4111 1111 1111 1111  -> declinada
```

Usar una fecha futura y un CVC de tres dígitos.

## Docker y despliegue

En el despliegue del VPS, Docker Compose carga el `.env` ubicado en la raíz
del proyecto y pasa las variables al contenedor backend. Las credenciales
Wompi deben incluirse explícitamente en el servicio `backend`:

```yaml
environment:
  WOMPI_BASE_URL: ${WOMPI_BASE_URL}
  WOMPI_PUBLIC_KEY: ${WOMPI_PUBLIC_KEY}
  WOMPI_PRIVATE_KEY: ${WOMPI_PRIVATE_KEY}
  WOMPI_INTEGRITY_SECRET: ${WOMPI_INTEGRITY_SECRET}
  WOMPI_EVENTS_SECRET: ${WOMPI_EVENTS_SECRET}
```

Reconstruir el backend:

```bash
docker compose up -d --build --force-recreate backend
```

Comprobar que las variables llegan sin mostrar sus valores:

```bash
docker exec semillero-backend python3 -c "import os; print('PUBLIC:', bool(os.getenv('WOMPI_PUBLIC_KEY'))); print('PRIVATE:', bool(os.getenv('WOMPI_PRIVATE_KEY'))); print('INTEGRITY:', bool(os.getenv('WOMPI_INTEGRITY_SECRET'))); print('EVENTS:', bool(os.getenv('WOMPI_EVENTS_SECRET')))"
```

### Publicación de fotos con Nginx

Si Nginx se ejecuta en el VPS fuera del contenedor, debe publicar la carpeta
del host que está montada en Docker. En este proyecto Compose se ejecuta desde
`/home/devadhan/semillero`, por lo que la carpeta real es
`/home/devadhan/semillero/backend/media`.

La configuración activa está en
`/etc/nginx/sites-enabled/semillero-bic-backend`. Dentro del bloque `server`
que contiene `listen 443 ssl` y `server_name portalbic.site
www.portalbic.site`, debe existir:

```nginx
location /media/ {
    alias /home/devadhan/semillero/backend/media/;

    types {
        image/webp webp;
        image/jpeg jpg jpeg;
        image/png png;
    }

    try_files $uri =404;
}
```

En el mismo bloque HTTPS se recomienda configurar estos encabezados para el
portal y la API. Ajusta la CSP si Wompi o Angular requieren orígenes externos:

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
add_header Content-Security-Policy "default-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'" always;
```

Prueba el Widget de Wompi antes de activar una CSP restrictiva, porque el pago
puede requerir dominios externos autorizados.

El `alias` debe terminar en `/` y debe apuntar a la carpeta del host, no a
`/app/media`, porque Nginx se ejecuta fuera del contenedor. No debe existir otro
bloque activo con `server_name portalbic.site`, porque Nginx puede ignorar la
configuración correcta por conflicto. Asegura permisos de lectura y recarga
Nginx:

```bash
sudo rm -f /etc/nginx/sites-enabled/portalbic
sudo chmod -R o+rX /home/devadhan/semillero/backend/media
sudo nginx -t
sudo systemctl reload nginx
curl -I https://portalbic.site/media/profile_photos/profile.webp
```

La respuesta esperada es `HTTP/1.1 200 OK` con
`Content-Type: image/webp`. Si Nginx está dentro de otro contenedor, esta
configuración cambia: ese contenedor también debe montar el mismo volumen y
usar `/app/media/` como `alias`.

## Consideraciones de seguridad para producción

La configuración de producción debe mantener:

- `SECRET_KEY` aleatoria y fuera del repositorio.
- `DEBUG=False`.
- Credenciales de proveedores fuera del código.
- Webhook validado con `WOMPI_EVENTS_SECRET`.
- Precio calculado en el backend desde una fuente confiable, no desde el
  valor recibido del cliente.
- Creación, edición y eliminación de viajes restringidas a administradores.

Estas variables y controles deben mantenerse durante el despliegue. La
confirmación temporal de Wompi no reemplaza la validación del webhook.

## Estado del proyecto

Implementado:

- Modelos, migraciones y API base de ventas y tiquetes.
- Reserva de silla por viaje.
- Ventas administrativas.
- Checkout Wompi Sandbox.
- Consulta temporal del estado de transacción.
- Compra múltiple con reserva atómica e idempotencia.
- Tiquetes con verificación pública firmada para QR.
- Consulta de factura Factus por compra.
- Recuperación y cambio seguro de contraseña.
- Cambio obligatorio de la contraseña inicial de cuentas creadas por administración.
- Solicitudes de soporte y confirmación de compra por correo.
- Configuración de variables Wompi en Docker.
- Documentación OpenAPI, Swagger y ReDoc.

Pendiente:

- Integración del Widget en el frontend.
- Configuración y prueba del webhook de Wompi.
- Correcciones de autorización detectadas en la revisión de seguridad.
- Generación visual del PDF en el frontend; el backend entrega los datos y la
  URL firmada para el QR.
