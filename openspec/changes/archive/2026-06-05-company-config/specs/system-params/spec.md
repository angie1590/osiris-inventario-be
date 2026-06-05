## ADDED Requirements

### Requirement: Nuevas claves de parámetros del sistema
El seed inicial debe incluir las nuevas claves de configuración del sistema relacionadas con documentación y reportes.

#### Scenario: Claves requeridas al inicializar
- **WHEN** se ejecuta el seed por primera vez
- **THEN** se crean las claves `doc_number_prefix` (default: `"OSR"`), `doc_number_padding` (default: `"6"`), y `report_include_logo` (default: `"true"`) si no existen

#### Scenario: Idempotencia
- **WHEN** el seed se ejecuta más de una vez
- **THEN** no se crean duplicados ni se sobreescriben valores existentes
