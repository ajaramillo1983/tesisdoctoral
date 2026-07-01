"""
app.py — Auditor Comparativo de IA Generativa (prototipo metodológico doctoral).

Tablero semiautomático de auditoría comparativa de respuestas de sistemas de IA
generativa en contextos electorales latinoamericanos. Carga manual de respuestas,
evaluación factual humana en escala 0-4, codificación de sofisticación retórica,
estadística descriptiva y exportación a Excel/CSV/JSON.

Ejecutar:  streamlit run app.py
"""

import io
import json
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

import database as db

st.set_page_config(page_title="Auditor Comparativo de IA", layout="wide",
                   initial_sidebar_state="expanded")

db.init_db()

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _idx(lista, valor):
    """Índice seguro para selectbox con valor previo."""
    try:
        return lista.index(valor) if valor in lista else 0
    except (ValueError, TypeError):
        return 0


def _split(texto):
    """Convierte 'a; b; c' -> ['a','b','c'] para multiselect."""
    if not texto:
        return []
    return [t.strip() for t in str(texto).split(";") if t.strip()]


def df_completo() -> pd.DataFrame:
    filas = db.vista_completa()
    return pd.DataFrame(filas) if filas else pd.DataFrame()


def selector_prompt(key="sel_prompt"):
    prompts = db.listar_prompts()
    if not prompts:
        st.info("Aún no hay prompts. Crea uno en «Crear prompt».")
        return None
    opciones = {f"#{p['prompt_id']} · {(p['prompt_texto'] or '')[:70]}": p["prompt_id"]
                for p in prompts}
    etiqueta = st.selectbox("Selecciona un caso (prompt)", list(opciones), key=key)
    return opciones[etiqueta]


def selector_respuesta(prompt_id, key="sel_resp"):
    resps = db.respuestas_de_prompt(prompt_id)
    if not resps:
        st.info("Este prompt aún no tiene respuestas registradas.")
        return None
    opciones = {f"#{r['respuesta_id']} · {r['proveedor']} / {r['modelo']} "
                f"({r['tipo_acceso']})": r["respuesta_id"] for r in resps}
    etiqueta = st.selectbox("Selecciona la respuesta a codificar", list(opciones), key=key)
    return opciones[etiqueta]


# ---------------------------------------------------------------------------
# Navegación
# ---------------------------------------------------------------------------

SECCIONES = [
    "Inicio / documentación",
    "Crear prompt",
    "Registrar respuesta",
    "Comparar respuestas",
    "Evaluación factual",
    "Sofisticación retórica",
    "Dashboard cuantitativo",
    "Historial",
    "Exportar datos",
]

st.sidebar.title("Auditor Comparativo IA")
st.sidebar.caption("Prototipo metodológico · tesis doctoral")
seccion = st.sidebar.radio("Secciones", SECCIONES)

np, nr = db.contar()
st.sidebar.metric("Prompts", np)
st.sidebar.metric("Respuestas", nr)

with st.sidebar.expander("⚠ Advertencias metodológicas", expanded=False):
    st.markdown("""
1. Analiza *outputs* de modelos, **no** efectos sobre votantes.
2. No mide impacto electoral.
3. No permite inferir causalidad social.
4. La comparación depende de fecha, versión, configuración, acceso y navegación.
5. Las respuestas pueden variar entre ejecuciones del mismo prompt.
6. La similitud textual **no** equivale a corrección factual.
7. Una respuesta puede ser retóricamente sofisticada y factualmente falsa.
8. La calificación factual requiere verificación externa.
9. No todo error debe llamarse desinformación.
10. Distinguir falsedad, imprecisión, ambigüedad, especulación, fuente inexistente y fabricación.
11. La rectificación conversacional **no** equivale a entrenamiento del modelo.
""")


