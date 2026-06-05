## Why

El backend de Osiris Inventario expone una API REST completa pero carece de interfaz de usuario. Los operadores, supervisores y administradores necesitan una aplicación web para gestionar el inventario sin interactuar directamente con la API.

## What Changes

- Crear el proyecto `osiris-inventario-fe` (Vite + React 18 + TypeScript + Tailwind CSS + shadcn/ui) como repositorio separado que consume el backend en `http://localhost:8000`.
- Implementar autenticación con JWT (login, logout, cambio de contraseña obligatorio, refresco automático de token).
- Implementar vistas diferenciadas por rol: Administrador, Operador, Supervisor.
- Implementar gestión completa de catálogo (categorías jerárquicas + productos con atributos personalizados).
- Implementar los 4 flujos de movimientos de inventario: Ingresos (IN), Egresos (EG), Bajas (BI) y Ajustes (AI) con flujo de aprobación OTP para BI/AI.
- Implementar visualización de Kardex por producto.
- Implementar módulo de reportes con exportación PDF y Excel.
- Implementar panel de auditoría (solo Admin/Supervisor).
- Implementar panel de administración: gestión de usuarios y parámetros del sistema.

## Capabilities

### New Capabilities

- `shell-and-routing`: Estructura del proyecto, router (React Router v6), layout con sidebar, protección de rutas por rol.
- `auth-ui`: Pantallas de login, cambio de contraseña, contexto de autenticación, interceptor Axios con refresco de token.
- `catalog-ui`: CRUD de categorías (árbol jerárquico), CRUD de productos con atributos dinámicos y filtros avanzados.
- `inventory-movements-ui`: Formularios para IN/EG con líneas múltiples; flujo de solicitud → generación OTP → aprobación para BI/AI.
- `kardex-ui`: Vista de Kardex por producto con saldos iniciales/finales y filtro de fechas.
- `reports-ui`: Módulo de reportes con filtros, tabla de resultados y botones de exportación PDF/Excel.
- `audit-ui`: Tabla de auditoría paginada con filtros avanzados y exportación Excel.
- `admin-ui`: Gestión de usuarios (CRUD) y parámetros del sistema; acceso exclusivo Admin.

### Modified Capabilities

## Impact

- **Nuevo repositorio**: `osiris-inventario-fe` (separado del backend).
- **Dependencias nuevas**: Vite, React 18, TypeScript, Tailwind CSS, shadcn/ui, React Router v6, Axios, React Query (TanStack Query), React Hook Form, Zod, Recharts (para métricas en consolidado).
- **API consumida**: Todos los endpoints del backend en `/api/v1/` incluyendo auth, categories, products, inventory, kardex, reports, audit, admin.
- **Sin cambios en el backend**: El frontend consume la API existente sin modificaciones.
