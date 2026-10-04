"""Convierte el linaje en el grafo que el visor ya sabe dibujar.

No inventa contrato: devuelve `Node`, `Edge` y `Citation` de `contract.py`, así que
las gafas y la web lo pintan **sin cambiar una línea** de su código.

Las dos capas se separan por la altura del grafo, que es como el visor da
profundidad:

- **Tronco histórico** → `type="evidence"` (capa 1), `agent_generated=False`,
  cada nodo con su cita real.
- **Ramas contrafactuales** → `type="hypothesis"` (capa 3), `agent_generated=True`,
  que el visor dibuja con borde discontinuo y **somete a revisión humana**.

Esa separación no es estética: `gate/bridge.py` sólo manda a revisión los nodos
`agent_generated`. Lo documentado no se revisa; lo propuesto, sí.
"""

from agent_lab import linaje
from ar_vr_bridge.contract import LAYER, Citation, Edge, Node

CURATED = "workspace.lab.documents_curated"


def _sql(statement: str, params: dict | None = None):
    from data_pipeline.databricks_io import Databricks
    return Databricks().sql(statement, params=params)


def _pasajes() -> dict[str, dict]:
    """Un pasaje real por cada documento del tronco, con su metadato.

    Se coge el trozo más largo del documento: es el que más contexto da y, al salir
    literal de `documents_curated`, sirve como `evidence_span` sin retocarlo.
    """
    ids = ", ".join(f"'{d}'" for d in linaje.doc_ids())
    filas = _sql(f"""
        SELECT doc_id, any_value(title), any_value(year), any_value(doi), any_value(url),
               any_value(source), max_by(text, length(text))
          FROM {CURATED}
         WHERE doc_id IN ({ids}) AND approved_by IS NOT NULL AND approved_by <> ''
      GROUP BY doc_id
    """)
    return {f[0]: {"title": f[1] or "", "year": f[2], "doi": f[3] or "", "url": f[4] or "",
                   "source": f[5] or "", "text": (f[6] or "").strip()} for f in filas}


def construir() -> tuple[list[Node], list[Edge], list[Citation]]:
    meta = _pasajes()
    citations: list[Citation] = []
    nodes: list[Node] = []
    edges: list[Edge] = []
    cita_de: dict[str, str] = {}

    for i, hito in enumerate(linaje.TRONCO):
        m = meta.get(hito["doc_id"])
        if m is None:
            continue  # sin documento curado no hay nodo: no se dibuja lo que no se puede citar
        cid = f"c{len(citations) + 1}"
        citations.append(Citation(
            id=cid, doc_id=hito["doc_id"], title=m["title"], year=m["year"],
            doi=m["doi"], url=m["url"], source=m["source"],
            snippet=m["text"][:400], score=1.0))
        cita_de[hito["id"]] = cid

        nodes.append(Node(
            id=hito["id"], type="evidence", layer=LAYER["evidence"],
            label=f'{hito["year"]} · {hito["titulo"]}'[:48],
            detail=(f'{hito["titulo"]}\n\n'
                    f'Pregunta: {hito["pregunta"]}\n'
                    f'Método: {hito["metodo"]}\n'
                    f'Resultado: {hito["resultado"]}\n'
                    f'Equipo: {hito["equipo"]}'),
            confidence=1.0, agent_generated=False, citation_ids=[cid],
            props=[{"year": str(hito["year"])}, {"capa": "historico"},
                   {"doc_id": hito["doc_id"]}]))

        if i:  # la cadena en orden cronológico
            anterior = linaje.TRONCO[i - 1]["id"]
            if any(n.id == anterior for n in nodes):
                edges.append(Edge(source=anterior, target=hito["id"], relation="supports",
                                  weight=1.0, citation_ids=[cid]))

    for rama in linaje.RAMAS:
        if not any(n.id == rama["desde"] for n in nodes):
            continue
        nodes.append(Node(
            id=rama["id"], type="hypothesis", layer=LAYER["hypothesis"],
            label=rama["titulo"][:48],
            detail=(f'HIPÓTESIS GENERADA — NO VERIFICADA\n\n{rama["detalle"]}\n\n'
                    f'Comprobable con: {rama["comprobable_con"]}'),
            confidence=rama["confianza"], agent_generated=True,
            citation_ids=[cita_de[rama["desde"]]],
            props=[{"capa": "contrafactual"}, {"bifurca_de": rama["desde"]}]))
        edges.append(Edge(source=rama["desde"], target=rama["id"], relation="tests",
                          weight=rama["confianza"], citation_ids=[cita_de[rama["desde"]]]))

    return nodes, edges, citations
