---
name: facturas-crear-y-validar
description: Crea y valida una factura electrónica estándar (tipo 01, operation_type 10) con la API de Factus, incluyendo cómo componer customer, items, payment_details y cash_rounding_amount a partir de los distintos módulos de datos del sistema.
---

# Skill: Crear y Validar Facturas Electrónicas — Factus API

## Propósito

Este skill enseña a los integradores a crear y validar facturas electrónicas de venta (tipo estándar, `operation_type: "10"`) a través de la API de Factus. Al completar este skill, el integrador podrá construir el cuerpo de la solicitud correctamente, manejar los campos requeridos y opcionales, e interpretar la respuesta.

---

## Modelo mental: la factura es la unión de varios módulos de datos

Antes de construir el body de la solicitud, ten en cuenta que **una factura no es una sola fuente de información**: es el resultado de combinar datos que normalmente viven en módulos/servicios distintos de tu propio sistema (y en algunos casos, de la API de Factus). Resuelve cada bloque por separado y luego únelos en un solo JSON:

| Bloque del payload | De dónde debe salir |
|---------------------|----------------------|
| `numbering_range_id` | Del módulo de **rangos de numeración** de Factus (`GET /v2/numbering-ranges`). Solo es obligatorio si manejas más de un rango activo; si solo tienes uno, puedes omitirlo. |
| `customer` | De tu propio módulo de clientes/CRM (identificación, nombre, dirección, email, teléfono). Opcionalmente puedes autocompletar nombre y correo consultando el servicio de la DIAN (`GET /v2/dian/acquirer?identification_document_code=&identification_number=`) que expone Factus. Los **códigos** (`identification_document_code`, `legal_organization_code`, `tribute_code`, `responsibilities`, `municipality_code`, `country_code`) deben salir de tus tablas de referencia (catálogos de códigos DIAN que Factus documenta). |
| `items` | De tu propio catálogo de productos/servicios — Factus no gestiona catálogo, tú decides qué se factura. Los **códigos** (`unit_measure_code`, `standard_code`, `items.*.taxes.*.code`, `items.*.withholding_taxes.*.code`) también salen de tus tablas de referencia. |
| `payment_details` | De la configuración de medios/formas de pago de tu sistema (caja, pasarela de pagos, cuentas, etc.), combinada con los códigos de `payment_form` y `payment_method_code` de tus tablas de referencia. |
| `cash_rounding_amount` | **No proviene de ningún módulo externo.** Es un valor que tú calculas al comparar la suma de `payment_details.*.amount` contra el `total` real de la factura, para conciliar diferencias de redondeo (máximo ±500.00). |
| `establishment` (opcional) | Del módulo de configuración de tu empresa, solo si manejas más de un establecimiento/sede. |

En resumen: reúne primero cliente, ítems, medios de pago y rango de numeración desde sus respectivas fuentes, calcula el ajuste de redondeo si aplica, y solo entonces ensambla el JSON final descrito abajo.

---

## Endpoint

| Método | Ruta                        |
|--------|-----------------------------|
| `POST` | `/v2/bills/validate`        |

| Ambiente   | URL base                                    |
|------------|---------------------------------------------|
| Sandbox    | `https://api-sandbox.factus.com.co/v2/bills/validate` |
| Producción | `https://api.factus.com.co/v2/bills/validate`         |

---

## Autenticación y Cabeceras

Todas las solicitudes requieren un Bearer Token en la cabecera `Authorization`. Obtén el token mediante el endpoint de autenticación (`/oauth/token`).

```http
Authorization: Bearer {access_token}
Content-Type: application/json
Accept: application/json
```

---

## Estructura de la Solicitud (Body)

El body se envía en formato JSON. La factura se organiza en tres grandes bloques:

1. **Datos generales** — metadatos de la factura (referencia, tipo, rango, pago, etc.)
2. **Datos del cliente** — objeto `customer`
3. **Productos / servicios** — array `items`

### Campos de Nivel Raíz

