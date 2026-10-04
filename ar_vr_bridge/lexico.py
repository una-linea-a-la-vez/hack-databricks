"""Búsqueda léxica (BM25) sobre los trozos curados: el respaldo cuando el índice vectorial no responde.

Existe por un hecho medido el 2026-10-04: al migrar a una cuenta nueva, Vector Search se quedó
en "pending endpoint provisioning" durante horas, y sin índice el laboratorio no podía buscar
nada aunque el corpus curado estuviera entero en `documents_curated`. Con esto el bridge sigue
citando pasajes reales del mismo corpus; en cuanto el índice responde, `retrieval.search` vuelve
solo a la búsqueda semántica.

Qué es y qué no es:
  - BM25 clásico (k1=1.5, b=0.75) sobre título + texto de cada trozo, en memoria.
  - Mismo filtro que el recomendado para el índice (docs/CURACION.md): relevancia de PET y
    `language = 'en'`, y solo documentos aprobados (`approved_by`).
  - La puntuación que se devuelve NO es la de BM25 (no está acotada): es la fracción de la
    consulta, pesada por IDF, que aparece en el trozo. 0.70 significa que el 70 % de lo que la
    consulta tiene de específico está en el pasaje, así el umbral de `retrieval` sigue diciendo
    algo comparable a "hay evidencia".
  - Busca palabras, no significado: "termoestabilidad" no casa con "thermal stability". El
    corpus y el índice son en inglés; el Explorer ya traduce la pregunta a consultas en inglés.
"""

from __future__ import annotations

import math
import re
import threading
import time
from collections import Counter, defaultdict

CURATED = "workspace.lab.documents_curated"
FILTRO = ("approved_by IS NOT NULL AND approved_by <> '' AND language = 'en' AND "
          "relevance IN ('nucleo_pet_enzima', 'enzima_plasticos_sin_pet', 'estructura')")
PAGINA = 2500          # filas por consulta: el resultado INLINE falla por encima de 25 MB
K1, B = 1.5, 0.75

_PALABRA = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# Palabras huecas en inglés: sin ellas "what is the effect of" no puntúa como evidencia.
_VACIAS = set("""a an and are as at be been being but by can could did do does for from had has have how
if in into is it its may might more most no not of on or our over per such than that the their them then
there these they this those through to under up was we were what when where which while who why will
with within would you your about after also among both each other some via using used use""".split())


def tokens(texto: str) -> list[str]:
    return [t for t in _PALABRA.findall((texto or "").lower()) if len(t) > 1 and t not in _VACIAS]


class Indice:
    def __init__(self, filas: list[dict]):
        self.filas = filas
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.largos: list[int] = []
        for i, fila in enumerate(filas):
            conteo = Counter(tokens(f"{fila.get('title') or ''} {fila.get('text') or ''}"))
            self.largos.append(sum(conteo.values()))
            for termino, n in conteo.items():
                self.postings[termino].append((i, n))
        self.medio = (sum(self.largos) / len(self.largos)) if self.largos else 1.0
        total = len(filas)
        self.idf = {t: math.log(1 + (total - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}

    def buscar(self, consulta: str, n: int) -> list[dict]:
        terminos = list(dict.fromkeys(tokens(consulta)))
        if not terminos:
            return []
        peso_total = sum(self.idf.get(t, 0.0) for t in terminos) or 1.0
        bm25: dict[int, float] = defaultdict(float)
        cubierto: dict[int, float] = defaultdict(float)
        for t in terminos:
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, frecuencia in self.postings[t]:
                norma = K1 * (1 - B + B * self.largos[i] / self.medio)
                bm25[i] += idf * frecuencia * (K1 + 1) / (frecuencia + norma)
                cubierto[i] += idf
        mejores = sorted(bm25, key=bm25.__getitem__, reverse=True)[:n]
        return [{**self.filas[i], "score": round(cubierto[i] / peso_total, 3), "bm25": round(bm25[i], 3)}
                for i in mejores]


_indice: Indice | None = None
_cargado: float = 0.0
_cerrojo = threading.Lock()
TTL_S = 3600


def _cargar(sql) -> Indice:
    columnas = ["chunk_id", "doc_id", "title", "year", "doi", "url", "source", "text"]
    filas: list[dict] = []
    desde = 0
    while True:
        pagina = sql(f"SELECT {', '.join(columnas)} FROM {CURATED} WHERE {FILTRO} "
                     f"ORDER BY chunk_id LIMIT {PAGINA} OFFSET {desde}")
        filas.extend(dict(zip(columnas, f)) for f in pagina)
        if len(pagina) < PAGINA:
            return Indice(filas)
        desde += PAGINA


def indice(sql) -> Indice:
    """El índice en memoria, construido una vez (unos segundos) y renovado cada hora."""
    global _indice, _cargado
    with _cerrojo:
        if _indice is None or time.time() - _cargado > TTL_S:
            _indice = _cargar(sql)
            _cargado = time.time()
        return _indice


def buscar(consulta: str, n: int, sql) -> list[dict]:
    return indice(sql).buscar(consulta, n)
