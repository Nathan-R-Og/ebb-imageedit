from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import sys, re

class TextInfo(object):
    def in_asm(self, file):
        lines = open(file, "r").readlines()
        self.entries = {}


        new_entry = []
        key = ""
        for line in lines:
            if line.endswith(":\n"):

                if key != "":
                    self.entries[key] = new_entry

                new_entry = []
                key = line.split(":")[0]
                continue

            line = line.strip()
            if line.startswith(".byte "):
                line = line.split(" ", 1)[1]
            if line.startswith("kanafix "):
                line = line.split(" ", 1)[1]
            if line.endswith(",newLine"):
                line = line[:-len(",newLine")]
            if line == "stopText":
                continue

            pattern = r'"([^"]*)"|\'([^\']*)\'|([^"\']+)'
            parts = re.findall(pattern, line)
            reconstructed_modified = []
            for match_group in parts:
                if match_group[0]:  # Double-quoted content
                    reconstructed_modified.append(match_group[0])
                elif match_group[1]: # Single-quoted content
                    reconstructed_modified.append(match_group[1])
                else: # Non-quoted content
                    for x in match_group[2].split(","):
                        if x == "":
                            continue
                        reconstructed_modified.append(f"{{{x}}}")

            line = "".join(reconstructed_modified)


            new_entry.append(line)

        if new_entry != [] and key != "":
            self.entries[key] = new_entry


    def out_asm(self):
        lines = []
        for entry in list(self.entries.keys()):
            outlines = [f"{entry}:\n"]
            line_i = 0
            for line in self.entries[entry]:

                pattern = r'{([^{}]*)}|([^{}]+)'
                parts = re.findall(pattern, line)
                reconstructed_modified = []
                has_text = False
                for match_group in parts:
                    if match_group[0]:  # brackets
                        reconstructed_modified.append(f"{match_group[0]}")
                    elif match_group[1]: # rest
                        has_text = True
                        if match_group[1].find("\"") != -1:
                            reconstructed_modified.append(f"'{match_group[1]}'")
                        else:
                            reconstructed_modified.append(f'"{match_group[1]}"')

                if line_i < len(self.entries[entry]) - 1:
                    if has_text:
                        reconstructed_modified.append("newLine")
                else:
                    reconstructed_modified.append("stopText")

                csv = ",".join(reconstructed_modified)
                line = ".byte "+csv+"\n"


                line_i += 1
                outlines.append(line)
            lines += outlines
            lines.append("\n")

        return lines

Text_Stuff : TextInfo = None

class TextEdit(QTextEdit):
    def __init__(self):
        super().__init__()

        self.diamondize = False
        self.colorize = True
        self.doublize = False
        self.dMargin = False

        font = QFont("monospace")
        font.setFixedPitch(True)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.textChanged.connect(self.on_change)

        self.setAcceptRichText(True)

        self.entry = []
        self.entry_key = ""
        self.temp_html = ""

    def save(self):
        global Text_Stuff
        if Text_Stuff == None:
            return
        if self.entry_key == '':
            return
        Text_Stuff.entries[self.entry_key] = self.entry

    def load_entry(self, entry):
        self.entry = entry
        self.temp_html = self.parse_entry(entry)
        self.setHtml(self.temp_html)

        s = Editor.toPlainText()
        if Editor.diamondize:
            if s.find("*") != -1:
                Editor.setHtml(Editor.temp_html.replace("*", "◆"))
        if not Editor.diamondize:
            if s.find("◆") != -1:
                Editor.setHtml(Editor.temp_html.replace("◆", "*"))

    def reload_entry(self):
        self.load_entry(self.entry)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.insertHtml("<br>")
        elif event.key() == Qt.Key.Key_Asterisk:
            if self.diamondize:
                self.insertHtml("◆")
            else:
                self.insertHtml("*")
        else:
            super().keyPressEvent(event)


    def parse_entry(self, entry):
        n = []
        for i in range(len(entry)):
            line = entry[i]

            pattern = r'{([^{}]*)}|([^{}]+)'
            parts = re.findall(pattern, line)
            reconstructed_modified = []
            for match_group in parts:
                if match_group[0]:  # brackets
                    context = "{"+match_group[0]+"}"
                    if self.colorize:
                        context = f'<span style="color: red;">{context}</span>'
                    reconstructed_modified.append(context)
                else: # Non-quoted content
                    reconstructed_modified.append(match_group[1])

            line = "".join(reconstructed_modified)

            n.append(line)

        styles = ["white-space: pre"]

        if self.doublize:
            styles.append("line-height: 2")

        styles = ";\n".join(styles)+";\n"

        output = f"<p style=\"{styles}\">"+"<br>".join(n)+"</p>"
        return output

    def on_change(self):
        entry_copy = self.toPlainText().replace("◆", "*").split("\n")

        errs = False

        for i in range(len(entry_copy)):
            line = entry_copy[i]
            if line.find("}") != -1 or line.find("{") != -1:
                openbraces = 0

                for char in line:
                    if char == '{':
                        openbraces += 1
                    elif char == '}':
                        openbraces -= 1

                if openbraces != 0:
                    print("ERR")
                    errs = True
                    break
            entry_copy[i] = line


        self.temp_html = self.parse_entry(entry_copy)

        if not errs:
            self.entry = entry_copy
            self.save()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self.viewport())
        pen = QPen(QColor(255, 0, 0, 255))
        pen.setWidth(1)
        painter.setPen(pen)

        font_metrics = QFontMetrics(self.currentFont())
        char_width = font_metrics.horizontalAdvance("X")
        left_margin = self.document().documentMargin()
        if self.dMargin:
            x_pos_d = int(left_margin + (22 * char_width))
            painter.drawLine(x_pos_d, 0, x_pos_d, self.viewport().height())

        painter.end()

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


