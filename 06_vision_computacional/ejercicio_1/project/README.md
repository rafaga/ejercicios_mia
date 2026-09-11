# Computer vision

Pixels, convolution, and Sobel you can read line by line (**no NumPy, no
OpenCV**): an image is a list of lists; a filter multiplies a neighborhood
by a kernel and sums. The default examples are the lecture grids: a
**0|9 step** and an **8×8 letter E**.

## Setup

```bash
cd "Visión computacional/project"
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows (PowerShell):

```powershell
cd "Visión computacional/project"
python3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Later sessions: activate the venv again, then run the programs.
Deactivate with `deactivate`.

## Programs

| File | Role |
|---|---|
| `01_show_image.py` | Grid of numbers + ASCII gray (or R, G, B) |
| `02_one_pixel.py` | One convolution at the probe cell, term by term |
| `03_filter.py` | Slide the kernel over the whole image |
| `04_compare.py` | Lecture numbers, padding, threshold, template SSD |

```bash
python 01_show_image.py
python 02_one_pixel.py
python 03_filter.py
python 04_compare.py
python 01_show_image.py --image data/step.yaml
python 01_show_image.py --image data/rgb_bars.yaml
python 02_one_pixel.py --kernel sobel_x
python 03_filter.py --filter mean
python 03_filter.py --filter sobel
python 03_filter.py --filter edges
python 03_filter.py --image data/letter_e.yaml --filter edges
python 04_compare.py --only lecture
python 04_compare.py --only pad
python 04_compare.py --only threshold
python 04_compare.py --only template
python 04_compare.py --only rgb
```

`02_one_pixel.py` defaults to `data/step.yaml` (lecture arithmetic).
The others default to the letter E (01) or the synthetic scene (03).

## Edit the image

Open a file in `data/` (or copy one).

**`gray`** — type the matrix yourself:

```yaml
name: Lecture step 0|9
kind: gray
pad: edge          # edge | zero | none
probe: [2, 2]      # row, col for program 02
kernel: mean3      # mean3 | mean5 | sobel_x | sobel_y | sharpen | identity
show_kernels: [mean3, sobel_x, sobel_y]
threshold: 0.5     # program 03 edges: fraction of max |G|
pixels:
  - [0, 0, 0, 9, 9]
```

You can replace `kernel: mean3` with an explicit matrix:

```yaml
kernel:
  - [-1, 0, 1]
  - [-2, 0, 2]
  - [-1, 0, 1]
```

**`scene`** — circle + rectangle, same layout as the lecture plot:

```yaml
kind: scene
size: 28
threshold: 0.28
```

**`rgb` / `rgb_bars`** — three channels. Filters use gray = (R+G+B)/3.

**`template:`** on a gray image is the patch that program 04 slides (SSD).

## What to expect

**`data/step.yaml`** (program 02) replays the lecture:

- Mean 3×3 at (2, 2): six 0s and three 9s → **3**
- Sobel-X at (2, 2): **36**
- Sobel-Y at (2, 2): **0** (the edge is vertical)

**`03_filter.py --filter mean`** on the scene — the circle and the rectangle
stay, but the jump at the contour is softer (mean 5×5).

**`03_filter.py --filter edges`** — threshold τ = 0.28 × max Sobel magnitude
draws the two contours.

**`04_compare.py`**

- Lecture: the three numbers above.
- Pad: `edge` keeps a 5×5 output; `zero` darkens the frame; `none` returns 3×3.
- Threshold: τ = 0.10 and 0.28 look similar on this clean scene; 0.70 starts
  to drop corners. Add noise in the YAML if you want a messy low-τ map.
- Template: SSD = 0 at **(2, 4)** — that is where the E was pasted.
- RGB: gold is high R and G, low B.

A convolutional net (the last lecture slides) is the same sum Σ K·I, with K
learned. This project stops at kernels you choose.
