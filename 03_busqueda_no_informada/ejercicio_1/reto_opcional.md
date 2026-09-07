# Reporte

para este ejercicio se eligio la Pareja **Arad** y **Drobeta**

Compara además el número de nodos expandidos: ¿cuál algoritmo “trabajó” más en tu instancia?

Trabajo mas UCS por que genero mas nodos y expandio mas nodos que su contraparte BFS.

## Evidencia de Ejecución

```zsh
inteligencia-artificial/Búsqueda no informada/project on  main [?] via 🐍 3.14.7 via project
➜ python 02_breadth_first_search.py --from-city Arad --to Drobeta
Algorithm: Breadth-first search
Problem:   Arad → Drobeta
Status:    success
Path:      Arad → Sibiu → Rimnicu Vilcea → Craiova → Drobeta
Depth:     4 roads
Cost:      486 km
Expanded:  10 nodes
Generated: 26 nodes
Frontier:  max size 5

inteligencia-artificial/Búsqueda no informada/project on  main [?] via 🐍 3.14.7 via project
➜ python 03_uniform_cost_search.py --from-city Arad --to Drobeta
Algorithm: Uniform-cost search
Problem:   Arad → Drobeta
Status:    success
Path:      Arad → Timisoara → Lugoj → Mehadia → Drobeta
Depth:     4 roads
Cost:      374 km
Expanded:  11 nodes
Generated: 29 nodes
Frontier:  max size 4

inteligencia-artificial/Búsqueda no informada/project on  main [?] via 🐍 3.14.7 via project
➜ python 04_depth_first_search.py --from-city Arad --to Drobeta
Algorithm: Depth-first search
Problem:   Arad → Drobeta
Status:    success
Path:      Arad → Sibiu → Fagaras → Bucharest → Pitesti → Craiova → Drobeta
Depth:     6 roads
Cost:      809 km
Expanded:  7 nodes
Generated: 21 nodes
Frontier:  max size 7

inteligencia-artificial/Búsqueda no informada/project on  main [?] via 🐍 3.14.7 via project
➜ python 05_depth_limited_search.py --from-city Arad --to Drobeta --limit 2
Algorithm: Depth-limited search
Problem:   Arad → Drobeta
Status:    cutoff
Detail:    limit=2
Expanded:  4 nodes
Generated: 12 nodes
Frontier:  max size 6

inteligencia-artificial/Búsqueda no informada/project on  main [?] via 🐍 3.14.7 via project
➜ python 05_depth_limited_search.py --from-city Arad --to Drobeta --limit 4
Algorithm: Depth-limited search
Problem:   Arad → Drobeta
Status:    success
Detail:    limit=4
Path:      Arad → Sibiu → Rimnicu Vilcea → Craiova → Drobeta
Depth:     4 roads
Cost:      486 km
Expanded:  8 nodes
Generated: 18 nodes
Frontier:  max size 8

inteligencia-artificial/Búsqueda no informada/project on  main [?] via 🐍 3.14.7 via project
➜ python 05_depth_limited_search.py --from-city Arad --to Bucharest --limit 3
Algorithm: Depth-limited search
Problem:   Arad → Bucharest
Status:    success
Detail:    limit=3
Path:      Arad → Sibiu → Fagaras → Bucharest
Depth:     3 roads
Cost:      450 km
Expanded:  3 nodes
Generated: 5 nodes
Frontier:  max size 6

inteligencia-artificial/Búsqueda no informada/project on  main [?] via 🐍 3.14.7 via project
➜ python 06_iterative_deepening_search.py --from-city Arad --to Drobeta
Algorithm: Iterative deepening search
Problem:   Arad → Drobeta
Status:    success
Detail:    last_limit=4
Path:      Arad → Sibiu → Rimnicu Vilcea → Craiova → Drobeta
Depth:     4 roads
Cost:      486 km
Expanded:  22 nodes
Generated: 58 nodes
Frontier:  max size 8
```
