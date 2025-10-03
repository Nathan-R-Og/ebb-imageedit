from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys
import numpy as np

from copy import deepcopy

from PIL import Image, ImageDraw
from PIL.ImageQt import ImageQt

from MapEditor import MapInfo
from MapEditor import map_tile_properties
Map_Stuff : MapInfo = None
from MapEditor import palettes
from MapEditor import palette_image
from MapEditor import template

ts1_override = -1
ts2_override = -1
palette_override = -1
use_tileset_override = False

###Chunk Stuff
#chunk graphicsitem
class Tileset(object):
    def __init__(self, id, x, y):
        self.visible = False
        self.id = id
        global template
        self.pixmap : QGraphicsPixmapItem = QGraphicsPixmapItem(template)
        self.pixmap.setPos(x,y)
        self.generated = False

    def generate_pixmap(self, ts1=0, palette_s=0, palette_i=0):
        ##make_chunk
        global palettes

        use_bg_palette = palettes[palette_s*4:(palette_s+1)*4][palette_i]


        #newImage = Image.new("RGBA", (64, 64))

        pixels = {}

        for tile8_i in range(4*0x10):
            tile8 = deepcopy(Map_Stuff.graphics8[tile8_i+ts1*(0x40)])

            x8 = tile8_i % 0x10
            y8 = tile8_i // 0x10

            new_tile = palette_image(tile8, use_bg_palette)
            pixels[tile8_i] = new_tile
            new_tile = None

        #construct 8x8 of 8x8s
        p_array = []
        for i in range(4*0x10):
            p_array.append(pixels[i])

        s = []
        for i in range(4):
            x = p_array[i*0x10:(i+1)*0x10]
            s.append(np.hstack(x))
        newImage = Image.fromarray(np.vstack(s)).convert("RGBA")
        self.pixmap.setPixmap(QPixmap.fromImage(ImageQt(newImage)))
        self.generated = True
        newImage = None

class TILESET_Scene(QGraphicsScene):
    def __init__(self, xp, yp, w, h):
        super(TILESET_Scene, self).__init__(xp, yp, w, h)
        self.id = 0

        self.set = Tileset(0, 0, 0)
        self.addItem(self.set.pixmap)
        self.window : QGraphicsView = None

        self.selection = QGraphicsRectItem()
        self.selection.setZValue(1000)
        self.addItem(self.selection)
        self.tile_grid = GridItem(8, QColor(255, 0, 0), 8, 8, 1)
        self.tile_grid.setZValue(998)
        self.addItem(self.tile_grid)

    def queue_update(self):
        if self.window == None:
            return
        global Chunk_Toolbar, Tile_Toolbar
        if Chunk_Toolbar == None:
            return
        if Tile_Toolbar == None:
            return
        self.set.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.palette_v, Tile_Toolbar.palette_v)

    def init_selection(self):
        print(self.window.current_position)
        if self.window.current_position == None:
            self.window.current_position = (0,0)

        self.selection.setRect(0, 0, 8, 8)
        self.window.current_position = (self.window.current_position[0] * 8,
                                        self.window.current_position[1] * 8)
        self.selection.setX(self.window.current_position[0])
        self.selection.setY(self.window.current_position[1])
        pen = QPen()
        pen.setWidth(3)
        pen.setColor(QColor(255, 0, 0))
        self.selection.setPen(pen)

        self.window.update_selection()
        print(self.window.current_position)

