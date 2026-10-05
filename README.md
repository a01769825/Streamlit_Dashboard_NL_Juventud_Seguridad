# MVP — Dashboard de Riesgo Territorial

Ecosistema de prevención escolar-comunitaria del reclutamiento juvenil (AMM) ·
Concurso Red de Conocimiento 2026 · Consejo Nuevo León

⚠️ **Los datos incluidos son SINTÉTICOS** (generados con una semilla fija para
que sean reproducibles). Sirven para probar el dashboard, no para tomar
decisiones. Ver la sección 6 para reemplazarlos por datos reales.

---

## 1. Qué contiene esta carpeta

```
risk_dashboard_mvp/
├── app.py                 # La aplicación Streamlit (lo que ejecutas)
├── risk_score.py           # Lógica del score de riesgo (separada, fácil de ajustar)
├── data_generator.py       # Script que generó los CSV de prueba (opcional, no se usa al correr la app)
├── requirements.txt        # Librerías necesarias
├── README.md                # Este archivo
└── data/
    ├── colonias.csv
    ├── escuelas.csv          # ahora con abandono por SEXO + imputación de adolescentes
    ├── incidentes.csv         # tipología real: 7 delitos de Palermo + 3 proxies REDIM
    ├── espacios_juveniles.csv
    └── desapariciones.csv     # NUEVO: reportes de desaparición de adolescentes, por sexo
```

## 0. Cambios de esta versión (v2) — por qué se añadió una dimensión de género

Esta versión incorpora hallazgos del documento "Perspectiva de Género NL" que
no estaban en la v1:

1. **Tipología de incidentes corregida**: ya no son categorías genéricas,
   sino los 7 delitos de Palermo que concentran la mayoría de los casos de
   adolescentes privados de la libertad + los 3 proxies que REDIM agregó
   para México (portación de armas, privación de la libertad, asociación
   delictuosa).
2. **Abandono escolar desagregado por sexo** (`tasa_abandono_hombres_pct`,
   `tasa_abandono_mujeres_pct`) en vez de una sola tasa promedio.
3. **Nueva capa de desapariciones de adolescentes, por sexo** — indicador
   citado explícitamente como disponible en registros administrativos.
4. **`alerta_genero` como indicador INDEPENDIENTE** del score de riesgo
   general (ver `risk_score.py` para la justificación completa): evita que
   el riesgo específico hacia las mujeres quede escondido dentro de un
   promedio general.

**Lo que se dejó fuera a propósito:** cualquier dato sobre quién recluta
dentro de la familia (ej. el hallazgo de que la madre es nombrada como
reclutadora en algunos casos de NL). Ese tipo de información es sensible,
no es territorial/geográfica, y cartografiarla sería inapropiado y
potencialmente peligroso. Se maneja únicamente a nivel de protocolo
familiar/SAT, fuera de este dashboard.

## 2. Instalación (una sola vez)

Necesitas Python 3.10+ instalado. Luego, en una terminal, dentro de esta carpeta:

```bash
# (recomendado) crear un entorno virtual
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate

# instalar dependencias
pip install -r requirements.txt
```

## 3. Ejecutar el dashboard

```bash
streamlit run app.py
```

Esto abre automáticamente tu navegador en `http://localhost:8501`. Si no se
abre solo, copia esa URL en el navegador.

Para detenerlo: `Ctrl + C` en la terminal.

## 4. Qué puedes hacer en el MVP

- **Filtrar** por municipio/polígono desde la barra lateral.
- **Activar/desactivar capas** del mapa: riesgo por colonia (burbujas rojo/
  amarillo/verde), escuelas (coloreadas por tasa de abandono), mapa de calor
  de incidentes, espacios juveniles (activos/subutilizados/abandonados).
- **Ver las tablas** de detalle en las 4 pestañas inferiores.
- **Descargar** la tabla de riesgo por colonia en CSV (botón en la pestaña 1).

## 5. Cómo funciona el score de riesgo (resumen)

