from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys, os, yaml
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

i = 0
while i < len(sprite_palette):
    color = 0
    while color < len(sprite_palette[i]):
        if color == 0:
            color += 1
            continue
        id = sprite_palette[i][color]
        id = NES_PALETTE[id*3:(id+1)*3]
        sprite_palette[i][color] = (id[0], id[1], id[2])
        color += 1
    i += 1

table_mix = None
table_0 = None
table_1 = None

class Painter(QWidget):
    def __init__(self, parent=None, id=-1):
        super(Painter, self).__init__(parent)
        self.id = id

    def paintEvent(self, event):
        image = [table_0, table_1][self.id]
        if image == None:
            return
        painter = QPainter(self)
        pixmap = QPixmap.fromImage(ImageQt(image))
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

class SpritePainter(QWidget):
    def __init__(self):
        super(SpritePainter, self).__init__(None)
        self.fps = 10
        self.frame = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.timer.start(round(1000 / self.fps))

    def next_frame(self):
        self.frame += 1
        global loaded_definitions
        if self.frame >= len(loaded_definitions):
            self.frame = 0
        self.timer.start(round(1000 / self.fps))
        self.update()

    def paintEvent(self, event):
        global table_mix
        global loaded_definitions

        if len(loaded_definitions) == 0:
            return
        if table_mix == None:
            return

        painter = QPainter(self)
        images = []
        for y in range(table_mix.size[1] // 8):
            for x in range(table_mix.size[0] // 8):
                space = (x*8, y*8, (x+1)*8, (y+1)*8)
                image = table_mix.crop(space)
                images.append(image)

        defis = []
        for defi in loaded_definitions:
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


class Window(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("MOTHER Animation Creator")

        # Button with a text and parent widget
        table_0_h = QHBoxLayout()
        centerBtn = QPushButton(text="Load Table 0", parent=self)
        centerBtn.clicked.connect(lambda: self.load_table(0))
        centerBtn.setFixedSize(100, 64)
        table_0_h.addWidget(centerBtn)
        table_0_h.addWidget(Painter(None, 0))

        table_1_h = QHBoxLayout()
        centerBtn2 = QPushButton(text="Load Table 1", parent=self)
        centerBtn2.clicked.connect(lambda: self.load_table(1))
        centerBtn2.setFixedSize(100, 64)
        table_1_h.addWidget(centerBtn2)
        table_1_h.addWidget(Painter(None, 1))

        self.sprites : SpritePainter = SpritePainter()
        spritedef_h = QHBoxLayout()
        centerBtn4 = QPushButton(text="Load Spritedef", parent=self)
        centerBtn4.clicked.connect(self.load_spritedef)
        centerBtn4.setFixedSize(100, 64)
        spritedef_h.addWidget(centerBtn4)
        spritedef_h.addWidget(self.sprites)

        self.definition_list = Example()

        layout = QVBoxLayout()
        layout.addLayout(table_0_h)
        layout.addLayout(table_1_h)
        layout.addLayout(spritedef_h)
        layout.addWidget(self.definition_list)
        self.setLayout(layout)

    def load_spritedef(self):
        file_dialog = QFileDialog()
        file_path = file_dialog.getOpenFileNames(self, "Select File", "", "Definition Files (*.yaml)")[0]
        if not file_path:
            return

        global loaded_definitions
        for path in file_path:
            loaded_definitions.append(DefinitionEntry(path))
        self.definition_list.update()
        global load_operation
        load_operation = 1

    def create_mixtable(self):
        global table_0
        global table_1
        if not table_0:
            return
        elif not table_1:
            return

        global table_mix
        table_mix = Image.new("RGBA", (0x80, 0x80))
        table_mix.paste(table_0, (0*8, 0*8, 16*8, 8*8))
        table_mix.paste(table_1, (0*8, 8*8, 16*8, 16*8))

    def load_table(self, id):
        global table_0
        global table_1
        file_dialog = QFileDialog()
        file_path = file_dialog.getOpenFileName(self, "Select File", "", "Png Files (*.png)")[0]
        if not file_path:
            return

        image = Image.open(file_path, 'r')
        image = image.convert("RGBA")
        if id == 0:
            table_0 = image
        elif id == 1:
            table_1 = image
        self.create_mixtable()

class DefinitionEntry(QListWidgetItem):
    def __init__(self, file):
        super().__init__()
        self.filepath = file
        self.definition_data = self.get_def_data(file)

    def get_def_data(self, path):
        return yaml.safe_load(open(path, "r"))

loaded_definitions : list[DefinitionEntry] = []
load_operation = 0

class Example(QWidget):

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            if self.listWidget.selectedItems():
                item = self.listWidget.currentItem()
                row = self.listWidget.row(item)
                self.listWidget.takeItem(row)
                self.do_row_move()
        else:
            super().keyPressEvent(event)


    def add_item(self, fajl):
        item = QListWidgetItem()
        item.setTextAlignment(Qt.AlignmentFlag.AlignBottom)
        item.setText(fajl)
        return item

    def __init__(self):
        super().__init__()
        myself = QHBoxLayout(self)

        #make list
        self.listWidget = QListWidget()
        self.listWidget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.listWidget.setMovement(QListView.Movement.Snap)
        self.listWidget.model().rowsMoved.connect(self.do_row_move)
        #self.listWidget.itemSelectionChanged.connect(self.on_selection_change)
        myself.addWidget(self.listWidget)

        actual_vbox = QVBoxLayout(self)

        palettes = QHBoxLayout()
        palettes_label = QLabel("Palettes: ")
        palettes.addWidget(palettes_label)
        self.def_palette_1 = QSpinBox()
        self.def_palette_1.setMaximum(0b11)
        self.def_palette_1.setMinimum(0)
        palettes.addWidget(self.def_palette_1)
        self.def_palette_2 = QSpinBox()
        self.def_palette_2.setMaximum(0b11)
        self.def_palette_2.setMinimum(0)
        palettes.addWidget(self.def_palette_2)
        actual_vbox.addLayout(palettes)
        myself.addLayout(actual_vbox)

    def on_selection_change(self):
        global loaded_definitions
        item = self.listWidget.currentItem()
        definition = [file.definition_data for file in loaded_definitions if file.filepath == item.text()]
        if len(definition) > 0:
            definition = definition[0]

        self.def_palette_1.setValue(definition[0]["p1"])
        self.def_palette_2.setValue(definition[0]["p2"])

    def paintEvent(self, event):
        self.do_update()

    def do_row_move(self):
        global load_operation
        load_operation = -1
        self.do_update()

    def do_update(self):
        global loaded_definitions
        global load_operation

        if len(loaded_definitions) == 0:
            return

        files = []
        for i in range(self.listWidget.count()):
            files.append(self.listWidget.item(i).text())

        self.listWidget.clear()
        if load_operation == -1:
            loaded_definitions = [DefinitionEntry(file) for file in files]

        load_operation = 0

        for foo in loaded_definitions:
            self.listWidget.addItem(self.add_item(foo.filepath))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())