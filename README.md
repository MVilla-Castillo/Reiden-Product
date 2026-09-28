# CRM para concesionaria automotriz

Sistema de gestión de leads desarrollado para una automotora de sucursal
única. El proyecto nació de un acercamiento directo al cliente, sin
convenio institucional ni programa de práctica de por medio.

## El problema

La automotora recibía alrededor de 600 leads mensuales desde redes
sociales y convertía cerca de 5 a venta. El equipo comercial —un
administrador y 4 vendedores— no tenía criterio de priorización ni
trazabilidad del seguimiento: los contactos llegaban a un canal común,
se atendían por orden de llegada y no quedaba registro de en qué punto
del proceso se perdían.

## La solución

Una máquina de estados finitos de 5 estados que modela el ciclo de vida
del lead, con categorización para separar contactos con intención de
compra del volumen general, y asignación trazable por vendedor.

### Decisiones de diseño

**Modelo de datos.** PostgreSQL con histórico de estados del lead: cada
transición queda registrada en lugar de sobrescribir el estado anterior.
Esto permite reconstruir en qué etapa se pierden los contactos, que era
justamente lo que el cliente no podía ver. La relación
cliente–vehículo–cotización se modeló para soportar múltiples
cotizaciones por cliente sobre distintas unidades.

**Arquitectura.** Separación hexagonal con la lógica de dominio aislada
de la infraestructura, siguiendo principios SOLID. La FSM vive en el
dominio y no depende del framework, lo que permite cambiar la capa de
persistencia o la interfaz sin tocar las reglas de transición.

**Control de acceso.** Tres perfiles con aislamiento de datos: un
vendedor accede solo a sus leads y conversaciones, el administrador ve
la operación completa, y un perfil de desarrollo para mantenimiento.
El aislamiento se aplica a nivel de consulta, no de interfaz.

**Flujos automatizados.** Categorización, asignación, seguimiento y
alertas.

## Stack

- **Backend:** Python / Django
- **Base de datos:** PostgreSQL
- **Frontend:** Angular
- **Contenerización:** Docker / docker-compose
- **Testing:** pytest
- **Despliegue:** Railway
- **Gestión de dependencias:** uv

## Estructura

```
core/       Lógica de dominio y componentes transversales
crm/        Módulo de gestión de leads, FSM y perfiles
frontend/   Cliente Angular
docs/       Documentación del proyecto
```

## Estado del proyecto

Frontend desplegado en Railway. El desarrollo se detuvo a tres semanas
del despliegue del backend: el dueño vendió la empresa y se retiró del
rubro. El código queda como referencia del diseño y la implementación
alcanzada.

## Sobre el desarrollo

Proyecto de dos desarrolladores, con asistencia de agentes de IA bajo
dirección técnica propia (ver `AGENTS.md`). Las decisiones de
arquitectura, el modelo de datos, el diseño de la FSM y los criterios
de aceptación de las pruebas fueron definidos por el equipo; la
generación de código se apoyó en agentes.

## Ejecución local

[Completar: comandos de docker-compose y variables de entorno
necesarias según .env.example]