class TILESET_Viewer(QGraphicsView):
    def __init__(self, parent):
        super().__init__()
        self.placets = 1

        self._main = parent
        scalar = (4, 4)
        self.scale(scalar[0], scalar[1])
        sizer = (8*0x10*scalar[0], 8*4*scalar[1])
        self._scene = TILESET_Scene(0, 0, sizer[0], sizer[1])
        self.setScene(self._scene)
        self.setSceneRect(QRectF(0, 0, sizer[0]/scalar[0], sizer[1]/scalar[1]))
        self.setFixedSize(sizer[0], sizer[1])

        self._scene.window = self
        global Map_Stuff
        if Map_Stuff != None:
            self._scene.queue_update()

        self.setMouseTracking(True)
        self.current_position = None

        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setStyleSheet("border-width: 0px; border-style: solid")
        self.setStyleSheet("border: 0px")

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scene.init_selection()

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
        not_clicking |= x >= 8 * 0x10
        not_clicking |= y < 0
        not_clicking |= y >= 8 * 0x10
        if not_clicking:
            return

        self.current_position = (x // 8, y // 8)
        self.update_selection()

    def update_selection(self):
        global Map_Stuff, map_tile_properties
        global Chunk_Toolbar, Tile_Toolbar
        global Chunk_Select_V, Tile1_Select_V, Tile2_Select_V, Chunk_Edit_V
        if Map_Stuff == None:
            return

        print(self.current_position)

        self._scene.selection.setPos(self.current_position[0]*8,self.current_position[1]*8)
        self._scene.update() #required so there isnt artifacting

    def mouseMoveEvent(self, a0):
        super().mouseMoveEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.placets = 1
            self.move_selection(a0, False)
        elif a0.buttons() & Qt.MouseButton.RightButton:
            self.placets = 2
            self.move_selection(a0, False)

    def mousePressEvent(self, a0):
        super().mousePressEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.placets = 1
            self.move_selection(a0, False)
        elif a0.buttons() & Qt.MouseButton.RightButton:
            self.placets = 2
            self.move_selection(a0, False)

    def mouseReleaseEvent(self, a0):
        super().mouseReleaseEvent(a0)

    def mouseDoubleClickEvent(self, a0):
        super().mouseDoubleClickEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.placets = 1
            self.move_selection(a0, False)
        elif a0.buttons() & Qt.MouseButton.RightButton:
            self.placets = 2
            self.move_selection(a0, False)

### Metatile stuff
class Metatile(object):
    def __init__(self, id, x, y, its2=False):
        self.visible = False
        self.id = id
        global template
        self.pixmap : QGraphicsPixmapItem = QGraphicsPixmapItem(template)
        self.pixmap.setPos(x*16,y*16)
        self.generated = False
        self.which = its2

    def generate_pixmap(self, ts1=0, ts2=0, palette_i=0, paletteNum=0, show_collision=False):
        ##make_chunk
        global palettes
        global map_tile_properties

        use_bg_palette = palettes[palette_i*4:(palette_i+1)*4]

        #newImage = Image.new("RGBA", (64, 64))

        if self.which:
            ts1 = ts2

        pixels = {}

        tile16 = deepcopy(Map_Stuff.graphics16[self.id+(ts1 * 128)])
        for tile8_i in range(4):
            tile8 = deepcopy(Map_Stuff.graphics8[tile16[tile8_i]])

            my_palette = use_bg_palette[paletteNum]

            new_tile = palette_image(tile8, my_palette)
            pixels[tile8_i] = new_tile
            new_tile = None

        #construct 8x8 of 8x8s
        p_array = []
        for i in range(4):
            p_array.append(pixels[i])

        s = []
        for i in range(2):
            x = p_array[i*2:(i+1)*2]
            s.append(np.hstack(x))
        newImage = Image.fromarray(np.vstack(s)).convert("RGBA")

        if show_collision:
            collision = map_tile_properties[(ts1 * 0x80) + self.id]

            if collision != 0:
                overlay = Image.new('RGBA', newImage.size, (0, 0, 0, 0))
                draw_overlay = ImageDraw.Draw(overlay)
                color = (255, 0, 0, 99)


                if collision & 0b00010000: #full collision
                    draw_overlay.polygon([(0, 0), (0, 16), (16, 16), (16, 0)], color, color)
                else:
                    if collision & 0b00001000: # top left on this tile is blocked
                        draw_overlay.polygon([(0, 0), (0, 8), (8, 0)], color, color)
                    if collision & 0b00000100: # bottom left on this tile is blocked
                        draw_overlay.polygon([(0, 16), (0, 8), (8, 16)], color, color)
                    if collision & 0b00000010: # bottom right on this tile is blocked
                        draw_overlay.polygon([(16, 8), (8, 16), (16, 16)], color, color)
                    if collision & 0b00000001: # top right on this tile is blocked
                        draw_overlay.polygon([(8, 0), (16, 0), (16, 8)], color, color)


                newImage = Image.alpha_composite(newImage, overlay)

        newImage.save("TESTTILE.png")

        self.pixmap.setPixmap(QPixmap.fromImage(ImageQt(newImage)))
        self.generated = True
        newImage = None

class METATILE_Scene(QGraphicsScene):
    def __init__(self, xp, yp, w, h):
        super(METATILE_Scene, self).__init__(xp, yp, w, h)
        self.tiles = []
        self.window : QGraphicsView = None

        for y in range(8):
            for x in range(16):
                i = x + (y * 16)
                new_tile = Metatile(i, x, y)
                self.tiles.append(new_tile)
                self.addItem(new_tile.pixmap)

        self.selection = QGraphicsRectItem()
        self.selection.setZValue(1000)
        self.addItem(self.selection)
        self.tile_grid = GridItem(16, QColor(255, 0, 0), 16, 8, 1)
        self.tile_grid.setZValue(998)
        self.addItem(self.tile_grid)

    def queue_update(self):
        if self.window == None:
            return
        global Chunk_Toolbar, Tile_Toolbar
        if Chunk_Toolbar == None:
            return
        if Tile_Toolbar == None:
            return
        for tile in self.tiles:
            if not tile.generated:
                ts1 = Chunk_Toolbar.tileset1
                ts2 = Chunk_Toolbar.tileset2
                pv = Chunk_Toolbar.palette_v
                tile.generate_pixmap(ts1, ts2, pv, Tile_Toolbar.palette_v, Tile_Toolbar.collision)

    def init_selection(self):
        print(self.window.current_position)
        if self.window.current_position == None:
            self.window.current_position = (0,0)

        self.selection.setRect(0, 0, 16, 16)
        self.window.current_position = (self.window.current_position[0] * 16,
                                        self.window.current_position[1] * 16)
        self.selection.setX(self.window.current_position[0])
        self.selection.setY(self.window.current_position[1])
        pen = QPen()
        pen.setWidth(5)
        pen.setColor(QColor(255, 0, 0))
        self.selection.setPen(pen)

        self.window.update_selection()
        print(self.window.current_position)

#scene viewer
class METATILE_Viewer(QGraphicsView):
    def __init__(self, parent):
        super().__init__()
        self._main = parent
        scalar = (2, 2)
        self.scale(scalar[0], scalar[1])
        sizer = (16*16*scalar[0], 16*8*scalar[1])
        self._scene = METATILE_Scene(0, 0, sizer[0], sizer[1])
        self.setScene(self._scene)
        self.setSceneRect(QRectF(0, 0, sizer[0]/scalar[0], sizer[1]/scalar[1]))
        self.setFixedSize(sizer[0], sizer[1])

        self._scene.window = self
        global Map_Stuff
        if Map_Stuff != None:
            self._scene.queue_update()

        self.setMouseTracking(True)
        self.current_position = None

        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setStyleSheet("border-width: 0px; border-style: solid")
        self.setStyleSheet("border: 0px")

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scene.init_selection()

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
        not_clicking |= x >= 16 * 16
        not_clicking |= y < 0
        not_clicking |= y >= 8 * 16
        if not_clicking:
            return

        self.current_position = (x // 16, y // 16)
        self.update_selection()

    def update_selection(self):
        global Metatile_Edit_V
        if Metatile_Edit_V:
            Metatile_Edit_V._scene.secondary = self._scene.tiles[0].which
            Metatile_Edit_V._scene.index = self.current_position[0] + (self.current_position[1] * 0x10)
            Metatile_Edit_V._scene.tile.generated = False

        self._scene.selection.setPos(self.current_position[0]*16,self.current_position[1]*16)
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

###displayers for the one metatile you are actually editing
#scene manager
class Single_METATILE_Scene(QGraphicsScene):
    def __init__(self, xp, yp, w, h):
        super(Single_METATILE_Scene, self).__init__(xp, yp, w, h)
        self.window : QGraphicsView = None
        self.index = 0
        self.secondary = False

        self.tile = Metatile(self.index, 0, 0)
        self.which = self.secondary
        self.addItem(self.tile.pixmap)

        self.selection = QGraphicsRectItem()
        self.selection.setZValue(1000)
        self.addItem(self.selection)
        self.tile_grid = GridItem(8, QColor(255, 0, 0), 8, 8, 1)
        self.tile_grid.setZValue(998)
        self.addItem(self.tile_grid)

    def queue_update(self):

        if self.window == None:
            return
        global Chunk_Toolbar
        if Chunk_Toolbar == None:
            return
        global Tile_Toolbar
        if Tile_Toolbar == None:
            return
        if not self.tile.generated:

            self.tile.id = self.index
            self.which = self.secondary

            ts1 = Chunk_Toolbar.tileset1
            ts2 = Chunk_Toolbar.tileset2
            pv = Chunk_Toolbar.palette_v
            self.tile.generate_pixmap(ts1, ts2, pv, Tile_Toolbar.palette_v, Tile_Toolbar.collision)


    def init_selection(self):
        print(self.window.current_position)
        if self.window.current_position == None:
            self.window.current_position = (0,0)

        self.selection.setRect(0, 0, 8, 8)
        self.window.current_position = (self.window.current_position[0] * 8,
                                        self.window.current_position[1] * 8)
        self.selection.setX(self.window.current_position[0])
        self.selection.setY(self.window.current_position[1])
        pen = QPen()
        pen.setWidth(2)
        pen.setColor(QColor(255, 0, 0))
        self.selection.setPen(pen)

        self.window.update_selection()
        print(self.window.current_position)

class Single_METATILE_Viewer(QGraphicsView):
    def __init__(self, parent):
        super().__init__()
        self.placets = 1

        self._main = parent
        scalar = (4, 4)
        self.scale(scalar[0], scalar[1])
        sizer = (16*scalar[0], 16*scalar[1])
        self._scene = Single_METATILE_Scene(0, 0, sizer[0], sizer[1])
        self.setScene(self._scene)
        self.setSceneRect(QRectF(0, 0, sizer[0]/scalar[0], sizer[1]/scalar[1]))
        self.setFixedSize(sizer[0], sizer[1])

        self._scene.window = self
        global Map_Stuff
        if Map_Stuff != None:
            self._scene.queue_update()

        self.setMouseTracking(True)
        self.current_position = None

        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setStyleSheet("border-width: 0px; border-style: solid")
        self.setStyleSheet("border: 0px")

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scene.init_selection()

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
        not_clicking |= x >= 8 * 2
        not_clicking |= y < 0
        not_clicking |= y >= 8 * 2
        if not_clicking:
            return

        if self.placets == 1: #tile mode
            self.current_position = (x // 8, y // 8)
        elif self.placets == 2: #collision mode
            self.current_position = (x // 6, y // 6)
        self.update_selection()

    def update_selection(self):
        global Map_Stuff, map_tile_properties
        global Chunk_Toolbar, Tile_Toolbar
        global Chunk_Select_V, Tile1_Select_V, Tile2_Select_V, Chunk_Edit_V
        global Tileset_Select_V
        if Map_Stuff == None:
            return
        if Tileset_Select_V == None:
            return


        usar = Chunk_Toolbar.tileset1
        if self._scene.tile.which:
            usar = Chunk_Toolbar.tileset2
        adr = (usar * 0x80) + self._scene.tile.id

        x,y = self.current_position

        if self.placets == 1:
            tile8_i = x + (y * 2)
            print(Map_Stuff.graphics16[adr][tile8_i])

            x2,y2 = Tileset_Select_V.current_position
            get_id = x2 + (y2 * 0x10)

            Map_Stuff.graphics16[adr][tile8_i] = get_id

            self._scene.selection.setPos(self.current_position[0]*8,self.current_position[1]*8)

            if Chunk_Toolbar.tileset1 == Chunk_Toolbar.tileset2:
                metatile = Tile1_Select_V._scene.tiles[self._scene.tile.id]
                metatile.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
                metatile = Tile2_Select_V._scene.tiles[self._scene.tile.id]
                metatile.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
            else:
                if self._scene.tile.which:
                    metatile = Tile2_Select_V._scene.tiles[self._scene.tile.id]
                    metatile.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
                else:
                    metatile = Tile1_Select_V._scene.tiles[self._scene.tile.id]
                    metatile.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)

            for chunk in Chunk_Select_V._scene.chunks:
                chunk.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Chunk_Toolbar.collision)
            Chunk_Edit_V._scene.chunk.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Chunk_Toolbar.collision)

        elif self.placets == 2:
            collision = map_tile_properties[adr]
            if x == 0 and y == 0: #top left
                collision ^= 0b00001000
            elif x == 2 and y == 0: #top right
                collision ^= 0b00000001
            elif x == 0 and y == 2: #bottom left
                collision ^= 0b00000100
            elif x == 2 and y == 2: #bottom right
                collision ^= 0b00000010
            elif x == 1 and y == 1: #middle
                collision ^= 0b00010000

            map_tile_properties[adr] = collision

            if Tile_Toolbar.collision:
                if Chunk_Toolbar.tileset1 == Chunk_Toolbar.tileset2:
                    metatile = Tile1_Select_V._scene.tiles[self._scene.tile.id]
                    metatile.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
                    metatile = Tile2_Select_V._scene.tiles[self._scene.tile.id]
                    metatile.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
                else:
                    if self._scene.tile.which:
                        metatile = Tile2_Select_V._scene.tiles[self._scene.tile.id]
                        metatile.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
                    else:
                        metatile = Tile1_Select_V._scene.tiles[self._scene.tile.id]
                        metatile.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)

            if Chunk_Toolbar.collision:
                for chunk in Chunk_Select_V._scene.chunks:
                    chunk.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Chunk_Toolbar.collision)
                Chunk_Edit_V._scene.chunk.generate_pixmap(Chunk_Toolbar.tileset1, Chunk_Toolbar.tileset2, Chunk_Toolbar.palette_v, Chunk_Toolbar.collision)


        self._scene.tile.generated = False
        self._scene.update() #required so there isnt artifacting


    def mouseMoveEvent(self, a0):
        super().mouseMoveEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.placets = 1
            self.move_selection(a0, False)
        elif a0.buttons() & Qt.MouseButton.RightButton:
            self.placets = 2
            self.move_selection(a0, False)

    def mousePressEvent(self, a0):
        super().mousePressEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.placets = 1
            self.move_selection(a0, False)
        elif a0.buttons() & Qt.MouseButton.RightButton:
            self.placets = 2
            self.move_selection(a0, False)

    def mouseReleaseEvent(self, a0):
        super().mouseReleaseEvent(a0)

    def mouseDoubleClickEvent(self, a0):
        super().mouseDoubleClickEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.placets = 1
            self.move_selection(a0, False)
        elif a0.buttons() & Qt.MouseButton.RightButton:
            self.placets = 2
            self.move_selection(a0, False)





