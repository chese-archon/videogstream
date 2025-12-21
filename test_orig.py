import sys
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow

from window_orig import MainWindow
#from window_cam_my import MainWindowCam
from window_cam import MainWindowCam

app = QApplication(sys.argv)

#w = QMainWindow()
w = MainWindowCam() #w = MainWindow()


w.setWindowTitle("Плеер")
w.show()

app.exec()
# protocol rtp, rtsp, quic

# gst-launch-1.0 -e udpsrc port=5000 ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! tee name=t ! queue! fpsdisplaysink t. ! queue ! nvh264enc ! matroskamux | filesink location=test_rtp.mp4
# ПРЕДУПРЕЖДЕНИЕ: ошибочный конвейер: элемент «avdec_h264» не найден
# filesink: команда не найдена
