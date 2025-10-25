from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys
import numpy as np

from copy import deepcopy

from PIL import Image, ImageOps
from PIL.ImageQt import ImageQt
import yaml
import os
from glob import glob

def image_to_bits(image:Image):
    color_map = {
        (0,0,0,255): 0,
        (102,102,102,255): 1,
        (173,173,173,255): 2,
        (255,254,255,255): 3,
    }

    page_tiles = []
    for y in range(image.size[1]//8):
        for x in range(image.size[0]//8):
            rect = (x*8, y*8, (x+1)*8, (y+1)*8)
            newImage = np.array(image.crop(rect)).flatten()
            bits = bytearray()
            for i in range(len(newImage)//4):
                color = tuple(newImage[i*4:(i+1)*4])
                bits.append(color_map[color])
            page_tiles.append(bits)
    return page_tiles

def palette_image(data, palette, s=3):
    lookup_table = np.array(palette, dtype=np.uint8)
    colored_image = lookup_table[data]
    colored_image.shape = (8,8,s)
    return colored_image

texture_pages = []
for i in range(32):
    texture_pages.append(image_to_bits(Image.open(f"extract/battle/graphics/{i}.png")))

extra_page = image_to_bits(Image.open(f"extract/battle/graphics/extra.png"))

enemy_tile_pointers = open("extract/battle/enemy_tiles/pointers.txt", "r").readlines()

#sort extra tiles by file number
fuck = glob("extract/battle/enemy_tiles/extra/*.txt")
balls = {}
ar = []
for file in fuck:
    key = int(os.path.basename(file).replace(".txt", ""), 16)
    balls[key] = file
    ar.append(key)
ar.sort()
fuck = [balls[key] for key in ar]
enemy_extra_tiles = [open(file, "r").readlines() for file in fuck]

battle_positionings_r = open("split/battle/positionings.bin", "rb").read()
battle_positionings = []
i = 0
while i < len(battle_positionings_r):
    battle_positionings.append([byte for byte in battle_positionings_r[i:i+4]])
    i += 4

#sort palettes by file number
fuck = glob("split/battle/palettes/*.bin")
balls = {}
ar = []
for file in fuck:
    key = int(file.split("\\")[-1].split(".bin")[0])
    balls[key] = file
    ar.append(key)
ar.sort()
fuck = [balls[key] for key in ar]
enemy_palettes = [open(file, "rb").read() for file in fuck]

NES_PALETTE = open("nes.pal", "rb").read()

def convert_palettes_to_rgb():
    global enemy_palettes
    global NES_PALETTE
    p = 0
    while p < len(enemy_palettes):
        palette = enemy_palettes[p]
        s = []
        i = 0
        while i < len(palette):
            id = palette[i]
            id2 = NES_PALETTE[id*3:(id+1)*3]
            s.append((id2[0], id2[1], id2[2]))
            i += 1
        x = []
        i = 0
        while i < len(s):
            x.append(s[i:i+4])
            i += 4
        enemy_palettes[p] = x
        p += 1
convert_palettes_to_rgb()

#oam alpha
for i in range(len(enemy_palettes)):
    for x in range(4):
        enemy_palettes[i][4+x][0] = (0,0,0,0)
        for s in range(3):
            z = enemy_palettes[i][4+x][s+1]
            enemy_palettes[i][4+x][s+1] = (z[0],z[1],z[2],255)

class BattleInfo(object):
    def __init__(self, stream):
        #TODO: THIS REQUIRES LINKING!!!
        data_loaded = yaml.safe_load(stream)

        self.enemies = data_loaded["enemies"]
        self.position = data_loaded["position"]
        self.encounter = data_loaded["encounter"]
        self.palette = data_loaded["palette"]
        self.music = data_loaded["music"]
    def save(self, stream):
        dict = {
            "enemies": self.enemies,
            "position": self.position,
            "encounter": self.encounter,
            "palette": self.palette,
            "music": self.music,
        }
        stream.write(yaml.dump(dict))


class EnemyInfo(object):
    def __init__(self, stream):
        #TODO: THIS REQUIRES LINKING!!!
        data_loaded = yaml.safe_load(stream)

        self.unk = data_loaded["unk"]
        self.init_status = data_loaded["init_status"]
        self.flags = data_loaded["flags"]
        self.subpal = data_loaded["subpal"]
        self.gtile = data_loaded["gtile"]
        self.gfx = data_loaded["gfx"]
        self.final_action = data_loaded["final_action"]
        self.altitude = data_loaded["altitude"]
        self.message_defeat = data_loaded["message_defeat"]
        self.unkParam = data_loaded["unkParam"]
        self.graphic_page = data_loaded["graphic_page"]

        self.health = data_loaded["health"]
        self.pp = data_loaded["pp"]
        self.offense = data_loaded["offense"]
        self.defense = data_loaded["defense"]
        self.fight = data_loaded["fight"]
        self.speed = data_loaded["speed"]
        self.wisdom = data_loaded["wisdom"]
        self.strength = data_loaded["strength"]
        self.force = data_loaded["force"]
        self.exp = data_loaded["exp"]
        self.money = data_loaded["money"]
        self.item = data_loaded["item"]

        self.battle_actions = data_loaded["battle_actions"]
        self.name_pointer = data_loaded["name_pointer"]

template = None

#chunk graphicsitem
class EnemyGraphic(object):
    def __init__(self, enemy_stat, id, x, y):
        self.info : EnemyInfo = enemy_stat
        self.id = id
        global template
        self.pixmap : QGraphicsPixmapItem = QGraphicsPixmapItem(template)
        self.pixmap.setPos(x, y)
        self.generated = False
        self.tiles = yaml.safe_load(open("extract/"+enemy_tile_pointers[self.info.gtile].strip()+".yaml"))
        self.extra_tiles = []

    def generate_pixmap(self, battle_info: BattleInfo):
        page = self.info.graphic_page-32
        if page < 0:
            print("ERR")
            page = 0
        elif page > 32:
            print("ERR")
            page = 0

        palette_set = enemy_palettes[battle_info.palette]
        palette = palette_set[self.info.subpal]


        pixels = {}

        global texture_pages

        tile8_i = 0
        for tile in self.tiles["tiles"]:
            tile8 = deepcopy(texture_pages[page][tile])

            #paletteNum = Map_Stuff.palettes64[curTile["palette64"]][tile16_i]
            my_palette = palette

            new_tile = palette_image(tile8, my_palette)
            pixels[tile8_i] = new_tile
            new_tile = None
            tile8_i += 1

        #construct 8x8 of 8x8s
        p_array = []
        for i in range(tile8_i):
            p_array.append(pixels[i])

        s = []
        for i in range(self.tiles["height"]):
            x = p_array[i*self.tiles["width"]:(i+1)*self.tiles["width"]]
            s.append(np.hstack(x))
        newImage = Image.fromarray(np.vstack(s)).convert("RGBA")

        if self.info.gfx != 0:
            global extra_page
            count = int(enemy_extra_tiles[self.info.gfx][0])
            file = yaml.safe_load(open("extract/"+enemy_extra_tiles[self.info.gfx][1].strip()+'.yaml'))
            tiles = yaml.safe_load(open("extract/"+file[0]["tiles"]+'.yaml'))

            #battle sprites do NOT follow the single bit format.
            #i guess cuz the 4th pallete can also be technically used
            chosen_palettes = [
                palette_set[file[0]["p1"]+4],
                palette_set[file[0]["p2"]+4],
                palette_set[7],
                ]
            for tile in tiles:
                x,y = tile['posX'],tile['posY']

                tile_data = extra_page[tile["index"]]
                new_tile = palette_image(tile_data, palette_set[tile["palette"]+5], 4)

                s = Image.fromarray(new_tile).convert("RGBA")

                if bool(tile["flipX"]):
                    s = ImageOps.mirror(s)
                if bool(tile["flipY"]):
                    s = ImageOps.flip(s)

                z = QGraphicsPixmapItem()
                z.setPixmap(QPixmap.fromImage(ImageQt(s)))
                z.setPos(x-16, y-16)
                self.extra_tiles.append(z)




        self.pixmap.setPixmap(QPixmap.fromImage(ImageQt(newImage)))
        self.generated = True
        newImage = None

#scene manager
class Scene(QGraphicsScene):
    def __init__(self, xp, yp, w, h):
        super(Scene, self).__init__(xp, yp, w, h)
        self.chunks = []
        self.window : QGraphicsView = None

        self.setBackgroundBrush(QBrush(QColor('black')))

    def queue_update(self):
        if self.window == None:
            return

#scene viewer
class Viewer(QGraphicsView):
    def __init__(self, parent):
        super().__init__()
        self._main = parent
        sizer = (240, 64)
        self._scene = Scene(0, 0, sizer[0], sizer[1])
        self.setScene(self._scene)
        self.setSceneRect(QRectF(0, 0, sizer[0]/2, sizer[1]/2))
        self.setFixedSize(sizer[0], sizer[1])

        self._scene.window = self
        self._scene.queue_update()

        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setStyleSheet("border-width: 0px; border-style: solid")
        self.setStyleSheet("border: 0px")

    def paintEvent(self, event):
        super().paintEvent(event)
        self._scene.queue_update()
        self.update()

class ValueBox(QHBoxLayout):
    def __init__(self, text, *other):
        super().__init__()


        self.label = QLabel(text)
        self.widgets = []
        self.addWidget(self.label)
        for qwidget in other:
            if other.index(qwidget) == 0:
                self.valueBox = qwidget
            else:
                self.widgets.append(qwidget)

            if issubclass(type(qwidget), QBoxLayout): #handle recursiveness :D
                self.addLayout(qwidget)
            else:
                self.addWidget(qwidget)

class BattleTable(QVBoxLayout):
    def __init__(self, parent):
        super().__init__()
        self._main = parent

        global stat_files
        name_files = [os.path.basename(file).replace(".yaml", "") for file in stat_files]

        enemie_layout = QVBoxLayout()
        self.enemies_vb = []
        for i in range(4):
            enemy = QComboBox()
            will_be_called = QCheckBox()
            called = ValueBox("Will be called? ", will_be_called)
            letter = QComboBox()
            letter.addItems(["None", "A", "B", "C", "D"])
            vb = ValueBox(f"Enemy {i}: ", enemy, letter, called)
            enemy.addItems(["NONE"]+name_files)
            enemy.currentIndexChanged.connect(lambda index, s=i: self.enemy_changed(index, s))

            letter.currentIndexChanged.connect(lambda index, s=i: self.enemy_letter_changed(index, s))

            will_be_called.stateChanged.connect(lambda index, s=i: self.enemy_called_changed(index, s))

            enemie_layout.addLayout(vb)
            self.enemies_vb.append(vb)
        self.addLayout(enemie_layout)

        x = QSpinBox()
        self.bposition = ValueBox("Position: ", x)
        x.valueChanged.connect(self.position_changed)
        global battle_positionings
        x.setRange(0, len(battle_positionings)-1)
        x.setDisplayIntegerBase(16)
        self.addLayout(self.bposition)

        x = QSpinBox()
        self.bencounter = ValueBox("Encounter: ", x)
        x.valueChanged.connect(self.encounter_changed)
        self.addLayout(self.bencounter)

        x = QSpinBox()
        self.palette = ValueBox("Palette: ", x)
        x.valueChanged.connect(self.palette_changed)
        global enemy_palettes
        x.setRange(0, len(enemy_palettes)-1)
        x.setDisplayIntegerBase(16)
        self.addLayout(self.palette)

        x = QSpinBox()
        self.music = ValueBox("Music: ", x)
        x.valueChanged.connect(self.music_changed)
        self.addLayout(self.music)

        self.current_info : BattleInfo = None

        self.loading_info = False

    def load_info(self, info:BattleInfo):
        self.loading_info = True
        self.current_info = info

        global stat_files
        i = 0
        for enemy in info.enemies:
            dropdown : QComboBox = self.enemies_vb[i].valueBox
            if enemy["enemy"] == "NONE":
                dropdown.setCurrentIndex(0)
            else:
                dropdown.setCurrentIndex(stat_files.index("extract/"+enemy["enemy"]+".yaml")+1)

            letter : QComboBox = self.enemies_vb[i].widgets[0]
            letter.setCurrentIndex(enemy["label"])

            called : QCheckBox = self.enemies_vb[i].widgets[1].valueBox
            called.setChecked(enemy["called"])


            i += 1

        self.bposition.valueBox.setValue(info.position)
        self.bencounter.valueBox.setValue(info.encounter)
        self.palette.valueBox.setValue(info.palette)
        self.music.valueBox.setValue(info.music)
        self.loading_info = False

    def enemy_changed(self, value, enemy_i):
        if self.loading_info:
            return
        global stat_files
        blame_files = [file.replace(".yaml", "").replace("extract/", "") for file in stat_files]
        self.current_info.enemies[enemy_i]["enemy"] = (["NONE"]+blame_files)[value]
        self._main.update_graphic(self.current_info)

    def enemy_letter_changed(self, value, enemy_i):
        if self.loading_info:
            return
        self.current_info.enemies[enemy_i]["label"] = value

    def enemy_called_changed(self, boolean, enemy_i):
        if self.loading_info:
            return
        self.current_info.enemies[enemy_i]["called"] = boolean > 0

    def position_changed(self, value):
        if self.loading_info:
            return
        self.current_info.position = value
        self._main.update_graphic(self.current_info)

    def encounter_changed(self, value):
        if self.loading_info:
            return
        self.current_info.encounter = value

    def palette_changed(self, value):
        if self.loading_info:
            return
        self.current_info.palette = value
        self._main.update_graphic(self.current_info)

    def music_changed(self, value):
        if self.loading_info:
            return
        self.current_info.music = value

stat_files = glob("extract/battle/stats/*.yaml", recursive=True)
stat_files = [file.replace("\\", "/") for file in stat_files]

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MOTHER Battle Editor")

        toolbar = QToolBar("FileIO")
        self.addToolBar(toolbar)

        self.load_file = QAction("Load", self)
        self.load_file.triggered.connect(self.open_file)
        toolbar.addAction(self.load_file)

        self.write_file = QAction("Save", self)
        self.write_file.triggered.connect(self.save_file)
        self.write_file.setDisabled(True)
        toolbar.addAction(self.write_file)



        self.actual_window = QWidget()
        hbox = QHBoxLayout()
        self.actual_window.setLayout(hbox)

        b = QWidget()
        s = QVBoxLayout(b)
        global stat_files
        for file in stat_files:
            s.addWidget(QLabel(file))

        # 3. Create a QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidget(b)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


        hbox.addWidget(scroll_area)

        battle_side = QVBoxLayout()
        hbox.addLayout(battle_side)
        self.viewer = Viewer(self)
        battle_side.addWidget(self.viewer)
        battle_side.setAlignment(self.viewer, Qt.AlignmentFlag.AlignHCenter)
        self.battle_table = BattleTable(self)
        battle_side.addLayout(self.battle_table)

        self.setCentralWidget(self.actual_window)

    def open_file(self):
        file_dialog = QFileDialog()
        file_path = file_dialog.getOpenFileName(self, "Select File", "", "Yaml Files (*.yaml);;Binary Files (*.bin)")[0]
        if not file_path:
            return

        info = BattleInfo(open(file_path))
        self.battle_table.load_info(info)
        self.update_graphic(info)

        self.write_file.setDisabled(False)

        msgBox = QMessageBox()
        msgBox.setWindowTitle("INFO")
        msgBox.setText("File Loaded.")
        msgBox.exec()

    def update_graphic(self, info:BattleInfo):
        self.viewer._scene.clear()
        i = 0
        for enemy in info.enemies:
            if enemy["enemy"] == "NONE":
                i += 1
                continue
            x_pos = battle_positionings[info.position][i]*8
            stat = EnemyInfo(open("extract/"+enemy["enemy"]+".yaml"))
            new_object = EnemyGraphic(stat, i, 0, 0)
            new_object.pixmap.setPos(x_pos, new_object.tiles["ypos"]*8)
            self.viewer._scene.addItem(new_object.pixmap)
            new_object.generate_pixmap(info)

            for tile in new_object.extra_tiles:
                tile.setPos(x_pos+tile.x(), (new_object.tiles["ypos"]*8)+tile.y())
                self.viewer._scene.addItem(tile)


            i += 1
        self.viewer._scene.queue_update()

    def save_file(self):
        file_dialog = QFileDialog()
        file_path = file_dialog.getSaveFileName(self, "Select File", "", "Yaml Files (*.yaml);;Binary Files (*.bin)")[0]
        if not file_path:
            return

        self.battle_table.current_info.save(open(file_path, "w"))

        msgBox = QMessageBox()
        msgBox.setWindowTitle("INFO")
        msgBox.setText("File Saved.")
        msgBox.exec()

app = None
if __name__ == "__main__":
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont("earthbound-beginnings.ttf")

    template = QPixmap.fromImage(ImageQt(Image.new("RGBA", (1,1))))
    window = Window()
    window.show()
    sys.exit(app.exec())