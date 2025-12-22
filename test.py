import os
import sys

# # КРИТИЧЕСКИ ВАЖНО: настройки ДО импорта PyQt
# os.environ['QT_QPA_PLATFORM'] = 'xcb'
# os.environ['GDK_BACKEND'] = 'x11'
# os.environ['XDG_SESSION_TYPE'] = 'x11'

# # Отключаем Wayland
# os.environ.pop('WAYLAND_DISPLAY', None)

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