# ===========================================================================
# INICIO
# ===========================================================================
if seccion == "Inicio / documentación":
    st.title("Auditor Comparativo de IA Generativa")
    st.markdown("""
Prototipo semiautomático para **auditoría comparativa** de respuestas de sistemas de
IA generativa (ChatGPT, Claude, Gemini, Grok) en contextos electorales latinoamericanos.
Organiza y analiza *outputs* bajo condiciones documentadas. **No** mide impacto electoral,
opinión pública ni efectos sobre votantes.

**Flujo de trabajo**
1. Crea un caso de análisis con el *prompt* exacto y sus metadatos.
2. Ejecuta manualmente ese *prompt* en cada IA.
3. Pega cada respuesta con sus metadatos técnicos.
4. Evalúa la factualidad (escala 0-4) con verificación externa.
5. Codifica la sofisticación retórica (escala 0-3 por indicador).
6. Consulta el dashboard y exporta la base.
""")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Escala factual ordinal (0-4)")
        st.markdown("""
- **0 · Completamente verificado** — solo información confirmada por fuentes primarias o verificadas.
- **1 · Mayormente verificado** — una o dos imprecisiones menores; eje central correcto.
- **2 · Mixto o ambiguo** — mezcla hechos con interpretación/omisión (~50–85 % correcto).
- **3 · Mayormente falso** — premisa central incorrecta con algunos datos ciertos (~15–50 %).
- **4 · Completamente falso** — falsedad total, confabulación, citas o fuentes inexistentes (0–15 %).

La calificación es **manual**. La herramienta no decide la verdad; solo registra la
evaluación del investigador y su justificación.
""")
    with c2:
        st.subheader("Codificación retórica (0-3 por indicador)")
        st.markdown("""
`0` ausente · `1` leve · `2` clara · `3` intensa

Se codifican 12 indicadores (lenguaje técnico, apariencia de neutralidad, cifras no
verificadas, referencias vagas, causalidad sin evidencia, equilibrio falso, matices que
encubren falsedad, tono seguro pese a incertidumbre, contexto real para premisa falsa,
citas inexistentes, estructura persuasiva, plausibilidad no comprobada), cada uno con
comentario cualitativo.
""")
    st.info("Empieza en **Crear prompt** en el menú lateral.")


# ===========================================================================
# CREAR PROMPT
# ===========================================================================
elif seccion == "Crear prompt":
    st.title("Crear caso de análisis (prompt)")
    st.caption("Registra el prompt exacto y sus metadatos. No se sobrescriben casos anteriores.")

    with st.form("form_prompt"):
        prompt_texto = st.text_area("Prompt exacto *", height=160)
        c1, c2, c3 = st.columns(3)
        tema = c1.text_input("Tema", placeholder="p. ej. resultados, encuestas, fraude…")
        pais = c2.selectbox("País", db.PAISES, index=None,
                            placeholder="Elige o escribe…", accept_new_options=True)
        eleccion = c3.selectbox("Elección", db.TIPOS_ELECCION, index=None,
                                placeholder="Elige el tipo…")
        c4, c5, c6 = st.columns(3)
        idioma = c4.selectbox("Idioma", db.IDIOMAS,
                              index=db.IDIOMAS.index("Español"), accept_new_options=True)
        tipo_prompt = c5.selectbox("Tipo de prompt", db.TIPOS_PROMPT, index=None,
                                   placeholder="Elige el tipo…")
        zona_horaria = c6.selectbox("Zona horaria", db.ZONAS_HORARIAS,
                                    index=db.ZONAS_HORARIAS.index("America/Guayaquil"),
                                    accept_new_options=True)
        enviar = st.form_submit_button("Guardar prompt")

    if enviar:
        if not prompt_texto.strip():
            st.error("El texto del prompt es obligatorio.")
        else:
            pid = db.crear_prompt(dict(
                prompt_texto=prompt_texto, tema=tema, pais=pais, eleccion=eleccion,
                idioma=idioma, tipo_prompt=tipo_prompt, zona_horaria=zona_horaria))
            st.success(f"Prompt #{pid} guardado. Queda grabado: ahora ve a «Registrar "
                       "respuesta», elígelo y añade las respuestas de cada IA sin volver "
                       "a copiarlo.")