###Chunk Stuff
#chunk graphicsitem
class Chunk(object):
    def __init__(self, id, x, y):
        self.visible = False
        self.id = id
        global template
        self.pixmap : QGraphicsPixmapItem = QGraphicsPixmapItem(template)
        self.pixmap.setPos(x*64,y*64)
        self.generated = False

    def generate_pixmap(self, ts1=0, ts2=0, palette_i=0, show_collision=False):
        ##make_chunk
        global palettes
        global Map_Stuff
        global map_tile_properties

        g64_id = (ts1 * 64) + self.id

        curTile = Map_Stuff.graphics64[g64_id]
        for index in curTile["altTileset"]: #2 == altTileset
            curTile["curTiles"][index] = (ts2 * 128) + curTile["tileNums"][index]

        use_bg_palette = palettes[palette_i*4:(palette_i+1)*4]

        #newImage = Image.new("RGBA", (64, 64))

        pixels = {}

        collision = []

        for tile16_i in range(len(curTile["curTiles"])):
            tile16 = deepcopy(Map_Stuff.graphics16[curTile["curTiles"][tile16_i]])

            if show_collision:
                if tile16_i in curTile["altTileset"]:
                    collision.append(map_tile_properties[(ts2 * 0x80) + tile16[4]])
                else:
                    collision.append(map_tile_properties[(ts1 * 0x80) + tile16[4]])

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

        if show_collision:
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

