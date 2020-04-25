import sys
import os
import argparse
import re
import math
import yaml

from Verilog_VCD import parse_vcd
from Verilog_VCD import get_timescale
from Verilog_VCD import list_sigs

class Vcd2Wave(object):
    """docstring for Vcd2Wave"""
    # Ensure config start and end time are the same unit
    # Check end_time is in the VCD
    def __init__(self, cfg_name, vcd_name):
        self.cfg = {}
        # Read YAML file
        with open(cfg_name, 'r') as cfg_file:
            self.cfg.update(yaml.safe_load(cfg_file))

        self.vcd_name       = vcd_name
        self.vcd_signals    = []
        self.vcd_signal_map = {}
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
        # Dictionary indexed by signal keys
        # Each key contains the list of values for each clock edge
        # All the list should have the same length
        self.wavedrom = {}
        # It's the length of the lists in self.wavedrom
        self.clock_edge_cnt = 0
        self.bus_format = "h"

    def vcd_sig_list_gen(self):
        # First filter ref_signals on inst_name
        ref_signals = list_sigs(self.vcd_name)
        ref_signals = [x for x in ref_signals if self.cfg["inst_name"] in x]
        # print(ref_signals)
        # print(self.cfg)
        for s in self.cfg["signals"]:
            matches = 0
            full_name = self.cfg["inst_name"] + "." + s

            busregex = re.compile(r"%s(\[\d+\])*" % full_name)
            for ref_s in ref_signals:
                if busregex.match(ref_s):
                    matches += 1
                    print("%s matched %s" % (s, ref_s))
                    self.vcd_signals.append(ref_s)
                    # Don't break because there could be multiple matches
            assert(matches > 0), full_name + " not in ref_signals"

        return self.vcd_signals

    def gen_signal_map(self):
        for k in self.vcd:
            for net in self.vcd[k]["nets"]:
                if self.cfg["clk_name"] == net["name"]:
                    self.clock_symb = k
                else:
                    for s in self.cfg["signals"]:
                        # Normally no need to filter on hier since we already did it previously
                        # Handle buses here
                        # if s in net["name"]:
                            # print("%s should match %s" % (s, net["name"]))
                        busregex = re.compile(r"%s(\[\d+\])*" % s)
                        if busregex.match(net["name"]):
                        # if s == net["name"]:
                            self.vcd_signal_map[k] = str(s)
                            break


    def parse_vcd(self):
        self.vcd = parse_vcd(self.vcd_name, siglist=self.vcd_signals, opt_timescale=self.timeunit)
        self.gen_signal_map()
            # print(k)
            # print(self.vcd[k]["nets"][0]["name"])
            # print(self.vcd[k])
        # print(get_timescale())
        # print(self.vcd.keys())
        # print(self.vcd)

    # Convert 4 state bus
    def bus_convert(self, bus):
        bus_w = len(bus)
        bus_s = "".join(reversed(bus))
        if self.bus_format == "b":
            symb_cnt = bus_w
            if "x" in bus:
                return "0b" + (symb_cnt * "X")
            elif "z" in bus:
                return "0b" + (symb_cnt * "Z")
            else:
                return "0b" + bus_s
        elif self.bus_format == "d":
            symb_cnt = int(math.ceil(math.log10(2**bus_w)))
            if "x" in bus:
                return (symb_cnt * "X")
            elif "z" in bus:
                return (symb_cnt * "Z")
            else:
                return int("".join(reversed(bus)), 2)
        elif self.bus_format == "h":
            symb_cnt = -(bus_w // -4)
            if "x" in bus:
                return "0x" + (symb_cnt * "X")
            elif "z" in bus:
                return "0x" + (symb_cnt * "Z")
            else:
                return hex(int(bus_s, 2))

    # Collapse buses ?
    def collapse_bus_vcd(self):
        new_vcd = {}
        bus_map = {}
        # Sort keys of the same bus
        for s in self.cfg["signals"]:
            busregex = re.compile(r"%s(\[(?P<bit_nb>\d+)\])+" % s)
            for k in self.vcd:
                for net in self.vcd[k]["nets"]:
                    if busregex.match(net["name"]):
                        bit_nb = busregex.match(net["name"]).group("bit_nb")
                        # Part of a bus
                        if s not in bus_map:
                            bus_map[s] = {}

                        # Sort by bit_nb ?
                        bus_map[s][k] = (int(bit_nb), net["name"])

        print(bus_map)
        # Merge t,v
        tv = {}
        for s in bus_map:
            bus_w = len(bus_map[s])
            tv[s] = []
            # Binary format
            bus = [""] * bus_w
            signals_idx = {}
            t = 0
            # Init values
            for k in bus_map[s]:
                signals_idx[k] = 0
                bus[bus_map[s][k][0]] = self.vcd[k]["tv"][0][self.VAL_IDX]

            for k in signals_idx:
                if k in bus_map[s]:
                    if signals_idx[k] + 1 >= len(self.vcd[k]["tv"]):
                        del bus_map[s][k]
                        del self.vcd[k]
                        free_vcd_k = k

            # tv[s].append((t, "".join(bus)))
            tv[s].append((t, self.bus_convert(bus)))

            while len(bus_map[s]):

                # Get keys with next time value
                d = {k: self.vcd[k]["tv"][signals_idx[k] + 1][self.TIME_IDX] for k in bus_map[s]}
                t = min(d.values())
                # min_ks = min(d, key=d.get)
                min_ks = [key for key in d if d[key] == t]

                print("Minimum keys {}".format(min_ks))

                # Progress time for keys with the next value
                for k in min_ks:
                    signals_idx[k] += 1
                    bus[bus_map[s][k][0]] = self.vcd[k]["tv"][signals_idx[k]][self.VAL_IDX]

                # Remove keys in bus_maps if constant
                for k in signals_idx:
                    if k in bus_map[s]:
                        if signals_idx[k] + 1 >= len(self.vcd[k]["tv"]):
                            del bus_map[s][k]
                            del self.vcd[k]
                            free_vcd_k = k


                # t = self.vcd[min_ks[0]]["tv"][signals_idx[min_ks[0]]][self.TIME_IDX]
                tv[s].append((t, self.bus_convert(bus)))
                # tv[s].append((t, ("".join(bus), 2)))

            print(tv)
            self.vcd[free_vcd_k] = {"tv": tv[s], "nets": [{"hier": self.cfg["inst_name"], "name": s, "type": "wire", "size": str(bus_w)}]}
            print(self.vcd)

        self.gen_signal_map()

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
            if k in self.vcd_signal_map:
                print(self.vcd_signal_map[k])
            else:
                print(self.cfg["clk_name"])

            self.vcd[k]["tv"] = self.win_tv[k]
            print(self.win_tv[k])
        # print(self.clock_symb)
        # print(self.vcd_signal_map)

    def gen_wavedrom_array(self):
        self.wavedrom = {}
        # Wavedrom keys should be signal maps
        self.clock_edge_cnt = 0
        signals_idx = {}
        for k in self.vcd_signal_map.keys():
            signals_idx[k] = 0
            self.wavedrom[k] = []
        # signals_idx = {f:0 for f in self.vcd_signal_map.keys()}
        # Loop over clock times
        for i, (t, v) in enumerate(self.vcd[self.clock_symb]["tv"]):
            if v == "1":
                self.clock_edge_cnt += 1
                # self.wavedrom.append({})
                # Iterate over signals
                for s_k in self.vcd_signal_map.keys():
                    # print(s_k)
                    if signals_idx[s_k] >= 0:
                        # Progress in time
                        while self.vcd[s_k]["tv"][signals_idx[s_k]][self.TIME_IDX] < t:
                            signals_idx[s_k] += 1
                            if signals_idx[s_k] == len(self.vcd[s_k]["tv"]):
                                # Signal is constant from here
                                signals_idx[s_k] = -1
                                break

                        # print("Found time match clock %d signal %d" % (i, signals_idx[s_k]))
                    # print("Time clock %f signal %f" % (t, self.win_tv[s_k][signals_idx[s_k]][self.TIME_IDX]))
                    if signals_idx[s_k] < 0:
                        self.wavedrom[s_k].append(self.vcd[s_k]["tv"][-1][self.VAL_IDX])
                    elif t == self.vcd[s_k]["tv"][signals_idx[s_k]][self.TIME_IDX]:
                        self.wavedrom[s_k].append(self.vcd[s_k]["tv"][signals_idx[s_k]][self.VAL_IDX])
                    elif t < self.vcd[s_k]["tv"][signals_idx[s_k]][self.TIME_IDX]:
                        self.wavedrom[s_k].append(self.vcd[s_k]["tv"][signals_idx[s_k] - 1][self.VAL_IDX])
        print(self.wavedrom)


    def filter_wavedrom_array(self):
        max_idle_clk_cnt = 5
        new_clock_edge_cnt = 0
        new_wavedrom = {k: [] for k in self.wavedrom}
        idle_cnt     = {k: 0 for k in self.wavedrom}
        prev_val     = {k: "unknown" for k in self.wavedrom}
        # Detect from an index if there is no change, then generate ellipse symbol

        time_idx_ellipsed = []

        print("Filter Wavedrom array")

        for time_idx in range(self.clock_edge_cnt):
            ellipse_en = True
            for k in self.wavedrom:
                if self.wavedrom[k][time_idx] == prev_val[k]:
                    idle_cnt[k] += 1
                else:
                    idle_cnt[k] = 0
                    prev_val[k] = self.wavedrom[k][time_idx]

                if idle_cnt[k] <= max_idle_clk_cnt:
                    ellipse_en = False

            if ellipse_en:
                time_idx_ellipsed.append(time_idx)
                print("Ellipsed index %d" % time_idx)
            else:
                new_clock_edge_cnt += 1
                for k in self.wavedrom:
                    new_wavedrom[k].append(self.wavedrom[k][time_idx])

        self.wavedrom = new_wavedrom
        self.clock_edge_cnt = new_clock_edge_cnt


    def remove_last_comma(self, s):
        return s[:-2] + "\n"

    def open_bracket(self, indent):
        s = indent + "{\n"
        new_indent = indent + " " * 2
        return (s , new_indent)

    def close_bracket(self, indent):
        new_indent = indent[:-2]
        s = new_indent + "},\n"
        return (s, new_indent)

    def bus_wavedrom_replace(self, key, bus_data):
        # REVISIT: Check the type of bus_data, for now assume binary
        if self.vcd_signal_map[key] in self.cfg["signal_maps"]:
            return self.cfg["signal_maps"][self.vcd_signal_map[key]][str(int(bus_data, 2))]
        else:
            return bus_data


    def dump_wavedrom(self, outfname):
        # print(self.vcd_signal_map)
        indent = ""
        clk = "P"
        for i in range(self.clock_edge_cnt - 1):
            clk += "."
        with open (outfname, "w") as f:
            text = ""
            (text, indent) = self.open_bracket(indent)
            f.write(text)

            f.write(indent + "\"signal\": [\n")
            indent += " " * 2
            ############# Clock
            (text, indent) = self.open_bracket(indent)
            f.write(text)
            f.write(indent + "\"name\": \"%s\",\n" % self.cfg["clk_name"])
            f.write(indent + "\"wave\": \"%s\"\n" % clk)
            (text, indent) = self.close_bracket(indent)
            f.write(text)
            ############## Signals
            text = ""
            for k in self.wavedrom:
                is_bus = int(self.vcd[k]["nets"][0]["size"]) > 1
                bus_data = []
                wave = ""
                prev = ""
                for v in self.wavedrom[k]:
                    if v == prev:
                        wave += "."
                    else:
                        if is_bus:
                            wave += "="
                            bus_data.append(v)
                        else:
                            wave += v
                    prev = v

                text += indent + "{\n"
                indent += " " * 2
                if is_bus:
                    text += indent + "\"data\": [\n"
                    indent += " " * 2
                    for d in bus_data:
                        text += indent + "\"%s\",\n" % self.bus_wavedrom_replace(k, d)
                        # f.write(indent + "\"%s\",\n" % d)

                    text = self.remove_last_comma(text)

                    text += indent + "],\n"
                    indent = indent[:-2]

                text += indent + "\"name\": \"%s\",\n" % self.vcd_signal_map[k]
                text += indent + "\"wave\": \"%s\"\n" % wave
                indent = indent[:-2]
                text += indent + "},\n"

            text = self.remove_last_comma(text)
            f.write(text)
            indent = indent[:-2]
            f.write(indent + "],\n")

            ## Config
            f.write(indent + "\"config\": {\n")
            indent += " " * 2
            f.write(indent + "\"hscale\": 1\n")

            (text, indent) = self.close_bracket(indent)
            text = self.remove_last_comma(text)
            f.write(text)

            (text, indent) = self.close_bracket(indent)
            text = self.remove_last_comma(text)
            f.write(text)

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
    wavegen.collapse_bus_vcd()
    wavegen.window_vcd()
    wavegen.gen_wavedrom_array()
    wavegen.filter_wavedrom_array()
    wavegen.dump_wavedrom(args.output)

if __name__ == '__main__':
    main(sys.argv[1:])