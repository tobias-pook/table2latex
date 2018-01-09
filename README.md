# table2latex
Create latex files programatically from python or from csv dumps

## Installation
The package is currently not listed in pypi and you may install it manually.

```
git clone https://github.com/tobias-pook/table2latex.git
cd table2latex
pip  install --user -e .
```

## Examples
The repository contains the file `examples/car_example.csv` which is used for
the following examples.

### Creating a flat latex table from csv input
```
bin/csv2tex.py examples/car_example.csv
```