class Toolbar(QVBoxLayout):
    def __init__(self, parent):
        super().__init__()
        self._main = parent

        options = QVBoxLayout()
        mode = QHBoxLayout()
        mode_label = QLabel("Dialogue: ")
        mode.addWidget(mode_label)
        self.set_mode_dropdown = QComboBox()
        self.set_mode_dropdown.currentIndexChanged.connect(self.set_file)
        mode.addWidget(self.set_mode_dropdown)
        options.addLayout(mode)
        actual_options = QHBoxLayout()
        diamondize = QPushButton("Diamondize")
        diamondize.clicked.connect(self.toggle_diamondization)
        actual_options.addWidget(diamondize)
        colorize = QPushButton("Colorize")
        colorize.clicked.connect(self.toggle_colorization)
        actual_options.addWidget(colorize)
        doublize = QPushButton("Doublize")
        doublize.clicked.connect(self.toggle_doublization)
        actual_options.addWidget(doublize)
        margins = QPushButton("Margins")
        margins.clicked.connect(self.toggle_margins)
        actual_options.addWidget(margins)
        options.addLayout(actual_options)

        self.addLayout(options)
        self.index = -1

    def toggle_diamondization(self):
        global Editor
        if Editor == None:
            return

        Editor.diamondize = not Editor.diamondize

        s = Editor.toPlainText()
        if Editor.diamondize:
            if s.find("*") != -1:
                Editor.setHtml(Editor.temp_html.replace("*", "◆"))
        if not Editor.diamondize:
            if s.find("◆") != -1:
                Editor.setHtml(Editor.temp_html.replace("◆", "*"))

    def toggle_bracketization(self):
        global Editor
        if Editor == None:
            return

        Editor.bracketize = not Editor.bracketize
        Editor.reload_entry()

    def toggle_colorization(self):
        global Editor
        if Editor == None:
            return

        Editor.colorize = not Editor.colorize
        Editor.reload_entry()

    def toggle_doublization(self):
        global Editor
        if Editor == None:
            return

        Editor.doublize = not Editor.doublize
        Editor.reload_entry()

    def toggle_margins(self):
        global Editor
        if Editor == None:
            return

        Editor.dMargin = not Editor.dMargin
        Editor.update()

    def set_file(self, index):
        global Text_Stuff, Editor
        if Text_Stuff == None:
            return
        if Editor == None:
            return
        if index == self.index:
            return


        key = list(Text_Stuff.entries.keys())[index]
        Editor.entry_key = key
        Editor.load_entry(Text_Stuff.entries[key])
        self.index = index

    def load_files(self):
        global Text_Stuff, Editor
        if Text_Stuff == None:
            return
        self.set_mode_dropdown.addItems(list(Text_Stuff.entries.keys()))
        self.set_file(0)


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
        self.setWindowTitle("MOTHER Text Editor")

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

        self.setCentralWidget(ActualWindow())

    def open_file(self):
        msgBox = QMessageBox()

        file_dialog = QFileDialog()
        file_path = file_dialog.getOpenFileName(self, "Select Text", "", "Asm Files (*.asm)")[0]

        global Text_Stuff, Text_Toolbar
        if Text_Stuff == None:
            Text_Stuff = TextInfo()
        if file_path.endswith(".asm"):
            Text_Stuff.in_asm(file_path)

        self.write_file.setDisabled(False)

        Text_Toolbar.load_files()

        msgBox.setWindowTitle("INFO")
        msgBox.setText("Files Loaded.")
        msgBox.exec()


    def save_file(self):
        file_dialog = QFileDialog()
        file_path = file_dialog.getSaveFileName(self, "Select Map", "", "Asm Files (*.asm)")[0]

        #global Map_Stuff
        global Text_Stuff
        if file_path.endswith(".bin"):
            open(file_path, "wb").write(Text_Stuff.compile())
        elif file_path.endswith(".asm"):
            open(file_path, "w").writelines(Text_Stuff.out_asm())

        msgBox = QMessageBox()
        msgBox.setWindowTitle("INFO")
        msgBox.setText("Files Saved.")
        msgBox.exec()

    def change_theme(self):
        global Theme_Window
        if Theme_Window is None: # Prevent multiple instances if desired
            Theme_Window = ThemeWindow()
        Theme_Window.show()

Text_Toolbar : Toolbar = None

Editor : TextEdit = None

Theme_Window : ThemeWindow = None

class ActualWindow(QWidget):
    def __init__(self):
        super().__init__()

        global Text_Toolbar, Editor

        vbox = QVBoxLayout()
        Text_Toolbar = Toolbar(self)
        vbox.addLayout(Text_Toolbar)
        Editor = TextEdit()
        vbox.addWidget(Editor)
        self.setLayout(vbox)

app = None
if __name__ == "__main__":
    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont("earthbound-beginnings.ttf")

    window = Window()
    window.show()
    sys.exit(app.exec())