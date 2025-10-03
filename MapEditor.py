from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys
import numpy as np

from copy import deepcopy

from PIL import Image, ImageDraw
from PIL.ImageQt import ImageQt
import yaml

map_tile_properties = None

class MapInfo(object):

    color_map = {
        (0,0,0,255): 0,
        (102,102,102,255): 1,
        (173,173,173,255): 2,
        (255,254,255,255): 3,
    }

    def __init__(self):
        self.graphics8 = []
        for tileset in range(32):
            image = Image.open(f"extract/graphics/tileset{tileset+1}.png", 'r').convert("RGBA")
            for y in range(4):
                for x in range(0x10):
                    rect = (x*8, y*8, (x+1)*8, (y+1)*8)
                    newImage = np.array(image.crop(rect)).flatten()
                    bits = bytearray()
                    for i in range(len(newImage)//4):
                        color = tuple(newImage[i*4:(i+1)*4])
                        bits.append(self.color_map[color])

                    self.graphics8.append(bits)

    def in_yaml(self, yaml_file):

        data_loaded = yaml.safe_load(open(yaml_file, 'r'))

        #Map height * width in terms of 64x64 chunks
        self.mapTiles = data_loaded["mapTiles"]
        self.mapTileset = data_loaded["mapTileset"] #second tileset
        self.mapEvent = data_loaded["mapEvent"]

        #Same as above, divided by 4
        self.sectorPalette = data_loaded["sectorPalette"]
        self.sectorArea = data_loaded["sectorArea"]
        self.sectorTileset1 = data_loaded["sectorTileset1"]
        self.sectorTileset2 = data_loaded["sectorTileset2"]

        self.graphics16 = data_loaded["graphics16"]
        self.graphics64 = data_loaded["graphics64"]
        self.palettes64 = data_loaded["palettes64"]

    def out_yaml(self):

        dict = {
            "graphics64": self.graphics64,
            "palettes64": self.palettes64,
            "graphics16": self.graphics16,
            "mapTiles": self.mapTiles,
            "mapTileset": self.mapTileset,
            "mapEvent": self.mapEvent,
            "sectorPalette": self.sectorPalette,
            "sectorArea": self.sectorArea,
            "sectorTileset1": self.sectorTileset1,
            "sectorTileset2": self.sectorTileset2
        }

        if type(self.palettes64[0]) == bytearray:
           new = []
           for array in self.palettes64:
                s = []
                for byte in array:
                   s.append(byte)
                new.append(s)
           dict["palettes64"] = new

        return yaml.dump(dict, sort_keys=False, default_flow_style=True)


    def decompile(self, byte_data):
        #Map height * width in terms of 64x64 chunks
        self.mapTiles = []
        self.mapTileset = [] #second tileset
        self.mapEvent = []

        #Same as above, divided by 4
        self.sectorPalette = []
        self.sectorArea = []
        self.sectorTileset1 = []
        self.sectorTileset2 = []

        banksMap = [0x2000, 0x6000, 0xA000, 0xE000, 0x12000, 0x16000, 0x1A000]
        for offset in banksMap:
            for i in range(0x2000):
                tileOffs = offset + i #Offset of current 64x64 map data
                currentByte = byte_data[tileOffs]
                self.mapTiles.append(currentByte & 0b00111111); #Get lower 6 bits only of map data, store in array
                self.mapTileset.append((currentByte & 0b01000000) != 0)
                self.mapEvent.append((currentByte & 0b10000000) != 0)

        #Lower 6 bits of 3800-3FFF (skip 1st bank)
        banksSector = [0x5800, 0x9800, 0xD800, 0x11800, 0x15800, 0x19800, 0x1D800]
        for offset in banksSector:
            for i in range(0x200):
                tileOffs = offset + (i * 4) #Offset of current 256x256 sector data
                #First 6 bits of each byte
                self.sectorPalette.append(byte_data[tileOffs] & 0b00111111)
                self.sectorArea.append(byte_data[tileOffs+1] & 0b00111111)
                self.sectorTileset1.append(byte_data[tileOffs+2] & 0b00111111)
                self.sectorTileset2.append(byte_data[tileOffs+3] & 0b00111111)

        #Lower 6 bits of 3000-37FF
        self.graphics16 = []
        banks16 = [0x1000, 0x5000, 0x9000, 0xD000, 0x11000, 0x15000, 0x19000, 0x1D000]
        self.palettes64 = []
        curBank = 0
        for offset in banks16:
            for i in range(0x200):
                tileset = (curBank * 4) + (i // 0x80) #4 tilesets for each bank
                tileset *= 0x40
                tileOffs = offset + (i * 4) #Offset of current 16x16 tile data
                self.graphics16.append([
                    tileset + (  byte_data[tileOffs] & 0b00111111),
                    tileset + (byte_data[tileOffs+1] & 0b00111111),
                    tileset + (byte_data[tileOffs+2] & 0b00111111),
                    tileset + (byte_data[tileOffs+3] & 0b00111111),
                    i & 0b01111111
                ])
            for i in range(0x100):
                paletteOffs = offset + (i * 0x10); #Offset of current 64x64 palette data
                new_palette = bytearray()
                for j in range(0x10):
                    value = (byte_data[paletteOffs + j] & 0b11000000) >> 6
                    new_palette.append(value)
                self.palettes64.append(new_palette)
            curBank += 1

        #2000-2FFF
        banks64 = [0, 0x4000, 0x8000, 0xC000, 0x10000, 0x14000, 0x18000, 0x1C000]
        self.graphics64 = []
        curBank = 0
        for offset in banks64:
            for i in range(0x100):
                tileset = (curBank * 4) + (i // 64); #4 tilesets for each bank
                tileOffs = offset + (i * 16); #Offset of current 64x64 palette data
                curTiles = [] #Tile16's
                altTileset = []
                tileNums = []

                #Iterate through the 64x64 tile data & decode it
                for j in range(0x10):
                    subOffs = tileOffs + j
                    tileNum = byte_data[subOffs] & 0b01111111
                    #This gets the correct 16x16 tile from the loaded list (ignoring all that alternate tileset crap)
                    curTiles.append((tileset * 128) + tileNum)
                    tileNums.append(tileNum)

                    if (byte_data[subOffs] & 0b10000000): #If last bit is set, use alternate tileset
                        altTileset.append(j)

                self.graphics64.append({
                    "curTiles": curTiles,
                    "palette64": (curBank*0x100)+i,
                    "altTileset": altTileset,
                    "tileNums": tileNums
                })
            curBank += 1

    def compile(self):
        #Map height * width in terms of 64x64 chunks
        #self.mapTiles = []
        #self.mapTileset = [] #second tileset
        #self.mapEvent = []

        #Same as above, divided by 4
        #self.sectorPalette = []
        #self.sectorArea = []
        #self.sectorTileset1 = []
        #self.sectorTileset2 = []

        out_bytes = bytearray(0x1e000)

        banksMap = [0x2000, 0x6000, 0xA000, 0xE000, 0x12000, 0x16000, 0x1A000]
        array_i = 0
        for offset in banksMap:
            for i in range(0x2000):
                tileOffs = offset + i #Offset of current 64x64 map data
                currentByte = self.mapTiles[array_i] & 0b00111111
                currentByte |= (int(self.mapTileset[array_i]) & 0b1) << 6
                currentByte |= (int(self.mapEvent[array_i]) & 0b1) << 7
                out_bytes[tileOffs] |= currentByte

                array_i += 1

        #Lower 6 bits of 3800-3FFF (skip 1st bank)
        banksSector = [0x5800, 0x9800, 0xD800, 0x11800, 0x15800, 0x19800, 0x1D800]
        array_i = 0
        for offset in banksSector:
            for i in range(0x200):
                tileOffs = offset + (i * 4) #Offset of current 256x256 sector data
                #First 6 bits of each byte
                bytees = bytearray(4)
                bytees[0] = self.sectorPalette[array_i] & 0b00111111
                bytees[1] = self.sectorArea[array_i] & 0b00111111
                bytees[2] = self.sectorTileset1[array_i] & 0b00111111
                bytees[3] = self.sectorTileset2[array_i] & 0b00111111

                for i in range(len(bytees)):
                    out_bytes[tileOffs+i] |= bytees[i]
                array_i += 1

        #Lower 6 bits of 3000-37FF
        banks16 = [0x1000, 0x5000, 0x9000, 0xD000, 0x11000, 0x15000, 0x19000, 0x1D000]
        curBank = 0
        array_i = 0
        array_p = 0
        for offset in banks16:
            for i in range(0x200):
                tileset = (curBank * 4) + (i // 0x80) #4 tilesets for each bank
                tileset *= 0x40
                tileOffs = offset + (i * 4) #Offset of current 16x16 tile data

                tile1 = self.graphics16[array_i][0]-tileset
                tile2 = self.graphics16[array_i][1]-tileset
                tile3 = self.graphics16[array_i][2]-tileset
                tile4 = self.graphics16[array_i][3]-tileset
                byte_data = bytearray([tile1, tile2, tile3, tile4])

                for i in range(len(byte_data)):
                    out_bytes[tileOffs+i] |= byte_data[i]

                array_i += 1
            for i in range(0x100):
                paletteOffs = offset + (i * 0x10); #Offset of current 64x64 palette data
                data = self.palettes64[array_p]
                for j in range(0x10):
                    value = (data[j] & 0b11) << 6
                    out_bytes[paletteOffs+j] |= value
                array_p += 1
            curBank += 1

        #2000-2FFF
        banks64 = [0, 0x4000, 0x8000, 0xC000, 0x10000, 0x14000, 0x18000, 0x1C000]
        curBank = 0
        array_i = 0
        for offset in banks64:
            for i in range(0x100):
                tileset = (curBank * 4) + (i // 64); #4 tilesets for each bank
                tileOffs = offset + (i * 16); #Offset of current 64x64 palette data
                curTiles = [] #Tile16's

                #Iterate through the 64x64 tile data & decode it
                for j in range(0x10):
                    subOffs = tileOffs + j

                    tileNum = self.graphics64[array_i]["tileNums"][j]
                    out_bytes[subOffs] |= tileNum
                    #This gets the correct 16x16 tile from the loaded list (ignoring all that alternate tileset crap)
                    curTiles.append((tileset * 128) + tileNum)

                    if j in self.graphics64[array_i]["altTileset"]:
                        out_bytes[subOffs] |= 0b10000000

                array_i += 1
            curBank += 1

        return out_bytes

Map_Stuff : MapInfo = None

palette_data = bytearray()
map_palette_metadata = []
palettes = []

def load_palette_data(path):
    global palette_data
    global map_palette_metadata
    global palettes

    palette_data = bytearray(open(path, "rb").read())
    load_palette_from_binary(palette_data)

def load_palette_from_binary(bin):
    global map_palette_metadata
    global palettes
    map_palette_metadata = []
    palettes = []
    for i in range(len(bin)//4):
        data = bin[i*4:(i+1)*4]
        if i % 4 == 3:
            map_palette_metadata.append([data[0], data[2]])
            palettes.append([0xf, data[1], 0x30, data[3]])
        else:
            palettes.append([data[0], data[1], data[2], data[3]])
load_palette_data("split/map_palettes.bin")

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

def convert_palettes_to_rgb():
    global palettes
    global NES_PALETTE
    for i in range(len(palettes)):
        for color in range(len(palettes[i])):
            id = palettes[i][color]
            id2 = NES_PALETTE[id*3:(id+1)*3]
            palettes[i][color] = (id2[0], id2[1], id2[2])
convert_palettes_to_rgb()

def palette_image(data, palette, bands=3, width=8, height=8):
    lookup_table = np.array(palette, dtype=np.uint8)
    colored_image = lookup_table[data]
    colored_image.shape = (width,height,bands)
    return colored_image

template = None

#chunk graphicsitem
show_chunk_collision = False
class Chunk(object):
    def __init__(self, id, x, y):
        self.visible = False
        self.id = id
        global template
        self.pixmap : QGraphicsPixmapItem = QGraphicsPixmapItem(template)
        self.pixmap.setPos(x*64,y*64)
        self.generated = False

    def generate_pixmap(self):
        ##make_chunk
        global palettes
        global Map_Stuff
        global map_tile_properties

        chunk_x = self.id % 0x100
        chunk_y = self.id // 0x100

        sector_x = chunk_x // 4
        sector_y = chunk_y // 4
        sector_i = sector_x + (sector_y * 0x40)

        secondTileset = Map_Stuff.mapTileset[self.id]

        ts1 = Map_Stuff.sectorTileset1
        ts2 = Map_Stuff.sectorTileset2
        if secondTileset:
            ts1 = Map_Stuff.sectorTileset2
            ts2 = Map_Stuff.sectorTileset1

        g64_id = (ts1[sector_i] * 64) + Map_Stuff.mapTiles[self.id]

        curTile = Map_Stuff.graphics64[g64_id]
        for index in curTile["altTileset"]: #2 == altTileset
            curTile["curTiles"][index] = (ts2[sector_i] * 128) + curTile["tileNums"][index] #3 == tileNums

        palette_i = Map_Stuff.sectorPalette[sector_i]
        use_bg_palette = palettes[palette_i*4:(palette_i+1)*4]

        #newImage = Image.new("RGBA", (64, 64))

        pixels = {}

        collision = []

        for tile16_i in range(len(curTile["curTiles"])):
            tile16 = deepcopy(Map_Stuff.graphics16[curTile["curTiles"][tile16_i]])

            if tile16_i in curTile["altTileset"]:
                collision.append(map_tile_properties[(ts2[sector_i] * 0x80) + tile16[4]])
            else:
                collision.append(map_tile_properties[(ts1[sector_i] * 0x80) + tile16[4]])

            x16 = tile16_i % 4
            y16 = tile16_i // 4
            for tile8_i in range(4):
                tile8 = deepcopy(Map_Stuff.graphics8[tile16[tile8_i]])

                x8 = tile8_i % 2
                y8 = tile8_i // 2
                x8 += (x16*2)
                y8 += (y16*2)

                i = x8 + (y8*8)

                paletteNum = Map_Stuff.palettes64[curTile["palette64"]][tile16_i]
                my_palette = use_bg_palette[paletteNum]

                new_tile = palette_image(tile8, my_palette)
                pixels[i] = new_tile
                new_tile = None

        #construct 8x8 of 8x8s
        p_array = []
        for i in range(64):
            p_array.append(pixels[i])

        s = []
        for i in range(8):
            x = p_array[i*8:(i+1)*8]
            s.append(np.hstack(x))
        newImage = Image.fromarray(np.vstack(s)).convert("RGBA")

        global show_chunk_collision
        if show_chunk_collision:
            overlay = Image.new('RGBA', newImage.size, (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            color = (255, 0, 0, 99)

            for i in range(len(collision)):
                data = collision[i]
                x = (i % 4) * 16
                y = (i // 4) * 16
                if data != 0:
                    r = None
                    if data & 0b00010000: #full collision
                        r = [(0, 0), (0, 16), (16, 16), (16, 0)]
                        r = [(s[0]+x, s[1]+y) for s in r]
                        draw_overlay.polygon(r, color, color)
                    else:
                        if data & 0b00001000: # top left on this tile is blocked
                            r = [(0, 0), (0, 8), (8, 0)]
                            r = [(s[0]+x, s[1]+y) for s in r]
                            draw_overlay.polygon(r, color, color)
                        if data & 0b00000100: # bottom left on this tile is blocked
                            r = [(0, 16), (0, 8), (8, 16)]
                            r = [(s[0]+x, s[1]+y) for s in r]
                            draw_overlay.polygon(r, color, color)
                        if data & 0b00000010: # bottom right on this tile is blocked
                            r = [(16, 8), (8, 16), (16, 16)]
                            r = [(s[0]+x, s[1]+y) for s in r]
                            draw_overlay.polygon(r, color, color)
                        if data & 0b00000001: # top right on this tile is blocked
                            r = [(8, 0), (16, 0), (16, 8)]
                            r = [(s[0]+x, s[1]+y) for s in r]
                            draw_overlay.polygon(r, color, color)

            newImage = Image.alpha_composite(newImage, overlay)

        self.pixmap.setPixmap(QPixmap.fromImage(ImageQt(newImage)))
        self.generated = True
        newImage = None

class EBObject(QGraphicsRectItem):
    table_0 = None
    table_1 = None
    table_mix = None
    loaded_definitions = []
    being_moved = False
    fps = 10
    frame = 0
    position = None
    pixmap = None

    def __init__(self, x, y):
        super().__init__()
        self.position = (x, y)

        self.setRect(self.position[0]*16, (self.position[1]*16)+8, 16, 16)
        pen = QPen()
        pen.setWidth(5)
        pen.setColor(QColor(255, 0, 0))
        self.setPen(pen)

        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)
        self.timer.start(round(1000 / self.fps))

    def mouseMoveEvent(self, a0):
        if a0.buttons() & Qt.MouseButton.LeftButton:
            if self.being_moved:
                self.do_move(a0.pos())
                return

    def do_move(self, position):
        x,y = int(position.x()//16), int(position.y()//16)
        self.position = (x,y)

        self.setRect(x*16, (y*16)+8, 16, 16)
        self.update()

    def mousePressEvent(self, a0):
        self.being_moved = True

    def mouseReleaseEvent(self, a0):
        self.being_moved = False

    def mouseDoubleClickEvent(self, a0):
        self.being_moved = True

    def next_frame(self):
        self.frame += 1
        defis = []
        for defi in self.loaded_definitions:
            defis += defi.definition_data
        if self.frame >= len(defis):
            self.frame = 0
        self.timer.start(round(1000 / self.fps))
        self.update()

    def generate_pixmap(self, painter, option, widget):
        if len(self.loaded_definitions) == 0:
            return
        if self.table_mix == None:
            return

        painter = QPainter(self)
        images = []
        for y in range(self.table_mix.size[1] // 8):
            for x in range(self.table_mix.size[0] // 8):
                space = (x*8, y*8, (x+1)*8, (y+1)*8)
                image = self.table_mix.crop(space)
                images.append(image)

        defis = []
        for defi in self.loaded_definitions:
            defis += defi.definition_data

        definition = defis[self.frame]
        ppu_offset = definition["ppu"]

        p1 = definition["p1"]
        p2 = definition["p2"]

        tilepath = definition["tiles"]
        spriteTiles = yaml.safe_load(open(f"extract/{tilepath}.yaml", "r"))
        for tile in spriteTiles:
            tile_id = ppu_offset+tile["index"]

            image = images[tile_id].copy()
            if tile["flipX"]:
                image = ImageOps.mirror(image)
            if tile["flipY"]:
                image = ImageOps.flip(image)

            choose_palette = sprite_palette[[p1, p2][tile["palette"]]]

            data = np.array(image)   # "data" is a height x width x 4 numpy array
            red, green, blue, alpha = data.T # Temporarily unpack the bands for readability

            # Replace white with red... (leaves alpha values alone...)
            #transparent_areas = (red == 0) & (green == 0) & (blue == 0) & (alpha == 0)
            black_areas = (red == 0) & (green == 0) & (blue == 0) & (alpha == 255)
            gray_areas = (red == 102) & (green == 102) & (blue == 102) & (alpha == 255)
            white_areas = (red == 255) & (green == 254) & (blue == 255) & (alpha == 255)

            #data[..., :-1][transparent_areas.T] = (0, 0, 0) # Transpose back needed
            data[..., :-1][black_areas.T] = choose_palette[1] # Transpose back needed
            data[..., :-1][gray_areas.T] = choose_palette[2] # Transpose back needed
            data[..., :-1][white_areas.T] = choose_palette[3] # Transpose back needed

            im2 = Image.fromarray(data)

            pixmap = QPixmap.fromImage(ImageQt(im2))
            painter.drawPixmap(tile["posX"], tile["posY"], pixmap)
        painter.end()

    def load_table(self, img, id):
        image = Image.open(img, 'r')
        image = image.convert("RGBA")
        if id == 0:
            self.table_0 = image
        elif id == 1:
            self.table_1 = image
        self.create_mixtable()

    def create_mixtable(self):
        if not self.table_0:
            return
        elif not self.table_1:
            return

        self.table_mix = Image.new("RGBA", (0x80, 0x80))
        self.table_mix.paste(self.table_0, (0*8, 0*8, 16*8, 8*8))
        self.table_mix.paste(self.table_1, (0*8, 8*8, 16*8, 16*8))

    def load_spritedef(self, paths):
        for path in paths:
            self.loaded_definitions.append(DefinitionEntry(path))

class DefinitionEntry(object):
    def __init__(self, file):
        super().__init__()
        self.filepath = file
        self.definition_data = yaml.safe_load(open(file, "r"))

#scene manager
class Scene(QGraphicsScene):
    def __init__(self, xp, yp, w, h):
        super(Scene, self).__init__(xp, yp, w, h)
        self.chunks = []
        self.window : QGraphicsView = None

        for y in range(0xE0):
            for x in range(0x100):
                i = x + (y * 0x100)
                new_chunk = Chunk(i, x, y)
                self.chunks.append(new_chunk)
                self.addItem(new_chunk.pixmap)

        self.selection = QGraphicsRectItem()
        self.selection.setZValue(1000)
        self.addItem(self.selection)
        self.chunk_grid = GridItem(64, QColor(255, 0, 0), 0x100, 0xE0, 1)
        self.chunk_grid.setZValue(998)
        self.addItem(self.chunk_grid)
        self.sector_grid = GridItem(64*4, QColor(100, 100, 100), 0x100, 0xE0, 3)
        self.sector_grid.setZValue(999)
        self.addItem(self.sector_grid)

        new_object = EBObject(5, 5)
        new_object.setZValue(1001)
        self.addItem(new_object)

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


    def change_selection(self, mode):
        if mode in [Toolbar.Select_mode.Chunks, Toolbar.Select_mode.Sectors]:
            if self.window.current_position == None:
                self.window.current_position = (0,0)

            if mode == Toolbar.Select_mode.Chunks:
                self.selection.setRect(0, 0, 64, 64)
            else:
                self.selection.setRect(0, 0, 64*4, 64*4)
                self.window.current_position = ((self.window.current_position[0] // 4) * 4,
                                                (self.window.current_position[1] // 4) * 4)
                self.selection.setX(self.window.current_position[0])
                self.selection.setY(self.window.current_position[1])
            pen = QPen()
            pen.setWidth(5)
            pen.setColor(QColor(255, 0, 0))
            self.selection.setPen(pen)

            self.window.update_selection()
        else:
            self.selection.setRect(0,0,0,0)
            self.selection.setPen(QPen())

#grid handler
class GridItem(QGraphicsItem):
    def __init__(self, gridSize, color, x, y, width, parent=None):
        super().__init__(parent)
        self.gridSize = gridSize
        self.width = x*64
        self.height = y*64
        self.pen = QPen(color) # Light gray grid
        self.pen.setWidth(width)

    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget):
        painter.setPen(self.pen)

        # Draw vertical grid lines
        for x in range(0, self.width, self.gridSize):
            painter.drawLine(x, 0, x, self.height)

        # Draw horizontal grid lines
        for y in range(0, self.height, self.gridSize):
            painter.drawLine(0, y, self.width, y)

chunk_app = None
#scene viewer
class Viewer(QGraphicsView):
    def __init__(self, parent):
        super().__init__()
        self._main = parent
        self._scene = Scene(0x100*-32, 0xE0*-32, 0x100*64, 0xE0*64)
        self.setScene(self._scene)
        self.setSceneRect(self._scene.itemsBoundingRect())

        self._scene.window = self
        global Map_Stuff
        if Map_Stuff != None:
            self._scene.queue_update()

        self.setMouseTracking(True)
        self.current_position = None

    def paintEvent(self, event):
        super().paintEvent(event)
        global Map_Stuff
        if Map_Stuff != None:
            self._scene.queue_update()
        self.update()


    def move_selection(self, event, fix=True):
        position = event.pos()
        if fix:
            position -= self.pos()
        position = self.mapToScene(position)
        x,y = int(position.x()), int(position.y())
        not_clicking = x < 0
        not_clicking |= x >= 0x100 * 64
        not_clicking |= y < 0
        not_clicking |= y >= 0xE0 * 64
        if not_clicking:
            return

        self.current_position = (x // 64, y // 64)
        self.update_selection()

    def update_selection(self):
        x,y = self.current_position
        global palettes, Map_Stuff, Map_Toolbar

        chunk_x, chunk_y = x, y
        chunk_i = chunk_x + (chunk_y * 0x100)
        sector_x, sector_y = chunk_x // 4, chunk_y // 4
        sector_i = sector_x + (sector_y * 0x40)

        palette_i = Map_Stuff.sectorPalette[sector_i]

        secondTileset = 2 if Map_Stuff.mapTileset[chunk_i] else 1

        ts1 = Map_Stuff.sectorTileset1
        ts2 = Map_Stuff.sectorTileset2

        tileset = ts1[sector_i]
        tileset2 = ts2[sector_i]

        area = Map_Stuff.sectorArea[sector_i]

        if Map_Toolbar.select_mode in [Toolbar.Select_mode.Chunks, Toolbar.Select_mode.Sectors]:
            Map_Toolbar.palette.valueBox.setValue(palette_i)
            Map_Toolbar.tileset.valueBox.setValue(tileset)
            Map_Toolbar.tileset_2.valueBox.setValue(tileset2)

            if Map_Toolbar.select_mode == Toolbar.Select_mode.Chunks:
                Map_Toolbar.use_tileset.valueBox.setValue(secondTileset)
                self._scene.selection.setPos(chunk_x*64,chunk_y*64)
            else:
                Map_Toolbar.area.valueBox.setValue(area)
                self._scene.selection.setPos(sector_x*4*64,sector_y*4*64)
        self._scene.update() #required so there isnt artifacting

    def open_selection(self):
        x,y = self.current_position
        global palettes, Map_Stuff, Map_Toolbar

        chunk_x, chunk_y = x, y
        chunk_i = chunk_x + (chunk_y * 0x100)
        sector_x, sector_y = chunk_x // 4, chunk_y // 4
        sector_i = sector_x + (sector_y * 0x40)

        palette_i = Map_Stuff.sectorPalette[sector_i]

        secondTileset = True if Map_Stuff.mapTileset[chunk_i] else False

        ts1 = Map_Stuff.sectorTileset1
        ts2 = Map_Stuff.sectorTileset2

        tileset = ts1[sector_i]
        tileset2 = ts2[sector_i]

        global chunk_app
        from ChunkEditor import CE_Window
        if chunk_app is None: # Prevent multiple instances if desired
            chunk_app = CE_Window(Map_Stuff)

        from ChunkEditor import set_overrides, set_use_tileset_override, set_chunki, recieve_loads
        set_overrides(tileset, tileset2, palette_i)
        set_use_tileset_override(secondTileset)
        set_chunki(Map_Stuff.mapTiles[chunk_i])
        global map_tile_properties, palette_data
        recieve_loads(map_tile_properties, palette_data)
        chunk_app.show()

    def place_selection(self):
        x,y = self.current_position
        global palettes, Map_Stuff, Map_Toolbar, chunk_app
        if chunk_app == None:
            return

        chunk_x, chunk_y = x, y
        chunk_i = chunk_x + (chunk_y * 0x100)
        sector_x, sector_y = chunk_x // 4, chunk_y // 4
        sector_i = sector_x + (sector_y * 0x40)

        from ChunkEditor import get_chunki
        Map_Stuff.mapTiles[chunk_i] = get_chunki()
        self._scene.chunks[chunk_i].generated = False
        self._scene.update() #required so there isnt artifacting


    def mouseMoveEvent(self, a0):
        super().mouseMoveEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.move_selection(a0, False)
            self.place_selection()

    def mousePressEvent(self, a0):
        super().mousePressEvent(a0)
        self.move_selection(a0, False)
        if Map_Toolbar.select_mode == Toolbar.Select_mode.Chunks:
            if a0.buttons() & Qt.MouseButton.RightButton:
                self.open_selection()
            elif a0.buttons() & Qt.MouseButton.LeftButton:
                self.place_selection()


    def mouseReleaseEvent(self, a0):
        super().mouseReleaseEvent(a0)

    def mouseDoubleClickEvent(self, a0):
        super().mouseDoubleClickEvent(a0)
        self.move_selection(a0, False)

class ValueBox(QHBoxLayout):
    def __init__(self, label_name, range, hex=True):
        super().__init__()

        self.label = QLabel(label_name)
        self.valueBox = QSpinBox()
        self.valueBox.setRange(range[0], range[1])
        if hex:
            self.valueBox.setDisplayIntegerBase(16)

        self.addWidget(self.label)
        self.addWidget(self.valueBox)

    def show(self):
        for widget in [self.valueBox, self.label]:
            widget.show()

    def hide(self):
        for widget in [self.valueBox, self.label]:
            widget.hide()


import enum
class Toolbar(QVBoxLayout):
    class Select_mode(enum.Enum):
        No_Mode = 0
        Objects = 1
        Chunks = 2
        Sectors = 3

    def __init__(self, parent):
        super().__init__()
        self._main = parent
        self.select_mode = Toolbar.Select_mode.No_Mode

        options = QHBoxLayout()
        mode = QHBoxLayout()
        mode_label = QLabel("Selection Mode: ")
        mode.addWidget(mode_label)
        set_mode_dropdown = QComboBox()
        set_mode_dropdown.addItems(["None", "Objects", "Chunks", "Sectors"])
        set_mode_dropdown.currentIndexChanged.connect(lambda index: self.set_select_mode(Toolbar.Select_mode(index)))
        mode.addWidget(set_mode_dropdown)
        options.addLayout(mode)
        grid_views = QHBoxLayout()
        chunk_grid = QPushButton("Chunk Grid")
        chunk_grid.clicked.connect(lambda: self.toggle_grid(1))
        grid_views.addWidget(chunk_grid)
        sector_grid = QPushButton("Sector Grid")
        sector_grid.clicked.connect(lambda: self.toggle_grid(0))
        grid_views.addWidget(sector_grid)
        collision_view = QPushButton("Collision")
        collision_view.clicked.connect(self.toggle_collision)
        grid_views.addWidget(collision_view)
        options.addLayout(grid_views)


        self.addLayout(options)

        info = QHBoxLayout()
        self.palette = ValueBox("Palette: ", (0, len(palettes)//4-1), True)
        self.palette.valueBox.valueChanged.connect(self.palette_changed)
        info.addLayout(self.palette)

        self.tileset = ValueBox("Tileset: ", (0, 0x20-1), True)
        self.tileset.valueBox.valueChanged.connect(self.tileset_changed)
        info.addLayout(self.tileset)

        self.tileset_2 = ValueBox("Tileset 2: ", (0, 0x20-1), True)
        self.tileset_2.valueBox.valueChanged.connect(self.tileset_2_changed)
        info.addLayout(self.tileset_2)

        self.use_tileset = ValueBox("Use Tileset: ", (1, 2), True)
        self.use_tileset.valueBox.valueChanged.connect(self.use_tileset_changed)
        info.addLayout(self.use_tileset)

        self.area = ValueBox("Area: ", (0, 0x40-1), True)
        self.area.valueBox.valueChanged.connect(self.area_changed)
        info.addLayout(self.area)

        self.addLayout(info)

        self.set_select_mode(self.select_mode)

    def palette_changed(self, value):
        global Map_Viewer
        pos = Map_Viewer.current_position
        if not pos:
            return

        x, y = pos

        global Map_Stuff
        chunk_x, chunk_y = x, y
        chunk_i = chunk_x + (chunk_y * 0x100)
        sector_x, sector_y = chunk_x // 4, chunk_y // 4
        sector_i = sector_x + (sector_y * 0x40)

        if value == Map_Stuff.sectorPalette[sector_i]:
            return
        Map_Stuff.sectorPalette[sector_i] = value

        affected_chunks = []
        chunks = Map_Viewer._scene.chunks
        chunk_x2, chunk_y2 = (sector_x+1) * 4, (sector_y+1) * 4
        chunk_x3, chunk_y3 = (sector_x) * 4, (sector_y) * 4
        for c_y in range(chunk_y3, chunk_y2):
            for c_x in range(chunk_x3, chunk_x2):
                affected_chunks.append(chunks[c_x + (c_y * 0x100)])

        for chunk in affected_chunks:
            chunk.generate_pixmap()

        global chunk_app
        from ChunkEditor import set_overrides
        if not chunk_app is None: # Prevent multiple instances if desired
            set_overrides(Map_Stuff.sectorTileset1[sector_i], Map_Stuff.sectorTileset2[sector_i], Map_Stuff.sectorPalette[sector_i])

    def tileset_changed(self, value):
        global Map_Viewer
        pos = Map_Viewer.current_position
        if not pos:
            return

        x, y = pos

        global Map_Stuff
        chunk_x, chunk_y = x, y
        chunk_i = chunk_x + (chunk_y * 0x100)
        sector_x, sector_y = chunk_x // 4, chunk_y // 4
        sector_i = sector_x + (sector_y * 0x40)

        if value == Map_Stuff.sectorTileset1[sector_i]:
            return
        Map_Stuff.sectorTileset1[sector_i] = value

        affected_chunks = []
        chunks = Map_Viewer._scene.chunks
        chunk_x2, chunk_y2 = (sector_x+1) * 4, (sector_y+1) * 4
        chunk_x3, chunk_y3 = (sector_x) * 4, (sector_y) * 4
        for c_y in range(chunk_y3, chunk_y2):
            for c_x in range(chunk_x3, chunk_x2):
                affected_chunks.append(chunks[c_x + (c_y * 0x100)])

        for chunk in affected_chunks:
            chunk.generate_pixmap()

        global chunk_app
        from ChunkEditor import set_overrides
        if not chunk_app is None: # Prevent multiple instances if desired
            set_overrides(Map_Stuff.sectorTileset1[sector_i], Map_Stuff.sectorTileset2[sector_i], Map_Stuff.sectorPalette[sector_i])


    def tileset_2_changed(self, value):
        global Map_Viewer
        pos = Map_Viewer.current_position
        if not pos:
            return

        x, y = pos

        global Map_Stuff
        chunk_x, chunk_y = x, y
        chunk_i = chunk_x + (chunk_y * 0x100)
        sector_x, sector_y = chunk_x // 4, chunk_y // 4
        sector_i = sector_x + (sector_y * 0x40)

        if value == Map_Stuff.sectorTileset2[sector_i]:
            return
        Map_Stuff.sectorTileset2[sector_i] = value

        affected_chunks = []
        chunks = Map_Viewer._scene.chunks
        chunk_x2, chunk_y2 = (sector_x+1) * 4, (sector_y+1) * 4
        chunk_x3, chunk_y3 = (sector_x) * 4, (sector_y) * 4
        for c_y in range(chunk_y3, chunk_y2):
            for c_x in range(chunk_x3, chunk_x2):
                affected_chunks.append(chunks[c_x + (c_y * 0x100)])

        for chunk in affected_chunks:
            chunk.generate_pixmap()

        global chunk_app
        from ChunkEditor import set_overrides
        if not chunk_app is None: # Prevent multiple instances if desired
            set_overrides(Map_Stuff.sectorTileset1[sector_i], Map_Stuff.sectorTileset2[sector_i], Map_Stuff.sectorPalette[sector_i])

    def use_tileset_changed(self, value):
        global Map_Viewer
        pos = Map_Viewer.current_position
        if not pos:
            return

        x, y = pos

        global Map_Stuff
        chunk_x, chunk_y = x, y
        chunk_i = chunk_x + (chunk_y * 0x100)

        if value == (2 if Map_Stuff.mapTileset[chunk_i] else 1):
            return
        Map_Stuff.mapTileset[chunk_i] = (True if value == 2 else False)

        chunks = Map_Viewer._scene.chunks[chunk_i]
        chunks.generate_pixmap()

        global chunk_app
        from ChunkEditor import set_use_tileset_override
        if not chunk_app is None: # Prevent multiple instances if desired
            set_use_tileset_override(Map_Stuff.mapTileset[chunk_i])

    #doesnt really do anything visually. yet
    def area_changed(self, value):
        global Map_Viewer
        pos = Map_Viewer.current_position
        if not pos:
            return
        x, y = pos

        global Map_Stuff
        sector_x, sector_y = x // 4, y // 4
        sector_i = sector_x + (sector_y * 0x40)

        if value == Map_Stuff.sectorArea[sector_i]:
            return
        Map_Stuff.sectorArea[sector_i] = value

    def toggle_grid(self, i):
        global Map_Viewer
        sector_grid = Map_Viewer._scene.sector_grid
        chunk_grid = Map_Viewer._scene.chunk_grid
        if i == 0:
            sector_grid.setVisible(not sector_grid.isVisible())
        elif i == 1:
            chunk_grid.setVisible(not chunk_grid.isVisible())

    def toggle_collision(self):
        global show_chunk_collision, Map_Viewer
        show_chunk_collision = not show_chunk_collision
        for chunk in Map_Viewer._scene.chunks:
            chunk.generated = False

    def set_select_mode(self, mode):
        global Map_Viewer
        self.select_mode = mode
        Map_Viewer._scene.change_selection(mode)
        if self.select_mode == Toolbar.Select_mode.Chunks:
            self.use_tileset.show()
            self.area.hide()
        else:
            self.use_tileset.hide()
            self.area.show()

class NESPaletteSelector(QWidget):
    colorSelected = pyqtSignal(QColor, int)
    def __init__(self):
        super().__init__()
        self.colors_per_row = 16

        self.layout = QGridLayout()
        self.layout.setSpacing(0)
        self.setLayout(self.layout)

        # Example colors (you can expand this)
        self.colors = []

        global NES_PALETTE
        for id in range(len(NES_PALETTE)//3):
            id = NES_PALETTE[id*3:(id+1)*3]
            self.colors.append(QColor(id[0], id[1], id[2]))

        row = 0
        col = 0
        i = 0
        for color in self.colors:
            btn = QPushButton(hex(i))
            btn.setFixedSize(30, 30) # Set fixed size for the color swatch
            PaletteEditor.set_color(None, btn, color) #adjust text based on luminance
            btn.clicked.connect(lambda checked, c=color, id=i: self.colorSelected.emit(c, id))
            self.layout.addWidget(btn, row, col)

            col += 1
            if col >= self.colors_per_row:
                col = 0
                row += 1
            i += 1

class PaletteEditor(QMainWindow):
    def __init__(self, parent):
        super().__init__()

        self.pseudo_parent = parent

        self.setWindowTitle("Palette Editor")
        self.setGeometry(100, 100, 400, 300)

        window_widget = QWidget()

        lister = QVBoxLayout()
        lister.setAlignment(Qt.AlignmentFlag.AlignTop)
        window_widget.setLayout(lister)

        self.reload_button = QPushButton("Reset")
        self.reload_button.clicked.connect(self.reload)
        lister.addWidget(self.reload_button)

        self.palette_num = QSpinBox()
        self.palette_num.setDisplayIntegerBase(16)
        self.palette_num.setRange(0, 0x20-1)
        self.palette_num.valueChanged.connect(self.change_palette_num)
        lister.addWidget(self.palette_num)
        self.c_palette = -1

        self.color_widgets = []

        for i in range(4):
            reset = QHBoxLayout()
            for c in range(4):
                color = QPushButton()
                if not (i*4)+c in [12, 14]:
                    color.clicked.connect(lambda boolstore, btn=color: self.open_color(btn))
                reset.addWidget(color)
                self.color_widgets.append(color)
            lister.addLayout(reset)

        metadata = QHBoxLayout()
        self.unk_value = ValueBox("???: ", (0, 0xff), True)
        self.unk_value.valueBox.valueChanged.connect(self.unk_value_changed)
        self.null_chunk = ValueBox("Null Chunk: ", (0, 0xff), True)
        self.null_chunk.valueBox.valueChanged.connect(self.null_chunk_changed)
        metadata.addLayout(self.unk_value)
        metadata.addLayout(self.null_chunk)
        lister.addLayout(metadata)

        self.setCentralWidget(window_widget)

        self.change_palette_num(0)

        self.color_selector = None

    def reload(self):
        load_palette_data("split/map_palettes.bin")
        convert_palettes_to_rgb()

        #reload palette data
        okay_man = self.c_palette
        self.c_palette = -1
        self.change_palette_num(okay_man)

        #update rendered chunks
        global Map_Stuff, Map_Viewer
        if Map_Stuff != None:
            for chunk in Map_Viewer._scene.chunks:
                chunk.generated = False

    def set_color(self, widget, color:QColor):
        #luminance shit
        highest = 0
        use_fontcolor = "white"
        if color.red() > highest:
            highest = color.red()
        if color.blue() > highest:
            highest = color.blue()
        if color.green() > highest:
            highest = color.green()

        if highest > 0x80:
            use_fontcolor = "black"

        widget.setStyleSheet(f"""
        QPushButton {{
        background-color: {color.name()};
        color: {use_fontcolor};
        }}
        """)

    def get_color(self, widget):
        return widget.styleSheet().split("-color: #")[-1].split(";")[0]

    def open_color(self, widget):
        if self.color_selector == None:
            self.color_selector = QMainWindow()
            self.color_selector.setWindowTitle("NES Palette Picker")
        s = self.color_selector.centralWidget()
        if s == None:
            s = NESPaletteSelector()
            self.color_selector.setCentralWidget(s)
            s.colorSelected.connect(self.recieveColor)
        s.widget = widget
        self.color_selector.show()

    #changes the swatch
    def recieveColor(self, color, id):
        widget = self.color_selector.centralWidget().widget
        self.color_selector.close()
        self.set_color(widget, color)
        i = self.color_widgets.index(widget)
        global palettes, palette_data
        palettes[(self.c_palette*4)+i//4][i%4] = (color.red(), color.green(), color.blue())
        palette_data[(self.c_palette*16)+i] = id

        okay_man = self.c_palette
        self.c_palette = -1
        self.change_palette_num(okay_man)

        global Map_Stuff, Map_Viewer
        if Map_Stuff != None:
            for sector_y in range(0xE0//4):
                for sector_x in range(0x100//4):
                    sector_i = sector_x + (sector_y * 0x40)

                    if self.c_palette != Map_Stuff.sectorPalette[sector_i]:
                        continue

                    affected_chunks = []
                    chunks = Map_Viewer._scene.chunks
                    chunk_x2, chunk_y2 = (sector_x+1) * 4, (sector_y+1) * 4
                    chunk_x3, chunk_y3 = (sector_x) * 4, (sector_y) * 4
                    for c_y in range(chunk_y3, chunk_y2):
                        for c_x in range(chunk_x3, chunk_x2):
                            affected_chunks.append(chunks[c_x + (c_y * 0x100)])

                    for chunk in affected_chunks:
                        if chunk.generated:
                            chunk.generate_pixmap()

        global chunk_app
        if chunk_app == None:
            return

        from ChunkEditor import recieve_loads
        global map_tile_properties
        recieve_loads(map_tile_properties, palette_data)

    def unk_value_changed(self, value):
        global map_palette_metadata, palette_data
        map_palette_metadata[self.c_palette][0] = value #abstracted
        palette_data[(self.c_palette*(4*4))+(3*4)+0] = value #binary
        self.color_widgets[12].setText("0xf ("+(hex(value))+")")
    def null_chunk_changed(self, value):
        global map_palette_metadata, palette_data
        map_palette_metadata[self.c_palette][1] = value #abstracted
        palette_data[(self.c_palette*(4*4))+(3*4)+2] = value #binary
        self.color_widgets[14].setText("0x30 ("+(hex(value))+")")
    def change_palette_num(self, value):
        global palettes
        global map_palette_metadata
        global NES_PALETTE

        if value == self.c_palette:
            return
        self.c_palette = value

        i = 0
        pi = (value * 16)
        while i < 16:
            widget : QPushButton = self.color_widgets[i]
            color = palettes[pi//4][i%4]
            color = QColor(color[0], color[1], color[2])
            self.set_color(widget, color)

            #overrides
            if i == 12:
                widget.setText("0xf ("+(hex(palette_data[pi]))+")")
            elif i == 14:
                widget.setText("0x30 ("+(hex(palette_data[pi]))+")")
            else:
                widget.setText(hex(palette_data[pi]))

            i += 1
            pi += 1

        metadata = map_palette_metadata[value]
        self.unk_value.valueBox.setValue(metadata[0])
        self.null_chunk.valueBox.setValue(metadata[1])



class ThemeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Theme")
        self.setGeometry(100, 100, 400, 300)

        window_widget = QWidget()

        lister = QVBoxLayout()
        lister.setAlignment(Qt.AlignmentFlag.AlignTop)
        window_widget.setLayout(lister)

        # Add widgets to this new window as needed
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset)
        lister.addWidget(reset)

        # Add widgets to this new window as needed
        mother = QPushButton("Oppa Mother Style")
        mother.clicked.connect(self.mother_default)
        lister.addWidget(mother)

        self.setCentralWidget(window_widget)

    def mother_default(self):
        global app
        app.setStyleSheet(open("OppaMotherStyle.css", "r").read())

    def reset(self):
        global app
        app.setStyleSheet("""
                    QWidget {
                        font-family: "Arial";
                        font-size: 12px;
                    }
                    """)

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MOTHER map viewer")

        toolbar = QToolBar("FileIO")
        self.addToolBar(toolbar)

        self.load_file = QAction("Load", self)
        self.load_file.triggered.connect(self.open_file)
        toolbar.addAction(self.load_file)

        self.write_file = QAction("Save", self)
        self.write_file.triggered.connect(self.save_file)
        self.write_file.setDisabled(True)
        toolbar.addAction(self.write_file)

        self.theme_changer = QAction("Theme", self)
        self.theme_changer.triggered.connect(self.change_theme)
        toolbar.addAction(self.theme_changer)

        self.palette_changer = QAction("Palettes", self)
        self.palette_changer.triggered.connect(self.change_palette)
        toolbar.addAction(self.palette_changer)

        self.setCentralWidget(ActualWindow())

    def open_file(self):
        msgBox = QMessageBox()

        file_dialog = QFileDialog()
        file_path = file_dialog.getOpenFileName(self, "Select Map", "", "Binary Files (*.bin);;Yaml Files (*.yaml)")[0]

        mtp_path = "" # map_tile_properties
        palettes_path = "" #map_palettes
        if not file_path:
            file_path = "split/map.bin"
            mtp_path = "split/map_tile_properties.bin"
            palettes_path = "split/map_palettes.bin"
        else:
            mtp_path = file_dialog.getOpenFileName(self, "Select Collision", "", "Binary Files (*.bin);;Yaml Files (*.yaml)")[0]
            if not mtp_path:
                msgBox.setWindowTitle("DUDE")
                msgBox.setText("If you're gonna specify a custom map, please specify other custom files!")
                msgBox.exec()
                return
            palettes_path = file_dialog.getOpenFileName(self, "Select Palettes", "", "Binary Files (*.bin);;Yaml Files (*.yaml)")[0]
            if not palettes_path:
                msgBox.setWindowTitle("DUDE")
                msgBox.setText("If you're gonna specify a custom map, please specify other custom files!")
                msgBox.exec()
                return


        global Map_Stuff
        if Map_Stuff == None:
            Map_Stuff = MapInfo()
        if file_path.endswith(".bin"):
            Map_Stuff.decompile(open(file_path, "rb").read())
        elif file_path.endswith(".yaml"):
            Map_Stuff.in_yaml(file_path)

        global map_tile_properties
        map_tile_properties = bytearray(open(mtp_path, "rb").read())


        load_palette_data(palettes_path)
        convert_palettes_to_rgb()

        self.write_file.setDisabled(False)

        msgBox.setWindowTitle("INFO")
        msgBox.setText("Files Loaded.")
        msgBox.exec()


    def save_file(self):
        file_dialog = QFileDialog()
        file_path = file_dialog.getSaveFileName(self, "Select Map", "", "Binary Files (*.bin);;Yaml Files (*.yaml)")[0]

        mtp_path = "" # map_tile_properties
        palettes_path = "" #map_palettes
        if not file_path:
            file_path = "recompile/map.bin"
            mtp_path = "recompile/map_tile_properties.bin"
            palettes_path = "recompile/map_palettes.bin"
        else:
            mtp_path = file_dialog.getSaveFileName(self, "Select Collision", "", "Binary Files (*.bin);;Yaml Files (*.yaml)")[0]
            if not mtp_path:
                msgBox.setWindowTitle("DUDE")
                msgBox.setText("If you're gonna specify a custom map, please specify other custom files!")
                msgBox.exec()
                return
            palettes_path = file_dialog.getSaveFileName(self, "Select Palettes", "", "Binary Files (*.bin);;Yaml Files (*.yaml)")[0]
            if not palettes_path:
                msgBox.setWindowTitle("DUDE")
                msgBox.setText("If you're gonna specify a custom map, please specify other custom files!")
                msgBox.exec()
                return

        global Map_Stuff
        if file_path.endswith(".bin"):
            open(file_path, "wb").write(Map_Stuff.compile())
        elif file_path.endswith(".yaml"):
            open(file_path, "w").writelines(Map_Stuff.out_yaml())

        global palette_data
        open(palettes_path, "wb").write(palette_data)

        global map_tile_properties
        open(mtp_path, "wb").write(map_tile_properties)

        msgBox = QMessageBox()
        msgBox.setWindowTitle("INFO")
        msgBox.setText("Files Saved.")
        msgBox.exec()

    def change_theme(self):
        global Theme_Window
        if Theme_Window is None: # Prevent multiple instances if desired
            Theme_Window = ThemeWindow()
        Theme_Window.show()

    def change_palette(self):
        global Palette_Editor
        if Palette_Editor is None: # Prevent multiple instances if desired
            Palette_Editor = PaletteEditor(self)
        Palette_Editor.show()

Map_Viewer : Viewer = None
Map_Toolbar : Toolbar = None

Palette_Editor : PaletteEditor = None
Theme_Window : ThemeWindow = None

class ActualWindow(QWidget):
    def __init__(self):
        super().__init__()

        global Map_Viewer, Map_Toolbar

        vbox = QVBoxLayout()
        Map_Viewer = Viewer(self)
        Map_Toolbar = Toolbar(self)
        vbox.addLayout(Map_Toolbar)
        vbox.addWidget(Map_Viewer, stretch=1)
        self.setLayout(vbox)

app = None
if __name__ == "__main__":
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont("earthbound-beginnings.ttf")

    template = QPixmap.fromImage(ImageQt(Image.new("RGBA", (1,1))))
    window = Window()
    window.show()
    sys.exit(app.exec())