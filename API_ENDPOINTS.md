# Endpoints disponibles

Guía de integración para el frontend del backend de transporte.

## 1. Información general

La URL base depende del entorno. En producción puede ser:

```text
https://portalbic.site
```

Todos los endpoints que empiezan por `/api/` se agregan a esa URL.

Para endpoints protegidos se debe enviar:

```http
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json
```

Las respuestas usan JSON. Los identificadores (`id`) son enteros. Las
respuestas de listados de Django REST Framework pueden tener paginación si se
configura globalmente en el entorno.

## 2. Autenticación

### Obtener tokens

```http
POST /api/token/
```

No requiere autenticación.

Solicitud:

```json
{
  "username": "usuario",
  "password": "contraseña"
}
```

Respuesta:

```json
{
  "access": "ACCESS_TOKEN",
  "refresh": "REFRESH_TOKEN"
}
```

El token de acceso dura 30 minutos y el de renovación 7 días.

### Renovar el token

```http
POST /api/token/refresh/
```

Solicitud:

```json
{
  "refresh": "REFRESH_TOKEN"
}
```

Respuesta:

```json
{
  "access": "NUEVO_ACCESS_TOKEN"
}
```

## 3. Convenciones de endpoints CRUD

Los siguientes recursos usan `DefaultRouter`. Para un recurso `X`, las rutas
son:

| Operación | Método | Ruta |
|---|---|---|
| Listar | `GET` | `/recurso/` |
| Crear | `POST` | `/recurso/` |
| Consultar uno | `GET` | `/recurso/{id}/` |
| Reemplazar | `PUT` | `/recurso/{id}/` |
| Actualizar parcialmente | `PATCH` | `/recurso/{id}/` |
| Eliminar | `DELETE` | `/recurso/{id}/` |

Todos los recursos de esta sección requieren autenticación. En general, los
usuarios autenticados pueden consultar y solo un administrador puede crear,
editar o eliminar. Las excepciones se indican en cada sección.

## 4. Usuarios

### Registro público

```http
POST /api/accounts/register/
```

No requiere token. Recibe:

```json
{
  "identification_document_code": "13",
  "identification_number": "1000000000",
  "name": "Juan Perez",
  "email": "juan@example.com",
  "telephone": "3001234567",
  "password": "ClaveSegura123"
}
```

El backend valida duplicados, guarda la contraseña cifrada y fija el rol
`client`.

### Login

```http
POST /api/token/
```

El campo `username` acepta el correo o el número de documento:

```json
{
  "username": "juan@example.com",
  "password": "ClaveSegura123"
}
```

Las cuentas creadas por un administrativo inicialmente usan la cédula como
contraseña. El cliente debe cambiarla posteriormente desde un flujo de cambio
de contraseña, todavía pendiente de agregar.

### Perfil propio

```http
GET /api/accounts/me/
PATCH /api/accounts/me/
```

Requiere autenticación. El cliente solo puede consultar y editar su propio
nombre, correo y celular. El tipo, número de documento y `role` se devuelven
en la respuesta, pero son de solo lectura.

### Listar usuarios

```http
GET /api/accounts/users/
```

Solo administradores.

### Consultar un usuario

```http
GET /api/accounts/users/{id}/
```

Solo administradores.

### Crear un usuario

```http
POST /api/accounts/users/
```

Solo administradores. Campos actuales:

```json
{
  "username": "1000000000",
  "email": "cliente@example.com",
  "telephone": "3001234567",
  "identification_number": "1000000000",
  "first_name": "Juan",
  "last_name": "Perez",
  "password": "ContraseñaTemporal123!"
}
```

`role` es de solo lectura en el serializer y el registro creado queda como
cliente. No se debe exponer la contraseña en respuestas.

### Editar o eliminar usuarios

```http
PUT /api/accounts/users/{id}/
PATCH /api/accounts/users/{id}/
DELETE /api/accounts/users/{id}/
```

