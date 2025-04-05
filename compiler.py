import yaml
import png_to_binary
import os
from PIL import Image
from math import ceil, sqrt

out_path = "sheet_dump/"
if not os.path.exists(out_path):
    print("you have not ripped any files!")
    exit(hash("bad"))

data_loaded = yaml.safe_load(open("characters1.yaml", 'r'))

page_length = 0x800

types = data_loaded["type"]
assumed_palettes = data_loaded["assumed_palettes"]
splits = data_loaded["data"]

split_s = {}

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
        end = page_length

    for path in split.paths:
        if not path in (split_s.keys()):
            split_s[path] = [[start, end]]
        else:
            split_s[path].append([start, end])
    i += 1

sheet_bytes = bytearray(page_length)

for file in list(split_s.keys()):
    data = split_s[file]
    use_style = {}
    for style in data_loaded["styling"]:
        if style["name"] == file:
            use_style = style
            break
    if use_style == {}:
        continue

    image_path = f"{out_path}{file}.png"
    newImage = None

    if "tile_order" in list(use_style.keys()):
        fg = Image.open(image_path).convert("RGBA")

        unique_tiles = {}

        #get all unique tiles
        for y in range(len(use_style["tile_order"])):
            tileset = use_style["tile_order"][y]
            for x in range(len(tileset)):
                tile = tileset[x]
                if tile == "-":
                    tile = 0
                else:
                    tile = abs(tile)
                if not tile in unique_tiles:
                    use_style["tile_order"][y][x] = tile
                    unique_tiles[tile] = None
                else:
                    use_style["tile_order"][y][x] = -1

        for y in range(len(use_style["tile_order"])):
            tileset = use_style["tile_order"][y]
            for x in range(len(tileset)):
                tile = tileset[x]
                if tile == -1:
                    continue

                a = (x*8, y*8, (x+1)*8, (y+1)*8)
                unique_tiles[tile] = fg.crop(a)

        newWidth = ceil(sqrt(len(list(unique_tiles.keys()))))
        newHeight = newWidth
        newImage = Image.new("RGBA", (newWidth*8, newHeight*8))

        i = 0
        for y in range(newHeight):
            for x in range(newWidth):
                if i >= len(list(unique_tiles.keys())):
                    break
                a = (x*8, y*8, (x+1)*8, (y+1)*8)
                newImage.paste(unique_tiles[i], a)
                i += 1


    else:
        newImage = png_to_binary.PngToTilePng(image_path)

    file_bytes = png_to_binary.PngTo2bpp(newImage, style, assumed_palettes)

    i = 0
    for split in split_s[file]:
        length = split[1]-split[0]
        sheet_bytes[split[0]:split[1]] = file_bytes[i:i+length]
        i += length

open('characters1.bin', "wb").write(sheet_bytes)




