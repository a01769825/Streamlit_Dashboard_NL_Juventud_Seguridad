"""
MVP — Dashboard de Riesgo Territorial
Ecosistema de prevención escolar-comunitaria del reclutamiento juvenil, AMM.

Ejecutar con:  streamlit run app.py
"""

import pandas as pd
import pydeck as pdk
import streamlit as st

from risk_score import calcular_riesgo_por_colonia

st.set_page_config(
    page_title="Riesgo Territorial — Prevención Juvenil AMM",
    page_icon="🧭",
    layout="wide",
)

# ---------------------------------------------------------------------------
# 1. CARGA DE DATOS
# ---------------------------------------------------------------------------
# NOTA: estos CSV son SINTÉTICOS. Ver README.md -> "Cómo conectar datos reales"
# para reemplazarlos sin tener que tocar el resto del código.


@st.cache_data
def cargar_datos():
    colonias = pd.read_csv("data/colonias.csv")
    escuelas = pd.read_csv("data/escuelas.csv")
    incidentes = pd.read_csv("data/incidentes.csv")
    espacios = pd.read_csv("data/espacios_juveniles.csv")
    desapariciones = pd.read_csv("data/desapariciones.csv")
    return colonias, escuelas, incidentes, espacios, desapariciones


colonias, escuelas, incidentes, espacios, desapariciones = cargar_datos()
riesgo = calcular_riesgo_por_colonia(colonias, escuelas, incidentes, espacios, desapariciones)

# ---------------------------------------------------------------------------
# 2. BARRA LATERAL — FILTROS
# ---------------------------------------------------------------------------
st.sidebar.header("Filtros")

municipios_disponibles = sorted(riesgo["municipio"].unique())
municipios_sel = st.sidebar.multiselect(
    "Municipio / polígono",
    options=municipios_disponibles,
    default=municipios_disponibles,
)

st.sidebar.markdown("---")
st.sidebar.subheader("Capas en el mapa")
mostrar_colonias = st.sidebar.checkbox("Riesgo por colonia (burbujas)", value=True)
mostrar_escuelas = st.sidebar.checkbox("Escuelas (abandono escolar)", value=True)
mostrar_incidentes = st.sidebar.checkbox("Incidentes delictivos (7 delitos de Palermo)", value=False)
mostrar_espacios = st.sidebar.checkbox("Espacios juveniles", value=True)
mostrar_desapariciones = st.sidebar.checkbox("⚠️ Desapariciones de adolescentes (por sexo)", value=True)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Datos sintéticos de demostración — semilla fija, no representan "
    "cifras reales de Nuevo León. Ver README.md antes de usarlo con "
    "funcionarios del Consejo NL."
)
st.sidebar.caption(
    "⚠️ Este dashboard muestra riesgo TERRITORIAL. Deliberadamente NO "
    "incluye quién recluta dentro de la familia (hallazgo del documento "
    "de Perspectiva de Género): ese dato es sensible, no geográfico, y "
    "debe manejarse solo a nivel del protocolo familiar/SAT, nunca en "
    "un mapa."
)

# Aplicar filtro de municipio a todas las tablas
riesgo_f = riesgo[riesgo["municipio"].isin(municipios_sel)]
colonia_ids_f = set(riesgo_f["colonia_id"])
escuelas_f = escuelas[escuelas["colonia_id"].isin(colonia_ids_f)]
incidentes_f = incidentes[incidentes["colonia_id"].isin(colonia_ids_f)]
espacios_f = espacios[espacios["colonia_id"].isin(colonia_ids_f)]
desapariciones_f = desapariciones[desapariciones["colonia_id"].isin(colonia_ids_f)]

# ---------------------------------------------------------------------------
# 3. ENCABEZADO + KPIs
# ---------------------------------------------------------------------------
st.title("🧭 Dashboard de Riesgo Territorial — MVP")
st.caption(
    "Ecosistema de prevención escolar-comunitaria del reclutamiento juvenil · "
    "Piloto AMM · Concurso Red de Conocimiento 2026"
)

n_rojo = (riesgo_f["semaforo"] == "Rojo").sum()
n_amarillo = (riesgo_f["semaforo"] == "Amarillo").sum()
n_verde = (riesgo_f["semaforo"] == "Verde").sum()
n_alerta_genero = (riesgo_f["alerta_genero"] == "⚠️ Sí").sum()

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Colonias analizadas", len(riesgo_f))
col2.metric("🔴 Riesgo alto", int(n_rojo))
col3.metric("🟡 Riesgo medio", int(n_amarillo))
col4.metric("🟢 Riesgo bajo", int(n_verde))
col5.metric("Incidentes (180 días)", len(incidentes_f))
col6.metric("⚠️ Alertas de género", int(n_alerta_genero), help="Colonias donde las desapariciones de mujeres duplican o más a las de hombres (umbral documentado para NL)")

