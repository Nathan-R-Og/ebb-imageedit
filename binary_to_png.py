from PIL import Image, ImageOps
from math import ceil, sqrt

palette = open("nes.pal", "rb").read()

#create palette image
p_img = Image.new('P', (1, 1))
p_img.putpalette(palette)


whatIs = "sprite"
bg_color = (0,0,0,0)
shiftable = True

def Convert(data:bytearray, outpath:str, assumed_palettes:list, style:dict):
    tiles = []

    tile_order = []
    if "tile_order" in list(style.keys()):
        tile_order = style["tile_order"]
    use_palettes = None
    if "use_palettes" in list(style.keys()):
        use_palettes = style["use_palettes"]
    shift = {}
    if "shift" in list(style.keys()):
        shift = style["shift"]

    i = 0
    while i < len(data):

        tile = Image.new("RGBA", (8,8))
        lo = data[i:i+8]
        hi = data[i+8:i+0x10]
        ids = []
        for x in range(8):
            for b in range(8):
                hib = (hi[x] >> (7 - b)) & 1
                lob = (lo[x] >> (7 - b)) & 1
                ids.append((hib << 1) | lob)
        for y in range(8):
            for x in range(8):
                getId = ids[x+(y*8)]
                this_palette = []
                #multi entry
                if type(use_palettes) == list:
                    this_palette = assumed_palettes[use_palettes[i // 0x10]]
                #single entry
                elif type(use_palettes) == int:
                    this_palette = assumed_palettes[use_palettes]
                color = this_palette[getId]
                #color is alpha
                if color == -1:
                    tile.putpixel((x, y), bg_color)
                    continue
                color *= 3
                colorpos = palette[color: color+3]
                tile.putpixel((x, y), tuple(colorpos))
        tiles.append(tile)


        i += 0x10

    padTile = Image.new("RGBA", (8,8))
    padTile.paste(bg_color, (0, 0, 8, 8))
    if tile_order == []:

        #construct a tilemap image from only unique tiles
        newWidth = ceil(sqrt(len(tiles)))
        newHeight = newWidth
        newSize = (newWidth, newHeight)
        newImage = Image.new("RGBA", (newSize[0]*8, newSize[1]*8))
        i = 0
        while i < newSize[0]*newSize[1]:
            isPadding = i >= len(tiles)
            if not isPadding:
                tile = tiles[i]
            else:
                tile = padTile.copy()
            x = i % newSize[0]
            y = i // newSize[0]
            a = (x*8, y*8, (x+1)*8, (y+1)*8)

            newImage.paste(tile, a)

            if x == newSize[0]-1 and isPadding:
                a = (0, 0, a[2], a[3])
                newImage = newImage.crop(a)
                break
            i += 1
    else:
        newWidth = len(tile_order[0])
        newHeight = len(tile_order)
        newSize = (newWidth, newHeight)
        newImage = Image.new("RGBA", (newSize[0]*8, newSize[1]*8))
        i = 0
        while i < newSize[0]*newSize[1]:
            x = i % newSize[0]
            y = i // newSize[0]
            a = [x*8, y*8, (x+1)*8, (y+1)*8]

            tileId = tile_order[y][x]
            isPadding = tileId == None
            isFlipped = False

            if tileId == "-":
                tileId = 0
                isFlipped = True
            else:
                isFlipped = tileId < 0


            #add offset to the position if styled
            if shiftable:
                for entry in shift:
                    if tileId in list(entry.keys()):
                        a[0] += entry[tileId][0]
                        a[2] += entry[tileId][0]
                        a[1] += entry[tileId][1]
                        a[3] += entry[tileId][1]
                        break

            if not isPadding:
                tile = tiles[abs(tileId)]
                if isFlipped:
                    tile = ImageOps.mirror(tile)
            else:
                tile = padTile.copy()

            #get image contents in that position
            #composite over that, then paste
            #this allows for alpha layering. shouldnt be needed
            #but JUST IN CASE!!!
            newImage.paste(Image.alpha_composite(newImage.crop(a), tile), a)

            if x == newSize[0]-1 and isPadding:
                a = (0, 0, a[2], a[3])
                newImage = newImage.crop(a)
                break
            i += 1


    newImage.convert("RGBA")
    newImage.save(outpath)

    return newImage
