from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys
import numpy as np

from copy import deepcopy

from PIL import Image
from PIL.ImageQt import ImageQt
import yaml

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
        curBank = 0
        for offset in banksMap:
            for i in range(0x2000):
                tileOffs = offset + i #Offset of current 64x64 map data
                currentByte = byte_data[tileOffs]
                self.mapTiles.append(currentByte & 0b00111111); #Get lower 6 bits only of map data, store in array
                self.mapTileset.append((currentByte & 0b01000000) != 0)
                self.mapEvent.append((currentByte & 0b10000000) != 0)

            curBank += 1

        #Lower 6 bits of 3800-3FFF (skip 1st bank)
        banksSector = [0x5800, 0x9800, 0xD800, 0x11800, 0x15800, 0x19800, 0x1D800]
        curBank = 0
        for offset in banksSector:
            for i in range(0x200):
                tileOffs = offset + (i * 4) #Offset of current 256x256 sector data
                #First 6 bits of each byte
                self.sectorPalette.append(byte_data[tileOffs] & 0b00111111)
                self.sectorArea.append(byte_data[tileOffs+1] & 0b00111111)
                self.sectorTileset1.append(byte_data[tileOffs+2] & 0b00111111)
                self.sectorTileset2.append(byte_data[tileOffs+3] & 0b00111111)
            curBank += 1

        #Lower 6 bits of 3000-37FF
        self.graphics16 = []
        banks16 = [0x1000, 0x5000, 0x9000, 0xD000, 0x11000, 0x15000, 0x19000, 0x1D000]
        self.palettes64 = []
        curBank = 0
        for offset in banks16:
            for i in range(0x200):
                tileset = (curBank * 4) + (i // 0x80) #4 tilesets for each bank
                tileset *= 64
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
        curBank = 0
        array_i = 0
        for offset in banksMap:
            for i in range(0x2000):
                tileOffs = offset + i #Offset of current 64x64 map data
                currentByte = self.mapTiles[array_i] & 0b00111111
                currentByte |= (int(self.mapTileset[array_i]) & 0b1) << 6
                currentByte |= (int(self.mapEvent[array_i]) & 0b1) << 7
                out_bytes[tileOffs] |= currentByte

                array_i += 1

            curBank += 1

        #Lower 6 bits of 3800-3FFF (skip 1st bank)
        banksSector = [0x5800, 0x9800, 0xD800, 0x11800, 0x15800, 0x19800, 0x1D800]
        curBank = 0
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
            curBank += 1

        #Lower 6 bits of 3000-37FF
        banks16 = [0x1000, 0x5000, 0x9000, 0xD000, 0x11000, 0x15000, 0x19000, 0x1D000]
        curBank = 0
        array_i = 0
        array_p = 0
        for offset in banks16:
            for i in range(0x200):
                tileset = (curBank * 4) + (i // 0x80) #4 tilesets for each bank
                tileset *= 64
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

palette_data = open("split/map_palettes.bin", "rb").read()

palettes = []
for i in range(len(palette_data)//4):
    #this absolutely needs more work
    #fucks up some colors makes some good
    data = palette_data[i*4:(i+1)*4]
    data2 = data[2] & 0b00111111
    if (data[2] & 0b11000000 > 0):
        data2 = 0x30
    palettes.append([15, data[1], data2, data[3]])

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

def palette_image(data, palette):
    lookup_table = np.array(palette, dtype=np.uint8)
    colored_image = lookup_table[data]
    colored_image.shape = (8,8,3)
    return colored_image

template = None

#chunk graphicsitem
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

        chunk_x = self.id % 0x100
        chunk_y = self.id // 0x100

        sector_x = chunk_x // 4
        sector_y = chunk_y // 4
        sector_i = sector_x + (sector_y * 0x40)

        secondTileset = Map_Stuff.mapTileset[self.id]
        curTile = None

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

        for tile16_i in range(len(curTile["curTiles"])):
            tile16 = deepcopy(Map_Stuff.graphics16[curTile["curTiles"][tile16_i]])
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


        self.pixmap.setPixmap(QPixmap.fromImage(ImageQt(newImage)))
        self.generated = True
        newImage = None

class EBObject(QGraphicsRectItem):
    def __init__(self, x, y):
        super().__init__()
        self.position = (x, y)

        self.setRect(self.position[0]*16, (self.position[1]*16)+8, 16, 16)
        pen = QPen()
        pen.setWidth(5)
        pen.setColor(QColor(255, 0, 0))
        self.setPen(pen)

        self.being_moved = False

    def mouseMoveEvent(self, a0):
        if a0.buttons() & Qt.MouseButton.LeftButton:
            if self.being_moved:
                self.do_move(a0.pos())
                return

    def do_move(self, position):
        x,y = int(position.x()), int(position.y())

        x //= 16
        y //= 16

        self.position = (x,y)

        self.setRect(self.position[0]*16, (self.position[1]*16)+8, 16, 16)
        self.update()


    def mousePressEvent(self, a0):
        self.being_moved = True

    def mouseReleaseEvent(self, a0):
        self.being_moved = False

    def mouseDoubleClickEvent(self, a0):
        self.being_moved = True

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
        self.chunk_grid = GridItem(64, QColor(255, 0, 0), 1)
        self.chunk_grid.setZValue(998)
        self.addItem(self.chunk_grid)
        self.sector_grid = GridItem(64*4, QColor(100, 100, 100), 3)
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
            if mode == Toolbar.Select_mode.Chunks:
                self.selection.setRect(0, 0, 64, 64)

            else:
                self.selection.setRect(0, 0, 64*4, 64*4)
                self.selection.setX((self.selection.pos().x() // (64*4)) * (64*4))
                self.selection.setY((self.selection.pos().y() // (64*4)) * (64*4))
            pen = QPen()
            pen.setWidth(5)
            pen.setColor(QColor(255, 0, 0))
            self.selection.setPen(pen)

            self.window.current_position = (int(self.selection.pos().x()), int(self.selection.pos().y()))
            self.window.update_selection()
        else:
            self.selection.setRect(0,0,0,0)
            self.selection.setPen(QPen())

#grid handler
class GridItem(QGraphicsItem):
    def __init__(self, gridSize, color, width, parent=None):
        super().__init__(parent)
        self.gridSize = gridSize
        self.width = 0x100*64
        self.height = 0xE0*64
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
        not_clicking |= x > 0x100 * 64
        not_clicking |= y < 0
        not_clicking |= y > 0xE0 * 64
        if not_clicking:
            return

        self.current_position = (x // 64, y // 64)
        self.update_selection()

    def update_selection(self):
        x,y = self.current_position
        global palettes, Map_Stuff

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

        if self._main.toolbar.select_mode in [Toolbar.Select_mode.Chunks, Toolbar.Select_mode.Sectors]:
            self._main.toolbar.palette.valueBox.setValue(palette_i)
            self._main.toolbar.tileset.valueBox.setValue(tileset)
            self._main.toolbar.tileset_2.valueBox.setValue(tileset2)

            if self._main.toolbar.select_mode == Toolbar.Select_mode.Chunks:
                self._main.toolbar.use_tileset.valueBox.setValue(secondTileset)
                self._scene.selection.setPos(chunk_x*64,chunk_y*64)
            else:
                self._main.toolbar.area.valueBox.setValue(area)
                self._scene.selection.setPos(sector_x*4*64,sector_y*4*64)
        self._scene.update() #required so there isnt artifacting


    def mouseMoveEvent(self, a0):
        super().mouseMoveEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.move_selection(a0, False)

    def mousePressEvent(self, a0):
        super().mousePressEvent(a0)
        self.move_selection(a0, False)

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
        options.addLayout(grid_views)


        self.addLayout(options)

        info = QHBoxLayout()
        self.palette = ValueBox("Palette: ", (0, len(palettes)//4-1), True)
        self.palette.valueBox.valueChanged.connect(self.palette_changed)
        info.addLayout(self.palette)

        self.tileset = ValueBox("Tileset: ", (0, 0x40-1), True)
        info.addLayout(self.tileset)

        self.tileset_2 = ValueBox("Tileset_2: ", (0, 0x40-1), True)
        info.addLayout(self.tileset_2)

        self.use_tileset = ValueBox("Use Tileset: ", (1, 2), True)
        info.addLayout(self.use_tileset)

        self.area = ValueBox("Area: ", (0, 0x40-1), True)
        info.addLayout(self.area)

        self.addLayout(info)

        self.set_select_mode(self.select_mode)

    def palette_changed(self, value):

        pos = self._main.viewer.current_position
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
        chunks = self._main.viewer._scene.chunks
        chunk_x2, chunk_y2 = (sector_x+1) * 4, (sector_y+1) * 4
        chunk_x3, chunk_y3 = (sector_x) * 4, (sector_y) * 4
        for c_y in range(chunk_y3, chunk_y2):
            for c_x in range(chunk_x3, chunk_x2):
                affected_chunks.append(chunks[c_x + (c_y * 0x100)])

        for chunk in affected_chunks:
            chunk.generate_pixmap()

    def toggle_grid(self, i):
        sector_grid = self._main.viewer._scene.sector_grid
        chunk_grid = self._main.viewer._scene.chunk_grid
        if i == 0:
            sector_grid.setVisible(not sector_grid.isVisible())
        elif i == 1:
            chunk_grid.setVisible(not chunk_grid.isVisible())

    def set_select_mode(self, mode):
        self.select_mode = mode
        self._main.viewer._scene.change_selection(mode)
        if self.select_mode == Toolbar.Select_mode.Chunks:
            self.use_tileset.show()
            self.area.hide()
        else:
            self.use_tileset.hide()
            self.area.show()

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

        self.setCentralWidget(ActualWindow())

    #TODO: make yaml in yaml out
    def open_file(self):
        file_dialog = QFileDialog()
        file_path = file_dialog.getOpenFileName(self, "Select File", "", "Binary Files (*.bin);;Yaml Files (*.yaml)")[0]
        if not file_path:
            return

        global Map_Stuff
        if Map_Stuff == None:
            Map_Stuff = MapInfo()
        if file_path.endswith(".bin"):
            Map_Stuff.decompile(open(file_path, "rb").read())
        elif file_path.endswith(".yaml"):
            Map_Stuff.in_yaml(file_path)

        self.write_file.setDisabled(False)

        msgBox = QMessageBox()
        msgBox.setWindowTitle("INFO")
        msgBox.setText("File Loaded.")
        msgBox.exec()


    def save_file(self):
        file_dialog = QFileDialog()
        file_path = file_dialog.getSaveFileName(self, "Select File", "", "Binary Files (*.bin);;Yaml Files (*.yaml)")[0]
        if not file_path:
            return

        global Map_Stuff
        if file_path.endswith(".bin"):
            open(file_path, "wb").write(Map_Stuff.compile())
        elif file_path.endswith(".yaml"):
            open(file_path, "w").writelines(Map_Stuff.out_yaml())

        msgBox = QMessageBox()
        msgBox.setWindowTitle("INFO")
        msgBox.setText("File Saved.")
        msgBox.exec()

class ActualWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.viewer = Viewer(self)
        vbox = QVBoxLayout()
        self.toolbar = Toolbar(self)
        vbox.addLayout(self.toolbar)
        vbox.addWidget(self.viewer, stretch=1)
        self.setLayout(vbox)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    template = QPixmap.fromImage(ImageQt(Image.new("RGBA", (1,1))))
    window = Window()
    window.show()
    sys.exit(app.exec())