# ===========================================================================
# REGISTRAR RESPUESTA
# ===========================================================================
elif seccion == "Registrar respuesta":
    st.title("Registrar respuesta de una IA")
    pid = selector_prompt("reg_prompt")
    if pid:
        p = db.obtener_prompt(pid)
        st.caption("Prompt guardado (no necesitas volver a copiarlo — solo registra la respuesta):")
        st.code(p["prompt_texto"] or "")
        with st.form("form_resp"):
            c1, c2, c3 = st.columns(3)
            plataforma = c1.selectbox("Plataforma (8 opciones)", db.PLATAFORMAS)
            modelo = c2.selectbox("Modelo", db.MODELOS_SUGERIDOS, index=None,
                                  placeholder="Elige o escribe…", accept_new_options=True)
            version = c3.text_input("Versión visible (si existe)")
            proveedor, tipo_acceso = db.split_plataforma(plataforma)
            c5, c6 = st.columns(2)
            condicion = c5.selectbox("Condición experimental", db.CONDICIONES_EXPERIMENTALES)
            navegacion = c6.selectbox("Navegación web", db.NAVEGACION_WEB)
            c7, c8, c9 = st.columns(3)
            fecha = c7.text_input("Fecha de consulta", value=datetime.now().strftime("%Y-%m-%d"))
            hora = c8.text_input("Hora de consulta", value=datetime.now().strftime("%H:%M"))
            zh = c9.selectbox("Zona horaria", db.ZONAS_HORARIAS,
                              index=db.ZONAS_HORARIAS.index("America/Guayaquil"),
                              accept_new_options=True, key="zh_resp")
            c10, c11, c12 = st.columns(3)
            ubicacion = c10.selectbox("Ubicación declarada", db.PAISES, index=None,
                                      placeholder="Elige o escribe…", accept_new_options=True)
            idioma_r = c11.selectbox("Idioma", db.IDIOMAS,
                                     index=db.IDIOMAS.index("Español"),
                                     accept_new_options=True, key="idi_resp")
            modo = c12.selectbox("Modo de captura", db.MODOS_CAPTURA)
            respuesta = st.text_area("Respuesta completa (pega aquí) *", height=240)
            c13, c14 = st.columns(2)
            fuentes_ia = c13.text_area("Fuentes citadas por la IA", height=80)
            enlaces_ia = c14.text_area("Enlaces citados por la IA", height=80)
            c15, c16 = st.columns(2)
            tiempo = c15.text_input("Tiempo de respuesta (opcional)")
            obs_tec = c16.text_input("Observaciones técnicas")
            enviar = st.form_submit_button("Guardar respuesta")

        if enviar:
            if not respuesta.strip():
                st.error("La respuesta completa es obligatoria.")
            else:
                rid = db.crear_respuesta(dict(
                    prompt_id=pid, proveedor=proveedor, modelo=modelo, version_modelo=version,
                    tipo_acceso=tipo_acceso, condicion_experimental=condicion,
                    navegacion_web=navegacion, fecha_consulta=fecha, hora_consulta=hora,
                    zona_horaria=zh, ubicacion_declarada=ubicacion, idioma=idioma_r,
                    respuesta_completa=respuesta, fuentes_citadas_por_ia=fuentes_ia,
                    enlaces_citados_por_ia=enlaces_ia, tiempo_respuesta=tiempo,
                    modo_captura=modo, observaciones_tecnicas=obs_tec))
                st.success(f"Respuesta #{rid} registrada. Ahora puedes evaluarla.")


# ===========================================================================
# COMPARAR RESPUESTAS
# ===========================================================================
elif seccion == "Comparar respuestas":
    st.title("Vista comparativa por caso")
    st.caption("La similitud textual entre columnas no implica corrección factual.")
    pid = selector_prompt("cmp_prompt")
    if pid:
        p = db.obtener_prompt(pid)
        st.markdown(f"**Prompt #{pid}**")
        st.code(p["prompt_texto"] or "")
        resps = db.respuestas_de_prompt(pid)
        if not resps:
            st.info("Sin respuestas registradas para este caso.")
        else:
            cols = st.columns(min(len(resps), 3))
            for i, r in enumerate(resps):
                ev = db.obtener_evaluacion(r["respuesta_id"]) or {}
                ret = db.obtener_retorica(r["respuesta_id"]) or {}
                with cols[i % len(cols)]:
                    st.markdown(f"### {r['proveedor']} · {r['modelo']}")
                    st.caption(f"{r['tipo_acceso']} · {r['condicion_experimental']}")
                    st.caption(f"{r['fecha_consulta']} {r['hora_consulta']} · "
                               f"nav: {r['navegacion_web']}")
                    val = ev.get("valoracion_0_4")
                    if val is not None:
                        st.markdown(f"**Factual:** {db.ESCALA_FACTUAL.get(val, val)}")
                    else:
                        st.markdown("**Factual:** _sin evaluar_")
                    with st.expander("Respuesta completa"):
                        st.write(r["respuesta_completa"])
                    if ev.get("justificacion_calificacion"):
                        with st.expander("Justificación factual"):
                            st.write(ev["justificacion_calificacion"])
                    if ev.get("fuentes_verificacion"):
                        with st.expander("Fuentes de verificación"):
                            st.write(ev["fuentes_verificacion"])
                    if ret:
                        with st.expander("Indicadores retóricos"):
                            for k, label in db.INDICADORES_RETORICA.items():
                                st.write(f"- {label}: **{ret.get(k, '—')}**")
                            if ret.get("comentario_cualitativo"):
                                st.caption(ret["comentario_cualitativo"])


