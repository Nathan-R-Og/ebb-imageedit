#python script to format images and create binary/optimized png for tilemaps

from math import ceil, sqrt

from PIL import Image, ImageOps
import argparse
import sys

palette = open("nes.pal", "rb").read()

bg_color = (0xff,0,0xff)
#create palette image
p_img = Image.new('P', (1, 1))
p_img.putpalette(palette+bytearray(bg_color))

whatIs = "sprite"
assumed_palettes = [
    [-1, 0xF, 0x00, 0x30], #greyscale ?
    [-1, 0xF, 0x16, 0x37], #black/red/tan
    [-1, 0xF, 0x24, 0x37], #black/pink/tan ?
    [-1, 0xF, 0x12, 0x37], #black/blue/tan
]

def PngToTilePng(image:str):
    #image:[tiles]
    tile_keys = {}

    #bytes
    tiles = []

    #PIL.Images
    image_tiles = []

    fg = Image.open(image).convert("RGBA")
    for y in range(fg.size[1]):
        for x in range(fg.size[0]):
            pixel = fg.getpixel((x, y))
            if pixel == (0,0,0,0):
                fg.putpixel((x, y), bg_color)

    fg = fg.convert("RGB").quantize(palette=p_img, dither=0)


    for y in range(fg.size[1] // 8):
        for x in range(fg.size[0] // 8):
            #get 8x8 slice
            a = (x*8, y*8, (x+1)*8, (y+1)*8)
            cropped_img = fg.crop(a)

            #get pixel data
            data = cropped_img.tobytes()
            data2 = ImageOps.mirror(cropped_img).tobytes()

            exists = data in tiles
            exists_flipped_h = data2 in tiles


            #check if already exists
            if not (exists or exists_flipped_h):
                tiles.append(data)
                cropped_img.info["transparency"] = len(palette) // 3
                image_tiles.append(cropped_img)

            #get tile id and add
            if not image in list(tile_keys.keys()):
                tile_keys[image] = []

            #add id based on the version that exists
            if not exists and exists_flipped_h:
                tile_keys[image].append(tiles.index(data2))
            elif exists and not exists_flipped_h:
                tile_keys[image].append(tiles.index(data))

    padTile = Image.new("RGBA", (8,8))
    padTile.paste( (0,0,0,0), (0, 0, 8, 8))

    #construct a tilemap image from only unique tiles
    newWidth = ceil(sqrt(len(image_tiles)))
    newHeight = newWidth
    newSize = (newWidth, newHeight)
    newImage = Image.new("RGBA", (newSize[0]*8, newSize[1]*8))
    i = 0
    while i < newSize[0]*newSize[1]:
        isPadding = i >= len(image_tiles)
        if not isPadding:
            tile = image_tiles[i]
        else:
            tile = padTile.copy()

        for y in range(8):
            for x in range(8):
                pixel = tile.getpixel((x, y))
                if pixel == bg_color:
                    tile.putpixel((x, y), (0,0,0,0))

        x = i % newSize[0]
        y = i // newSize[0]
        a = (x*8, y*8, (x+1)*8, (y+1)*8)
        newImage.paste(tile, a)

        if x == newSize[0]-1 and isPadding:
            a = (0, 0, a[2], a[3])
            newImage = newImage.crop(a)
            break
        i += 1
    return newImage


#assumes rgba
def pixel_to_id(color):
    #0xf is also the default transparent
    #lets use -1 for a paletted alpha
    if color in [bg_color, (0,0,0,0)]:
        return -1
    #get only rgb
    b = bytes(color[:-1])
    #get id
    id = palette.find(b) // 3
    #0xf is the default black
    if b == bytes([0, 0, 0]):
        id = 0xf
    #0x30 is the default white. there are multiple
    elif b == bytes([0xff, 0xfe, 0xff]):
        id = 0x30
    return id

def PngTo2bpp(image:Image, style:dict={}, pal:list=[]):
    out_bytes = bytearray()

    for y in range(image.size[1] // 8):
        for x in range(image.size[0] // 8):
            #get 8x8 slice
            a = (x*8, y*8, (x+1)*8, (y+1)*8)
            cropped_img:Image = image.crop(a)

            #check if alpha
            #skip if so
            lohi = cropped_img.getcolors(maxcolors=4)
            if (len(lohi) == 1 and lohi[0][1] == (0,0,0,0)) and len(out_bytes) > 0:
                continue


            #get all unique colors and make a similar palette to ram
            unique_colors = cropped_img.getcolors(maxcolors=4)
            paletted_colors = []
            for color in unique_colors:
                paletted_colors.append(pixel_to_id(color[1]))
            paletted_colors.sort()

            #check if that palette exists
            #if not, throw it in the assumed_palettes list
            assumed_set = []
            freebie = -1
            if style == {}:
                for i in range(len(assumed_palettes)):
                    a = assumed_palettes[i]
                    if type(a) == list:
                        a.sort()
                        if set(a).intersection(set(paletted_colors)):
                            assumed_set = a
                    elif type(a) == int:
                        if a == -1:
                            freebie = i
            else:
                if type(style["use_palettes"]) == list:
                    ab = (image.size[0] // 8) * y
                    ab += x
                    get = style["use_palettes"][ab]
                    assumed_set = pal[get]
                elif type(style["use_palettes"]) == int:
                    assumed_set = pal[style["use_palettes"]]


            #if palette didnt exist already, throw it in
            if freebie != -1 and len(assumed_set) == 0:
                assumed_set = paletted_colors

            low = bytearray() #lo bitplane
            high = bytearray() #hi bitplane
            for pY in range(8):
                #get row
                colorIds = []
                for pX in range(8):
                    color = cropped_img.getpixel((pX, pY))
                    id = pixel_to_id(color)
                    colorIds.append(assumed_set.index(id))

                #lo plane
                byte = 0
                for i in range(8):
                    byte |= (colorIds[i] & 0b00000001) << (7 - i)
                low.append(byte)

                #hi plane
                byte = 0
                for i in range(8):
                    byte |= ((colorIds[i] & 0b00000010) >> 1) << (7 - i)
                high.append(byte)
            #write row
            out_bytes += low+high
    return out_bytes

if __name__ == "__main__":
    sys.argv = ['py.py', 'ninten.png', 'test.png']
    parser = argparse.ArgumentParser(description="make a tilemap")
    parser.add_argument(
        "path",
        type=str
    )

    args = parser.parse_args()

    newImage = PngToTilePng(args.path)
    open("test.bin", "wb").write(PngTo2bpp(newImage))

