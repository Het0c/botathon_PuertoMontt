# Botathon Puerto Montt · Cada hora cuenta

Base web **React + TypeScript + Vite**, con **Supabase para logs, revisiones y el plan aprobado**. La limpieza de datos la desarrolla el equipo en Python. Blue Prism permanece como componente del proceso del desafío; su integración real y el cálculo oficial los valida el equipo.

- [Aplicación web e instrucciones](cada-hora-cuenta/README.md)
- [Descargar base web v0.2.0](entregables/Botathon_Web_v0.2.0.zip?raw=true)
- [Contrato de resultados para Python/Blue Prism](cada-hora-cuenta/docs/CONTRATO.md)
- [Configuración de Supabase, usuarios y roles](cada-hora-cuenta/docs/SUPABASE.md)
- [Build y despliegue online](cada-hora-cuenta/docs/DESPLIEGUE.md)

## Arquitectura acordada

```text
Excel BUK/SIC
    → Python: limpieza (equipo)
    → Proceso del equipo / Blue Prism: cálculo y resultados validados
    → JSON de resultados
    → React: vista nacional, filtros y detalle
    → Supabase: revisiones, decisiones, logs y último plan aprobado
```

Una carga válida crea una revisión pendiente. Un revisor debe aprobarla para cambiar el plan visible. Un rechazo o un archivo inválido conserva la última versión aprobada. La demo funciona en memoria y se identifica en pantalla; la persistencia compartida requiere configurar el proyecto Supabase.

## Arranque

Se necesita Node 24. El frontend arranca sin un servidor Python local:

```bash
cd cada-hora-cuenta
npm ci
npm run dev
```

Para Supabase real, seguir su guía y configurar las variables públicas antes de compilar. Para generar la web: `npm run build`; salida `cada-hora-cuenta/dist/`. El workflow [React web](.github/workflows/web.yml) prueba y compila; permite desplegar manualmente a GitHub Pages una vez habilitado por el propietario.

## Traductor Python existente

El código original permanece en `bot_traductor.py`, con instrucciones en [LEEME.md](LEEME.md). Genera un libro intermedio para Blue Prism; el equipo implementará la adaptación de esa salida al JSON de resultados. La web no limpia los Excel ni certifica las fórmulas del kit.

```bash
pip install -r requirements.txt
python bot_traductor.py --contratos "Nac - Base contratos x mes.xlsx" --planificacion "Nac - Planificación Asistencial x mes.xlsx" --salida salida --csv
```

La documentación de pruebas está en [VALIDACION.md](cada-hora-cuenta/docs/VALIDACION.md). Los ejemplos del frontend son ficticios; no subir credenciales, nombres, RUT ni datos clínicos al repositorio.
