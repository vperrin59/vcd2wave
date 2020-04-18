#

import sys
import os
import json
import argparse
import re

from Verilog_VCD import parse_vcd
from Verilog_VCD import get_timescale
from Verilog_VCD import list_sigs

class Vcd2Wave(object):
    """docstring for Vcd2Wave"""
    # Ensure config start and end time are the same unit
    # Check end_time is in the VCD
    def __init__(self, cfg_name, vcd_name):
        self.cfg = {}
        with open(cfg_name) as json_file:
            self.cfg.update(json.load(json_file))

        self.vcd_name       = vcd_name
        self.vcd_signals    = []
        self.vcd_signal_keys = {}
        self.vcd            = None
        self.win_tv         = {}
        time_re = re.compile(r"(?P<value>[\d\.]+)(?P<unit>\w+)")
        self.timeunit = time_re.match(self.cfg["start_time"]).group("unit")
        # Start / End time in VCD unit
        self.start_time = float(time_re.match(self.cfg["start_time"]).group("value"))
        self.end_time = float(time_re.match(self.cfg["end_time"]).group("value"))
        self.clock_symb = None
        self.TIME_IDX = 0
        self.VAL_IDX = 1
        self.wavedrom = []
        self.clock_edge_cnt = 0
    # def collapse_bus_sigs(self, sigs):
    #     clps_sigs = set()
    #     for s in sigs:
    #         if "[" in s:
    #             bus_sig = s.split("[")[0]
    #             clps_sigs.add(bus_sig)
    #         else:
    #             clps_sigs.add(s)
    #     return clps_sigs

    def get_start_time(self):
        pass

    def vcd_sig_list_gen(self):
        # First filter ref_signals on inst_name
        ref_signals = list_sigs(self.vcd_name)
        ref_signals = [x for x in ref_signals if self.cfg["inst_name"] in x]
        # print(ref_signals)
        # print(self.cfg)
        for s in self.cfg["filter"]:
            matches = 0
            full_name = self.cfg["inst_name"] + "." + s

            busregex = re.compile(r"%s(\[\d+\])*" % full_name)
            for ref_s in ref_signals:
                if busregex.match(ref_s):
                    matches += 1
                    self.vcd_signals.append(ref_s)
                    # Don't break because there could be multiple matches
            assert(matches > 0), full_name + " not in ref_signals"

        return self.vcd_signals

    def parse_vcd(self):
        self.vcd = parse_vcd(self.vcd_name, siglist=self.vcd_signals, opt_timescale=self.timeunit)
        for k in self.vcd:
            for net in self.vcd[k]["nets"]:
                if self.cfg["clk_name"] == net["name"]:
                    self.clock_symb = k
                else:
                    for s in self.cfg["filter"]:
                        # Normally no need to filter on hier since we already did it previously
                        if s == net["name"]:
                            self.vcd_signal_keys[k] = str(s)
                            break

            # print(k)
            # print(self.vcd[k]["nets"][0]["name"])
            # print(self.vcd[k])
        # print(get_timescale())
        # print(self.vcd.keys())
        # print(self.vcd)

    # Collapse buses ?

    def window_vcd(self):
        self.win_tv = {}
        # Limit VCD to start and end times
        for k in self.vcd:
            start_idx = 0
            end_idx = len(self.vcd[k]["tv"])
            in_wdw = False
            print(self.vcd[k]["nets"][0]["name"])
            for i, (t, v) in enumerate(self.vcd[k]["tv"]):
                print(t)
                print(v)
                # print(self.start_time)
                if (not in_wdw) and (t >= self.start_time):
                    print("found start")
                    if t != self.start_time:
                        self.win_tv[k] = [(self.start_time, self.vcd[k]["tv"][i - 1][self.VAL_IDX])]
                    else:
                        self.win_tv[k] = []

                    start_idx = i
                    in_wdw  = True
                elif in_wdw and t > self.end_time:
                    end_idx = i
                    in_wdw  = False
                    break

                if in_wdw:
                    self.win_tv[k].append((t, v))

            # Signal is constant
            if k not in self.win_tv:
                self.win_tv[k] = [(self.start_time, self.vcd[k]["tv"][-1][self.VAL_IDX])]

        for k in self.win_tv:
            if k in self.vcd_signal_keys:
                print(self.vcd_signal_keys[k])
            else:
                print(self.cfg["clk_name"])
            print(self.win_tv[k])
        # print(self.clock_symb)
        # print(self.vcd_signal_keys)

    def gen_wavedrom_array(self):
        self.wavedrom = {}
        self.clock_edge_cnt = 0
        signals_idx = {}
        for k in self.vcd_signal_keys.keys():
            signals_idx[k] = 0
            self.wavedrom[k] = []
        # signals_idx = {f:0 for f in self.vcd_signal_keys.keys()}
        # Loop over clock times
        for i, (t, v) in enumerate(self.win_tv[self.clock_symb]):
            if v == "1":
                self.clock_edge_cnt += 1
                # self.wavedrom.append({})
                # Iterate over signals
                for s_k in self.vcd_signal_keys.keys():
                    # print(s_k)
                    if signals_idx[s_k] >= 0:
                        # Progress in time
                        while self.win_tv[s_k][signals_idx[s_k]][self.TIME_IDX] < t:
                            signals_idx[s_k] += 1
                            if signals_idx[s_k] == len(self.win_tv[s_k]):
                                # Signal is constant from here
                                signals_idx[s_k] = -1
                                break

                        # print("Found time match clock %d signal %d" % (i, signals_idx[s_k]))
                    # REVISIT: Handle the case where signal is constant
                    # print("Time clock %f signal %f" % (t, self.win_tv[s_k][signals_idx[s_k]][self.TIME_IDX]))
                    if signals_idx[s_k] < 0:
                        self.wavedrom[s_k].append(self.win_tv[s_k][-1][self.VAL_IDX])
                    elif t == self.win_tv[s_k][signals_idx[s_k]][self.TIME_IDX]:
                        self.wavedrom[s_k].append(self.win_tv[s_k][signals_idx[s_k]][self.VAL_IDX])
                    elif t < self.win_tv[s_k][signals_idx[s_k]][self.TIME_IDX]:
                        self.wavedrom[s_k].append(self.win_tv[s_k][signals_idx[s_k] - 1][self.VAL_IDX])
        print(self.wavedrom)

    def dump_wavedrom(self):
        # print(self.vcd_signal_keys)
        indent = ""
        clk = "P"
        for i in range(self.clock_edge_cnt - 1):
            clk += "."
        with open ("test.drom.json", "w") as f:
            f.write(indent + "{\n")
            indent += " " * 2
            f.write(indent + "\"signal\": [\n")
            indent += " " * 2
            ############# Clock
            f.write(indent + "{\n")
            indent += " " * 2
            f.write(indent + "\"name\": \"%s\",\n" % self.cfg["clk_name"])
            f.write(indent + "\"wave\": \"%s\"\n" % clk)
            indent = indent[:-2]
            f.write(indent + "},\n")
            ############## Signals
            for k in self.wavedrom:
                wave = ""
                prev = ""
                for v in self.wavedrom[k]:
                    if v == prev:
                        wave += "."
                    else:
                        wave += v
                    prev = v

                f.write(indent + "{\n")
                indent += " " * 2
                f.write(indent + "\"name\": \"%s\",\n" % self.vcd_signal_keys[k])
                f.write(indent + "\"wave\": \"%s\"\n" % wave)
                indent = indent[:-2]
                f.write(indent + "},\n")

            indent = indent[:-2]
            f.write(indent + "]\n")
            indent = indent[:-2]
            f.write(indent + "}\n")

# def vcd2wavedrom():
#     vcd = parse_vcd(config['input'])
#     timescale = int(re.match(r'(\d+)', get_timescale()).group(1))
#     vcd_dict = {}
#     for i in vcd:
#         vcd_dict[vcd[i]['nets'][0]['hier']+'.'+vcd[i]['nets'][0]['name']] = \
#             vcd[i]['tv']

#     homogenize_waves(vcd_dict, timescale)
#     dump_wavedrom(vcd_dict, timescale)


def main(argv):
    parser = argparse.ArgumentParser(description='Transform VCD to wavedrom')
    parser.add_argument('--config', dest='configfile', required=True)
    parser.add_argument('--input', nargs='?', dest='input', required=True)
    parser.add_argument('--output', nargs='?', dest='output', required=False)

    args = parser.parse_args(argv)
    args.input = os.path.abspath(os.path.join(os.getcwd(), args.input))

    wavegen = Vcd2Wave(args.configfile, args.input)
    wavegen.vcd_sig_list_gen()
    wavegen.parse_vcd()
    wavegen.window_vcd()
    wavegen.gen_wavedrom_array()
    wavegen.dump_wavedrom()
    # vcd2wavedrom()

if __name__ == '__main__':
    main(sys.argv[1:])