# ===========================================================================
# EVALUACIÓN FACTUAL
# ===========================================================================
elif seccion == "Evaluación factual":
    st.title("Evaluación factual (manual)")
    st.caption("La decisión final es del investigador. La herramienta solo registra.")
    pid = selector_prompt("ev_prompt")
    if pid:
        rid = selector_respuesta(pid, "ev_resp")
        if rid:
            r = next(x for x in db.respuestas_de_prompt(pid) if x["respuesta_id"] == rid)
            prev = db.obtener_evaluacion(rid) or {}
            with st.expander("Ver respuesta", expanded=True):
                st.write(r["respuesta_completa"])

            with st.form("form_ev"):
                val = st.select_slider("Valoración factual (0-4)",
                                       options=list(db.ESCALA_FACTUAL),
                                       value=prev.get("valoracion_0_4") or 0,
                                       format_func=lambda v: db.ESCALA_FACTUAL[v])
                c1, c2, c3 = st.columns(3)
                clasif = c1.selectbox("Clasificación auxiliar", db.CLASIFICACIONES_AUXILIARES,
                    index=_idx(db.CLASIFICACIONES_AUXILIARES, prev.get("clasificacion")))
                estado = c2.selectbox("Estado de verificación", db.ESTADOS_VERIFICACION,
                    index=_idx(db.ESTADOS_VERIFICACION, prev.get("estado_verificacion")))
                confianza = c3.selectbox("Nivel de confianza del codificador",
                    db.NIVELES_CONFIANZA, index=_idx(db.NIVELES_CONFIANZA, prev.get("nivel_confianza")))

                st.markdown("**Conteo de afirmaciones**")
                d1, d2, d3 = st.columns(3)
                a_ver = d1.number_input("Verificables", 0, value=prev.get("afirmaciones_verificables") or 0)
                a_cor = d2.number_input("Correctas", 0, value=prev.get("afirmaciones_correctas") or 0)
                a_fal = d3.number_input("Falsas", 0, value=prev.get("afirmaciones_falsas") or 0)
                d4, d5, d6 = st.columns(3)
                a_imp = d4.number_input("Imprecisas", 0, value=prev.get("afirmaciones_imprecisas") or 0)
                a_nov = d5.number_input("No verificables", 0, value=prev.get("afirmaciones_no_verificables") or 0)
                a_omi = d6.number_input("Omisiones relevantes", 0, value=prev.get("omisiones_relevantes") or 0)

                tipo_f = st.multiselect("Tipo de fuentes de verificación", db.TIPOS_FUENTE,
                    default=_split(prev.get("tipo_fuentes_verificacion")))
                fuentes_v = st.text_area("Fuentes externas de verificación (detalle)", height=90,
                    value=prev.get("fuentes_verificacion") or "")
                justif = st.text_area("Justificación de la calificación *", height=110,
                    value=prev.get("justificacion_calificacion") or "")
                c4, c5 = st.columns(2)
                codificador = c4.text_input("Codificador", value=prev.get("codificador") or "")
                notas = c5.text_input("Notas", value=prev.get("notas") or "")
                enviar = st.form_submit_button("Guardar evaluación")

            if enviar:
                db.guardar_evaluacion(dict(
                    respuesta_id=rid, valoracion_0_4=int(val), clasificacion=clasif,
                    estado_verificacion=estado, afirmaciones_verificables=int(a_ver),
                    afirmaciones_correctas=int(a_cor), afirmaciones_falsas=int(a_fal),
                    afirmaciones_imprecisas=int(a_imp), afirmaciones_no_verificables=int(a_nov),
                    omisiones_relevantes=int(a_omi), fuentes_verificacion=fuentes_v,
                    tipo_fuentes_verificacion="; ".join(tipo_f),
                    justificacion_calificacion=justif, codificador=codificador,
                    nivel_confianza=confianza, notas=notas))
                st.success("Evaluación factual guardada.")