| Campo | Tipo | Req. | Descripción |
|-------|------|------|-------------|
| `reference_code` | string | ✅ | Identificador único de la factura en tu sistema. Previene duplicados. |
| `document` | string | No | Código del tipo de documento. Por defecto `"01"` (Factura de venta). |
| `numbering_range_id` | integer | No | ID del rango de numeración. Obligatorio solo si tienes múltiples rangos activos. |
| `operation_type` | string | No | Código del tipo de operación. Por defecto `"10"` (Estándar). |
| `send_email` | boolean | No | Si `false`, no se envía correo al cliente. Por defecto `true`. |
| `observation` | string | No | Observación libre. Máximo 250 caracteres. |
| `created_time` | string | No | Fecha/hora de creación en formato `HH:mm:ss`. |
| `currency` | object | No | Muestra los totales de la factura en una moneda extranjera dentro de su representación gráfica. Si se envía, sus campos internos son obligatorios. |
| `cash_rounding_amount` | string | No | Ajuste de redondeo entre `payment_details` y el total. Rango: ±500.00. |

### `currency` (objeto, opcional)

| Campo | Tipo | Req. | Descripción |
|-------|------|------|-------------|
| `currency.type` | string | ✅ | Código internacional de la moneda extranjera a mostrar (distinta a la moneda local de emisión). |
| `currency.exchange_rate` | string | ✅ | Tasa de cambio usada para convertir los montos de la moneda local a la extranjera. |


### `payment_details` (array, requerido)

Un objeto por cada medio de pago utilizado.

| Campo | Tipo | Req. | Descripción |
|-------|------|------|-------------|
| `payment_form` | string | ✅ | Código de la forma de pago (`"1"` = contado, `"2"` = crédito). |
| `payment_method_code` | string | ✅ | Código del método de pago (ej. `"42"` = consignación, `"10"` = efectivo). |
| `reference_code` | string | No | Referencia interna del pago. |
| `amount` | string | ✅ | Monto pagado con ese medio. |
| `due_date` | string | No | Fecha de vencimiento `YYYY-MM-DD`. Requerido solo cuando `payment_form` = `"2"` (crédito). |

### `prepayment_details` (array, opcional)

Anticipos aplicados a la factura.

| Campo | Tipo | Req. | Descripción |
|-------|------|------|-------------|
| `reference_code` | string | ✅ | Código de referencia del anticipo. |
| `received_date` | string | ✅ | Fecha de recepción `YYYY-MM-DD`. |
| `amount` | string | ✅ | Monto del anticipo. |
| `note` | string | No | Nota adicional. Máximo 5000 caracteres. |

### `customer` (objeto, requerido)

| Campo | Tipo | Req. | Descripción |
|-------|------|------|-------------|
| `identification_document_code` | string | ✅ | Código del tipo de documento (ej. `"31"` = NIT, `"13"` = cédula). |
| `identification` | string | ✅ | Número de identificación **sin** dígito de verificación ni guion. |
| `dv` | string | No | Dígito de verificación del NIT. Si se omite, el API lo calcula. |
| `legal_organization_code` | string | ✅ | `"1"` = persona jurídica, `"2"` = persona natural. |
| `tribute_code` | string | No | Código del tributo. Por defecto `"ZZ"` (no aplica). |
| `responsibilities` | array | No | Códigos de tipo de responsabilidad fiscal. Por defecto `["R-99-PN"]`. |
| `company` | string | Cond. | Razón social. Obligatorio si `legal_organization_code` = `"1"`. |
| `trade_name` | string | No | Nombre comercial. |
| `names` | string | Cond. | Nombre del cliente. Obligatorio si `legal_organization_code` = `"2"`. |
| `address` | string | No | Dirección del cliente. |
| `email` | string | No | Correo electrónico. |
| `phone` | string | No | Teléfono de contacto. |
| `country_code` | string | No | Código del país del cliente. |
| `municipality_code` | string | No | Código del municipio colombiano (ej. `"68679"` = San Gil). Solo aplica si el cliente es de Colombia. |

### `items` (array, requerido)

Un objeto por cada producto o servicio facturado.

