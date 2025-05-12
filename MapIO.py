import yaml

byte_data = open("split/map.bin", "rb").read()

#Map height * width in terms of 64x64 chunks
mapTiles = []
mapTileset = [] #second tileset
mapEvent = []

#Same as above, divided by 4
sectorPalette = []
sectorArea = []
sectorTileset1 = []
sectorTileset2 = []

banksMap = [0x2000, 0x6000, 0xA000, 0xE000, 0x12000, 0x16000, 0x1A000]
curBank = 0
for offset in banksMap:
    for i in range(0x2000):
        tileOffs = offset + i #Offset of current 64x64 map data
        arrayOffs = (curBank * 0x2000) + i
        currentByte = byte_data[tileOffs]
        mapTiles.append(currentByte & 0b00111111); #Get lower 6 bits only of map data, store in array
        mapTileset.append((currentByte & 0b01000000) != 0)
        mapEvent.append((currentByte & 0b10000000) != 0)

    curBank += 1

#Lower 6 bits of 3800-3FFF (skip 1st bank)
banksSector = [0x5800, 0x9800, 0xD800, 0x11800, 0x15800, 0x19800, 0x1D800]
curBank = 0
for offset in banksSector:
    for i in range(0x200):
        tileOffs = offset + (i * 4) #Offset of current 256x256 sector data

        #First 6 bits of each byte
        sectorPalette.append(byte_data[tileOffs] & 0b00111111)
        sectorArea.append(byte_data[tileOffs+1] & 0b00111111)
        sectorTileset1.append(byte_data[tileOffs+2] & 0b00111111)
        sectorTileset2.append(byte_data[tileOffs+3] & 0b00111111)
    curBank += 1

from PIL import Image

graphics8 = []
for tileset in range(32):
    image = Image.open(f"extract/graphics/tileset{tileset+1}.png")
    for y in range(4):
        for x in range(0x10):
            newImage = image.crop((x*8, y*8, (x+1)*8, (y+1)*8))
            graphics8.append(newImage)