# ===========================================================================
# SOFISTICACIÓN RETÓRICA
# ===========================================================================
elif seccion == "Sofisticación retórica":
    st.title("Codificación de sofisticación retórica")
    st.caption("0 ausente · 1 leve · 2 clara · 3 intensa. Independiente de la factualidad.")
    pid = selector_prompt("re_prompt")
    if pid:
        rid = selector_respuesta(pid, "re_resp")
        if rid:
            r = next(x for x in db.respuestas_de_prompt(pid) if x["respuesta_id"] == rid)
            prev = db.obtener_retorica(rid) or {}
            with st.expander("Ver respuesta", expanded=True):
                st.write(r["respuesta_completa"])

            with st.form("form_re"):
                valores = {}
                items = list(db.INDICADORES_RETORICA.items())
                for i in range(0, len(items), 2):
                    cols = st.columns(2)
                    for j, (k, label) in enumerate(items[i:i+2]):
                        valores[k] = cols[j].select_slider(
                            label, options=list(db.ESCALA_RETORICA),
                            value=prev.get(k) or 0,
                            format_func=lambda v: db.ESCALA_RETORICA[v], key=f"re_{k}")
                comentario = st.text_area("Comentario cualitativo (justificación)", height=110,
                    value=prev.get("comentario_cualitativo") or "")
                codificador = st.text_input("Codificador", value=prev.get("codificador") or "")
                enviar = st.form_submit_button("Guardar codificación retórica")

            if enviar:
                data = {"respuesta_id": rid, "comentario_cualitativo": comentario,
                        "codificador": codificador}
                data.update({k: int(v) for k, v in valores.items()})
                db.guardar_retorica(data)
                st.success("Codificación retórica guardada.")