Solo administradores. La venta administrativa también busca o crea el cliente automáticamente,
pero para administrar clientes desde una pantalla separada están disponibles
estas rutas:

```http
GET /api/accounts/customers/search/?identification_number=1000000000
GET /api/accounts/customers/
POST /api/accounts/customers/
GET /api/accounts/customers/{id}/
PATCH /api/accounts/customers/{id}/
```

Solo administradores pueden utilizarlas. El payload para crear un cliente es:

```json
{
  "identification_number": "1000000000",
  "name": "Juan Perez",
  "email": "juan@example.com",
  "telephone": "3001234567",
  "identification_document_code": "13"
}
```

La búsqueda devuelve `404` si no existe un cliente con ese documento. Los
clientes creados por esta ruta no tienen una contraseña utilizable; el
frontend no debe enviar ni mostrar contraseñas. Los tipos de documento
disponibles son `13` (CC), `22` (CE), `41` (pasaporte) y `12` (TI).

## 5. Flota

Todos estos endpoints permiten lectura a usuarios autenticados y escritura
únicamente a administradores.

### Buses

```text
GET    /api/fleet/buses/
POST   /api/fleet/buses/
GET    /api/fleet/buses/{id}/
PUT    /api/fleet/buses/{id}/
PATCH  /api/fleet/buses/{id}/
DELETE /api/fleet/buses/{id}/
```

Crear un bus:

```json
{
  "plate": "ABC123",
  "capacity": 40,
  "model": "2024",
  "state": "Active"
}
```

Estados de bus: `Active`, `Inactive`, `Maintenance`.

### Conductores

```text
GET    /api/fleet/drivers/
POST   /api/fleet/drivers/
GET    /api/fleet/drivers/{id}/
PUT    /api/fleet/drivers/{id}/
PATCH  /api/fleet/drivers/{id}/
DELETE /api/fleet/drivers/{id}/
```

Crear un conductor:

```json
{
  "full_name": "Carlos Conductor",
  "user": 8,
  "license_number": "LIC123456",
  "address": "Calle 1 # 2-3",
  "phone_number": "3001234567"
}
```

El `user` debe referenciar un usuario cuyo rol sea `driver`.

### Sillas

```text
GET    /api/fleet/seats/
POST   /api/fleet/seats/
GET    /api/fleet/seats/{id}/
PUT    /api/fleet/seats/{id}/
PATCH  /api/fleet/seats/{id}/
DELETE /api/fleet/seats/{id}/
```

Crear una silla:

```json
{
  "bus": 1,
  "seat_number": "5",
  "row": "2",
  "col": "1"
}
```

El número de silla debe ser único dentro de cada bus.

## 6. Geografía

Todos los recursos geográficos permiten lectura a usuarios autenticados y
escritura únicamente a administradores.

### Departamentos

```text
GET    /api/geography/departments/
POST   /api/geography/departments/
GET    /api/geography/departments/{id}/
PUT    /api/geography/departments/{id}/
PATCH  /api/geography/departments/{id}/
DELETE /api/geography/departments/{id}/
```

Solicitud de ejemplo:

```json
{
  "department_name": "Santander"
}
```

### Ciudades

```text
GET    /api/geography/cities/
POST   /api/geography/cities/
GET    /api/geography/cities/{id}/
PUT    /api/geography/cities/{id}/
PATCH  /api/geography/cities/{id}/
DELETE /api/geography/cities/{id}/
```

Solicitud de ejemplo:

```json
{
  "city_name": "Bucaramanga",
  "department": 1
}
```

### Lugares

```text
GET    /api/geography/places/
POST   /api/geography/places/
GET    /api/geography/places/{id}/
PUT    /api/geography/places/{id}/
PATCH  /api/geography/places/{id}/
DELETE /api/geography/places/{id}/
```

Solicitud de ejemplo:

