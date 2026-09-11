# Reporte

## Archivos notebook

![Multilayer Perceptron-Original]("01 Multilayer perceptron.ipynb")
![Multilayer Perceptron-Modificado]("01-mod_Multilayer_Perceptron.ipynb")
![Keras-Multilayer Perceptron-Original]("02 Keras - multilayer perceptron - iris.ipynb")
![Keras-Multilayer Perceptron-Modificado]("02-mod Keras - multilayer perceptron - iris.ipynb")

## Cruvas de error/perdida

### Perceptron from scratch

Original
![Multilayer Perceptron-Original]("02-Keras_original.ipynb")

Modificado
![Multilayer Perceptron-Original]("02-Keras_original.ipynb")

### Keras

Original
![Multilayer Perceptron-Original]("02-Keras_original.ipynb")

┃ Layer (type)                    ┃ Output Shape           ┃       Param # ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ layer1 (Dense)                  │ (None, 3)              │            15 │
│ layer2 (Dense)                  │ (None, 3)              │            12 │
 Total params: 27 (108.00 B)
 Trainable params: 27 (108.00 B)
 Non-trainable params: 0 (0.00 B)

Modificado
![Multilayer Perceptron-Original]("02-Keras_modificado.ipynb")

┃ Layer (type)                    ┃ Output Shape           ┃       Param # ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ layer1 (Dense)                  │ (None, 3)              │            15 │
│ layer2 (Dense)                  │ (None, 3)              │            12 │
│ layer3 (Dense)                  │ (None, 3)              │            12 │
│ layer4 (Dense)                  │ (None, 3)              │            12 │

 Total params: 51 (204.00 B)
 Trainable params: 51 (204.00 B)
 Non-trainable params: 0 (0.00 B)

## Preguntas por responder

3. Un breve reporte (media página a una página) que responda:
   - ¿Bajar más el error al añadir dos capas, o se estancó / empeoró? ¿Igual
     en NumPy y en Keras?
   - ¿Las curvas de la notebook 01 y de Keras se parecen con la misma
     topología? Si no, ¿qué diferencias de implementación podrían explicarlo
     (orden de los datos, inicialización, vectorización, etc.)?
   - Con sigmoides apiladas y MSE, ¿tiene sentido que una red **más profunda**
     no aprenda mejor en Iris? Relaciónalo con lo que viste en las gráficas.
4. Evidencias de haber ejecutado en Colab (captura del entorno Colab o del
   menú Runtime).

## Evidencia