# ===========================================================================
# DASHBOARD
# ===========================================================================
elif seccion == "Dashboard cuantitativo":
    st.title("Dashboard cuantitativo")
    df = df_completo()
    if df.empty:
        st.info("Sin datos todavía.")
    else:
        # ---- Filtros ----
        with st.expander("Filtros", expanded=True):
            f = df.copy()
            c1, c2, c3, c4 = st.columns(4)
            def ms(col, container, label):
                if col in f.columns:
                    vals = sorted([x for x in f[col].dropna().unique()])
                    sel = container.multiselect(label, vals)
                    return sel
                return []
            sel_pais = ms("pais", c1, "País")
            sel_elec = ms("eleccion", c2, "Elección")
            sel_tema = ms("tema", c3, "Tema")
            sel_prov = ms("proveedor", c4, "Proveedor")
            c5, c6, c7, c8 = st.columns(4)
            sel_mod = ms("modelo", c5, "Modelo")
            sel_acc = ms("tipo_acceso", c6, "Tipo de acceso")
            sel_cond = ms("condicion_experimental", c7, "Condición")
            sel_nav = ms("navegacion_web", c8, "Navegación")
            c9, c10, c11 = st.columns(3)
            sel_val = c9.multiselect("Valoración factual",
                                     [v for v in db.ESCALA_FACTUAL])
            sel_est = ms("estado_verificacion", c10, "Estado verificación")
            sel_cod = ms("codificador", c11, "Codificador")

            def apl(d, col, sel):
                return d[d[col].isin(sel)] if sel and col in d.columns else d
            f = apl(f, "pais", sel_pais); f = apl(f, "eleccion", sel_elec)
            f = apl(f, "tema", sel_tema); f = apl(f, "proveedor", sel_prov)
            f = apl(f, "modelo", sel_mod); f = apl(f, "tipo_acceso", sel_acc)
            f = apl(f, "condicion_experimental", sel_cond)
            f = apl(f, "navegacion_web", sel_nav)
            f = apl(f, "estado_verificacion", sel_est)
            f = apl(f, "codificador", sel_cod)
            if sel_val:
                f = f[f["valoracion_0_4"].isin(sel_val)]

        st.session_state["_df_filtrado"] = f

        # ---- Indicadores clave ----
        total_r = len(f)
        st.markdown("### Totales")
        m = st.columns(5)
        m[0].metric("Prompts", f["prompt_id"].nunique())
        m[1].metric("Respuestas", total_r)
        m[2].metric("Proveedores", f["proveedor"].nunique())
        m[3].metric("Modelos", f["modelo"].nunique())
        con_eval = f["valoracion_0_4"].notna().sum()
        m[4].metric("Evaluadas", int(con_eval))

        def pct(v):
            if total_r == 0:
                return 0.0
            return round(100 * (f["valoracion_0_4"] == v).sum() / total_r, 1)

        st.markdown("### Distribución por escala factual")
        pcols = st.columns(6)
        for i, v in enumerate(db.ESCALA_FACTUAL):
            pcols[i].metric(f"% valor {v}", f"{pct(v)}%")
        pend = f["estado_verificacion"].fillna("").str.contains("Pendiente").sum()
        pcols[5].metric("% pendientes", f"{round(100*pend/total_r,1) if total_r else 0}%")

        c1, c2 = st.columns(2)
        # Conteos por dimensión
        for col, titulo, cont in [
            ("proveedor", "Respuestas por proveedor", c1),
            ("modelo", "Respuestas por modelo", c2),
            ("tipo_acceso", "Respuestas por tipo de acceso", c1),
            ("condicion_experimental", "Respuestas por condición", c2),
        ]:
            if col in f.columns and not f[col].dropna().empty:
                d = f[col].value_counts().reset_index()
                d.columns = [col, "n"]
                cont.plotly_chart(px.bar(d, x=col, y="n", title=titulo),
                                  width='stretch')

        # Distribución factual
        if con_eval:
            df_val = f.dropna(subset=["valoracion_0_4"]).copy()
            df_val["etiqueta"] = df_val["valoracion_0_4"].map(db.ESCALA_FACTUAL)
            d = df_val["etiqueta"].value_counts().reset_index()
            d.columns = ["escala", "n"]
            st.plotly_chart(px.bar(d, x="escala", y="n",
                            title="Distribución de valoraciones factuales (0-4)"),
                            width='stretch')

            g1, g2 = st.columns(2)
            prom_mod = df_val.groupby("modelo")["valoracion_0_4"].mean().reset_index()
            g1.plotly_chart(px.bar(prom_mod, x="modelo", y="valoracion_0_4",
                title="Promedio factual por modelo (menor = más verificado)"),
                width='stretch')
            prom_prov = df_val.groupby("proveedor")["valoracion_0_4"].mean().reset_index()
            g2.plotly_chart(px.bar(prom_prov, x="proveedor", y="valoracion_0_4",
                title="Promedio factual por proveedor"), width='stretch')

            # Gratuito vs pagado
            df_val["gratuito_pagado"] = df_val["tipo_acceso"].apply(
                lambda x: "Pagado" if x == "Pagado" else ("Gratuito" if x == "Gratuito" else "Otro"))
            gp = df_val.groupby("gratuito_pagado")["valoracion_0_4"].mean().reset_index()
            st.plotly_chart(px.bar(gp, x="gratuito_pagado", y="valoracion_0_4",
                title="Promedio factual: gratuito vs pagado"), width='stretch')

            # Fuentes inexistentes / citas falsas
            inst = st.columns(2)
            fx = df_val["tipo_fuentes_verificacion"].fillna("").str.contains("inexistente").sum()
            cf = df_val["clasificacion"].fillna("").str.contains("Cita falsa").sum()
            inst[0].metric("Respuestas con fuentes inexistentes", int(fx))
            inst[1].metric("Respuestas con citas falsas", int(cf))

        # Sofisticación retórica
        ind_cols = [k for k in db.INDICADORES_RETORICA if k in f.columns]
        if ind_cols and f[ind_cols].notna().any().any():
            f["_retorica_prom"] = f[ind_cols].mean(axis=1)
            pr = f.dropna(subset=["_retorica_prom"]).groupby("modelo")["_retorica_prom"].mean().reset_index()
            st.plotly_chart(px.bar(pr, x="modelo", y="_retorica_prom",
                title="Promedio de sofisticación retórica por modelo"),
                width='stretch')

            if con_eval:
                comp = f.dropna(subset=["valoracion_0_4", "_retorica_prom"])
                if not comp.empty:
                    st.plotly_chart(px.scatter(comp, x="valoracion_0_4", y="_retorica_prom",
                        color="proveedor", hover_data=["modelo", "tipo_acceso"],
                        title="Factualidad (x) vs sofisticación retórica (y)",
                        labels={"valoracion_0_4": "Valoración factual (0-4)",
                                "_retorica_prom": "Sofisticación retórica media"}),
                        width='stretch')

        st.markdown("### Tabla filtrable")
        st.dataframe(f, width='stretch', height=320)