```json
{
  "place_name": "Terminal de Bucaramanga",
  "city": 1,
  "place_point": {
    "type": "Point",
    "coordinates": [-73.1198, 7.1193]
  }
}
```

Las coordenadas usan GeoJSON: `[longitud, latitud]`.

## 7. Rutas

Una ruta relaciona un lugar de origen, un lugar de destino y una distancia.
Todos los métodos de lectura requieren autenticación; la escritura es solo
para administradores.

```text
GET    /api/routes/routes/
POST   /api/routes/routes/
GET    /api/routes/routes/{id}/
PUT    /api/routes/routes/{id}/
PATCH  /api/routes/routes/{id}/
DELETE /api/routes/routes/{id}/
```

Crear una ruta:

```json
{
  "origin": 10,
  "destination": 25,
  "distance_km": "96.50"
}
```

## 8. Viajes y tarifas

### Viajes

Los administradores pueden crear y modificar viajes. Los usuarios
autenticados pueden consultarlos; un conductor solo puede consultar los
viajes que tiene asignados.

```text
GET    /api/trips/trips/
POST   /api/trips/trips/
GET    /api/trips/trips/{id}/
PUT    /api/trips/trips/{id}/
PATCH  /api/trips/trips/{id}/
DELETE /api/trips/trips/{id}/
```

Crear un viaje:

```json
{
  "bus": 1,
  "driver": 2,
  "route": 3,
  "date_time_start": "2026-10-25T08:00:00-05:00",
  "date_time_end": null,
  "fuel_start": null,
  "fuel_end": null,
  "odometer_start": null,
  "odometer_end": null,
  "passengers_start": 0,
  "trip_state": "scheduled"
}
```

Estados: `scheduled`, `in_progress`, `completed` y `cancelled`.

### Tarifas

La tarifa pertenece a un viaje y se expresa en centavos de COP. Todos los
usuarios autenticados pueden consultar tarifas; solo los administradores
pueden crearlas, editarlas o eliminarlas.

```text
GET    /api/trips/fares/
POST   /api/trips/fares/
GET    /api/trips/fares/{id}/
PUT    /api/trips/fares/{id}/
PATCH  /api/trips/fares/{id}/
DELETE /api/trips/fares/{id}/
```

Crear una tarifa:

```json
{
  "trip": 15,
  "amount_cents": 2500000
}
```

`2500000` equivale a `$25.000 COP`. La tarifa debe ser mayor que cero y cada
viaje puede tener una sola tarifa.

Actualmente el viaje y su tarifa se guardan mediante dos solicitudes: primero
`POST /api/trips/trips/` y después `POST /api/trips/fares/` usando el ID
devuelto.

### Lecturas del viaje

Los administradores pueden gestionar todas las lecturas. El conductor
asignado puede crear y consultar lecturas de sus viajes.

```text
GET    /api/trips/readings/
POST   /api/trips/readings/
GET    /api/trips/readings/{id}/
PUT    /api/trips/readings/{id}/
PATCH  /api/trips/readings/{id}/
DELETE /api/trips/readings/{id}/
```

Solicitud:

```json
{
  "trip": 15,
  "time_stamp": "2026-10-25T09:00:00-05:00",
  "speed": "45.00",
  "fuel_level": "80.00",
  "reading_point": {
    "type": "Point",
    "coordinates": [-73.1198, 7.1193]
  }
}
```

### Eventos del viaje

Los permisos son iguales a los de las lecturas.

```text
GET    /api/trips/events/
POST   /api/trips/events/
GET    /api/trips/events/{id}/
PUT    /api/trips/events/{id}/
PATCH  /api/trips/events/{id}/
DELETE /api/trips/events/{id}/
```

Solicitud:

```json
{
  "trip": 15,
  "event_time_stamp": "2026-10-25T09:15:00-05:00",
  "event_point": {
    "type": "Point",
    "coordinates": [-73.1198, 7.1193]
  },
  "event_type": "stop",
  "description": "Parada autorizada"
}
```

