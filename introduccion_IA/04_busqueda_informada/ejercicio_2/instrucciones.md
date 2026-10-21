# Ejercicio 2 — A* para encontrar rutas en el mapa de México

## Contexto

En el ejercicio 1 corriste A* sobre el mapa de Rumania (20 ciudades, tabla AIMA).
El proyecto `Mexico map/` es el mismo tipo de problema a otra escala: un grafo
geográfico de **1,000 ciudades** mexicanas, con latitud/longitud reales y
aristas ponderadas en **km**. Hoy el HTML solo deja **explorar** el grafo
(buscar una ciudad, filtrar por estado, ver vecinos). **No calcula rutas.**

En este ejercicio **sí vas a programar**: vas a **reutilizar A\*** del proyecto
`Búsqueda informada/project` para agregar la opción de **encontrar la ruta**
entre dos ciudades, y **mostrarla** en el mapa.

El grafo ya está construido (`mexico_cities_graph.json` / `mexico_map.html`).
No regeneres las aristas ni cambies el 4-NN ni el MST. Solo añades búsqueda.

| Pieza | Dónde está | Qué usar |
|---|---|---|
| A* (`f = g + h`) | `Búsqueda informada/project/search/astar.py` | Reutilizar (importar o copiar y adaptar) |
| Nodo / problema | `romania/node.py`, `romania/problem.py` | Adaptar al grafo de México |
| Grafo México | `Mexico map/mexico_cities_graph.json` | `nodes[].lat/lon`, `edges[].km` |
| Haversine | `Mexico map/generate_mexico_graph.py` (`haversine`) | Heurística `h(n)` |
| Mapa interactivo | `Mexico map/mexico_map.html` | UI origen–destino y pintar la ruta |

## Objetivo

Agregar en `Mexico map/` la opción de calcular, con **A\***, la ruta de menor
costo en km entre dos ciudades, e **indicarla en el mapa**.

## Archivos a crear / modificar

Trabaja en `Mexico map/`. No cambies cómo se construye el grafo (4-NN ∪ MST)
ni el dump GeoNames.

**No regeneres** el grafo con `generate_mexico_graph.py` salvo que sepas
exactamente qué estás haciendo: ese script **reescribe** `mexico_map.html` y
borraría tu UI.

Sugerencia de archivos (puedes nombrarlos distinto si el README lo documenta):

- `Mexico map/find_route.py` — CLI que corre A* y imprime el camino.
- `Mexico map/mexico_map.html` — controles origen/destino y resaltado de la ruta.
- Código de búsqueda reutilizado o adaptado (A*, `Node`, problema de rutas).

No hace falta modificar `Búsqueda informada/project` salvo que importes desde
ahí; si copias A*, deja claro en un comentario de dónde sale.

## Requisitos

### Búsqueda (A*)

1. El estado es una ciudad del grafo. La acción es ir a un vecino. El costo de
   arista es `edges[].km` (ya está en kilómetros).
2. Usa **A\***: frontera ordenada por `f(n) = g(n) + h(n)`.
3. Heurística **admisible**: distancia **en línea recta** (haversine) desde la
   ciudad `n` hasta el **destino**, usando `lat` y `lon`. Es el análogo de la
   SLD de Rumania; no inventes una tabla. La función `haversine` del generador
   del grafo ya hace exactamente eso.
4. El grafo está **conectado** (4-NN ∪ MST), así que siempre debe existir
   camino entre cualquier par.
5. Hay **nombres repetidos** (~39, p. ej. `Puebla`, `Guadalupe`). Si el nombre
   no es único, desambigua (estado, id, o la más poblada) y **avisa** en la
   salida; no elijas un nodo al azar en silencio.

### Interfaz

6. CLI, al estilo de Rumania:

```bash
python find_route.py --from-city Tijuana --to Cancún
```

Debe reportar al menos: **Status**, **Path**, **Depth** (hops), **Cost** (km),
**Expanded**, y la heurística usada. Si el camino es muy largo, puedes imprimir
solo las primeras y últimas ciudades más el total; el mapa debe mostrar la
ruta completa.

7. En `mexico_map.html`, el usuario puede indicar **origen** y **destino** y
   ver la ruta: nodos del camino y aristas usadas, más el costo en km en el
   panel. No basta un `print` en terminal: la **opción** tiene que existir en
   el mapa.

