"""El linaje y sus bifurcaciones. Sin red: `_sql` se sustituye.

Lo que se fija aqui: que las dos capas NO se mezclen. Si una rama contrafactual
sale como `agent_generated=False`, el visor la dibuja como historia y deja de
mandarla a revision humana — que es exactamente el fallo que este proyecto existe
para evitar.
"""

import unittest

from agent_lab import linaje
from ar_vr_bridge import grafo_linaje

# doc_id, title, year, doi, url, source, text
FILAS = [[d, f"Titulo de {d}", 2020, "10.1/x", f"https://ejemplo/{d}", "europepmc",
          "Un pasaje suficientemente largo del documento curado para servir de evidencia."]
         for d in linaje.doc_ids()]


class Grafo(unittest.TestCase):
    def setUp(self):
        self.orig = grafo_linaje._sql
        grafo_linaje._sql = lambda s, params=None: list(FILAS)

    def tearDown(self):
        grafo_linaje._sql = self.orig

    def test_el_tronco_tiene_un_nodo_por_hito_y_todos_citan(self):
        nodes, _, citations = grafo_linaje.construir()
        historicos = [n for n in nodes if not n.agent_generated]
        self.assertEqual(len(historicos), len(linaje.TRONCO))
        self.assertTrue(all(n.citation_ids for n in historicos), "un hito sin cita no se dibuja")
        self.assertEqual(len(citations), len(linaje.TRONCO))

    def test_las_ramas_van_marcadas_como_generadas(self):
        nodes, _, _ = grafo_linaje.construir()
        ramas = [n for n in nodes if n.id.startswith("r")]
        self.assertEqual(len(ramas), len(linaje.RAMAS))
        self.assertTrue(all(n.agent_generated for n in ramas),
                        "una rama sin marcar se dibuja como historia y no va a revision")

    def test_las_dos_capas_estan_a_distinta_altura(self):
        nodes, _, _ = grafo_linaje.construir()
        alturas_historico = {n.layer for n in nodes if not n.agent_generated}
        alturas_rama = {n.layer for n in nodes if n.agent_generated}
        self.assertTrue(alturas_historico.isdisjoint(alturas_rama))

    def test_el_detalle_de_una_rama_avisa_de_que_no_esta_verificada(self):
        nodes, _, _ = grafo_linaje.construir()
        for n in (x for x in nodes if x.agent_generated):
            self.assertIn("NO VERIFICADA", n.detail)

    def test_cada_rama_cuelga_de_un_hito_que_existe(self):
        nodes, edges, _ = grafo_linaje.construir()
        ids = {n.id for n in nodes}
        for e in edges:
            self.assertIn(e.source, ids)
            self.assertIn(e.target, ids)

    def test_la_cadena_historica_va_en_orden_cronologico(self):
        nodes, edges, _ = grafo_linaje.construir()
        anios = {n.id: int(dict(p for d in n.props for p in d.items()).get("year", 0))
                 for n in nodes if not n.agent_generated}
        for e in (x for x in edges if x.relation == "supports"):
            self.assertLessEqual(anios[e.source], anios[e.target])

    def test_un_hito_sin_documento_curado_no_se_dibuja(self):
        # No se pinta lo que no se puede citar.
        grafo_linaje._sql = lambda s, params=None: FILAS[:2]
        nodes, _, citations = grafo_linaje.construir()
        self.assertEqual(len([n for n in nodes if not n.agent_generated]), 2)
        self.assertEqual(len(citations), 2)


class Datos(unittest.TestCase):
    def test_toda_rama_apunta_a_un_hito_del_tronco(self):
        ids = {h["id"] for h in linaje.TRONCO}
        for r in linaje.RAMAS:
            self.assertIn(r["desde"], ids)

    def test_toda_rama_dice_con_que_se_comprobaria(self):
        # Sin eso, una rama es una ocurrencia y no una hipotesis.
        for r in linaje.RAMAS:
            self.assertTrue(r["comprobable_con"].strip())


if __name__ == "__main__":
    unittest.main()
