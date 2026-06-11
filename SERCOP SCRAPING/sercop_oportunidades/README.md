# SERCOP Oportunidades

Dashboard Streamlit para identificar oportunidades de contratación pública en Ecuador relevantes para una firma de servicios profesionales.

## Funcionalidades

- Consulta la API oficial OCDS del SERCOP.
- Busca oportunidades por palabras clave de cuatro líneas de negocio.
- Normaliza procesos OCDS en una tabla operativa.
- Muestra el código del proceso y un enlace de verificación al buscador SOCE.
- Calcula un score de 0 a 100 con desglose por criterio.
- Permite filtrar por línea, fecha de cierre, monto, estado y score.
- Mantiene procesos revisados durante la sesión con `st.session_state`.
- Exporta la tabla filtrada a CSV.
- Incluye gráficos de distribución por línea y score vs. monto.

## Nota sobre la API

La documentación pública vigente del SERCOP indica estos endpoints:

- Búsqueda: `https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/api/search_ocds`
- Detalle por OCID: `https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/api/record?ocid=...`

El requerimiento menciona `/releases` y `/release/{ocid}`. La implementación usa los endpoints oficiales documentados y conserva la terminología de "releases" dentro del código de la aplicación.

Los estados y fases que aparecen en el dashboard provienen de Datos Abiertos/OCDS. Para decisiones comerciales, valida el código del proceso en el SOCE, porque el portal transaccional puede reflejar cambios antes que el portal de datos abiertos.

## Instalación local

Requisitos:

- Python 3.11 o superior
- Acceso a internet para consultar la API del SERCOP

Crear y activar un entorno virtual:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r sercop_oportunidades/requirements.txt
```

Ejecutar:

```powershell
streamlit run sercop_oportunidades/app.py
```

## Uso

1. Ajusta los filtros del sidebar.
2. Usa "Actualizar datos" para limpiar cache y volver a consultar.
3. Selecciona una fila de la tabla para ver el detalle, desglose del score y enlace al portal SERCOP.
4. Marca procesos como revisados durante la sesión.
5. Exporta el resultado filtrado a CSV cuando necesites compartirlo.

## Scoring

El score total suma hasta 100 puntos:

- Palabras clave: 40 puntos.
- Monto presupuestado: 25 puntos, con escala logarítmica y máximo para montos desde USD 50.000.
- Días hábiles hasta cierre: 20 puntos, favoreciendo entre 5 y 20 días hábiles.
- Entidad contratante conocida: 10 puntos.
- Tipo de proceso preferido: 5 puntos.

## Despliegue en Streamlit Community Cloud

El repositorio ya incluye:

- Dependencias Python fijadas en `sercop_oportunidades/requirements.txt`.
- Configuración de Streamlit en `.streamlit/config.toml`.
- Exclusiones para archivos locales y secretos en `.gitignore`.

Para desplegar:

1. Sube el contenido completo de `SERCOP SCRAPING` a un repositorio de GitHub.
2. En Streamlit Community Cloud, selecciona **Create app**.
3. Selecciona el repositorio y la rama que contiene la app.
4. Usa `sercop_oportunidades/app.py` como **Main file path**.
5. En **Advanced settings**, selecciona Python 3.11.
6. Despliega. La app no requiere secretos ni dependencias del sistema.

Para probar localmente de la misma forma en que se ejecutará en Community Cloud, inicia Streamlit desde la raíz del repositorio:

```powershell
streamlit run sercop_oportunidades/app.py
```

## Estructura

```text
sercop_oportunidades/
├── app.py
├── api/
│   └── sercop_client.py
├── core/
│   ├── keywords.py
│   └── scorer.py
├── ui/
│   ├── cards.py
│   └── filters.py
├── requirements.txt
└── README.md
```

Archivos de despliegue ubicados en la raíz del repositorio:

```text
.streamlit/config.toml
.gitignore
README.md
```