La A* del navegador puede ser un puerto del mismo algoritmo (el JSON del grafo
ya va incrustado en el HTML) o el resultado de un script Python que actualice
la vista. Lo que cuenta es que **A\*** calcule la ruta y el mapa la muestre.

### Parejas sugeridas para probar

- `Tijuana` → `Cancún` (península a península)
- `Mexico City` → `Monterrey`
- `Guadalajara` → `Mérida`
- `Hermosillo` → `Oaxaca`

Los nombres deben coincidir **exactamente** con el JSON (`Mexico City`, no
`CDMX`; `Cancún`, no `Cancun`).

## Pasos sugeridos

1. Abre el mapa y localiza tus dos ciudades:

```bash
open "Mexico map/mexico_map.html"    # macOS; en Windows: start el archivo
```

Confirma nombres en `mexico_cities_graph.json` (campos `name`, `state`, `lat`,
`lon`) o con la caja **Find a city**.

2. Relee A* en `Búsqueda informada/project/search/astar.py` y cómo Rumania
   arma `h` con coordenadas (`romania/heuristics.py`, rama euclidiana). Aquí
   `h` es haversine al destino, no una tabla.

3. Carga el JSON, arma un grafo no dirigido (cada arista vale en ambos
   sentidos) y un `h(estado)` que consulte lat/lon del destino.

4. Implementa `find_route.py` y verifica una pareja corta (p. ej. dos ciudades
   vecinas) antes de Tijuana → Cancún.

5. Agrega origen, destino y “Find route” (o equivalente) en el HTML. Resalta
   el camino; el resto del grafo puede atenuarse.

6. Comprueba que el costo CLI y el del mapa coinciden para la misma pareja.

## Criterios de aceptación

- A* (no BFS, no Dijkstra-sin-`h`, no “el vecino más cercano” a mano) calcula
  la ruta.
- `h(n)` es haversine al destino (admisible / consistente en este grafo, porque
  las aristas también son haversine).
- `python find_route.py --from-city ORIGEN --to DESTINO` corre y muestra camino
  y km.
- `mexico_map.html` permite elegir dos ciudades y **pinta** la ruta.
- Nombres ambiguos no se resuelven en silencio.
- El 4-NN / MST del grafo no cambió.

## Entrega

1. El código en `Mexico map/` (CLI + mapa) y lo que hayas reutilizado de A*.
2. Un README corto (en `Mexico map/` o junto al ejercicio) con cómo ejecutar
   el CLI y cómo usar la opción de ruta en el HTML.
3. Evidencias de **al menos dos** parejas distintas (capturas del mapa con la
   ruta y salida del CLI). Incluye una ruta **larga** (p. ej. Tijuana–Cancún o
   equivalente).
4. Un breve reporte (media página) que responda:
   - Qué usaste como estado (¿nombre? ¿id? ¿nombre + estado?) y cómo resolviste
     duplicados.
   - Por qué haversine es admisible aquí.
   - Costo en km y número de hops de tu ruta larga, y cuántos nodos expandió A*.

## Reto opcional

- Compara A* con **UCS** (o A* con `h = 0`) en la misma pareja: el costo en km
  debe coincidir; A* debería expandir **menos** nodos.
- Añade Greedy (`h` solo) y muestra en el mapa ambas rutas si discrepan.
- Si hay dos ciudades con el mismo nombre, fuerza el desambiguado por estado
  en la UI (`Puebla, Puebla` vs. la otra `Puebla`).

## Pistas

- Reutilizar A* no es pegar el archivo y esperar que compile: en Rumania el
  estado es un `str` único; en México el `id` entero (o `"Nombre|Estado"`) es
  más seguro.
- `h(n)` se calcula **al vuelo** con lat/lon; no necesitas una tabla 1000×1000.
- Haversine nunca sobreestima la distancia por aristas que **también** son
  haversine (desigualdad del triángulo). Por eso A* queda óptimo en km.
- El HTML se genera desde `HTML_TEMPLATE` en `generate_mexico_graph.py`. Si
  editas `mexico_map.html` a mano, **no vuelvas a correr** el generador o
  perderás la UI. Mejor documenta “no regenerar” o mueve la plantilla con
  cuidado.
- Coordenadas en el JSON: `lon` es X, `lat` es Y. Haversine usa
  `(lat1, lon1, lat2, lon2)` en ese orden (mira la función existente).
- Acentos y espacios importan: `León de los Aldama`, `Santiago de Querétaro`,
  `Mérida`.

