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
    └── sales/       Ventas, pagos y tiquetes
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

### Viajes

```text
/api/trips/trips/
/api/trips/readings/
/api/trips/events/
/api/trips/current-seat-states/
/api/trips/seat-state-history/
```

Un viaje relaciona obligatoriamente un bus, un conductor y una ruta.

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

- `Sale`: venta y estado comercial.
- `Payment`: información del pago y referencia del proveedor.
- `Ticket`: tiquete emitido, pasajero, viaje, silla y código único.

Cada tiquete reserva una silla para un viaje. No se puede emitir otro tiquete
activo para la misma combinación de viaje y silla.

### Consulta de ventas y tiquetes

```text
GET /api/sales/sales/
GET /api/sales/tickets/
```

Un cliente solo puede consultar sus propias ventas y tiquetes. Un
administrador puede consultar todas las ventas y tiquetes.

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
posteriormente por un flujo seguro de activación o recuperación.

## Wompi Sandbox

El cliente autenticado inicia una compra online con:

```text
POST /api/sales/wompi/checkout/
```

Ejemplo:

```json
{
  "trip": 1,
  "seat": 5
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

Las compras online reservan la silla durante 5 minutos. Si el pago no se
confirma dentro de ese plazo, la venta queda `expired` y la silla vuelve a
estar disponible. Una venta administrativa recibe `409 Conflict` mientras
exista una reserva online vigente.

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

### Webhook futuro

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

## Facturación electrónica

La facturación electrónica con Factus todavía no está implementada. Es
independiente del pago y del tiquete:

```text
Pago aprobado -> tiquete -> factura electrónica
```

La integración futura deberá usar Factus API Sandbox, OAuth2 y el endpoint de
validación de facturas. Factus genera o devuelve el CUFE después de validar la
factura; el backend no debe inventarlo ni calcularlo con un UUID.

Antes de implementarla se deben confirmar:

- Credenciales de Factus API, diferentes de las de Factus Pay.
- Datos fiscales del emisor.
- Rango y prefijo de numeración.
- Tipo de identificación y municipio del cliente.
- Tratamiento tributario e impuestos del tiquete.

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

## Seguridad pendiente

La configuración de producción debe mantener:

- `SECRET_KEY` aleatoria y fuera del repositorio.
- `DEBUG=False`.
- Credenciales de proveedores fuera del código.
- Webhook validado con `WOMPI_EVENTS_SECRET`.
- Precio calculado en el backend desde una fuente confiable, no desde el
  valor recibido del cliente.
- Creación, edición y eliminación de viajes restringidas a administradores.

El análisis de seguridad identificó estos puntos como pendientes de corrección
antes de usar pagos y ventas en producción. La confirmación temporal de Wompi
no reemplaza la validación del webhook para un despliegue definitivo.

## Estado del proyecto

Implementado:

- Modelos, migraciones y API base de ventas y tiquetes.
- Reserva de silla por viaje.
- Ventas administrativas.
- Checkout Wompi Sandbox.
- Consulta temporal del estado de transacción.
- Configuración de variables Wompi en Docker.
- Documentación OpenAPI, Swagger y ReDoc.

Pendiente:

- Integración del Widget en el frontend.
- Configuración y prueba del webhook de Wompi.
- Cálculo de precios en el backend.
- Correcciones de autorización detectadas en la revisión de seguridad.
- Facturación electrónica con Factus.
- Generación visual de PDF o QR del tiquete.
