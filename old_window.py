# import sys
# from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QComboBox
# from PyQt6.QtCore import Qt, QTimer
# from PyQt6.QtGui import QIcon

# import gi
# gi.require_version('Gst', '1.0')
# gi.require_version('GstVideo', '1.0')
# from gi.repository import Gst, GObject, GstVideo

# Gst.init(None)


import os
import sys

# Импортируем PyQt
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QComboBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6 import QtCore

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GObject, GstVideo

Gst.init(None)

def get_window_handle(widget):
    #int(handle)
    if widget.windowHandle() is None:
        widget.winId()
        
    handle = widget.windowHandle().winId()
    return int(handle)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        layout_main = QVBoxLayout()
        self.central_widget.setLayout(layout_main)

        self.screen_wgt = QLabel(self)
        self.screen_wgt.setStyleSheet("QLabel { background-color: black; color: white }")
        self.screen_wgt.setAlignment(Qt.AlignmentFlag.AlignCenter)# text to center
        #font size
        fnt = self.screen_wgt.font()
        fnt.setPointSizeF(72)
        self.screen_wgt.setFont(fnt)
        layout_main.addWidget(self.screen_wgt) # apply all


        #procrutka
        self.progress = QSlider(Qt.Orientation.Horizontal, self)
        layout_main.addWidget(self.progress)

        self.progress.valueChanged.connect(self.on_progress_changed)
        self.progress.sliderMoved.connect(self.on_progress_moved)
        
        #create btns
        layou_ctrl = QHBoxLayout()
        layout_main.addLayout(layou_ctrl)

        # C:\Users\Maibenben\Downloads\piptures\images\PlayVideo.png
        self.btn_play = QPushButton("", self)
        #self.btn_pause = QPushButton("Pause", self)
        #self.btn_stop = QPushButton("Stop", self)
        self.btn_pause = QPushButton("", self)
        self.btn_stop = QPushButton("", self)
        #image for icons
        self.btn_play.setIcon(QIcon("PlayVideo.png"))
        self.btn_pause.setIcon(QIcon("Pause.png"))
        self.btn_stop.setIcon(QIcon("Stop.png"))

        layou_ctrl.addWidget(self.btn_play)
        layou_ctrl.addWidget(self.btn_pause)
        layou_ctrl.addWidget(self.btn_stop)

        layou_ctrl.addStretch(1)# btns to left

        self.speed = QComboBox(self)
        self.speed.addItems(("0.5", "1.0", "1.5", "2.0"))
        self.speed.setCurrentIndex(1)
        self.speed.currentIndexChanged.connect(self.on_speed_changed)
        layou_ctrl.addWidget(self.speed)

        #zvuk
        self.sound = QSlider(Qt.Orientation.Horizontal, self)
        layou_ctrl.addWidget(self.sound)
        
        self.current_time = 0
        self.current_speed = 1

        #self.sound.valueChanged.connect(self.on_progress_changed)
        
        self.pipeline = Gst.parse_launch("videotestsrc ! videoconvert ! xvimagesink name=sink")# self.pipeline = Gst.parse_launch("videotestsrc ! videoconvert ! glimagesink name=sink")
        #self.pipeline = Gst.parse_launch(" filesrc location=\"/home/anna/Загрузки/cat.mp4\" ! decodebin ! videoconvert ! glimagesink name=sink")
        #self.pipeline.set_state(Gst.State.PLAYING)
        wnd = get_window_handle(self.screen_wgt)
        
        
        
        self.videosink = self.pipeline.get_by_name("sink")
        self.videosink.set_window_handle(wnd)
        
        #self.overlay = self.videosink.do_cast(GstVideo)


    def showEvent(self, event):
        super().showEvent(event)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.pipeline.get_state(1e9)
        (ok, duration) = self.pipeline.query_duration(Gst.Format.TIME)
        if (ok):
            self.progress.setMaximum(int(duration * 1e-9))
        self.timer = QTimer()
        self.timer.timeout.connect(self.timerEvent)
        self.timer.start(100)
        
    def on_progress_moved(self, value):
        #pass
        print("on_progress_moved", value)
        self.pipeline.seek(self.current_speed, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, Gst.SeekType.SET, value * 1e9, Gst.SeekType.END, 0)
    
    def on_progress_changed(self, value):
        pass
        # print("on_progress_changed", value)
        # self.screen_wgt.setText(str(value))
        
    def timerEvent(self):
        (ok, current) = self.pipeline.query_position(Gst.Format.TIME)
        if(ok):
            self.current_time = current
            self.progress.setValue(int(current * 1e-9))
            #self.progress.setValue(self.current_time)
            
    def on_speed_changed(self, value):
        if value == 0:
            self.current_speed = 0.5
        elif value == 1:
            self.current_speed = 1.0
        elif value == 2:
            self.current_speed = 1.5
        else:
            self.current_speed = 2.0
        self.pipeline.seek(self.current_speed, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, Gst.SeekType.SET, self.current_time, Gst.SeekType.END, 0)
