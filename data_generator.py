"""
Generador de datos sintéticos para el MVP del Dashboard de Riesgo Territorial.

IMPORTANTE: Estos son datos SINTÉTICOS (inventados pero geográficamente
realistas) para poder construir y probar el dashboard. Antes de presentarlo
al Consejo NL hay que reemplazar los 4 archivos CSV generados aquí con datos
reales (ver README.md, sección "Cómo conectar datos reales").

Fuentes que deberían reemplazar estos datos sintéticos:
- escuelas.csv       -> SEP NL / estudio de abandono escolar EMS (CONL 2026)
- incidentes.csv      -> Observatorio de Seguridad, Consejo NL (carpetas de
                         investigación geo-referenciadas, si están disponibles)
- espacios_juveniles.csv -> Catastro municipal / IMPLAN de cada municipio
- colonias.csv        -> Se calcula automáticamente agregando los 3 anteriores
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(seed=42)  # semilla fija = resultados reproducibles

# Centros aproximados (lat, lon) de los 5 polígonos prioritarios
MUNICIPIOS = {
    "García":               (25.8133, -100.5967),
    "Juárez":               (25.6487, -100.0956),
    "General Escobedo":     (25.7969, -100.3271),
    "Monterrey (Topo Chico)": (25.7340, -100.3407),
    "Santa Catarina":       (25.6736, -100.4581),
}

# Cuántas colonias sintéticas por municipio (ajustar cuando haya datos reales)
N_COLONIAS_POR_MUNICIPIO = 4


def jitter(lat, lon, km_radius=2.5, n=1):
    """Genera puntos aleatorios alrededor de un centro, dentro de un radio en km."""
    deg_radius = km_radius / 111.0  # 1 grado ~ 111 km
    angles = RNG.uniform(0, 2 * np.pi, n)
    radii = deg_radius * np.sqrt(RNG.uniform(0, 1, n))
    d_lat = radii * np.sin(angles)
    d_lon = radii * np.cos(angles) / np.cos(np.radians(lat))
    return lat + d_lat, lon + d_lon


def generar_colonias():
    rows = []
    colonia_id = 0
    for municipio, (lat0, lon0) in MUNICIPIOS.items():
        lats, lons = jitter(lat0, lon0, km_radius=3.0, n=N_COLONIAS_POR_MUNICIPIO)
        for i in range(N_COLONIAS_POR_MUNICIPIO):
            colonia_id += 1
            rows.append({
                "colonia_id": f"COL-{colonia_id:03d}",
                "colonia_nombre": f"Colonia {municipio.split()[0]} {i + 1}",
                "municipio": municipio,
                "lat": lats[i],
                "lon": lons[i],
            })
    return pd.DataFrame(rows)


def generar_escuelas(colonias_df):
    """
    Tasa de abandono separada por sexo.

    Ancla sintética: estudio de abandono EMS citado en el documento base
    (CONL/SE-NL/Tec/Capital Común, 2026) reporta a nivel estatal 10.4%
    hombres vs. 6.9% mujeres. Se usa esa brecha relativa (~1.5x) como
    referencia para generar los datos sintéticos por escuela, con
    variación realista alrededor de esa proporción (no siempre se cumple
    igual en cada plantel).

    adolescentes_imputados_180d: proxy de "Imputación de adolescentes por
    los siete delitos de Palermo, por plantel" (indicador explícitamente
    recomendado en el documento de Perspectiva de Género, sección 2).
    """
    rows = []
    escuela_id = 0
    for _, col in colonias_df.iterrows():
        n_escuelas = RNG.integers(1, 3)  # 1 o 2 escuelas EMS por colonia
        lats, lons = jitter(col["lat"], col["lon"], km_radius=0.8, n=n_escuelas)
        for i in range(n_escuelas):
            escuela_id += 1
            base = float(np.clip(RNG.normal(10, 5), 1, 35))
            # brecha hombres/mujeres variable alrededor de la razón ~1.5x
            razon = RNG.normal(1.5, 0.35)
            abandono_h = float(np.clip(base * max(razon, 0.4), 1, 40))
            abandono_m = float(np.clip(base / max(razon, 0.4), 1, 40))
            rows.append({
                "escuela_id": f"ESC-{escuela_id:03d}",
                "escuela_nombre": f"EMS Técnica {col['colonia_nombre']} #{i + 1}",
                "colonia_id": col["colonia_id"],
                "municipio": col["municipio"],
                "lat": lats[i],
                "lon": lons[i],
                "matricula": int(RNG.integers(150, 900)),
                "tasa_abandono_hombres_pct": round(abandono_h, 1),
                "tasa_abandono_mujeres_pct": round(abandono_m, 1),
                "adolescentes_imputados_180d": int(RNG.poisson(lam=max(base / 4, 0.3))),
            })
    return pd.DataFrame(rows)


def generar_incidentes(colonias_df, dias=180):
    """
    Tipología alineada a la metodología real del proyecto (no inventada):
    los 7 delitos de Palermo que concentran la mayoría de los casos de
    adolescentes privados de la libertad (REDIM/ONC) + los 3 proxies que
    REDIM agregó para el contexto mexicano. Fuente: documento "Perspectiva
    de Género NL", sección 2 (Medición del éxito o fracaso del proyecto).

    Pesos: extorsión y narcomenudeo se ponderan más alto porque el
    Observatorio de Seguridad de Consejo NL (hallazgo 2T-2026) reporta que
    son los delitos de Palermo que más han crecido recientemente.

    sexo_adolescente_vinculado: cuando el incidente corresponde a un
    adolescente imputado, se asigna sexo con las proporciones reales
    reportadas por REDIM/ONC (2019) para cada tipo de delito. Para tipos
    sin ese desglose documentado se deja "No aplica".
    """
    rows = []
    inc_id = 0

    # (tipo, peso, proporción de mujeres entre adolescentes vinculados o None)
    tipos_info = [
        ("Extorsión", 0.20, None),
        ("Narcotráfico (narcomenudeo)", 0.18, 0.180),
        ("Feminicidio y homicidio", 0.07, 0.165),
        ("Lesiones", 0.15, None),
        ("Secuestro / privación de la libertad", 0.08, 0.281),
        ("Robo de vehículos", 0.12, None),
        ("Trata de personas", 0.03, 0.776),
        ("Portación/posesión ilícita de armas", 0.10, None),
        ("Asociación delictuosa", 0.07, None),
    ]
    tipos = [t[0] for t in tipos_info]
    pesos_tipo = [t[1] for t in tipos_info]
    pesos_tipo = list(np.array(pesos_tipo) / sum(pesos_tipo))
    prop_mujeres = {t[0]: t[2] for t in tipos_info}

    for _, col in colonias_df.iterrows():
        n_incidentes = RNG.poisson(lam=RNG.uniform(3, 18))
        lats, lons = jitter(col["lat"], col["lon"], km_radius=1.2, n=max(n_incidentes, 1))
        fechas = pd.Timestamp.today().normalize() - pd.to_timedelta(
            RNG.integers(0, dias, size=max(n_incidentes, 1)), unit="D"
        )
        tipos_asignados = RNG.choice(tipos, size=max(n_incidentes, 1), p=pesos_tipo)
        for i in range(n_incidentes):
            inc_id += 1
            tipo = tipos_asignados[i]
            p_mujer = prop_mujeres.get(tipo)
            if p_mujer is None:
                sexo = "No aplica"
            else:
                sexo = "Mujer" if RNG.random() < p_mujer else "Hombre"
            rows.append({
                "incidente_id": f"INC-{inc_id:04d}",
                "colonia_id": col["colonia_id"],
                "municipio": col["municipio"],
                "lat": lats[i],
                "lon": lons[i],
                "tipo": tipo,
                "sexo_adolescente_vinculado": sexo,
                "fecha": fechas[i].date().isoformat(),
            })
    return pd.DataFrame(rows)


def generar_desapariciones(colonias_df, dias=180):
    """
    Reportes de desaparición/no localización de adolescentes, por sexo.

    Indicador citado explícitamente como "ya disponible en registros
    administrativos" en el documento de Perspectiva de Género. Se simula
    con la proporción documentada para NL: la proporción de MUJERES entre
    adolescentes desaparecidos duplica a la de HOMBRES.
    """
    rows = []
    rep_id = 0
    for _, col in colonias_df.iterrows():
        n_reportes = RNG.poisson(lam=RNG.uniform(0.3, 2.5))
        if n_reportes == 0:
            continue
        lats, lons = jitter(col["lat"], col["lon"], km_radius=1.0, n=n_reportes)
        fechas = pd.Timestamp.today().normalize() - pd.to_timedelta(
            RNG.integers(0, dias, size=n_reportes), unit="D"
        )
        # proporción NL: mujeres ~2x hombres -> p(mujer) ≈ 0.67
        sexos = RNG.choice(["Mujer", "Hombre"], size=n_reportes, p=[0.67, 0.33])
        for i in range(n_reportes):
            rep_id += 1
            rows.append({
                "reporte_id": f"DES-{rep_id:03d}",
                "colonia_id": col["colonia_id"],
                "municipio": col["municipio"],
                "lat": lats[i],
                "lon": lons[i],
                "sexo": sexos[i],
                "fecha": fechas[i].date().isoformat(),
            })
    return pd.DataFrame(rows)


def generar_espacios_juveniles(colonias_df):
    rows = []
    esp_id = 0
    tipos = ["Cancha deportiva", "Centro comunitario", "Biblioteca", "Espacio cultural"]
    for _, col in colonias_df.iterrows():
        # entre 0 y 2 espacios activos por colonia (muchas colonias con 0 = oportunidad)
        n_espacios = RNG.choice([0, 1, 1, 2], p=[0.3, 0.35, 0.25, 0.10])
        if n_espacios == 0:
            continue
        lats, lons = jitter(col["lat"], col["lon"], km_radius=1.0, n=n_espacios)
        for i in range(n_espacios):
            esp_id += 1
            rows.append({
                "espacio_id": f"ESP-{esp_id:03d}",
                "espacio_nombre": f"{RNG.choice(tipos)} {col['colonia_nombre']}",
                "colonia_id": col["colonia_id"],
                "municipio": col["municipio"],
                "lat": lats[i],
                "lon": lons[i],
                "tipo": tipos[0],
                "estado": RNG.choice(["Activo", "Subutilizado", "Abandonado"], p=[0.4, 0.4, 0.2]),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    colonias = generar_colonias()
    escuelas = generar_escuelas(colonias)
    incidentes = generar_incidentes(colonias)
    espacios = generar_espacios_juveniles(colonias)
    desapariciones = generar_desapariciones(colonias)

    colonias.to_csv("data/colonias.csv", index=False)
    escuelas.to_csv("data/escuelas.csv", index=False)
    incidentes.to_csv("data/incidentes.csv", index=False)
    espacios.to_csv("data/espacios_juveniles.csv", index=False)
    desapariciones.to_csv("data/desapariciones.csv", index=False)

    print(f"Colonias: {len(colonias)}")
    print(f"Escuelas: {len(escuelas)}")
    print(f"Incidentes: {len(incidentes)}")
    print(f"Espacios juveniles: {len(espacios)}")
    print(f"Reportes de desaparición: {len(desapariciones)}")
    print("Archivos CSV generados en data/")