#scene manager
class CHUNK_Scene(QGraphicsScene):
    def __init__(self, xp, yp, w, h):
        super(CHUNK_Scene, self).__init__(xp, yp, w, h)
        self.chunks = []
        self.window : QGraphicsView = None

        for y in range(8):
            for x in range(8):
                i = x + (y * 8)
                new_chunk = Chunk(i, x, y)
                self.chunks.append(new_chunk)
                self.addItem(new_chunk.pixmap)

        self.selection = QGraphicsRectItem()
        self.selection.setZValue(1000)
        self.addItem(self.selection)
        self.chunk_grid = GridItem(64, QColor(255, 0, 0), 8, 8, 1)
        self.chunk_grid.setZValue(998)
        self.addItem(self.chunk_grid)

    def queue_update(self):
        if self.window == None:
            return
        global Chunk_Toolbar
        if Chunk_Toolbar == None:
            return
        for chunk in self.chunks:
            if not chunk.generated:
                ts1 = Chunk_Toolbar.tileset1
                ts2 = Chunk_Toolbar.tileset2
                pv = Chunk_Toolbar.palette_v
                col = Chunk_Toolbar.collision
                chunk.generate_pixmap(ts1, ts2, pv, col)

    def init_selection(self):
        print(self.window.current_position)
        if self.window.current_position == None:
            self.window.current_position = (0,0)

        self.selection.setRect(0, 0, 64, 64)
        self.window.current_position = (self.window.current_position[0] * 64,
                                        self.window.current_position[1] * 64)
        self.selection.setX(self.window.current_position[0])
        self.selection.setY(self.window.current_position[1])
        pen = QPen()
        pen.setWidth(5)
        pen.setColor(QColor(255, 0, 0))
        self.selection.setPen(pen)

        self.window.update_selection()
        print(self.window.current_position)

