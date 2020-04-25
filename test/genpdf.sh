python ../src/vcd2wave.py --config example_cfg.yaml --input ../vcd/dump.vcd --output test.drom.json

wavedrompy --input test.drom.json --svg test.drom.svg
inkscape --file test.drom.svg --export-pdf test.drom.pdf
