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

Las cuentas con `password_change_required: true` solo pueden consultar su
perfil mínimo, cambiar contraseña, gestionar su foto/carné y cerrar sesión.
El resto de endpoints protegidos responde `401/403` hasta completar el cambio.

## 1.2. Cuenta, recuperación y activación

### Cerrar sesión

```http
POST /api/accounts/logout/
Authorization: Bearer ACCESS_TOKEN
```

Body:

```json
{"refresh": "REFRESH_TOKEN"}
```

Responde `204 No Content` y revoca el refresh token. Los refresh tokens se
rotan y el anterior deja de ser válido después de una renovación.

### Solicitar recuperación de contraseña

```http
POST /api/accounts/password/reset/
```

No requiere autenticación. Body:

```json
{"email": "cliente@example.com"}
```

Siempre responde `202 Accepted` con el mismo mensaje, exista o no la cuenta:

```json
{"detail": "Si existe una cuenta asociada, recibirás las instrucciones."}
```

El enlace se envía por correo y usa el formato
`FRONTEND_BASE_URL/clientes/restablecer-contrasena#token=...`. El token dura
30 minutos por defecto, es de un solo uso, se almacena como hash y nunca se
devuelve en la respuesta ni se registra.

### Confirmar recuperación

```http
POST /api/accounts/password/reset/confirm/
```

Body: `{"token": "TOKEN_TEMPORAL", "new_password": "NuevaClaveSegura123!"}`.
Responde `200 OK` al actualizar la contraseña. Un token inválido, vencido o
usado responde `400` con `code: invalid_or_expired_token`. Las sesiones
emitidas antes del cambio dejan de ser válidas.

### Activación excepcional de cuenta

```http
POST /api/accounts/activation/request/
```

Este flujo no se utiliza para las cuentas creadas normalmente por el
administrador, porque esas cuentas se entregan activas con la contraseña
inicial igual al documento. Solo aplica si soporte marca explícitamente una
cuenta como inactiva. No requiere autenticación. Body:
`{"email": "cliente@example.com"}`.
Responde `202` con el mensaje genérico
`Si corresponde habilitar esta cuenta, recibirás las instrucciones.`.

### Confirmar activación

```http
POST /api/accounts/activation/confirm/
```

Body: `{"token": "TOKEN_TEMPORAL", "new_password": "ClaveSegura123!"}`.
Responde `200 OK` y habilita la cuenta existente sin cambiar su rol, ventas,
facturas ni tiquetes.

### Cambiar contraseña autenticado

```http
POST /api/accounts/me/password/
Authorization: Bearer ACCESS_TOKEN
```

Body: `{"current_password": "ClaveActual123!", "new_password": "NuevaClaveSegura123!"}`.
Responde `200 OK` con `reauthentication_required: true`. La contraseña actual
incorrecta responde `400` con error en `current_password`.

## 1.3. Soporte

### Crear solicitud

```http
POST /api/support/requests/
Authorization: Bearer ACCESS_TOKEN
```

Body:

```json
{
  "category": "payment",
  "sale": 18,
  "subject": "Mi pago todavía aparece pendiente",
  "message": "Realicé el pago y necesito revisar su estado."
}
```

`sale` es opcional, pero si se envía debe pertenecer al cliente. Categorías:
`payment`, `invoice`, `ticket`, `change`, `cancellation`, `account`, `other`.
Responde `201` con `id`, referencia `SOL-000025`, estado `open` y fechas.
Crear otra solicitud dentro de 60 segundos responde `429`.

### Consultar solicitudes propias

```http
GET /api/support/requests/
GET /api/support/requests/{id}/
Authorization: Bearer ACCESS_TOKEN
```

El listado está paginado con la configuración estándar (`count`, `next`,
`previous`, `results`). Nunca devuelve solicitudes de otros clientes. La
solicitud de cancelación no cancela ventas ni inicia reembolsos.

## 1.4. Contactos y políticas oficiales

```http
GET /api/public/customer-service/
```

No requiere autenticación. Devuelve `email`, `phone`, `whatsapp`,
`business_hours`, `timezone`, `changes_policy_url`, `refunds_policy_url`,
`privacy_policy_url` y `terms_url`. Los valores no configurados son `null`;
se definen mediante variables de entorno del servidor.

## 1.5. Confirmación de compra por correo

Después de un pago aprobado el backend envía una confirmación, sin depender
del navegador. Incluye compra, total, ruta, salida, pasajeros, sillas y
códigos de tiquete. Un fallo de correo no cancela la venta ni los tiquetes.

