import os
import sys

from PyQt6.QtWidgets import QApplication, QMainWindow
from window_cam import MainWindow

#from window_cam_bahanov import MainWindowCam
#from window import MainWindow

app = QApplication(sys.argv)

#w = MainWindowCam() 

w = MainWindow()
w.setWindowTitle("Видеоплеер")
w.show()

app.exec()