# Fila adicional: brecha de abandono escolar por sexo (no ocultar un sexo dentro de un promedio)
if not escuelas_f.empty:
    prom_h = escuelas_f["tasa_abandono_hombres_pct"].mean()
    prom_m = escuelas_f["tasa_abandono_mujeres_pct"].mean()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Abandono escolar — hombres", f"{prom_h:.1f}%")
    col_b.metric("Abandono escolar — mujeres", f"{prom_m:.1f}%")
    col_c.metric("Desapariciones mujeres vs. hombres (180d)", f"{len(desapariciones_f[desapariciones_f['sexo']=='Mujer'])} vs. {len(desapariciones_f[desapariciones_f['sexo']=='Hombre'])}")

st.markdown("---")

# ---------------------------------------------------------------------------
# 4. MAPA (pydeck, capas activables)
# ---------------------------------------------------------------------------
COLOR_SEMAFORO = {
    "Rojo": [220, 53, 69, 180],
    "Amarillo": [255, 193, 7, 180],
    "Verde": [40, 167, 69, 180],
}

capas = []

# 1. Capa de Riesgo por colonia (Burbujas)
if mostrar_colonias and not riesgo_f.empty:
    riesgo_plot = riesgo_f.copy()
    
    # Conversion securisee en couleur RGB
    def get_color_semaforo(sem):
        sem_str = str(sem).lower()
        if "alto" in sem_str:
            return [220, 50, 50, 180]   # Rouge
        elif "medio" in sem_str:
            return [230, 180, 40, 180]  # Jaune
        return [50, 180, 80, 180]       # Vert

    riesgo_plot["color_rgb"] = riesgo_plot["semaforo"].apply(get_color_semaforo)
    riesgo_plot["radio"] = 150 + riesgo_plot["riesgo_score"] * 6

    capas.append(
        pdk.Layer(
            "ScatterplotLayer",  # <- Nom exact requis par Pydeck
            data=riesgo_plot,
            get_position=["lon", "lat"],
            get_fill_color="color_rgb",
            get_radius="radio",
            pickable=True,
            opacity=0.8,
            stroked=True,
            get_line_color=[0, 0, 0, 120],
        )
    )

# 2. Capa de Escuelas
if mostrar_escuelas and not escuelas_f.empty:
    esc_plot = escuelas_f.copy()
    esc_plot["tasa_avg"] = (esc_plot["tasa_abandono_hombres_pct"] + esc_plot["tasa_abandono_mujeres_pct"]) / 2
    esc_plot["color_rgb"] = esc_plot["tasa_avg"].apply(
        lambda x: [180, 30, 30, 220] if x >= 18 else [230, 140, 30, 220] if x >= 10 else [60, 120, 200, 220]
    )

    capas.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=esc_plot,
            get_position=["lon", "lat"],
            get_fill_color="color_rgb",
            get_radius=180,
            pickable=True,
        )
    )

# 3. Capa de Incidentes (Heatmap)
if mostrar_incidentes and not incidentes_f.empty:
    capas.append(
        pdk.Layer(
            "HeatmapLayer",
            data=incidentes_f,
            get_position=["lon", "lat"],
            radius_pixels=60,
            intensity=1,
            threshold=0.05,
        )
    )

# 4. Capa de Espacios juveniles
if mostrar_espacios and not espacios_f.empty:
    esp_plot = espacios_f.copy()
    esp_plot["color_rgb"] = esp_plot["estado"].apply(
        lambda e: [40, 180, 90, 200] if e == "activo" else [220, 160, 40, 200] if e == "subutilizado" else [120, 120, 120, 200]
    )
    capas.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=esp_plot,
            get_position=["lon", "lat"],
            get_fill_color="color_rgb",
            get_radius=150,
            pickable=True,
        )
    )

# 5. Capa de Desapariciones
if mostrar_desapariciones and not desapariciones_f.empty:
    des_plot = desapariciones_f.copy()
    des_plot["color_rgb"] = des_plot["sexo"].apply(
        lambda s: [160, 60, 200, 220] if str(s).lower().startswith("m") or str(s).lower() == "femenino" else [40, 120, 220, 220]
    )
    capas.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=des_plot,
            get_position=["lon", "lat"],
            get_fill_color="color_rgb",
            get_radius=200,
            pickable=True,
        )
    )

if mostrar_escuelas and not escuelas_f.empty:
    esc_plot = escuelas_f.copy()
    esc_plot["tasa_abandono_pct"] = (esc_plot["tasa_abandono_hombres_pct"] + esc_plot["tasa_abandono_mujeres_pct"]) / 2
    esc_plot["color"] = esc_plot["tasa_abandono_pct"].apply(
        lambda x: [180, 30, 30, 200] if x >= 18 else [230, 140, 30, 200] if x >= 10 else [60, 120, 200, 200]
    
    )
    capas.append(
        pdk.Layer(
            "ScatterLayer",
            data=esc_plot,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=90,
            pickable=True,
            stroked=True,
            get_line_color=[255, 255, 255, 180],
        )
    )

