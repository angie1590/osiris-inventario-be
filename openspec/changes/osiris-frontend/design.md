## Context

El backend Osiris Inventario expone 42 endpoints REST con JWT auth. El frontend se crea como un proyecto nuevo en `osiris-inventario-fe` (hermano del directorio backend). Consumirá el API en `http://localhost:8000/api/v1`. No hay SPA existente ni estado compartido a migrar.

## Goals / Non-Goals

**Goals:**
- SPA React 18 con TypeScript estricto
- Autenticación JWT con refresco silencioso y protección de rutas
- Vistas diferenciadas por rol (admin / operator / supervisor)
- Cobertura funcional de todos los módulos del backend
- Exportación PDF y Excel delegada al backend

**Non-Goals:**
- SSR / Next.js
- Modo offline / PWA
- Tests de integración end-to-end (Playwright/Cypress) en este alcance
- Internacionalización (i18n)

## Decisions

### D1 — Vite + React 18 + TypeScript
**Decisión**: Vite como build tool, React 18 con TypeScript estricto.
**Alternativas**: CRA (descontinuado), Next.js (overhead de SSR innecesario para una app de gestión interna).
**Razón**: Vite ofrece HMR ultra-rápido y build optimizado. TypeScript estricto desde el inicio evita deuda técnica en una app con muchos formularios y tipos de la API.

### D2 — Tailwind CSS + shadcn/ui
**Decisión**: Tailwind para utilidades de estilo, shadcn/ui para componentes (basados en Radix UI).
**Alternativas**: MUI (opinionado, difícil de personalizar), Ant Design (bundle pesado).
**Razón**: shadcn/ui copia los componentes al proyecto (sin dependencia de versión de la librería), es accesible por defecto (Radix), y se integra naturalmente con Tailwind. Ideal para un sistema de gestión.

### D3 — TanStack Query (React Query) para server state
**Decisión**: Toda la comunicación con el backend pasa por `useQuery` / `useMutation` de TanStack Query v5.
**Alternativas**: Context + `useEffect` manual, SWR.
**Razón**: Caché automático, deduplicación de requests, invalidación por mutation, estados de loading/error/success listos. Elimina ~80% del boilerplate de fetching.

### D4 — React Router v6 con Outlet y loaders
**Decisión**: React Router v6 con rutas anidadas. Layouts de autenticación y de app shell implementados como `<Outlet>`.
**Razón**: Permite protección de rutas por rol en el nivel de layout sin duplicar guards en cada componente.

### D5 — Axios con interceptores para auth
**Decisión**: Instancia Axios singleton (`src/lib/api.ts`) con interceptor de request (attach Bearer token) e interceptor de response (retry automático con refresh token en 401).
**Alternativas**: Fetch nativo (sin interceptores nativos), ky (menos conocido).
**Razón**: El patrón de refresh token requiere retry de request, lo que es más limpio con interceptores de Axios. TanStack Query usa esta instancia directamente.

### D6 — React Hook Form + Zod para formularios
**Decisión**: React Hook Form para manejo de formularios, Zod para validación de esquemas.
**Alternativas**: Formik + Yup (más pesado, peor performance en re-renders).
**Razón**: RHF no causa re-renders en cada keystroke (uncontrolled). Zod comparte el mismo lenguaje de tipos con TypeScript y puede generar tipos inferidos automáticamente.

### D7 — Tokens: access en memoria, refresh en localStorage
**Decisión**: El access token se guarda solo en memoria (variable de módulo en `api.ts`). El refresh token en localStorage.
**Razón**: Access token en memoria protege contra XSS (no accesible desde scripts externos). Refresh en localStorage permite persistencia de sesión entre refreshes de página.

### D8 — Estructura de carpetas por feature
**Decisión**: Organización por feature: `src/features/auth/`, `src/features/catalog/`, etc. Componentes compartidos en `src/components/ui/` (shadcn) y `src/components/shared/`.
**Alternativas**: Estructura por tipo (components/, hooks/, services/).
**Razón**: En una app con muchos módulos (8 features), la estructura por feature mantiene la cohesión y facilita encontrar/modificar todo lo relacionado a un módulo.

## Risks / Trade-offs

- **[Risk] Refresh token race condition** — Múltiples requests concurrentes fallando en 401 pueden generar múltiples llamadas a `/auth/refresh`. → Mitigación: mutex/flag en el interceptor que serializa el refresh y reintenta los requests pendientes.
- **[Risk] shadcn/ui component updates** — Al estar copiados en el proyecto, no se actualizan automáticamente. → Trade-off aceptado: control total sobre los componentes.
- **[Risk] CORS en desarrollo** — El proxy de Vite (`vite.config.ts`) debe redirigir `/api` al backend para evitar problemas de CORS. → Configurar `server.proxy` desde el inicio.
- **[Risk] Tipos de API no tipados** — Sin OpenAPI codegen, los tipos se escriben a mano y pueden desincronizarse. → Mitigación: mantener `src/types/api.ts` como fuente de verdad de los tipos de respuesta del backend.

## Migration Plan

1. Crear repo `osiris-inventario-fe` con `npm create vite@latest -- --template react-ts`.
2. Instalar dependencias: Tailwind, shadcn/ui, React Router v6, Axios, TanStack Query, React Hook Form, Zod, Recharts.
3. Configurar proxy Vite hacia `http://localhost:8000`.
4. Implementar shell, auth, y protección de rutas antes de cualquier feature.
5. Implementar features en orden: catálogo → movimientos → Kardex → reportes → auditoría → admin.

## Open Questions

- ¿Se desplegará en producción (nginx, Vercel, etc.) o solo en desarrollo local? Afecta la configuración del proxy y la URL base del API.
- ¿Se necesitan tests unitarios de componentes (Vitest + Testing Library)? No incluidos en este alcance pero pueden agregarse como tarea opcional.
