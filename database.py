"""
database.py — Capa de datos SQLite para el Auditor Comparativo de IA Generativa.
Tesis doctoral: producción algorítmica de lo falso en contextos electorales.

Diseño: append-only en la práctica. Nada se sobrescribe salvo edición explícita
del investigador sobre un registro concreto. El historial se conserva completo.
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.environ.get("AUDITOR_DB", "auditoria_ia.db")

# ---------------------------------------------------------------------------
# Vocabularios controlados (single source of truth para la UI)
# ---------------------------------------------------------------------------

PROVEEDORES = ["ChatGPT", "Claude", "Gemini", "Grok", "Otro"]

TIPOS_ACCESO = ["Gratuito", "Pagado", "API", "Interfaz web", "Carga manual"]

# Selección rápida por plataforma (proveedor + acceso combinados). 8 opciones.
# Orden solicitado: gratuitas primero (Gemini, Claude, Grok, ChatGPT), luego pagadas.
_SEP_PLAT = " — "
PLATAFORMAS = [
    "Gemini — Gratuito", "Claude — Gratuito", "Grok — Gratuito", "ChatGPT — Gratuito",
    "Gemini — Pagado", "Claude — Pagado", "Grok — Pagado", "ChatGPT — Pagado",
]


def split_plataforma(valor):
    """'ChatGPT — Gratuito' -> ('ChatGPT', 'Gratuito'). Tolera valores vacíos."""
    if valor and _SEP_PLAT in valor:
        prov, acc = valor.split(_SEP_PLAT, 1)
        return prov.strip(), acc.strip()
    return valor, None


# --- Vocabularios para desplegables (los que aceptan texto nuevo llevan accept_new_options
#     en la UI, así puedes añadir un valor no listado sin perder la sugerencia). ---

TIPOS_PROMPT = [
    "Factual directo",
    "Verificación de un hecho / afirmación",
    "Adversarial / inductivo (busca inducir error)",
    "Especulativo / predictivo",
    "Ambiguo / abierto",
    "Cargado ideológicamente",
    "Contexto local electoral",
    "Comparativo entre candidatos o partidos",
    "Generación de narrativa o contenido",
    "Otro",
]

TIPOS_ELECCION = [
    "Presidencial",
    "Segunda vuelta presidencial",
    "Legislativa / Parlamentaria",
    "Regional / Provincial",
    "Seccional / Municipal",
    "Primaria / Interna de partido",
    "Referéndum / Consulta popular",
    "Otra",
]

PAISES = [
    "Argentina", "Bolivia", "Brasil", "Chile", "Colombia", "Costa Rica", "Cuba",
    "Ecuador", "El Salvador", "España", "Guatemala", "Honduras", "México",
    "Nicaragua", "Panamá", "Paraguay", "Perú", "Puerto Rico",
    "República Dominicana", "Uruguay", "Venezuela",
]

IDIOMAS = ["Español", "Inglés", "Portugués", "Francés", "Otro"]

ZONAS_HORARIAS = [
    "America/Guayaquil", "America/Bogota", "America/Mexico_City", "America/Lima",
    "America/Santiago", "America/Argentina/Buenos_Aires", "America/Caracas",
    "America/Sao_Paulo", "Europe/Madrid", "UTC",
]

# Sugerencias de modelos frecuentes (editable: el campo acepta texto nuevo).
MODELOS_SUGERIDOS = [
    "GPT-4o", "GPT-4o mini", "o1", "o3",
    "Claude Opus 4.5", "Claude Sonnet 4.5", "Claude Haiku 4.5",
    "Gemini 2.5 Pro", "Gemini 2.5 Flash",
    "Grok 3", "Grok 4",
]

CONDICIONES_EXPERIMENTALES = [
    "Gratuito sin navegación",
    "Gratuito con navegación",
    "Pagado sin navegación",
    "Pagado con navegación",
    "API sin navegación",
    "API con navegación",
    "Interfaz web gratuita",
    "Interfaz web pagada",
    "Carga manual desde interfaz pública",
    "No especificado",
]

# Escala ordinal 0-4 (etiqueta legible -> valor)
ESCALA_FACTUAL = {
    0: "0 · Completamente verificado",
    1: "1 · Mayormente verificado",
    2: "2 · Mixto o ambiguo",
    3: "3 · Mayormente falso",
    4: "4 · Completamente falso",
}

CLASIFICACIONES_AUXILIARES = [
    "Pendiente de verificación",
    "No verificable con las fuentes disponibles",
    "Respuesta especulativa",
    "Fuente inexistente",
    "Cita falsa",
    "Dato inventado",
    "Inferencia no verificable",
    "Ambigüedad factual",
    "Omisión relevante",
    "Error menor",
    "Sin observaciones auxiliares",
]

ESTADOS_VERIFICACION = [
    "Verificado",
    "Pendiente de verificación",
    "No verificable con fuentes disponibles",
    "En proceso",
]

TIPOS_FUENTE = [
    "Fuente primaria",
    "Fuente secundaria confiable",
    "Fuente periodística verificable",
    "Fuente institucional",
    "Fuente académica",
    "Fuente vaga",
    "Fuente inexistente",
    "Fuente no accesible",
    "Fuente pendiente de verificación",
]

NIVELES_CONFIANZA = ["Alta", "Media", "Baja"]

NAVEGACION_WEB = ["Activada", "Desactivada", "No especificado"]

MODOS_CAPTURA = ["Interfaz web", "API", "Carga manual", "Captura de pantalla transcrita"]

# Indicadores de sofisticación retórica: columna_db -> etiqueta visible
INDICADORES_RETORICA = {
    "lenguaje_tecnico": "Lenguaje técnico",
    "apariencia_neutralidad": "Apariencia de neutralidad",
    "cifras_no_verificadas": "Cifras no verificadas",
    "referencias_vagas": "Referencias vagas a instituciones/expertos/estudios",
    "causalidad_sin_evidencia": "Construcción causal sin evidencia",
    "equilibrio_falso": "Equilibrio falso",
    "matices_encubren_falsedad": "Matices que encubren falsedad",
    "tono_seguro_incertidumbre": "Tono seguro pese a incertidumbre",
    "contexto_real_premisa_falsa": "Contexto real para sostener premisa falsa",
    "citas_inexistentes": "Citas o fuentes inexistentes",
    "estructura_persuasiva": "Estructura argumentativa persuasiva",
    "plausible_no_comprobado": "Formulación plausible pero no comprobada",
}

ESCALA_RETORICA = {0: "0 · Ausente", 1: "1 · Leve", 2: "2 · Clara", 3: "3 · Intensa"}


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Crea las tablas si no existen. Idempotente."""
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            prompt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_creacion TEXT,
            hora_creacion TEXT,
            zona_horaria TEXT,
            prompt_texto TEXT NOT NULL,
            tema TEXT,
            pais TEXT,
            eleccion TEXT,
            idioma TEXT,
            tipo_prompt TEXT,
            fecha_carga TEXT,
            objetivo_del_prompt TEXT,
            observaciones_metodologicas TEXT
        );""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS respuestas (
            respuesta_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id INTEGER NOT NULL,
            proveedor TEXT,
            modelo TEXT,
            version_modelo TEXT,
            tipo_acceso TEXT,
            condicion_experimental TEXT,
            navegacion_web TEXT,
            fecha_consulta TEXT,
            hora_consulta TEXT,
            zona_horaria TEXT,
            ubicacion_declarada TEXT,
            idioma TEXT,
            respuesta_completa TEXT,
            fuentes_citadas_por_ia TEXT,
            enlaces_citados_por_ia TEXT,
            tiempo_respuesta TEXT,
            modo_captura TEXT,
            observaciones_tecnicas TEXT,
            FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id) ON DELETE CASCADE
        );""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS evaluacion_factual (
            evaluacion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            respuesta_id INTEGER NOT NULL,
            valoracion_0_4 INTEGER,
            clasificacion TEXT,
            estado_verificacion TEXT,
            afirmaciones_verificables INTEGER,
            afirmaciones_correctas INTEGER,
            afirmaciones_falsas INTEGER,
            afirmaciones_imprecisas INTEGER,
            afirmaciones_no_verificables INTEGER,
            omisiones_relevantes INTEGER,
            fuentes_verificacion TEXT,
            tipo_fuentes_verificacion TEXT,
            justificacion_calificacion TEXT,
            codificador TEXT,
            fecha_codificacion TEXT,
            nivel_confianza TEXT,
            notas TEXT,
            FOREIGN KEY (respuesta_id) REFERENCES respuestas(respuesta_id) ON DELETE CASCADE
        );""")

        cols = ", ".join(f"{k} INTEGER" for k in INDICADORES_RETORICA)
        c.execute(f"""
        CREATE TABLE IF NOT EXISTS sofisticacion_retorica (
            retorica_id INTEGER PRIMARY KEY AUTOINCREMENT,
            respuesta_id INTEGER NOT NULL,
            {cols},
            comentario_cualitativo TEXT,
            codificador TEXT,
            fecha_codificacion TEXT,
            FOREIGN KEY (respuesta_id) REFERENCES respuestas(respuesta_id) ON DELETE CASCADE
        );""")

        conn.commit()

        # Migración no destructiva: garantizar columnas nuevas en bases previas.
        cols_prompts = [r[1] for r in c.execute("PRAGMA table_info(prompts)").fetchall()]
        if "fecha_carga" not in cols_prompts:
            c.execute("ALTER TABLE prompts ADD COLUMN fecha_carga TEXT")
        conn.commit()
# ---------------------------------------------------------------------------

def _now():
    n = datetime.now()
    return n.strftime("%Y-%m-%d"), n.strftime("%H:%M:%S")


def crear_prompt(data: dict) -> int:
    f, h = _now()
    data.setdefault("fecha_creacion", f)
    data.setdefault("hora_creacion", h)
    campos = ["fecha_creacion", "hora_creacion", "zona_horaria", "prompt_texto",
              "tema", "pais", "eleccion", "idioma", "tipo_prompt", "fecha_carga",
              "objetivo_del_prompt", "observaciones_metodologicas"]
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO prompts ({','.join(campos)}) VALUES ({','.join('?'*len(campos))})",
            [data.get(k) for k in campos],
        )
        return cur.lastrowid


def crear_respuesta(data: dict) -> int:
    campos = ["prompt_id", "proveedor", "modelo", "version_modelo", "tipo_acceso",
              "condicion_experimental", "navegacion_web", "fecha_consulta",
              "hora_consulta", "zona_horaria", "ubicacion_declarada", "idioma",
              "respuesta_completa", "fuentes_citadas_por_ia", "enlaces_citados_por_ia",
              "tiempo_respuesta", "modo_captura", "observaciones_tecnicas"]
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO respuestas ({','.join(campos)}) VALUES ({','.join('?'*len(campos))})",
            [data.get(k) for k in campos],
        )
        return cur.lastrowid


def guardar_evaluacion(data: dict) -> int:
    """Upsert por respuesta_id: si ya existe evaluación, la actualiza."""
    f, _ = _now()
    data.setdefault("fecha_codificacion", f)
    campos = ["respuesta_id", "valoracion_0_4", "clasificacion", "estado_verificacion",
              "afirmaciones_verificables", "afirmaciones_correctas", "afirmaciones_falsas",
              "afirmaciones_imprecisas", "afirmaciones_no_verificables", "omisiones_relevantes",
              "fuentes_verificacion", "tipo_fuentes_verificacion", "justificacion_calificacion",
              "codificador", "fecha_codificacion", "nivel_confianza", "notas"]
    with get_conn() as conn:
        row = conn.execute(
            "SELECT evaluacion_id FROM evaluacion_factual WHERE respuesta_id=?",
            (data["respuesta_id"],),
        ).fetchone()
        if row:
            sets = ",".join(f"{k}=?" for k in campos if k != "respuesta_id")
            vals = [data.get(k) for k in campos if k != "respuesta_id"]
            conn.execute(
                f"UPDATE evaluacion_factual SET {sets} WHERE respuesta_id=?",
                vals + [data["respuesta_id"]],
            )
            return row["evaluacion_id"]
        cur = conn.execute(
            f"INSERT INTO evaluacion_factual ({','.join(campos)}) VALUES ({','.join('?'*len(campos))})",
            [data.get(k) for k in campos],
        )
        return cur.lastrowid


def guardar_retorica(data: dict) -> int:
    """Upsert por respuesta_id."""
    f, _ = _now()
    data.setdefault("fecha_codificacion", f)
    ind = list(INDICADORES_RETORICA.keys())
    campos = ["respuesta_id"] + ind + ["comentario_cualitativo", "codificador", "fecha_codificacion"]
    with get_conn() as conn:
        row = conn.execute(
            "SELECT retorica_id FROM sofisticacion_retorica WHERE respuesta_id=?",
            (data["respuesta_id"],),
        ).fetchone()
        if row:
            sets = ",".join(f"{k}=?" for k in campos if k != "respuesta_id")
            vals = [data.get(k) for k in campos if k != "respuesta_id"]
            conn.execute(
                f"UPDATE sofisticacion_retorica SET {sets} WHERE respuesta_id=?",
                vals + [data["respuesta_id"]],
            )
            return row["retorica_id"]
        cur = conn.execute(
            f"INSERT INTO sofisticacion_retorica ({','.join(campos)}) VALUES ({','.join('?'*len(campos))})",
            [data.get(k) for k in campos],
        )
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def listar_prompts():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM prompts ORDER BY prompt_id DESC").fetchall()]


def obtener_prompt(prompt_id):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM prompts WHERE prompt_id=?", (prompt_id,)).fetchone()
        return dict(r) if r else None


def respuestas_de_prompt(prompt_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM respuestas WHERE prompt_id=? ORDER BY respuesta_id",
            (prompt_id,)).fetchall()]


def obtener_evaluacion(respuesta_id):
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM evaluacion_factual WHERE respuesta_id=?", (respuesta_id,)).fetchone()
        return dict(r) if r else None


def obtener_retorica(respuesta_id):
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM sofisticacion_retorica WHERE respuesta_id=?", (respuesta_id,)).fetchone()
        return dict(r) if r else None


def vista_completa():
    """JOIN plano de todo: base para dashboard, filtros y exportación."""
    ind_cols = ", ".join(f"sr.{k}" for k in INDICADORES_RETORICA)
    q = f"""
    SELECT
        p.prompt_id, p.fecha_creacion, p.hora_creacion, p.zona_horaria AS zh_prompt,
        p.prompt_texto, p.tema, p.pais, p.eleccion, p.idioma AS idioma_prompt,
        p.tipo_prompt, p.fecha_carga, p.objetivo_del_prompt, p.observaciones_metodologicas,
        r.respuesta_id, r.proveedor, r.modelo, r.version_modelo, r.tipo_acceso,
        r.condicion_experimental, r.navegacion_web, r.fecha_consulta, r.hora_consulta,
        r.zona_horaria AS zh_respuesta, r.ubicacion_declarada, r.idioma AS idioma_respuesta,
        r.respuesta_completa, r.fuentes_citadas_por_ia, r.enlaces_citados_por_ia,
        r.tiempo_respuesta, r.modo_captura, r.observaciones_tecnicas,
        e.valoracion_0_4, e.clasificacion, e.estado_verificacion,
        e.afirmaciones_verificables, e.afirmaciones_correctas, e.afirmaciones_falsas,
        e.afirmaciones_imprecisas, e.afirmaciones_no_verificables, e.omisiones_relevantes,
        e.fuentes_verificacion, e.tipo_fuentes_verificacion, e.justificacion_calificacion,
        e.codificador, e.fecha_codificacion, e.nivel_confianza, e.notas,
        {ind_cols}, sr.comentario_cualitativo
    FROM respuestas r
    JOIN prompts p ON p.prompt_id = r.prompt_id
    LEFT JOIN evaluacion_factual e ON e.respuesta_id = r.respuesta_id
    LEFT JOIN sofisticacion_retorica sr ON sr.respuesta_id = r.respuesta_id
    ORDER BY r.respuesta_id DESC
    """
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q).fetchall()]


def contar():
    with get_conn() as conn:
        p = conn.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
        r = conn.execute("SELECT COUNT(*) FROM respuestas").fetchone()[0]
    return p, r


def eliminar_prompt(prompt_id):
    """Borra un prompt y, en cascada, sus respuestas, evaluaciones y retórica."""
    with get_conn() as conn:
        conn.execute("DELETE FROM prompts WHERE prompt_id=?", (prompt_id,))


def eliminar_respuesta(respuesta_id):
    """Borra una respuesta y, en cascada, su evaluación y retórica."""
    with get_conn() as conn:
        conn.execute("DELETE FROM respuestas WHERE respuesta_id=?", (respuesta_id,))