| Campo | Tipo | Req. | Descripción |
|-------|------|------|-------------|
| `code_reference` | string | ✅ | Código de referencia del producto/servicio. |
| `name` | string | ✅ | Nombre del producto o servicio. |
| `quantity` | string | ✅ | Cantidad (máximo dos decimales). |
| `discount_rate` | string | Cond. | Porcentaje de descuento (máximo dos decimales). Usa `"0.00"` si no aplica. Usa este campo **o** `discount_amount`, no ambos. |
| `discount_amount` | string | No | Monto fijo de descuento (máximo dos decimales). Alternativa a `discount_rate`; no envíes ambos campos a la vez. |
| `price` | string | ✅ | Precio unitario sin impuestos ni descuentos (máximo dos decimales). |
| `unit_measure_code` | string | ✅ | Código de unidad de medida (ej. `"94"` = unidad). |
| `standard_code` | string | ✅ | Código del estándar de producto (ej. `"999"` = adopción del contribuyente). |
| `note` | string | No | Información adicional del ítem. |
| `taxes` | array | ✅ | Impuestos del ítem (ver tabla abajo). |
| `withholding_taxes` | array | No | Autorretenciones del ítem. |

#### `items.*.taxes` (array)

| Campo | Tipo | Req. | Descripción |
|-------|------|------|-------------|
| `code` | string | ✅ | Código del impuesto (ej. `"01"` = IVA, `"04"` = INC). |
| `rate` | string | ✅ | Tasa del impuesto en porcentaje (ej. `"19.00"`). |
| `is_excluded` | boolean | No | `true` si el ítem está excluido de impuestos. |

#### `items.*.withholding_taxes` (array, opcional)

| Campo | Tipo | Req. | Descripción |
|-------|------|------|-------------|
| `code` | string | ✅ | Código de la retención. |
| `rate` | string | ✅ | Tasa de retención en porcentaje (máximo dos decimales). |

### `allowance_charges` (array, opcional)

Descuentos o recargos a nivel de factura.

| Campo | Tipo | Req. | Descripción |
|-------|------|------|-------------|
| `concept_type` | string | ✅ | Código del concepto de descuento/recargo. |
| `is_surcharge` | boolean | ✅ | `true` = recargo, `false` = descuento. |
| `reason` | string | ✅ | Razón del descuento o recargo. |
| `base_amount` | string | ✅ | Base de cálculo (máximo dos decimales). |
| `amount` | string | ✅ | Valor aplicado (máximo dos decimales). |

### Objetos Opcionales Avanzados

| Objeto | Cuándo usarlo |
|--------|---------------|
| `establishment` | Cuando manejas múltiples establecimientos. Si se envía, todos sus campos internos son obligatorios (`name`, `address`, `phone_number`, `email`, `municipality_code`). |
| `billing_period` | Para servicios públicos, arrendamientos, matrículas, etc. Campos: `start_date`, `end_date` (formato `YYYY-MM-DD`). |
| `order_reference` | Para referenciar una orden de pedido. Campos: `reference_code`, `issue_date`. |
| `related_documents` | Obligatorio cuando `document` = `"03"`. Array de documentos relacionados. |

---

## Ejemplo de Solicitud — Factura Estándar

```json
{
  "reference_code": "FACT-2026-0124",
  "document": "01",
  "numbering_range_id": 389,
  "operation_type": "10",
  "observation": "Observación de prueba",
  "payment_details": [
    {
      "payment_form": "1",
      "payment_method_code": "42",
      "reference_code": "pago-001",
      "amount": "83300"
    }
  ],
  "cash_rounding_amount": "0.00",
  "customer": {
    "identification_document_code": "31",
    "identification": "123456789",
    "company": "Alan company name",
    "trade_name": "Alan trade name",
    "address": "calle 1 # 1-1",
    "email": "alan.company@email.com",
    "phone": "1234567890",
    "legal_organization_code": "1",
    "tribute_code": "ZZ",
    "country_code": "CO",
    "responsibilities": ["R-99-PN"],
    "municipality_code": "68679"
  },
  "items": [
    {
      "code_reference": "PROD-000A",
      "name": "Producto A",
      "quantity": "1.00",
      "discount_rate": "0.00",
      "price": "10000.00",
      "unit_measure_code": "94",
      "standard_code": "999",
      "taxes": [
        {
          "code": "01",
          "rate": "19.00"
        }
      ]
    },
    {
      "code_reference": "PROD-000B",
      "name": "Producto B",
      "quantity": "3.00",
      "discount_rate": "0.00",
      "price": "20000.00",
      "unit_measure_code": "94",
      "standard_code": "999",
      "taxes": [
        {
          "code": "01",
          "rate": "19.00"
        }
      ]
    }
  ]
}
```

