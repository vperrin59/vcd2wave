# vcd2wave

Python script to transform a VCD (it doesn't support EVCD) file to JSON wavedrom file (https://wavedrom.com/) format

```
usage: vcd2wave.py [-h] --config CONFIGFILE --input [INPUT]
                       [--output [OUTPUT]]

Transform VCD to wavedrom JSON file

optional arguments:
  -h, --help           show this help message and exit
  --config CONFIGFILE
  --input [INPUT]
  --output [OUTPUT]
```

## Quickstart

Test the example given by running `source genpdf.sh` in the test directory.

## Config options

### Instance name

This define the level of the hierarchy in the VCD where you want to plot signals

### Signals

This will select signals at the defined level of hierarchy. The selected signals will be processed and dumped in the json output

### Signal maps

This is typically used for enum types in order to represent the enum value instead of the binary value in the json

### Max idle

The script can ellipse clock ticks in the VCD when there are no activity in the selected signals. That defines the maximum allowed clock ticks without activity to be plotted

### Start time

This is the starting time to process the signals in the VCD

### End time

This is the ending time to process the signals in the VCD

### Clock name

This is the clock name to be used as reference for clock ticks in the json output