Ver `risk_score.py` para el detalle exacto y los comentarios. En resumen,
por cada colonia:

```
riesgo = 0.40 × (abandono escolar normalizado)
       + 0.40 × (incidentes en 180 días, normalizado)
       − 0.20 × (espacios juveniles activos, normalizado)
```

Reescalado a 0–100 y clasificado en semáforo (Verde / Amarillo / Rojo). **Las
ponderaciones (0.40 / 0.40 / 0.20) son un punto de partida razonable, no una
verdad fija** — deben discutirse con el equipo técnico del Consejo NL y, si
es posible, validarse contra casos ya conocidos (p. ej., ¿coincide con las
colonias que el Observatorio de Seguridad ya identifica como prioritarias?).

## 6. Cómo conectar datos reales (el paso más importante)

El dashboard no necesita que cambies el código de `app.py` ni de
`risk_score.py` — solo reemplaza los 4 archivos CSV en `data/`, **manteniendo
exactamente los mismos nombres de columna**:

| Archivo | Columnas requeridas | Fuente sugerida |
|---|---|---|
| `colonias.csv` | `colonia_id, colonia_nombre, municipio, lat, lon` | Catastro municipal / IMPLAN |
| `escuelas.csv` | `escuela_id, escuela_nombre, colonia_id, municipio, lat, lon, matricula, tasa_abandono_hombres_pct, tasa_abandono_mujeres_pct, adolescentes_imputados_180d` | SEP NL / estudio de abandono EMS (CONL 2026); imputación vía Fiscalía/INEGI |
| `incidentes.csv` | `incidente_id, colonia_id, municipio, lat, lon, tipo, sexo_adolescente_vinculado, fecha` | Observatorio de Seguridad, Consejo NL. `tipo` debe ser uno de los 7 delitos de Palermo + 3 proxies REDIM (ver lista en `data_generator.py`) |
| `espacios_juveniles.csv` | `espacio_id, espacio_nombre, colonia_id, municipio, lat, lon, tipo, estado` | Relevamiento propio / municipios |
| `desapariciones.csv` | `reporte_id, colonia_id, municipio, lat, lon, sexo, fecha` | Fiscalía NL / REDIM — reportes de no localización de adolescentes |

**Nota sobre incidentes:** si el Observatorio de Seguridad solo publica
cifras agregadas (por municipio o por trimestre, no por coordenada), una
alternativa realista para el piloto es estimar la distribución dentro de
cada colonia usando la densidad poblacional como proxy, y dejarlo
explícitamente marcado como "estimado" en el dashboard (agregar una columna
`es_estimado: true/false`). Esto hay que decidirlo con el equipo del
Observatorio — no inventar precisión que no existe.

Si en vez de CSV terminas con los datos en una hoja de Google Sheets o en
una base de datos, el único cambio necesario es la función `cargar_datos()`
al inicio de `app.py` — el resto de la aplicación no cambia.

## 7. Próximos pasos razonables después de este MVP

1. Validar la fórmula de riesgo con el equipo técnico del Consejo NL.
2. Reemplazar los CSV sintéticos por datos reales (sección 6).
3. Agregar autenticación simple si el dashboard va a compartirse fuera del
   equipo (Streamlit soporta esto vía `streamlit-authenticator` o,
   más simple, desplegando en un entorno con acceso restringido).
4. Desplegarlo para que el Consejo NL pueda verlo sin instalar nada:
   la opción más rápida y gratuita es
   [Streamlit Community Cloud](https://streamlit.io/cloud) — conectas el
   repositorio de GitHub y se publica solo. Para un despliegue interno
   controlado por NL, otra opción es un contenedor Docker simple (decirme
   si quieres que prepare el `Dockerfile`).
5. Conectar este dashboard con el Sistema de Alerta Temprana (SAT) escolar
   descrito en el plan general, para que la capa de "escuelas" se actualice
   automáticamente con los semáforos individuales por estudiante (agregados
   a nivel escuela, nunca mostrando datos de un estudiante identificable).