#scene viewer
class CHUNK_Viewer(QGraphicsView):
    def __init__(self, parent):
        super().__init__()

        self._main = parent
        scalar = (1, 1)
        self.scale(scalar[0], scalar[1])
        sizer = (64*8*scalar[0], 64*8*scalar[1])
        self._scene = CHUNK_Scene(0, 0, sizer[0], sizer[1])
        self.setScene(self._scene)
        self.setSceneRect(QRectF(0, 0, sizer[0]/scalar[0], sizer[1]/scalar[1]))
        self.setFixedSize(sizer[0], sizer[1])

        self._scene.window = self
        global Map_Stuff
        if Map_Stuff != None:
            self._scene.queue_update()

        self.setMouseTracking(True)
        self.current_position = None

        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setStyleSheet("border-width: 0px; border-style: solid")
        self.setStyleSheet("border: 0px")

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scene.init_selection()

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
        not_clicking |= x >= 8 * 64
        not_clicking |= y < 0
        not_clicking |= y >= 8 * 64
        if not_clicking:
            return

        self.current_position = (x // 64, y // 64)
        self.update_selection()

    def update_selection(self):
        self._scene.selection.setPos(self.current_position[0]*64,self.current_position[1]*64)
        global Chunk_Edit_V
        if Chunk_Edit_V == None:
            self._scene.update() #required so there isnt artifacting
            return
        x,y = self.current_position
        i = x + (y * 8)
        c : Chunk = Chunk_Edit_V._scene.chunk
        c.id = i
        c.generated = False
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







###displayers for that one chunk you are actually editing
#scene manager
class Single_CHUNK_Scene(QGraphicsScene):
    def __init__(self, xp, yp, w, h):
        super(Single_CHUNK_Scene, self).__init__(xp, yp, w, h)
        self.chunks = []
        self.window : QGraphicsView = None

        new_chunk = Chunk(0, 0, 0)
        self.chunk = new_chunk
        self.addItem(new_chunk.pixmap)

        self.selection = QGraphicsRectItem()
        self.selection.setZValue(1000)
        self.addItem(self.selection)
        self.chunk_grid = GridItem(16, QColor(255, 0, 0), 8, 8, 1)
        self.chunk_grid.setZValue(998)
        self.addItem(self.chunk_grid)

    def queue_update(self):
        if self.window == None:
            return
        global Chunk_Toolbar
        if Chunk_Toolbar == None:
            return
        if not self.chunk.generated:
            ts1 = Chunk_Toolbar.tileset1
            ts2 = Chunk_Toolbar.tileset2
            pv = Chunk_Toolbar.palette_v
            col = Chunk_Toolbar.collision

            self.chunk.generate_pixmap(ts1, ts2, pv, col)

    def init_selection(self):
        print(self.window.current_position)
        if self.window.current_position == None:
            self.window.current_position = (0,0)

        self.selection.setRect(0, 0, 16, 16)
        self.window.current_position = (self.window.current_position[0] * 16,
                                        self.window.current_position[1] * 16)
        self.selection.setX(self.window.current_position[0])
        self.selection.setY(self.window.current_position[1])
        pen = QPen()
        pen.setWidth(5)
        pen.setColor(QColor(255, 0, 0))
        self.selection.setPen(pen)

        self.window.update_selection()
        print(self.window.current_position)

class Single_CHUNK_Viewer(QGraphicsView):
    def __init__(self, parent):
        super().__init__()
        self.placets = 1

        self._main = parent
        scalar = (2, 2)
        self.scale(scalar[0], scalar[1])
        sizer = (64*scalar[0], 64*scalar[1])
        self._scene = Single_CHUNK_Scene(0, 0, sizer[0], sizer[1])
        self.setScene(self._scene)
        self.setSceneRect(QRectF(0, 0, sizer[0]/scalar[0], sizer[1]/scalar[1]))
        self.setFixedSize(sizer[0], sizer[1])

        self._scene.window = self
        global Map_Stuff
        if Map_Stuff != None:
            self._scene.queue_update()

        self.setMouseTracking(True)
        self.current_position = None

        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setStyleSheet("border-width: 0px; border-style: solid")
        self.setStyleSheet("border: 0px")

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scene.init_selection()

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
        not_clicking |= x >= 4 * 16
        not_clicking |= y < 0
        not_clicking |= y >= 4 * 16
        if not_clicking:
            return

        self.current_position = (x // 16, y // 16)
        self.update_selection()

    def update_selection(self):
        global Map_Stuff
        if Map_Stuff == None:
            return

        global Chunk_Toolbar
        ts1 = Chunk_Toolbar.tileset1
        ts2 = Chunk_Toolbar.tileset2

        get_chunk_data = Map_Stuff.graphics64[(ts1 * 64) + self._scene.chunk.id]

        x,y = self.current_position
        tile_i = x + (y * 4)

        get_id = -1
        tile_id = 0
        if self.placets == 1:
            global Tile1_Select_V
            x2,y2 = (0,0)
            if Tile1_Select_V != None:
                x2,y2 = Tile1_Select_V.current_position
            get_id = x2 + (y2 * 16)
            #remove from altTileset
            if tile_i in get_chunk_data["altTileset"]:
                get_chunk_data["altTileset"].remove(tile_i)

            tile_id = get_id + (ts1 * 0x80)
        else:
            global Tile2_Select_V
            x2,y2 = (0,0)
            if Tile2_Select_V != None:
                x2,y2 = Tile2_Select_V.current_position
            get_id = x2 + (y2 * 16)
            #add to altTileset
            if not get_id in get_chunk_data["altTileset"]:
                get_chunk_data["altTileset"].append(tile_i)
            tile_id = get_id + (ts2 * 0x80)

        global Tile_Toolbar
        if Tile_Toolbar != None:
            Map_Stuff.palettes64[get_chunk_data["palette64"]][tile_i] = Tile_Toolbar.palette_v

        get_chunk_data['curTiles'][tile_i] = tile_id
        get_chunk_data["tileNums"][tile_i] = get_id

        global Chunk_Select_V
        if Chunk_Select_V != None:
            Chunk_Select_V._scene.chunks[self._scene.chunk.id].generated = False

        self._scene.selection.setPos(self.current_position[0]*16,self.current_position[1]*16)
        self._scene.chunk.generated = False
        self._scene.update() #required so there isnt artifacting


    def mouseMoveEvent(self, a0):
        super().mouseMoveEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.placets = 1
            self.move_selection(a0, False)
        elif a0.buttons() & Qt.MouseButton.RightButton:
            self.placets = 2
            self.move_selection(a0, False)

    def mousePressEvent(self, a0):
        super().mousePressEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.placets = 1
            self.move_selection(a0, False)
        elif a0.buttons() & Qt.MouseButton.RightButton:
            self.placets = 2
            self.move_selection(a0, False)

    def mouseReleaseEvent(self, a0):
        super().mouseReleaseEvent(a0)

    def mouseDoubleClickEvent(self, a0):
        super().mouseDoubleClickEvent(a0)
        if a0.buttons() & Qt.MouseButton.LeftButton:
            self.placets = 1
            self.move_selection(a0, False)
        elif a0.buttons() & Qt.MouseButton.RightButton:
            self.placets = 2
            self.move_selection(a0, False)


from MapEditor import GridItem
from MapEditor import ValueBox

class MToolbar(QVBoxLayout):

    def __init__(self, parent):
        super().__init__()
        self._main = parent

        options = QHBoxLayout()
        grid_views = QHBoxLayout()
        tile_grid = QPushButton("Tile Grid")
        tile_grid.clicked.connect(self.toggle_grid)
        grid_views.addWidget(tile_grid)
        tile_grid = QPushButton("Tile Collision")
        tile_grid.clicked.connect(self.toggle_collision)
        grid_views.addWidget(tile_grid)
        options.addLayout(grid_views)

        self.addLayout(options)

        info = QHBoxLayout()
        self.palette = ValueBox("Palette: ", (0, 4-1), True)
        self.palette.valueBox.valueChanged.connect(self.palette_changed)
        info.addLayout(self.palette)

        self.addLayout(info)

        self.palette_v = 0

        self.collision = False

    def palette_changed(self, value):
        if value == self.palette_v:
            return

        global Chunk_Toolbar, Tile1_Select_V, Tile2_Select_V, Metatile_Edit_V
        self.palette_v = value
        ts1 = Chunk_Toolbar.tileset1
        ts2 = Chunk_Toolbar.tileset2
        pv = Chunk_Toolbar.palette_v
        for tile in Tile1_Select_V._scene.tiles:
            tile.generate_pixmap(ts1, ts2, pv, self.palette_v, self.collision)
        for tile in Tile2_Select_V._scene.tiles:
            tile.generate_pixmap(ts1, ts2, pv, self.palette_v, self.collision)
        Metatile_Edit_V._scene.tile.generate_pixmap(ts1, ts2, pv, self.palette_v, self.collision)


    def toggle_grid(self):
        global Tile1_Select_V, Tile2_Select_V
        global Metatile_Edit_V, Tileset_Select_V
        for grid in [Tile1_Select_V._scene.tile_grid,
                     Tile2_Select_V._scene.tile_grid,
                     Metatile_Edit_V._scene.tile_grid,
                     Tileset_Select_V._scene.tile_grid,
                    ]:
            grid.setVisible(not grid.isVisible())

    def toggle_collision(self):
        global Chunk_Toolbar, Tile1_Select_V, Tile2_Select_V, Metatile_Edit_V
        self.collision = not self.collision
        ts1 = Chunk_Toolbar.tileset1
        ts2 = Chunk_Toolbar.tileset2
        pv = Chunk_Toolbar.palette_v
        for tile in Tile1_Select_V._scene.tiles:
            tile.generate_pixmap(ts1, ts2, pv, self.palette_v, self.collision)
        for tile in Tile2_Select_V._scene.tiles:
            tile.generate_pixmap(ts1, ts2, pv, self.palette_v, self.collision)
        Metatile_Edit_V._scene.tile.generate_pixmap(ts1, ts2, pv, self.palette_v, self.collision)

class Toolbar(QVBoxLayout):
    def __init__(self, parent):
        super().__init__()
        self._main = parent

        options = QHBoxLayout()
        grid_views = QHBoxLayout()
        chunk_grid = QPushButton("Chunk Grid")
        chunk_grid.clicked.connect(self.toggle_grid)
        grid_views.addWidget(chunk_grid)
        chunk_grid = QPushButton("Chunk Collision")
        chunk_grid.clicked.connect(self.toggle_collision)
        grid_views.addWidget(chunk_grid)
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

        self.addLayout(info)

        self.tileset1 = 0
        self.tileset2 = 0
        self.palette_v = 0

        self.collision = False

    def palette_changed(self, value):
        if value == self.palette_v:
            return

        global Chunk_Select_V, Chunk_Edit_V
        global Tile1_Select_V, Tile2_Select_V, Metatile_Edit_V
        global Tile_Toolbar
        self.palette_v = value
        for chunk in Chunk_Select_V._scene.chunks:
            chunk.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, self.collision)
        for metatile in Tile1_Select_V._scene.tiles:
            metatile.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
        Chunk_Edit_V._scene.chunk.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, self.collision)
        for metatile in Tile2_Select_V._scene.tiles:
            metatile.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
        Metatile_Edit_V._scene.tile.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)

    def tileset_changed(self, value):
        if value == self.tileset1:
            return

        global Chunk_Select_V, Chunk_Edit_V
        global Tile1_Select_V, Tile2_Select_V, Metatile_Edit_V
        global Tile_Toolbar
        self.tileset1 = value
        for chunk in Chunk_Select_V._scene.chunks:
            chunk.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, self.collision)
        for metatile in Tile1_Select_V._scene.tiles:
            metatile.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
        Chunk_Edit_V._scene.chunk.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, self.collision)
        for metatile in Tile2_Select_V._scene.tiles:
            metatile.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
        Metatile_Edit_V._scene.tile.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)


    def tileset_2_changed(self, value):
        if value == self.tileset2:
            return

        global Chunk_Select_V, Chunk_Edit_V
        global Tile1_Select_V, Tile2_Select_V, Metatile_Edit_V
        global Tile_Toolbar
        self.tileset2 = value
        for chunk in Chunk_Select_V._scene.chunks:
            chunk.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, self.collision)
        for metatile in Tile1_Select_V._scene.tiles:
            metatile.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
        Chunk_Edit_V._scene.chunk.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, self.collision)
        for metatile in Tile2_Select_V._scene.tiles:
            metatile.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)
        Metatile_Edit_V._scene.tile.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, Tile_Toolbar.palette_v, Tile_Toolbar.collision)


    def toggle_grid(self):
        global Chunk_Select_V, Chunk_Edit_V
        chunk_grid = Chunk_Select_V._scene.chunk_grid
        chunk_grid.setVisible(not chunk_grid.isVisible())
        chunk_grid = Chunk_Edit_V._scene.chunk_grid
        chunk_grid.setVisible(not chunk_grid.isVisible())

    def toggle_collision(self):
        global Chunk_Select_V, Chunk_Edit_V
        self.collision = not self.collision
        for chunk in Chunk_Select_V._scene.chunks:
            chunk.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, self.collision)
        Chunk_Edit_V._scene.chunk.generate_pixmap(self.tileset1, self.tileset2, self.palette_v, self.collision)