---

## Respuesta Exitosa (`201 Created`)

```json
{
  "status": "Created",
  "message": "Documento con el código de referencia {uuid} registrado y validado con éxito",
  "data": {
    "reference_code": "b64930df-2a57-4210-b04d-9a013c05fdb2",
    "number": "SETP990002443",
    "document_type": { "code": "01", "name": "Factura electrónica de Venta" },
    "operation_type": { "code": "10", "name": "Estándar" },
    "is_validated": true,
    "validated_at": "13-05-2026 08:21:49 AM",
    "errors": {},
    "cufe": "a821f2e05cb1b82e0f74...",
    "links": {
      "qr": "https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey=...",
      "public_url": "https://app-sandbox.factus.com.co/documents/bills/..."
    },
    "totals": {
      "prepayment_amount": "0.00",
      "gross_amount": "70000.00",
      "taxable_amount": "70000.00",
      "tax_amount": "13300.00",
      "surcharge_amount": "0.00",
      "total": "83300.00"
    },
    "customer": { ... },
    "items": [ ... ],
    "company": { ... },
    "numbering_range": { ... }
  }
}
```

### Campos clave de la respuesta

| Campo | Descripción |
|-------|-------------|
| `data.number` | Número oficial de la factura asignado por el rango (ej. `"SETP990002443"`). |
| `data.cufe` | Código Único de Factura Electrónica. Identificador ante la DIAN. |
| `data.is_validated` | `true` si la DIAN validó el documento. |
| `data.errors` | Objeto con advertencias de la DIAN (no necesariamente rechazan la factura). |
| `data.links.qr` | URL para el código QR del documento. |
| `data.links.public_url` | URL pública del documento en Factus. |
| `data.totals` | Resumen de valores: bruto, impuesto, total. |

---

## Reglas y Advertencias Importantes

> **Los campos opcionales de tipo objeto o array, una vez reciben datos, se convierten en requeridos**: todos sus campos internos deben enviarse completos; no pueden ir vacíos.

- **`reference_code`** debe ser único por factura. Si se repite, el API rechazará la solicitud para evitar duplicados.
- **NIT sin DV**: En `customer.identification` envía solo el número sin el dígito verificador ni guion. El campo `customer.dv` es independiente y opcional (el API lo calcula si se omite).
- **Persona jurídica vs. natural**: Si `legal_organization_code` = `"1"` → `company` es obligatorio. Si = `"2"` → `names` es obligatorio.
- **Crédito (`payment_form` = `"2"`)**: El campo `due_date` pasa a ser obligatorio en `payment_details`.
- **Todos los valores numéricos** (precios, cantidades, tasas) se envían como `string` con máximo dos decimales.
- **El campo `errors` en la respuesta** contiene notificaciones de la DIAN (FAJ44b, RUT01, etc.) pero no implican necesariamente el rechazo de la factura. Verificar `is_validated`.

---

## Tipos de Facturas Disponibles

Este skill cubre únicamente la factura **Estándar**. La API de Factus soporta otros tipos de operación con campos adicionales propios (mandatos, transporte, sector salud); consulta la documentación oficial de Factus para esos casos.

| Tipo | `operation_type` |
|------|------------------|
| Estándar | `"10"` |
| Mandatos | `"11"` |
| Transporte | `"12"` |
| Sector Salud — SS-CUFE / SS-CUDE / SS-Reporte / SS-Recaudo / SS-Número / Sin Aporte | (ver documentación oficial) |

---

## Flujo de Integración Recomendado

```
1. Autenticarse → POST /oauth/token → obtener access_token
2. Obtener rangos activos → GET /v2/numbering-ranges → seleccionar numbering_range_id
3. Construir el body de la factura con los campos requeridos
4. POST /v2/bills/validate → guardar data.number y data.cufe en tu sistema
5. Verificar data.is_validated = true
6. Revisar data.errors (notificaciones DIAN, no necesariamente rechazo)
```
