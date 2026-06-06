## Context

El backend expone `GET/POST/PATCH /api/v1/company` (singleton). El frontend no tiene ninguna pantalla para consumirlo. El resto de la aplicación (inventario y reportes) quedará bloqueado hasta que el administrador complete la configuración, pero no existe forma visible de hacerlo desde la UI.

El frontend usa React 18 + Vite + TypeScript, TanStack Query v5, React Hook Form + Zod, shadcn/ui con Tailwind v4, React Router v6 y Axios con refresh token automático.

## Goals / Non-Goals

**Goals:**
- Página `/admin/company` funcional: crear configuración si no existe, editar si ya existe.
- Banner de advertencia en el layout principal cuando `is_complete = false`.
- Hooks TanStack Query reutilizables para los tres endpoints.
- Subida de logo como base64 (archivo local) con validación de 2 MB.

**Non-Goals:**
- Preview de logo en vista de imagen completa.
- Crop o redimensionado del logo.
- Carga de logo a un CDN externo (se usa base64 directamente).
- Página de solo lectura para operadores/supervisores (el banner es suficiente).

## Decisions

### D1: Una sola página para crear y editar
El modelo es singleton: si no existe se hace POST, si existe se hace PATCH. La página detecta el estado via `useCompanyConfig()` y ajusta el submit handler. Evita dos rutas y duplicación de formulario.

Alternativa descartada: rutas separadas `/admin/company/new` y `/admin/company/edit` — innecesario para un singleton.

### D2: Input de logo con dos modos — archivo o URL
El campo logo acepta un `data:image/...;base64,...` o una URL HTTP/S. Se implementa con un Tabs de dos pestañas: "Subir archivo" (input `type=file` → FileReader) y "URL directa" (input text). El valor resultante es siempre un string que se envía en el campo `logo`.

Validación en frontend: el archivo no puede superar 2 MB antes de convertirlo (se valida `file.size`), en línea con el límite del backend (2 097 152 caracteres).

Alternativa descartada: solo URL — no permite logos locales sin CDN.

### D3: Banner en AppLayout, con acción directa para admin
El banner se muestra en `AppLayout.tsx` justo debajo del header, ocupando todo el ancho. Se consulta `useCompanyConfig()` con `staleTime: 30s`; si la respuesta es 404 o `is_complete = false`, se muestra el banner.

- Para `admin`: banner amarillo/warning con link "Configurar ahora → /admin/company".
- Para otros roles: banner amarillo informativo sin link ("El administrador debe completar la configuración de empresa").

El banner no bloquea la navegación; el bloqueo real lo hace el backend cuando se intenta operar.

Alternativa descartada: modal modal bloqueante al entrar — intrusivo y dificulta navegar si el admin quiere revisar datos antes de configurar.

### D4: Query key y caché
`['company-config']` como query key; `staleTime: 30_000`, `retry: 1`. El banner no hace fetching extra: reutiliza el mismo query key a través de `useCompanyConfig()`. Invalidar en onSuccess de create y update.

### D5: Tipos en `api.ts`
Añadir `CompanyConfig`, `CreateCompanyPayload` y `UpdateCompanyPayload` al archivo `src/types/api.ts` existente, alineados con el schema del backend.

## Risks / Trade-offs

- **Logo base64 en DB como texto**: Imágenes grandes (hasta 2 MB) se envían en el body de PATCH. Aceptable para una configuración singleton de baja frecuencia de cambio.  
  Mitigación: validación de tamaño en frontend antes del submit.

- **Banner genera fetch extra en cada montaje del layout**: `useCompanyConfig` con `staleTime: 30s` minimiza requests; después del primer fetch usa caché.  
  Mitigación: staleTime y un solo hook compartido.

## Migration Plan

No hay datos a migrar. La tabla `company_config` está vacía en producción hasta que el admin la configure. La ruta `/admin/company` es nueva y no reemplaza ninguna existente.

Rollback: revertir los archivos nuevos y quitar la ruta de `App.tsx` + el sidebar item.
