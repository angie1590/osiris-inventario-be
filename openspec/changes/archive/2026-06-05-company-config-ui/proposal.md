## Why

La funcionalidad de Configuración de Empresa fue implementada en el backend (`company-config`) pero no tiene interfaz de usuario: los administradores no pueden gestionar los datos corporativos desde el panel, lo que hace inaccesible la configuración requerida para generar documentos y reportes.

## What Changes

- Se agrega la página `/admin/company` visible solo para administradores, con un formulario para crear y editar la configuración de empresa (razón social, nombre comercial, RUC, dirección, teléfono, email, logo).
- Se agrega el ítem "Empresa" en el sidebar para el rol `admin`.
- Se agrega un banner de advertencia global en el `AppLayout` cuando la empresa no está configurada (`is_complete = false`), orientando al administrador a completar la configuración antes de operar.
- Se agregan los hooks TanStack Query para `GET`, `POST` y `PATCH /api/v1/company`.
- Se implementa la subida de logo como base64 (lectura local via `FileReader`, con límite de 2 MB) o como URL directa.

## Capabilities

### New Capabilities
- `company-config-ui`: Página de administración de la configuración corporativa de la empresa: formulario de datos, subida de logo, indicador de completitud y banner de advertencia en el layout principal.

### Modified Capabilities
- `company-config`: Se añaden requisitos de comportamiento UI al spec existente (visualización del estado de completitud, banner bloqueante para no-admins, acceso de solo lectura al dato para otros roles).

## Impact

- **Frontend**: Nuevo componente `AdminCompanyPage.tsx` en `src/pages/admin/`; hooks en `src/features/admin/hooks.ts`; sidebar actualizado; banner en `AppLayout.tsx`.
- **API**: Consume los endpoints ya implementados `GET/POST/PATCH /api/v1/company`.
- **Routing**: Nueva ruta `/admin/company` bajo el guard `require_admin`.
- **No hay cambios en el backend.**