from MapEditor import NESPaletteSelector
from MapEditor import PaletteEditor
from MapEditor import ThemeWindow

class CE_Window(QMainWindow):
    def __init__(self, inherit:MapInfo=None):
        super().__init__()

        global Map_Stuff
        if inherit:
            Map_Stuff = inherit

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



Chunk_Select_V : CHUNK_Viewer = None
Chunk_Toolbar : Toolbar = None
Chunk_Edit_V : Single_CHUNK_Viewer = None

Tile1_Select_V : METATILE_Viewer = None
Tile2_Select_V : METATILE_Viewer = None
Metatile_Edit_V : Single_METATILE_Viewer = None
Tile_Toolbar : MToolbar = None

Tileset_Select_V : TILESET_Viewer = None

from MapEditor import Palette_Editor
from MapEditor import Theme_Window

class ActualWindow(QWidget):
    def __init__(self):
        super().__init__()
        global Chunk_Select_V
        global Chunk_Toolbar
        global Chunk_Edit_V

        global Tile1_Select_V
        global Tile2_Select_V
        global Metatile_Edit_V
        global Tile_Toolbar

        global Tileset_Select_V

        vbox = QVBoxLayout()
        Chunk_Toolbar = Toolbar(self)
        vbox.addLayout(Chunk_Toolbar)
        Chunk_Select_V = CHUNK_Viewer(self)
        hbox = QHBoxLayout()
        hbox.addWidget(Chunk_Select_V, stretch=1)
        Chunk_Edit_V = Single_CHUNK_Viewer(self)
        hbox.addWidget(Chunk_Edit_V, stretch=1)
        vbox.addLayout(hbox)


        hboxT = QHBoxLayout()
        vboxT = QVBoxLayout()
        Tile1_Select_V = METATILE_Viewer(self)
        Tile2_Select_V = METATILE_Viewer(self)
        sbox = QVBoxLayout()
        Tile_Toolbar = MToolbar(self)
        sbox.addLayout(Tile_Toolbar)
        vboxT.addWidget(Tile1_Select_V, stretch=1)
        for tile in Tile1_Select_V._scene.tiles:
            tile.which = False
        vboxT.addWidget(Tile2_Select_V, stretch=1)
        for tile in Tile2_Select_V._scene.tiles:
            tile.which = True
        hboxT.addLayout(vboxT)
        Metatile_Edit_V = Single_METATILE_Viewer(self)
        hboxT.addWidget(Metatile_Edit_V, stretch=1)
        sbox.addLayout(hboxT)

        Tileset_Select_V = TILESET_Viewer(self)
        hboxT.addWidget(Tileset_Select_V)

        hbox = QHBoxLayout()
        hbox.addLayout(vbox)
        hbox.addLayout(sbox)

        self.setLayout(hbox)

