import sys
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow

from window import MainWindow


app = QApplication(sys.argv)

#w = QMainWindow()
w = MainWindow()

w.setWindowTitle("jngbjgfgj")
w.show()

app.exec()