if mostrar_incidentes and not incidentes_f.empty:
    capas.append(
        pdk.Layer(
            "HeatmapLayer",
            data=incidentes_f,
            get_position=["lon", "lat"],
            opacity=0.4,
        )
    )

if mostrar_desapariciones and not desapariciones_f.empty:
    des_plot = desapariciones_f.copy()
    des_plot["color"] = des_plot["sexo"].map(
        {"Mujer": [155, 30, 150, 220], "Hombre": [30, 100, 180, 220]}
    )
    capas.append(
        pdk.Layer(
            "ScatterLayer",
            data=des_plot,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=110,
            pickable=True,
            stroked=True,
            get_line_color=[255, 255, 255, 200],
        )
    )

if mostrar_espacios and not espacios_f.empty:
    esp_plot = espacios_f.copy()
    esp_plot["color"] = esp_plot["estado"].map(
        {"Activo": [20, 120, 20, 220], "Subutilizado": [120, 120, 20, 220], "Abandonado": [100, 100, 100, 220]}
    )
    capas.append(
        pdk.Layer(
            "ScatterLayer",
            data=esp_plot,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=70,
            pickable=True,
        )
    )

if colonias["lat"].notna().any():
    vista_inicial = pdk.ViewState(
        latitude=float(colonias["lat"].mean()),
        longitude=float(colonias["lon"].mean()),
        zoom=9.3,
        pitch=0,
    )
else:
    vista_inicial = pdk.ViewState(latitude=25.72, longitude=-100.35, zoom=9)

if not riesgo_f.empty:
    lat_center = float(riesgo_f["lat"].mean())
    lon_center = float(riesgo_f["lon"].mean())
else:
    lat_center, lon_center = 25.72, -100.35

vista_inicial = pdk.ViewState(
    latitude=lat_center,
    longitude=lon_center,
    zoom=10.5,
    pitch=0,
)

st.pydeck_chart(
    pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        initial_view_state=vista_inicial,
        layers=capas,
        tooltip={"text": "{colonia_nombre}\n{escuela_nombre}"},
    )
)

leyenda_cols = st.columns(6)
leyenda_cols[0].markdown("🔴 Riesgo alto / abandono alto")
leyenda_cols[1].markdown("🟡 Riesgo medio")
leyenda_cols[2].markdown("🟢 Riesgo bajo / espacio activo")
leyenda_cols[3].markdown("🔵 Escuela (abandono bajo)")
leyenda_cols[4].markdown("🟣 Desaparición — mujer")
leyenda_cols[5].markdown("🔷 Desaparición — hombre")

st.markdown("---")

# ---------------------------------------------------------------------------
# 5. TABLAS DE DETALLE
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Riesgo por colonia", "🏫 Escuelas (por sexo)", "🚨 Incidentes", "👤 Desapariciones", "🏀 Espacios juveniles"]
)

with tab1:
    st.dataframe(
        riesgo_f[
            [
                "colonia_nombre", "municipio", "semaforo", "riesgo_score", "alerta_genero",
                "abandono_hombres_pct", "abandono_mujeres_pct",
                "n_incidentes_180d", "adolescentes_imputados_180d",
                "desapariciones_mujeres_180d", "desapariciones_hombres_180d",
                "n_espacios_activos",
            ]
        ].sort_values("riesgo_score", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "`alerta_genero` es un indicador INDEPENDIENTE del semáforo general "
        "(ver risk_score.py): una colonia puede salir en verde en el score "
        "compuesto y aun así tener una alerta de género activa — a propósito, "
        "para no esconder el riesgo femenino dentro de un promedio."
    )
    st.download_button(
        "⬇️ Descargar CSV de riesgo por colonia",
        riesgo_f.to_csv(index=False).encode("utf-8"),
        file_name="riesgo_por_colonia.csv",
        mime="text/csv",
    )

with tab2:
    st.dataframe(
        escuelas_f.sort_values("adolescentes_imputados_180d", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

with tab3:
    st.dataframe(incidentes_f.sort_values("fecha", ascending=False), use_container_width=True, hide_index=True)
    st.caption("Tipología = 7 delitos de Palermo + 3 proxies REDIM (no categorías genéricas).")

with tab4:
    st.dataframe(desapariciones_f.sort_values("fecha", ascending=False), use_container_width=True, hide_index=True)
    st.caption(
        "Indicador citado explícitamente como disponible en registros "
        "administrativos (documento Perspectiva de Género, sección 2)."
    )

with tab5:
    st.dataframe(espacios_f, use_container_width=True, hide_index=True)
