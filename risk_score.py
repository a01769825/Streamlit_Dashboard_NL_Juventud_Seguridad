"""
Cálculo del score de riesgo compuesto por colonia.

Fórmula MVP (simple y transparente a propósito — ajustar ponderaciones
con el equipo técnico del Consejo NL antes de usarla para decisiones reales):

    riesgo = 0.40 * abandono_normalizado   (promedio hombres+mujeres)
           + 0.40 * incidentes_normalizado
           - 0.20 * espacios_normalizado

- abandono_normalizado: tasa de abandono PROMEDIO (hombres y mujeres) de las
  escuelas de la colonia, normalizada 0-1.
- incidentes_normalizado: # incidentes en los últimos 180 días (los 7 delitos
  de Palermo + proxies REDIM), normalizado 0-1.
- espacios_normalizado: # espacios juveniles ACTIVOS, normalizado 0-1
  (factor protector, por eso resta).

El resultado se reescala a 0-100 y se clasifica en semáforo (Verde/Amarillo/Rojo).

--------------------------------------------------------------------------
ALERTA DE GÉNERO — por qué es una columna SEPARADA y no se mezcla al score
--------------------------------------------------------------------------
El documento "Perspectiva de Género NL" advierte explícitamente: un sistema
que asuma patrones pasivos para niñas y activos para varones subestimaría
el riesgo de una parte de la población femenina. Si el riesgo de género se
promediara dentro de un solo score compuesto, una colonia con desapariciones
de mujeres muy por encima de lo esperado podría "esconderse" detrás de un
score general bajo (p. ej., si el abandono escolar masculino es bajo ahí).

Por eso `alerta_genero` se calcula y se muestra como un indicador propio,
visible siempre, independientemente del semáforo general:
    razón_mujeres_hombres = desapariciones_mujeres / desapariciones_hombres
    alerta_genero = "Sí" si razón >= 2.0 (umbral documentado para NL:
                     la proporción de mujeres desaparecidas duplica a la
                     de hombres) Y hay al menos 3 reportes en la colonia
                     (para no alertar sobre ruido estadístico en n muy bajas)
"""

import numpy as np
import pandas as pd


def _normalizar(serie: pd.Series) -> pd.Series:
    if serie.max() == serie.min():
        return pd.Series(0.0, index=serie.index)
    return (serie - serie.min()) / (serie.max() - serie.min())


def calcular_riesgo_por_colonia(colonias, escuelas, incidentes, espacios, desapariciones=None):
    df = colonias.copy().set_index("colonia_id")

    # --- Abandono escolar (promedio hombres/mujeres, + desglose visible) ---
    abandono_h = escuelas.groupby("colonia_id")["tasa_abandono_hombres_pct"].mean()
    abandono_m = escuelas.groupby("colonia_id")["tasa_abandono_mujeres_pct"].mean()
    df["abandono_hombres_pct"] = abandono_h.reindex(df.index).fillna(0).round(1)
    df["abandono_mujeres_pct"] = abandono_m.reindex(df.index).fillna(0).round(1)
    df["abandono_prom_pct"] = ((df["abandono_hombres_pct"] + df["abandono_mujeres_pct"]) / 2).round(1)

    # --- Imputación de adolescentes por plantel (proxy de reclutamiento) ---
    imputados = escuelas.groupby("colonia_id")["adolescentes_imputados_180d"].sum()
    df["adolescentes_imputados_180d"] = imputados.reindex(df.index).fillna(0)

    # --- Incidentes (7 delitos de Palermo + proxies REDIM) ---
    n_incidentes = incidentes.groupby("colonia_id").size()
    df["n_incidentes_180d"] = n_incidentes.reindex(df.index).fillna(0)

    # --- Espacios juveniles activos (factor protector) ---
    n_espacios_activos = (
        espacios[espacios["estado"] == "Activo"].groupby("colonia_id").size()
    )
    df["n_espacios_activos"] = n_espacios_activos.reindex(df.index).fillna(0)

    # --- Score compuesto (sin género, ver nota arriba) ---
    df["_abandono_n"] = _normalizar(df["abandono_prom_pct"])
    df["_incidentes_n"] = _normalizar(df["n_incidentes_180d"])
    df["_espacios_n"] = _normalizar(df["n_espacios_activos"])

    score = 0.40 * df["_abandono_n"] + 0.40 * df["_incidentes_n"] - 0.20 * df["_espacios_n"]
    df["riesgo_score"] = ((score + 0.20) / 1.00 * 100).clip(0, 100).round(1)

    def semaforo(x):
        if x >= 67:
            return "Rojo"
        if x >= 34:
            return "Amarillo"
        return "Verde"

    df["semaforo"] = df["riesgo_score"].apply(semaforo)

    # --- Alerta de género (indicador independiente, ver docstring) ---
    if desapariciones is not None and not desapariciones.empty:
        des_m = desapariciones[desapariciones["sexo"] == "Mujer"].groupby("colonia_id").size()
        des_h = desapariciones[desapariciones["sexo"] == "Hombre"].groupby("colonia_id").size()
        df["desapariciones_mujeres_180d"] = des_m.reindex(df.index).fillna(0)
        df["desapariciones_hombres_180d"] = des_h.reindex(df.index).fillna(0)
        total = df["desapariciones_mujeres_180d"] + df["desapariciones_hombres_180d"]
        razon = df["desapariciones_mujeres_180d"] / df["desapariciones_hombres_180d"].replace(0, np.nan)
        df["alerta_genero"] = np.where(
            (razon >= 2.0) & (total >= 3), "⚠️ Sí", "No"
        )
    else:
        df["desapariciones_mujeres_180d"] = 0
        df["desapariciones_hombres_180d"] = 0
        df["alerta_genero"] = "Sin datos"

    return df.drop(columns=["_abandono_n", "_incidentes_n", "_espacios_n"]).reset_index()
