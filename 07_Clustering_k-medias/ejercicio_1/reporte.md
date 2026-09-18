# Reporte

## Archivos notebook

- [K-Medias Modificado](01_K-medias-mod.ipynb)
- [K-Medias Original](01_K-medias.ipynb)

## Comparación de Graficas

| inercia    |  k=3   | k=5    | k=8    | silueta k=5 |
|------------|-------:|-------:|-------:|------------:|
| Original   | 653.22 | 224.07 | 127.13 |  0.6555     |
| Modificada | 487.42 | 181.56 | 106.20 |  0.5609     |

La primera imagen de cada grupo es el notebook original y la segunda es la modificada.

**Original**

> blob_centers = np.array(
>     [[ 0.2,  2.3],
>      [-1.5 ,  2.3],
>      [-2.8,  1.8],
>      [-2.8,  2.8],
>      [-2.8,  1.3]])
> blob_std = np.array([0.4, 0.3, 0.1, 0.1, 0.1])

**Modificado**

> blob_centers = np.array(
>     [[ 0.2,  2.3],
>      [-1.5 ,  2.3],
>      [-2.1,  1.8],
>      [-0.5,  2.8],
>      [-3.4,  1.3]])
> blob_std = np.array([0.4, 0.3, 0.1, 0.1, 0.1])

### Scatter de blobs

![Antes](images/scatter.png)
![Despues](images/scatter-mod.png)

### Diagrama de Voronoi (k=5)

![Antes](images/voronoi.png)
![Despues](images/voronoi-mod.png)

### Curva de codo / Inercia

![Antes](images/codo-inercia.png)
![Despues](images/codo-inercia-mod.png)

### Curva de Silueta

![Antes](images/silueta.png)
![Despues](images/silueta-mod.png)

## Evidencia Colab

![Evidencia Colab](images/evidencia.png)