Para reenviar una confirmación:

```http
POST /api/sales/sales/{sale_id}/resend-confirmation/
Authorization: Bearer ACCESS_TOKEN
```

No requiere body. Solo el comprador o un administrador puede usarlo y la
venta debe estar pagada. Responde `202 Accepted`; un fallo SMTP responde
`503` con `code: email_unavailable`.

## 1.1. Consulta pública para la página principal

Estos endpoints no requieren token y son de solo lectura. Devuelven únicamente
la información necesaria para mostrar la oferta de transporte, sin exponer
datos del conductor, del bus ni información operativa interna.

### Rutas disponibles

```http
GET /api/public/routes/
```

La respuesta usa la paginación estándar del backend:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 3,
      "origin": {
        "id": 10,
        "name": "Terminal de Bucaramanga",
        "city": {
          "id": 1,
          "name": "Bucaramanga",
          "department": {
            "id": 1,
            "name": "Santander"
          }
        }
      },
      "destination": {
        "id": 25,
        "name": "Terminal de San Gil",
        "city": {
          "id": 2,
          "name": "San Gil",
          "department": {
            "id": 1,
            "name": "Santander"
          }
        }
      },
      "distance_km": "96.50"
    }
  ]
}
```

### Viajes programados

```http
GET /api/public/trips/
```

Este endpoint devuelve únicamente viajes con estado `scheduled` cuya fecha de
inicio todavía no ha pasado. Incluye la ruta, horario y tarifa (en centavos);
no requiere autenticación y también usa paginación.

Admite los filtros opcionales `origin`, `destination` (identificadores de
terminal) y `date` (`YYYY-MM-DD`):

```http
GET /api/public/trips/?origin=10&destination=25&date=2026-11-04
```

Cada viaje incluye `id`, `route`, `date_time_start`, `date_time_end`,
`fare_amount_cents` y `currency` (`COP`).

### Disponibilidad de sillas

```http
GET /api/trips/trips/{trip_id}/seats/
GET /api/trips/trips/{trip_id}/available-seats/
```

No requiere autenticación. Devuelve `trip`, `server_time` y la lista completa de sillas correspondientes a la capacidad registrada del autobús (`bus.capacity`), sin paginación ni truncamiento.

Los asientos se ordenan de forma natural por fila (`row`), columna (`col`) y número de silla (`seat_number`), siguiendo la distribución estándar de 4 columnas (2 + pasillo + 2, donde columnas 1 y 2 van a la izquierda del pasillo y 3 y 4 a la derecha).

Cada objeto de silla incluye:
- `id`: identificador numérico de la silla.
- `seat_number`: número visible de la silla (ej. `"1"` a la capacidad del bus).
- `row`: número de fila (ej. `"1"`, `"2"`...).
- `col`: número de columna (`"1"`, `"2"`, `"3"`, `"4"`).
- `status`: estado actual de la silla:
  - `available`: disponible para selección y compra.
  - `reserved`: bloqueada por una reserva online en curso (dentro del tiempo límite de 10 minutos). Incluye tanto sillas principales como adicionales de compras multi-tiquete.
  - `sold`: tiquete ya emitido y pagado para este viaje.

Esta consulta no garantiza la reserva; el checkout y la venta administrativa vuelven a validarla bajo bloqueo transaccional.

## 1.2. Portal del cliente

### Foto de perfil

```http
POST /api/accounts/me/photo/
DELETE /api/accounts/me/photo/
```

Requiere autenticación. El `POST` usa `multipart/form-data` con el campo
`photo`. Se aceptan JPG, PNG y WEBP, con máximo 5 MB y 2000 x 2000 píxeles.
`GET /api/accounts/me/` devuelve `photo_url`.

`photo_url` solo se devuelve cuando el archivo existe realmente en
`MEDIA_ROOT/profile_photos/`. La URL `/media/...` responde `200 OK`; para
archivos WEBP el `Content-Type` es `image/webp`. El almacenamiento de
`MEDIA_ROOT` debe ser persistente en producción.

### Carné digital

```http
GET /api/accounts/me/card/
GET /api/accounts/cards/verify/?token=QR_TOKEN
```

El primer endpoint requiere autenticación. El QR contiene una referencia
firmada y opaca, nunca el JWT ni los datos personales completos. El carné
identifica al cliente, pero no sustituye un tiquete ni acredita una compra.
La vigencia es indefinida mientras la cuenta esté activa: la respuesta
devuelve `valid_until: null` y `validity: "indefinite_while_active"`. Si la
cuenta se desactiva, el estado del carné pasa a `revoked`.

Los QR de tiquetes son verificables, no consumibles: la consulta no cambia
`issued` a `used`. El token vence después de 30 días por defecto y la respuesta
pública devuelve solo el primer nombre y el documento enmascarado. La operación
de abordaje debe implementarse por separado si se requiere consumo único.

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

Cuando la cuenta fue creada por un administrador, la contraseña inicial es el
número de documento. La respuesta JWT incluye
`password_change_required: true`; después de iniciar sesión, Angular debe
mostrar el cambio obligatorio usando `/api/accounts/me/password/`.

Las cuentas creadas por un administrativo quedan activas y usan inicialmente
el número de documento como contraseña. Después del primer inicio de sesión,
Angular debe solicitar el cambio mediante `/api/accounts/me/password/`.
El login incluye el indicador `password_change_required: true` mientras el
cliente no haya definido una contraseña nueva. La contraseña inicial nunca se
devuelve en las respuestas.

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

### Tipos de bus

Los tipos de bus son administrables y tienen una capacidad máxima. Todos los
métodos de lectura requieren autenticación; crear, editar y eliminar tipos
requiere administrador.

```text
GET    /api/fleet/bus-types/
POST   /api/fleet/bus-types/
GET    /api/fleet/bus-types/{id}/
PUT    /api/fleet/bus-types/{id}/
PATCH  /api/fleet/bus-types/{id}/
DELETE /api/fleet/bus-types/{id}/
```

Crear un tipo:

```json
{
  "name": "Bus urbano",
  "code": "bus-urbano",
  "max_capacity": 60
}
```

Se pueden crear, por ejemplo, los tipos `Bus urbano`, `Buseta` y `Microbús`.
La capacidad máxima debe definirse según la configuración real de la flota.

Crear un bus:

```json
{
  "plate": "ABC123",
  "capacity": 40,
  "model": "2024",
  "bus_type": 1,
  "state": "Active"
}
```

`bus_type` es opcional para conservar los buses existentes. Cuando se envía,
`capacity` no puede superar `max_capacity` del tipo seleccionado. La respuesta
del bus incluye también `bus_type_detail`.

Estados de bus: `Active`, `Inactive`, `Maintenance`.

### Conductores

```text
GET    /api/fleet/drivers/
GET    /api/fleet/drivers/?search={nombre_licencia_o_telefono}
GET    /api/fleet/drivers/?is_active={true|false}
GET    /api/fleet/drivers/?license_number={licencia}
POST   /api/fleet/drivers/
GET    /api/fleet/drivers/{id}/
PUT    /api/fleet/drivers/{id}/
PATCH  /api/fleet/drivers/{id}/
DELETE /api/fleet/drivers/{id}/
```

Crear un conductor (Ficha operativa pura sin relación con usuario):

El conductor se registra únicamente con sus datos laborales/operativos. No requiere usuario, ni rol, ni correo, ni contraseña.

```json
{
  "full_name": "Carlos Conductor",
  "license_number": "LIC123456",
  "address": "Calle 1 # 2-3",
  "phone_number": "3001234567",
  "is_active": true
}
```

*Nota:* Si un conductor desea comprar una boleta de viaje, lo hace como cualquier cliente común y corriente desde la plataforma pública registrándose con su cuenta de cliente, sin mezclar sus datos de chofer.

### Sillas

```text
GET    /api/fleet/seats/
GET    /api/fleet/seats/?bus={bus_id}
POST   /api/fleet/seats/
GET    /api/fleet/seats/{id}/
PUT    /api/fleet/seats/{id}/
PATCH  /api/fleet/seats/{id}/
DELETE /api/fleet/seats/{id}/
```

- `GET /api/fleet/seats/?bus={bus_id}`: devuelve todos los registros de sillas del bus indicado sin paginación artificial. Si los registros de sillas en base de datos son inferiores a `bus.capacity`, el backend completa automáticamente las sillas faltantes siguiendo la distribución 2 + pasillo + 2, conservando los IDs y posiciones ya existentes.
- Crear una silla manualmente (`POST`):

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
GET    /api/routes/routes/?search={ciudad_o_lugar}
GET    /api/routes/routes/?origin={place_id}
GET    /api/routes/routes/?destination={place_id}
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

*Validaciones:*
- `origin` y `destination` no pueden ser el mismo lugar.
- No se permiten duplicados del mismo par origen-destino.
- `distance_km` debe ser estrictamente mayor a 0.
- La respuesta incluye los nombres descriptivos de apoyo (`origin_name`, `destination_name`, `origin_city`, `destination_city`).

## 8. Viajes y tarifas

### Viajes

Los administradores pueden crear y modificar viajes. Todos los usuarios
autenticados pueden consultarlos.

```text
GET    /api/trips/trips/
GET    /api/trips/trips/?route={route_id}
GET    /api/trips/trips/?bus={bus_id}
GET    /api/trips/trips/?driver={driver_id}
GET    /api/trips/trips/?state={scheduled|in_progress|completed|cancelled}
GET    /api/trips/trips/?date={YYYY-MM-DD}
POST   /api/trips/trips/
GET    /api/trips/trips/{id}/
PUT    /api/trips/trips/{id}/
PATCH  /api/trips/trips/{id}/
DELETE /api/trips/trips/{id}/
```

Crear un viaje (permite tarifa integrada `fare_amount_cents` en un solo paso):

```json
{
  "bus": 1,
  "driver": 2,
  "route": 3,
  "date_time_start": "2026-10-25T08:00:00-05:00",
  "date_time_end": "2026-10-25T14:00:00-05:00",
  "fare_amount_cents": 5000000,
  "fuel_start": null,
  "fuel_end": null,
  "odometer_start": null,
  "odometer_end": null,
  "passengers_start": 0,
  "trip_state": "scheduled"
}
```

*Validaciones clave:*
- **Estado del Bus:** El bus asignado debe estar activo (`state: "Active"`).
- **No solapamiento de Bus:** El bus no puede tener otro viaje activo (`scheduled` o `in_progress`) en el mismo rango de fecha y hora.
- **No solapamiento de Conductor:** El conductor no puede tener otro viaje activo en el mismo rango de fecha y hora.
- **Conductor activo:** El conductor no puede tener `is_active: false`.
- **Campos descriptivos en respuesta:** Incluye `bus_plate`, `driver_name`, `origin`, `destination` y `fare_amount_cents`.

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

Cada tiquete incluye `verification_token` y `verification_url`. Angular puede
usar `verification_url` como contenido del QR al generar el PDF.

Para descargar las boletas, el frontend debe generar un PDF desde el detalle
de la compra, con una página por tiquete. Cada página debe mostrar el viaje,
terminales, horario, pasajero, silla, `ticket_code` y el QR.

El QR no debe contener el JWT ni confiar únicamente en `ticket_code`.

### Verificar un tiquete

```http
GET /api/sales/tickets/verify/?token=VERIFICATION_TOKEN
```

No requiere autenticación. La respuesta confirma si el tiquete existe y
devuelve su estado: `issued`, `used` o `cancelled`.

```json
{
  "valid": true,
  "status": "issued",
  "ticket_code": "uuid-del-tiquete",
  "trip": {
    "id": 15,
    "origin": "Terminal Norte",
    "destination": "Terminal Sur",
    "date_time_start": "2026-11-04T20:00:00-05:00",
    "date_time_end": null
  },
  "passenger": {
    "name": "Ana Pérez",
    "identification_number": "100000001"
  },
  "seat": {
    "id": 5,
    "seat_number": "01"
  }
}
```

`valid` solo es `true` para tiquetes `issued`. Un tiquete `used` o
`cancelled` continúa identificándose, pero no es válido para abordar.

### Registrar abordaje

El endpoint público de verificación QR es únicamente de consulta. No cambia
el estado del tiquete. El registro de abordaje requiere autenticación y, por
ahora, solo está permitido a usuarios con rol `admin`.

```http
POST /api/sales/tickets/check-in/
Authorization: Bearer ACCESS_TOKEN_OPERADOR
Content-Type: application/json
Idempotency-Key: identificador-unico-del-intento
```

Solicitud:

```json
{
  "verification_token": "TOKEN_OBTENIDO_DEL_QR",
  "trip": 15
}
```

`verification_token` es el token firmado de la boleta, no el JWT. `trip` es
obligatorio y debe ser el viaje que el operador está controlando. Angular no
debe enviar el ID del operador, la hora ni el estado deseado.

La regla actual del backend permite abordar únicamente cuando el viaje está
en estado `scheduled` o `in_progress`. Los estados `completed` y `cancelled`
no admiten abordajes. Actualmente no existe una ventana horaria adicional:
la decisión se toma con el estado almacenado del viaje, no con la hora del
navegador. Si se agrega una ventana en el futuro, será una regla del backend.

El backend valida que el token sea de una boleta, que pertenezca al viaje
enviado, que la boleta esté `issued` y que la venta esté `paid`. La operación
es atómica: cambia `issued` a `used` y crea el registro de auditoría en la
misma transacción. La base de datos garantiza como máximo un abordaje por
tiquete.

Respuesta `201 Created`:

```json
{
  "detail": "Abordaje registrado.",
  "ticket_id": 30,
  "ticket_code": "codigo-del-tiquete",
  "status": "used",
  "trip": 15,
  "seat": {
    "id": 5,
    "seat_number": "01"
  },
  "check_in": {
    "id": 8,
    "checked_in_at": "2026-11-05T17:30:00-05:00",
    "checked_in_by": {
      "id": 2,
      "name": "Operador"
    }
  }
}
```

La misma `Idempotency-Key`, usada por el mismo administrador con el mismo
contenido, devuelve el resultado original con `200 OK` y `replayed: true`.
Las claves se conservan indefinidamente para mantener la recuperación segura
de reintentos; debe planificarse una política de limpieza antes de cambiar
esta retención. Una clave con otros datos o usada por otro operador devuelve
`409` con `idempotency_conflict`.

Errores:

- `400 invalid_request`: faltan datos o tienen formato incorrecto.
- `401`: sesión ausente o vencida.
- `403 permission_denied`: el usuario no tiene rol `admin`.
- `404 invalid_ticket`: token inválido, vencido o inexistente.
- `409 wrong_trip`: la boleta pertenece a otro viaje.
- `409 already_used`: el abordaje ya fue registrado.
- `409 ticket_cancelled`: la boleta está cancelada.
- `409 sale_not_paid`: la venta no está pagada.
- `409 trip_not_boardable`: el viaje está cancelado o finalizado.
- `409 idempotency_conflict`: la clave se reutilizó con otros datos.

Después del abordaje, `GET /api/sales/tickets/verify/` continúa siendo
público y devuelve `valid: false` y `status: "used"`. No expone los datos
del operador. El detalle autenticado del tiquete incluye `check_in` con la
hora y el operador.

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
  "seats": [5, 6, 7],
  "payment_method": "cash"
}
```

