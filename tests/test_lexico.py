"""El respaldo léxico: BM25 sobre los trozos curados cuando el índice vectorial no responde."""

import unittest
from unittest import mock

from ar_vr_bridge import lexico, retrieval

FILAS = [
    {"chunk_id": "a#1", "doc_id": "europepmc:1", "title": "Thermostable PETase variants", "year": 2022,
     "doi": "10.1/a", "url": "", "source": "europepmc",
     "text": "Engineered PETase variants retained activity after 24 h at 65 C, improving thermostability."},
    {"chunk_id": "b#1", "doc_id": "europepmc:2", "title": "MHETase structure", "year": 2019,
     "doi": "10.1/b", "url": "", "source": "europepmc",
     "text": "MHETase hydrolyses MHET into terephthalic acid and ethylene glycol."},
    {"chunk_id": "c#1", "doc_id": "openalex:3", "title": "Plastic waste policy", "year": 2020,
     "doi": "10.1/c", "url": "", "source": "openalex",
     "text": "Recycling policy and economics of plastic waste."},
]


class Bm25(unittest.TestCase):
    def test_ordena_por_pertinencia_y_puntua_cobertura(self):
        idx = lexico.Indice(FILAS)
        res = idx.buscar("PETase thermostability variants", 3)
        self.assertEqual(res[0]["chunk_id"], "a#1")
        self.assertEqual(res[0]["score"], 1.0)          # los tres terminos estan en el trozo
        self.assertTrue(all(r["chunk_id"] != "c#1" for r in res))

    def test_palabras_huecas_no_cuentan_como_evidencia(self):
        self.assertEqual(lexico.Indice(FILAS).buscar("what is the of", 3), [])

    def test_carga_paginada(self):
        paginas = [[["x"] * 8] * lexico.PAGINA, [["y"] * 8] * 3]
        consultas = []

        def sql(stmt):
            consultas.append(stmt)
            return paginas[len(consultas) - 1]

        idx = lexico._cargar(sql)
        self.assertEqual(len(idx.filas), lexico.PAGINA + 3)
        self.assertIn(f"OFFSET {lexico.PAGINA}", consultas[1])
        self.assertIn("approved_by IS NOT NULL", consultas[0])


class Respaldo(unittest.TestCase):
    def setUp(self):
        retrieval._vectorial_caido_hasta = 0.0
        lexico._indice = lexico.Indice(FILAS)
        lexico._cargado = 10 ** 12   # no recargar en el test

    def tearDown(self):
        lexico._indice = None
        retrieval._vectorial_caido_hasta = 0.0

    def test_indice_caido_usa_bm25_con_el_mismo_contrato(self):
        with mock.patch.object(retrieval, "indice_por_trozos", side_effect=RuntimeError("not ready")), \
             mock.patch.object(retrieval, "aprobados", return_value=None):
            citas, hay, _ = retrieval.search("PETase thermostability variants", 2)
        self.assertEqual(retrieval.ultimo_modo, "lexico")
        self.assertEqual(citas[0].doc_id, "europepmc:1")
        self.assertTrue(hay)
        self.assertIn("65 C", citas[0].snippet)          # el pasaje real, no una aproximacion

    def test_el_fallo_se_recuerda_y_no_se_reintenta_en_cada_pregunta(self):
        llamadas = mock.Mock(side_effect=RuntimeError("not ready"))
        with mock.patch.object(retrieval, "indice_por_trozos", llamadas), \
             mock.patch.object(retrieval, "aprobados", return_value=None):
            retrieval.search("PETase", 2)
            retrieval.search("MHETase", 2)
        self.assertEqual(llamadas.call_count, 1)


if __name__ == "__main__":
    unittest.main()
