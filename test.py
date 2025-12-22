import sys
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow
from window import MainWindow

app = QApplication(sys.argv)
w = MainWindow()
w.setWindowTitle("Плеер")
w.show()

app.exec()