Los valores de `seats` son los ID de las sillas. Se aceptan entre 1 y 10
sillas, todas para el mismo cliente. Para conservar compatibilidad también se
acepta `seat` como una sola silla, pero no se pueden enviar `seat` y `seats`
en la misma solicitud.

`payment_method` puede ser `cash`, `transfer` o `card`.

El backend obtiene la tarifa desde el viaje y calcula
`amount_cents = tarifa_del_viaje * cantidad_de_sillas`. No se debe enviar
`amount_cents` ni ningún precio. El viaje debe estar programado y tener una
tarifa válida.

La operación es atómica: crea una sola venta `paid`, un pago aprobado, un
`SaleItem` y un tiquete por cada silla, o no crea ninguno. Todas las sillas
deben pertenecer al bus del viaje. Una silla vendida o con una reserva online
vigente causa `409 Conflict` para toda la solicitud; las reservas online
vencen después de 5 minutos.

Para evitar duplicados, se recomienda enviar:

```http
Idempotency-Key: identificador-unico-del-intento
```

La misma clave con el mismo contenido devuelve la venta original con `200`,
sin crear otra venta, pago, tiquete o factura. La misma clave con contenido
diferente devuelve `409 Conflict`. La clave también es segura ante solicitudes
simultáneas.

Respuesta `201 Created` (resumen):