#Lower 6 bits of 3000-37FF
graphics16 = []
banks16 = [0x1000, 0x5000, 0x9000, 0xD000, 0x11000, 0x15000, 0x19000, 0x1D000]
curBank = 0
for offset in banks16:
    for i in range(0x200):
        tileset = (curBank * 4) + (i // 0x80) #4 tilesets for each bank
        tileset *= 64
        tileOffs = offset + (i * 4) #Offset of current 16x16 tile data
        graphics16.append([
            graphics8[tileset + (  byte_data[tileOffs] & 0b00111111)],
            graphics8[tileset + (byte_data[tileOffs+1] & 0b00111111)],
            graphics8[tileset + (byte_data[tileOffs+2] & 0b00111111)],
            graphics8[tileset + (byte_data[tileOffs+3] & 0b00111111)],
            i & 0b01111111
        ])
    curBank += 1

palettes64 = []
curBank = 0
for offset in banks16:
    for i in range(0x100):
        paletteOffs = offset + (i * 0x10); #Offset of current 64x64 palette data
        new_palette = []
        for j in range(0x10):
            value = (byte_data[paletteOffs + j] & 0b11000000) >> 6
            new_palette.append(value)
        palettes64.append(new_palette)
    curBank += 1

#2000-2FFF
banks64 = [0, 0x4000, 0x8000, 0xC000, 0x10000, 0x14000, 0x18000, 0x1C000]
graphics64 = []
curBank = 0
for offset in banks64:
    for i in range(0x100):
        tileset = (curBank * 4) + (i // 64); #4 tilesets for each bank
        tileOffs = offset + (i * 16); #Offset of current 64x64 palette data
        curTiles = [0]*16 #Tile16's
        altTileset = []
        tileNums = [0]*16

        #Iterate through the 64x64 tile data & decode it
        for j in range(0x10):
            subOffs = tileOffs + j
            tileNum = byte_data[subOffs] & 0b01111111
            #This gets the correct 16x16 tile from the loaded list (ignoring all that alternate tileset crap)
            curTiles[j] = graphics16[(tileset * 128) + tileNum]
            tileNums[j] = tileNum

            if (byte_data[subOffs] & 0b10000000): #If last bit is set, use alternate tileset
                altTileset.append(j)

        graphics64.append([
            curTiles,
            palettes64[(curBank*0x100)+i],
            altTileset,
            tileNums
        ])
    curBank += 1

palette_data = open("split/map_palettes.bin", "rb").read()

palettes = []
for i in range(len(palette_data)//4):
    #this absolutely needs more work
    #fucks up some colors makes some good
    data = palette_data[i*4:(i+1)*4]
    data2 = data[2] & 0b00111111
    if data[2] > data2:
        data2 = 0x30
    palettes.append([15, data[1], data2, data[3]])


from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys, os, yaml
from copy import deepcopy
import numpy as np

from PIL import Image, ImageOps
from PIL.ImageQt import ImageQt

NES_PALETTE = open("sheets/nes.pal", "rb").read()

sprite_palette = [
[-1, 0xF, 0x00, 0x30], #greyscale
[-1, 0xF, 0x16, 0x37], #black/red/tan
[-1, 0xF, 0x24, 0x37], #black/pink/tan
[-1, 0xF, 0x12, 0x37], #black/blue/tan
]

#init nes palette
for i in range(len(sprite_palette)):
    for color in range(len(sprite_palette[i])):
        if color == 0:
            continue
        id = sprite_palette[i][color]
        id = NES_PALETTE[id*3:(id+1)*3]
        sprite_palette[i][color] = (id[0], id[1], id[2])

for i in range(len(palettes)):
    for color in range(len(palettes[i])):
        id = palettes[i][color]
        id2 = NES_PALETTE[id*3:(id+1)*3]
        palettes[i][color] = (id2[0], id2[1], id2[2])
##

def palette_image(image, palette):
    data = np.array(image)   # "data" is a height x width x 4 numpy array
    red, green, blue, alpha = data.T # Temporarily unpack the bands for readability

    # Replace white with red... (leaves alpha values alone...)
    #transparent_areas = (red == 0) & (green == 0) & (blue == 0) & (alpha == 0)
    black_areas = (red == 0) & (green == 0) & (blue == 0) & (alpha == 255)
    gray_areas = (red == 102) & (green == 102) & (blue == 102) & (alpha == 255)
    lgray_areas = (red == 173) & (green == 173) & (blue == 173) & (alpha == 255)
    white_areas = (red == 255) & (green == 254) & (blue == 255) & (alpha == 255)

    data[..., :-1][black_areas.T] = palette[0] # Transpose back needed
    data[..., :-1][gray_areas.T] = palette[1] # Transpose back needed
    data[..., :-1][lgray_areas.T] = palette[2] # Transpose back needed
    data[..., :-1][white_areas.T] = palette[3] # Transpose back needed

    return Image.fromarray(data)

template = Image.new("RGBA", (1,1))

class Chunk(object):
    def __init__(self, id):
        self.visible = False
        self.id = id
        self.pixmap : QGraphicsPixmapItem = QGraphicsPixmapItem(QPixmap.fromImage(ImageQt(template)))
        self.generated = False

    def generate_pixmap(self):
        ##make_chunk
        newImage = Image.new("RGBA", (64, 64))

        global mapTileset, mapTiles
        global graphics64, graphics16, graphics8
        global sectorTileset1, sectorTileset2
        global sectorPalette, palettes, palettes64

        chunk_x = self.id % 0x100
        chunk_y = self.id // 0x100

        sector_x = chunk_x // 4
        sector_y = chunk_y // 4
        sector_i = sector_x + (sector_y * 0x40)

        secondTileset = mapTileset[self.id]
        curTile = None

        ts1 = sectorTileset1
        ts2 = sectorTileset2
        if secondTileset:
            ts1 = sectorTileset2
            ts2 = sectorTileset1

        g64_id = (ts1[sector_i] * 64) + mapTiles[self.id]

        curTile = deepcopy(graphics64[g64_id])
        for index in curTile[2]: #2 == altTileset
            curTile[0][index] = graphics16[(ts2[sector_i] * 128) + curTile[3][index]] #3 == tileNums

        palette_i = sectorPalette[sector_i]

        use_bg_palette = palettes[palette_i*4:(palette_i+1)*4]

        for tile16_i in range(len(curTile[0])):
            tile16 = curTile[0][tile16_i]
            x16 = tile16_i % 4
            y16 = tile16_i // 4
            for tile8_i in range(4):
                tile8 = tile16[tile8_i]

                x8 = tile8_i % 2
                y8 = tile8_i // 2
                x8 += (x16*2)
                y8 += (y16*2)

                paletteNum = curTile[1][tile16_i]
                my_palette = use_bg_palette[paletteNum]

                new_tile = palette_image(tile8, my_palette)
                rect = (x8*8, y8*8, (x8+1)*8, (y8+1)*8)
                newImage.paste(new_tile, rect)

        self.pixmap.setPixmap(QPixmap.fromImage(ImageQt(newImage)))
        self.pixmap.update()
        self.generated = True


class Scene(QGraphicsScene):
    def __init__(self, xp, yp, w, h):
        super(Scene, self).__init__(xp, yp, w, h)
        self.chunks = []
        self.window : QGraphicsView = None

        for y in range(0xE0):
            for x in range(0x100):
                i = x + (y * 0x100)
                new_chunk = Chunk(i)
                self.chunks.append(new_chunk)
                new_chunk.pixmap.setPos(x*64,y*64)
                self.addItem(new_chunk.pixmap)

        print(len(self.items()))

        self.queue_update()

        print("DONE")

    def queue_update(self):
        if self.window == None:
            return
        actual = self.window.mapToScene(self.window.rect()).boundingRect().getRect()
        maxx = actual[2:]
        poss = actual[:2]


        #the 'boundaries' of chunks.
        fake_rect = [
            round(poss[0]/64),
            round(poss[1]/64),
            round((poss[0]+maxx[0])/64),
            round((poss[1]+maxx[1])/64),
        ]

        for y in range(fake_rect[1], fake_rect[3]):
            for x in range(fake_rect[0], fake_rect[2]):
                i = x + (y * 0x100)
                chunk : Chunk = self.chunks[i]
                if not chunk.generated:
                    chunk.generate_pixmap()
        self.update()


class Viewer(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = Scene(0x100*-32, 0xE0*-32, 0x100*64, 0xE0*64)
        self.setScene(self._scene)
        self.setSceneRect(self._scene.itemsBoundingRect())

        self._scene.window = self
        self._scene.queue_update()

    def paintEvent(self, event):
        super().paintEvent(event)
        self._scene.queue_update()
        self.update()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MOTHER Animation Creator")
        self.viewer = Viewer()

        self.setCentralWidget(self.viewer)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())