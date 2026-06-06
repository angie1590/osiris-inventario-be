## 1. Tipos y hooks

- [x] 1.1 Agregar tipos `CompanyConfig`, `CreateCompanyPayload` y `UpdateCompanyPayload` a `src/types/api.ts`
- [x] 1.2 Agregar hooks `useCompanyConfig()`, `useCreateCompany()` y `useUpdateCompany()` en `src/features/admin/hooks.ts`

## 2. Página de configuración de empresa

- [x] 2.1 Crear `src/pages/admin/AdminCompanyPage.tsx` con formulario React Hook Form + Zod para los campos: razón social, nombre comercial, RUC, dirección, teléfono, email
- [x] 2.2 Implementar lógica de submit dual: `POST` si no existe configuración, `PATCH` si ya existe; mostrar toast de éxito en ambos casos
- [x] 2.3 Implementar sección de logo con dos tabs — "Subir archivo" (FileReader → base64, validación ≤ 2 MB, preview) y "URL directa" (input text)
- [x] 2.4 Mostrar vista previa del logo actual si existe en la configuración cargada

## 3. Navegación y routing

- [x] 3.1 Agregar ítem "Empresa" (icono `Building2` de lucide-react) al array `NAV_ITEMS` en `src/components/shared/Sidebar.tsx`, roles: `['admin']`
- [x] 3.2 Agregar lazy import de `AdminCompanyPage` y ruta `/admin/company` en `src/App.tsx` bajo el `RoleGuard` de admin

## 4. Banner de advertencia

- [x] 4.1 En `src/layouts/AppLayout.tsx`, consumir `useCompanyConfig()` y renderizar un banner amarillo debajo del header cuando `is_complete = false` o la empresa no existe; para admin incluir link "Configurar ahora → /admin/company"; para otros roles mostrar texto informativo sin link