```json
{
  "id": 25,
  "status": "paid",
  "trip": 15,
  "quantity": 3,
  "unit_amount_cents": 2500000,
  "amount_cents": 7500000,
  "payment_method": "cash",
  "tickets": [
    {
      "id": 30,
      "trip": 15,
      "seat": 5,
      "ticket_code": "codigo-tiquete-30",
      "status": "issued",
      "verification_url": "https://portalbic.site/api/sales/tickets/verify/?token=..."
    }
  ],
  "factus_invoice": {
    "status": "issued",
    "number": "NUMERO-FACTURA",
    "cufe": "CUFE",
    "public_url": "https://..."
  }
}
```

`tickets` contiene una entrada por silla e incluye los datos del pasajero,
emisión y verificación QR. Si Factus falla, la venta y los tiquetes se
conservan y `factus_invoice.status` será `error` con `error_message`; la
factura puede reintentarse con el endpoint administrativo de reintento.

Errores:

- `400`: datos inválidos, viaje sin tarifa, viaje no programado, sillas
  duplicadas o que no pertenecen al bus.
- `403`: el usuario no tiene rol `admin`.
- `409` con `code: seats_unavailable`: una o más sillas están `sold` o
  `reserved`. La propiedad `unavailable_seats` incluye `seat`, `seat_number`
  y `reason`.