Tipos: `stop`, `accident`, `speeding`, `route_deviation` y `emergency`.

### Estado actual de sillas

Es un recurso de solo lectura. El administrador ve todos los estados y el
conductor asignado ve los estados de sus viajes.

```text
GET /api/trips/current-seat-states/
GET /api/trips/current-seat-states/{id}/
```

### Historial de estados de sillas

También es de solo lectura y usa los mismos permisos del estado actual.

```text
GET /api/trips/seat-state-history/
GET /api/trips/seat-state-history/{id}/
```

## 9. Ventas y tiquetes

### Consultar ventas

```http
GET /api/sales/sales/
GET /api/sales/sales/{id}/
```

Un administrador puede consultar todas las ventas. Un cliente solo puede
consultar sus propias ventas.

La respuesta incluye, cuando existen, `tickets`, `payment` y
`factus_invoice`. El precio histórico de la venta está en `amount_cents`.

### Consultar tiquetes

```http
GET /api/sales/tickets/
GET /api/sales/tickets/{id}/
```

Un administrador puede consultar todos los tiquetes. Un cliente solo puede
consultar los tiquetes de sus propias ventas. Los tiquetes son de solo lectura.

### Venta administrativa

Solo administradores:

```http
POST /api/sales/admin-sales/
```

Solicitud:

```json
{
  "identification_number": "1000000000",
  "name": "Juan Perez",
  "email": "juan@example.com",
  "telephone": "3001234567",
  "trip": 15,
  "seat": 5,
  "payment_method": "cash"
}
```

`payment_method` puede ser `cash`, `transfer` o `card`.

El backend obtiene la tarifa desde el viaje, crea la venta como `paid` y
genera el tiquete. No se debe enviar `amount_cents`: el frontend no puede
definir el precio. Si la silla tiene una reserva online vigente, responde
`409 Conflict`. Las reservas online vencen después de 5 minutos.

Si el documento no existe, el endpoint crea un usuario cliente. Actualmente
no hay un endpoint independiente para buscar o crear clientes con un payload
reducido.

## 10. Compra online con Wompi

### Crear checkout

```http
POST /api/sales/wompi/checkout/
```

Solicitud:

```json
{
  "trip": 15,
  "seat": 5,
  "redirect_url": "https://frontend.example.com/resultado"
}
```

`redirect_url` es opcional. El usuario debe estar autenticado.

El backend valida la silla, obtiene el precio de `TripFare`, crea una venta
`pending`, reserva la silla durante 5 minutos y devuelve datos para el Widget
de Wompi:

```json
{
  "sale_id": 20,
  "reference": "SALE-20-...",
  "public_key": "pub_test_...",
  "currency": "COP",
  "amount_in_cents": 2500000,
  "signature_integrity": "..."
}
```

El frontend debe usar esos valores con el Widget. Nunca debe enviar un precio
propio ni enviar datos de tarjeta al backend.

### Confirmar el estado de una transacción

```http
POST /api/sales/wompi/status/
```

Solicitud:

```json
{
  "sale_id": 20,
  "transaction_id": "ID_DEVUELTO_POR_WOMPI"
}
```

El backend consulta Wompi con la clave privada y verifica referencia, monto,
moneda y estado. Solo `APPROVED` marca la venta como pagada y genera el
tiquete. `DECLINED` y `ERROR` marcan la venta como fallida.

### Webhook de Wompi

```http
POST /api/sales/wompi/webhook/
```

Lo llama Wompi, no el frontend. Debe configurarse en el panel de Wompi y
enviarse con el formato de evento del proveedor. El backend valida la firma y
procesa eventos `transaction.updated`. No se debe simular este endpoint desde
el frontend sin la firma válida.

## 11. Factus

### Reintentar una factura

Solo administradores:

```http
POST /api/sales/factus/invoices/{sale_id}/retry/
```