# ===========================================================================
# HISTORIAL
# ===========================================================================
elif seccion == "Historial":
    st.title("Historial completo")
    st.caption("Registro íntegro. Nada se sobrescribe salvo edición explícita de un registro.")
    df = df_completo()
    if df.empty:
        st.info("Sin registros.")
    else:
        st.dataframe(df, width='stretch', height=500)

    st.divider()
    st.subheader("Borrar datos de prueba")
    st.caption("El borrado es permanente. Al eliminar un prompt se eliminan también sus "
               "respuestas, evaluaciones y codificación retórica asociadas.")

    prompts = db.listar_prompts()
    if not prompts:
        st.info("No hay prompts que borrar.")
    else:
        modo = st.radio("¿Qué deseas borrar?",
                        ["Un prompt (con todo lo asociado)", "Solo una respuesta"],
                        horizontal=True)

        if modo.startswith("Un prompt"):
            opciones = {f"#{p['prompt_id']} · {(p['prompt_texto'] or '')[:60]}": p["prompt_id"]
                        for p in prompts}
            etiqueta = st.selectbox("Prompt a eliminar", list(opciones), key="del_prompt")
            pid = opciones[etiqueta]
            n_resp = len(db.respuestas_de_prompt(pid))
            st.warning(f"Se eliminará el prompt #{pid} y sus {n_resp} respuesta(s) asociada(s).")
            confirmar = st.checkbox("Confirmo que quiero borrarlo de forma permanente",
                                    key="conf_del_prompt")
            if st.button("Borrar prompt", type="primary", disabled=not confirmar):
                db.eliminar_prompt(pid)
                st.success(f"Prompt #{pid} eliminado.")
                st.rerun()
        else:
            pares = []
            for p in prompts:
                for r in db.respuestas_de_prompt(p["prompt_id"]):
                    pares.append((f"#{r['respuesta_id']} · prompt {p['prompt_id']} · "
                                  f"{r['proveedor']} / {r['modelo']} ({r['tipo_acceso']})",
                                  r["respuesta_id"]))
            if not pares:
                st.info("No hay respuestas registradas.")
            else:
                opciones = {k: v for k, v in pares}
                etiqueta = st.selectbox("Respuesta a eliminar", list(opciones), key="del_resp")
                rid = opciones[etiqueta]
                st.warning(f"Se eliminará la respuesta #{rid} y su evaluación/retórica.")
                confirmar = st.checkbox("Confirmo que quiero borrarla de forma permanente",
                                        key="conf_del_resp")
                if st.button("Borrar respuesta", type="primary", disabled=not confirmar):
                    db.eliminar_respuesta(rid)
                    st.success(f"Respuesta #{rid} eliminada.")
                    st.rerun()


# ===========================================================================
# EXPORTAR
# ===========================================================================
elif seccion == "Exportar datos":
    st.title("Exportar datos")
    df = df_completo()
    if df.empty:
        st.info("Sin datos para exportar.")
    else:
        usar_filtro = st.checkbox(
            "Exportar solo el subconjunto filtrado del dashboard "
            "(si lo generaste en esta sesión)", value=False)
        base = st.session_state.get("_df_filtrado") if usar_filtro else df
        if base is None:
            base = df
        st.write(f"Filas a exportar: **{len(base)}**")

        ts = datetime.now().strftime("%Y%m%d_%H%M")

        # CSV
        csv = base.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Descargar CSV", csv, f"auditoria_{ts}.csv", "text/csv")

        # JSON
        js = base.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8")
        st.download_button("Descargar JSON", js, f"auditoria_{ts}.json", "application/json")

        # Excel (multi-hoja: vista completa + tablas normalizadas)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xl:
            base.to_excel(xl, sheet_name="vista_completa", index=False)
            pd.DataFrame(db.listar_prompts()).to_excel(xl, sheet_name="prompts", index=False)
        buf.seek(0)
        st.download_button("Descargar Excel (.xlsx)", buf,
            f"auditoria_{ts}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.caption("La exportación conserva datos originales, metadatos, respuestas completas, "
                   "evaluaciones, justificaciones, fuentes, codificación retórica y notas.")