def recieve_loads(mtp, palette_d):
    global map_tile_properties
    map_tile_properties = mtp

    from MapEditor import load_palette_from_binary, convert_palettes_to_rgb
    load_palette_from_binary(palette_d)
    convert_palettes_to_rgb()

def get_mtp():
    global map_tile_properties
    return map_tile_properties


def set_chunki(i):
    global Chunk_Select_V
    if Chunk_Select_V == None:
        return
    x = i % 8
    y = i // 8
    Chunk_Select_V.current_position = (x, y)
    Chunk_Select_V.update_selection()

def get_chunki():
    global Chunk_Select_V
    if Chunk_Select_V == None:
        return
    x,y = Chunk_Select_V.current_position
    return x + (y * 8)

def set_use_tileset_override(u2=False):
    global use_tileset_override
    use_tileset_override = u2
    global ts1_override, ts2_override, palette_override
    set_overrides(ts1_override, ts2_override, palette_override)


def set_overrides(ts1, ts2, palette):
    global ts1_override, ts2_override, palette_override
    ts1_override, ts2_override, palette_override = (ts1, ts2, palette)

    global Chunk_Toolbar, use_tileset_override
    Chunk_Toolbar.palette.valueBox.setValue(palette_override)
    Chunk_Toolbar.palette.valueBox.setDisabled(True)
    if use_tileset_override:
        Chunk_Toolbar.tileset.valueBox.setValue(ts2_override)
        Chunk_Toolbar.tileset.valueBox.setDisabled(True)
        Chunk_Toolbar.tileset_2.valueBox.setValue(ts1_override)
        Chunk_Toolbar.tileset_2.valueBox.setDisabled(True)
    else:
        Chunk_Toolbar.tileset.valueBox.setValue(ts1_override)
        Chunk_Toolbar.tileset.valueBox.setDisabled(True)
        Chunk_Toolbar.tileset_2.valueBox.setValue(ts2_override)
        Chunk_Toolbar.tileset_2.valueBox.setDisabled(True)



chunk_app = None
if __name__ == "__main__":
    chunk_app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont("earthbound-beginnings.ttf")

    template = QPixmap.fromImage(ImageQt(Image.new("RGBA", (1,1))))
    window = CE_Window()
    window.show()
    sys.exit(chunk_app.exec())