No requiere cuerpo. Ejemplo:

```http
POST /api/sales/factus/invoices/20/retry/
```

Se utiliza cuando la venta quedó pagada pero la factura no pudo emitirse.
Factus se configura exclusivamente mediante variables de entorno; las
credenciales nunca deben enviarse desde el frontend.

Las ventas pagadas intentan generar la factura automáticamente. El resultado
se consulta dentro de `factus_invoice` en la respuesta de la venta.

## 12. Documentación técnica

### Esquema OpenAPI

```http
GET /api/schema/
```

### Swagger UI

```text
/api/schema/swagger-ui/
```

### ReDoc

```text
/api/schema/redoc/
```

Estas rutas sirven para explorar el esquema generado por Django REST
Framework y `drf-spectacular`.

## 13. Resumen de permisos

| Recurso | Lectura | Escritura |
|---|---|---|
| Usuarios | Administrador | Administrador |
| Buses, conductores, sillas | Usuario autenticado | Administrador |
| Departamentos, ciudades, lugares | Usuario autenticado | Administrador |
| Rutas | Usuario autenticado | Administrador |
| Viajes | Usuario autenticado; conductor solo los asignados | Administrador |
| Tarifas | Usuario autenticado | Administrador |
| Lecturas y eventos | Administrador o conductor asignado | Administrador o conductor asignado |
| Estados de sillas | Administrador o conductor asignado | Solo lectura |
| Ventas | Administrador o propietario | Solo lectura, excepto venta administrativa |
| Tiquetes | Administrador o propietario de la venta | Solo lectura |
| Wompi checkout/status | Usuario autenticado | Operación controlada por el backend |
| Wompi webhook | Proveedor Wompi | Operación controlada por firma |
| Reintento Factus | Administrador | Operación controlada por el backend |

## 14. Flujo recomendado para vender

### Venta administrativa

```text
1. Consultar viajes: GET /api/trips/trips/
2. Consultar tarifas: GET /api/trips/fares/
3. Mostrar las sillas del bus asociado al viaje.
4. Enviar POST /api/sales/admin-sales/.
5. Mostrar la venta, el tiquete y el estado de Factus.
```

### Venta online

```text
1. Consultar viajes y tarifas.
2. Seleccionar una silla.
3. Enviar POST /api/sales/wompi/checkout/.
4. Abrir el Widget de Wompi con la respuesta.
5. Enviar POST /api/sales/wompi/status/ con el resultado.
6. Consultar GET /api/sales/sales/{id}/ o GET /api/sales/tickets/.
```

### Compra online de varias sillas

```http
POST /api/sales/wompi/multi-checkout/
```

Solicitud:

```json
{
  "trip": 15,
  "passengers": [
    {
      "seat": 5,
      "name": "Ana Perez",
      "identification_number": "100000001",
      "email": "ana@example.com",
      "telephone": "3001234567"
    },
    {
      "seat": 6,
      "name": "Luis Perez",
      "identification_number": "100000002",
      "email": "luis@example.com",
      "telephone": "3007654321"
    }
  ],
  "redirect_url": "https://portalbic.site/clientes/comprar"
}
```

El backend calcula el total, reserva todas las sillas durante cinco minutos y
devuelve un único `purchase_id`, `reference`, `amount_in_cents`,
`signature_integrity` y `expires_at` para el Widget de Wompi. Si una silla no
está disponible, responde `409` y no deja reservas parciales.

Para confirmar el pago se utiliza `POST /api/sales/wompi/status/` enviando
`purchase_id` y el `transaction_id` de Wompi:

```json
{
  "purchase_id": 31,
  "transaction_id": "ID_DEVUELTO_POR_WOMPI"
}
```

Se genera un tiquete por pasajero; una confirmación repetida no duplica los
tiquetes. El endpoint individual continúa usando `sale_id`.

El precio siempre debe provenir del backend. El frontend solo lo muestra.
