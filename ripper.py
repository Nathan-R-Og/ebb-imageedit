import yaml
import binary_to_png
import os
import hashlib
from glob import glob

data_loaded = yaml.safe_load(open("characters1.yaml", 'r'))



rhash = "5bacf7ba94c539a1caf623dbe12059a3"

roms = glob("*.nes")
useRom = None
for rom in roms:
    getHash = hashlib.md5(open(rom, "rb").read()).hexdigest()
    if getHash != rhash:
        print("bad rom!")
        exit(hash("bad"))
    else:
        useRom = rom
        break

if useRom == None:
    print("no rom found!")
    exit(hash("bad"))

byteData = open(useRom, "rb").read()[0x58010:0x58010+0x800]

#byteData = open(data_loaded["binary"], "rb").read()

types = data_loaded["type"]
assumed_palettes = data_loaded["assumed_palettes"]
splits = data_loaded["data"]

binary_files = {}

class Split(object):
    def __init__(self, start:int, paths):
        self.start = start
        if type(paths) == str:
            self.paths = [paths]
        elif type(paths) == list:
            self.paths = paths



def getSplitData(split):
    #single file
    if type(split) == list:
        return Split(split[0], split[1])
    #multifile
    elif type(split) == dict:
        key = list(split.keys())[0]
        return Split(key, split[key])

i = 0
while i < len(splits):
    split = getSplitData(splits[i])

    start = split.start
    end = 0

    if i < len(splits)-1:
        end = getSplitData(splits[i+1]).start
    else:
        end = len(byteData)

    split_bytes = byteData[start:end]
    for file in split.paths:
        if not file in list(binary_files.keys()):
            binary_files[file] = split_bytes
        else:
            binary_files[file] += split_bytes

    i += 1


out_path = "sheet_dump/"
if not os.path.exists(out_path):
    os.mkdir(out_path)

#for file in list(binary_files.keys()):
#    open(f"{out_path}{file}.bin", "wb").write(binary_files[file])

for file in list(binary_files.keys()):
    data = binary_files[file]
    use_style = []
    for style in data_loaded["styling"]:
        if style["name"] == file:
            use_style = style
            break
    if use_style == []:
        continue

    binary_to_png.shiftable = False

    binary_to_png.Convert(data,
        f"{out_path}{file}.png",
        assumed_palettes,
        use_style,
        )