Si el documento no existe, el endpoint crea un usuario cliente. Actualmente
no hay un endpoint independiente para buscar o crear clientes con un payload
reducido.

## 10. Compra online con Wompi

### Crear checkout

```http
POST /api/sales/wompi/checkout/
Idempotency-Key: identificador-unico-del-intento
```

Solicitud:

```json
{
  "trip": 15,
  "passengers": [
    {
      "seat": 5,
      "name": "Ana Pérez",
      "identification_document_code": "13",
      "identification_number": "100000001",
      "email": "ana@example.com",
      "telephone": "3001234567"
    },
    {
      "seat": 6,
      "name": "Luis Pérez",
      "identification_document_code": "13",
      "identification_number": "100000002",
      "email": "luis@example.com",
      "telephone": "3007654321"
    }
  ],
  "redirect_url": "https://frontend.example.com/resultado"
}
```

`redirect_url` es opcional. El usuario debe estar autenticado.
El comprador es el usuario autenticado; no se crean cuentas para los
pasajeros. No hay restricción artificial de máximo 10 boletas; se pueden comprar tantas sillas como estén disponibles en el viaje. La clave de idempotencia
es obligatoria y repetirla devuelve la misma venta sin crear otra.

El backend valida las sillas (completando los registros del bus si faltaban respecto a su capacidad), obtiene el precio de `TripFare`, crea una venta `pending`, reserva todas las sillas durante **10 minutos** y devuelve los datos para el Widget de Wompi:

```json
{
  "sale_id": 20,
  "reference": "sale-20",
  "public_key": "pub_test_...",
  "currency": "COP",
  "amount_in_cents": 5000000,
  "signature_integrity": "...",
  "expiration_time": "2026-11-06T22:45:00.000Z",
  "signature_integrity_with_expiration": "...",
  "redirect_url": "https://frontend.example.com/resultado",
  "expires_at": "2026-11-06T17:45:00-05:00",
  "server_time": "2026-11-06T17:35:00-05:00",
  "quantity": 2
}
```

#### Integración en el Widget de Wompi:
- **`signature_integrity_with_expiration`**: debe enviarse en `signature.integrity` (o `data-signature:integrity`). Incluye la fecha de expiración en el hash SHA-256 (`<reference><amount><currency><expiration_time><secret>`).
- **`expiration_time`**: debe enviarse tal como llega en formato UTC ISO 8601 (`expirationTime` o `data-expiration-time`). Activa el contador nativo de Wompi y hace que la pasarela rechace pagos fuera de tiempo.
- **`signature_integrity`**: se mantiene disponible por retrocompatibilidad con integraciones anteriores.

Si una sola silla no está disponible o ya está reservada por otro cliente (incluso como asiento secundario en otra orden), la operación responde `409 Conflict` y no crea reservas parciales.

Al aprobarse el pago se emite un tiquete por silla. Los reintentos del webhook o de consulta de estado son idempotentes. Una factura Factus representa toda la compra y contiene un concepto por boleta.

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

El backend consulta Wompi con la clave privada y verifica referencia, monto, moneda y estado:
- `APPROVED`: si las sillas siguen disponibles, marca la venta como `paid` y genera los tiquetes. Si la reserva ya había expirado y las sillas fueron ocupadas por otra compra, marca la venta como `refund_required` y notifica por correo a los administradores para gestionar la reubicación o devolución del dinero desde Wompi.
- `DECLINED`, `ERROR`, `VOIDED`: marcan la venta como `failed` (o `expired` si ya venció el tiempo).
- Estados posibles de la venta (`sale_status`): `pending`, `paid`, `failed`, `cancelled`, `expired`, `refund_required`.

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

El cliente puede consultar su propia factura con:

```http
GET /api/sales/sales/{sale_id}/invoice/
```

Si Factus aún no la ha emitido, la respuesta indica `status: pending` o
`status: error`; no se genera un documento ficticio. Un cliente no puede
consultar facturas de otra venta.

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

El precio siempre debe provenir del backend. El frontend solo lo muestra.
