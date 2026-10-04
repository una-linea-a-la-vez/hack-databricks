"""El linaje de las PET hidrolasas y sus bifurcaciones.

Caso de uso: enseñar que una cadena de descubrimientos reales —Yoshida 2016,
Austin 2018, Knott 2020, Tournier 2020, Lu 2022— **tuvo bifurcaciones**, y que en
cada nodo el investigador pudo haber tomado otro camino.

Dos capas, y la distinción entre ellas es lo único que hace honesto el ejercicio:

- **Tronco (`historico`)**: lo que de verdad ocurrió. Cada nodo cita un `doc_id`
  del corpus curado y una frase de ese documento. Se verifica con la puerta de
  procedencia como cualquier otra afirmación.
- **Ramas (`contrafactual`)**: lo que el laboratorio propone que *se pudo haber
  intentado*. Son hipótesis **generadas**, van marcadas `agent_generated=True` y
  el visor las dibuja con borde discontinuo. No se presentan como historia.

Mezclar las dos capas sería exactamente el fallo que este proyecto existe para
evitar: una afirmación plausible sin respaldo, indistinguible de una documentada.

El premio Nobel de esta historia es el de **Frances Arnold (2018, evolución
dirigida)**: es la técnica que habilita toda la cadena, no un galardón a la PETasa.
"""

# Cada hito: id, año, qué se preguntaron, cómo lo probaron, qué salió, y el
# documento del corpus que lo respalda. Los `evidence_span` se cotejan literal
# contra `documents_curated`, así que se copian de ahí, nunca se escriben a mano.
TRONCO = [
    {
        "id": "h2016",
        "year": 2016,
        "titulo": "Una bacteria usa PET como fuente de carbono",
        "pregunta": "¿Existe un organismo capaz de vivir del PET?",
        "metodo": "Cribado de 250 muestras ambientales de una planta de reciclaje en Sakai, "
                  "con film de PET de baja cristalinidad como única fuente de carbono; "
                  "SEM para ver la erosión de la superficie y LC-MS para medir los subproductos.",
        "resultado": "Ideonella sakaiensis, que secreta dos enzimas: PETasa y MHETasa.",
        "doc_id": "europepmc:26965627",
        "equipo": "Yoshida et al., Science",
    },
    {
        "id": "h2018",
        "year": 2018,
        "titulo": "El sitio activo de la PETasa es más abierto que el de las cutinasas",
        "pregunta": "¿Por qué la PETasa degrada PET mejor que enzimas emparentadas?",
        "metodo": "Cristalografía de rayos X sobre la proteína purificada para mapear "
                  "la estructura 3D del sitio activo.",
        "resultado": "Estructura resuelta; estrechar el sitio activo hacia la forma de "
                     "cutinasa AUMENTÓ la actividad, al contrario de lo esperado.",
        "doc_id": "europepmc:29666242",
        "equipo": "Austin, McGeehan, Beckham et al., PNAS",
    },
    {
        "id": "h2020a",
        "year": 2020,
        "titulo": "PETasa y MHETasa trabajan mejor acopladas",
        "pregunta": "¿La degradación mejora si las dos enzimas actúan como un sistema?",
        "metodo": "Dinámica molecular por supercomputación más una proteína quimérica "
                  "que une ambas enzimas.",
        "resultado": "El sistema de dos enzimas degrada hasta 6 veces más rápido.",
        "doc_id": "europepmc:32989159",
        "equipo": "Knott, Erickson, Beckham et al., PNAS",
    },
    {
        "id": "h2020b",
        "year": 2020,
        "titulo": "Una cutinasa de compost sirve para despolimerizar a escala industrial",
        "pregunta": "¿Se puede llevar la degradación enzimática a escala de botella?",
        "metodo": "Ingeniería de una cutinasa de hojas de compost (LCC) hasta la variante "
                  "hiperestable LCC-ICCG.",
        "resultado": "Despolimerización industrial de botellas de PET.",
        "doc_id": "europepmc:32269349",
        "equipo": "Tournier, Marty et al. (Carbios), Nature",
    },
    {
        "id": "h2022",
        "year": 2022,
        "titulo": "El aprendizaje automático predice qué mutaciones estabilizan",
        "pregunta": "¿Puede un modelo elegir las mutaciones en vez del cribado exhaustivo?",
        "metodo": "Modelo entrenado sobre ~19 000 secuencias de ab-hidrolasas y los datos "
                  "publicados de estabilidad térmica; predijo 5 cambios de aminoácido.",
        "resultado": "FAST-PETase degrada envases comerciales en horas a temperatura moderada.",
        "doc_id": "europepmc:35478237",
        "equipo": "Lu, Diaz, Alper et al., Nature",
    },
]

# Las bifurcaciones. `desde` es el nodo del tronco donde el camino pudo torcerse.
# `comprobable_con` dice contra qué se contrastaría: sin eso, una rama es una
# ocurrencia, no una hipótesis.
RAMAS = [
    {
        "id": "r2018-termo",
        "desde": "h2018",
        "titulo": "Optimizar termoestabilidad en vez de actividad",
        "detalle": "En 2018 se estrechó el sitio activo para ganar actividad. La vía "
                   "alternativa era priorizar la estabilidad térmica: una enzima más lenta "
                   "pero operativa a 70 °C podría rendir más en un reactor industrial que "
                   "una rápida que se desnaturaliza.",
        "comprobable_con": "pet_activity_ml: comparar actividad a 40 °C frente a 60 °C "
                           "controlando por descriptores de secuencia.",
        "confianza": 0.62,
    },
    {
        "id": "r2020-sin-coctel",
        "desde": "h2020a",
        "titulo": "Una sola enzima más rápida en vez del sistema de dos",
        "detalle": "El cóctel PETasa+MHETasa dio 6x. La alternativa era concentrar el "
                   "esfuerzo en una única enzima que hidrolizara también el MHET, evitando "
                   "la complejidad de expresar y purificar dos proteínas.",
        "comprobable_con": "pet_activity_ml: ver si las enzimas con mayor actividad sobre "
                           "sustrato cristalino comparten descriptores de una sola familia.",
        "confianza": 0.55,
    },
    {
        "id": "r2022-actividad",
        "desde": "h2022",
        "titulo": "Entrenar el modelo sobre actividad medida, no sobre estabilidad",
        "detalle": "FAST-PETase se obtuvo prediciendo estabilidad térmica. Entrenar sobre "
                   "actividad medida habría optimizado otra cosa: quizá una enzima muy "
                   "rápida a temperatura ambiente pero inservible en un reactor caliente.",
        "comprobable_con": "pet_activity_ml: entrenar con `activity` como objetivo y "
                           "comparar el macro-F1 contra el modelo de estabilidad, con la "
                           "partición cv_split publicada.",
        "confianza": 0.58,
    },
]


def por_id(nodo_id: str) -> dict | None:
    for h in TRONCO:
        if h["id"] == nodo_id:
            return h
    return None


def ramas_de(nodo_id: str) -> list[dict]:
    return [r for r in RAMAS if r["desde"] == nodo_id]


def doc_ids() -> list[str]:
    """Los documentos que el tronco cita. Se usan para traer sus pasajes."""
    return [h["doc_id"] for h in TRONCO]
