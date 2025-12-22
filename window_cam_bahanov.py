import sys
import time

import os
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['GDK_BACKEND'] = 'x11'
os.environ['XDG_SESSION_TYPE'] = 'x11'

from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QSpinBox, QLabel, QSlider, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6 import QtCore
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GObject, GstVideo, GLib
Gst.init(None)

def get_window_handle(widget):
    if widget.windowHandle() is None:
        widget.winId()

    handle = widget.windowHandle().winId()
    return int(handle)

class MainWindowCam(QMainWindow):
    def __init__(self):
        super().__init__()

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        layout_main = QVBoxLayout()
        self.central_widget.setLayout(layout_main)

        self.screen_wdgt = QLabel(self)
        self.screen_wdgt.setStyleSheet("QLabel { background-color: black; color: white; }")
        self.screen_wdgt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fnt = self.screen_wdgt.font()
        fnt.setPointSizeF(72)
        self.screen_wdgt.setFont(fnt)
        layout_main.addWidget(self.screen_wdgt)


        self.progress = QSlider(Qt.Orientation.Horizontal, self)
        layout_main.addWidget(self.progress)

        self.progress.valueChanged.connect(self.on_progress_changed)
        self.progress.sliderMoved.connect(self.on_progress_moved)

        layout_ctrl = QHBoxLayout()
        layout_main.addLayout(layout_ctrl)


        self.btn_play = QPushButton("P", self)
        self.btn_stop = QPushButton("S", self)
        self.btn_connect = QPushButton("Connect", self)
        self.sb_port = QSpinBox(self)
        self.sb_port.setMaximum(65535)
        self.sb_port.setMinimum(0)
        self.sb_port.setValue(5000)
        #self.btn_play.setIcon(QIcon("Play.svg"))
        self.btn_play.setIcon(QIcon("PlayVideo.png"))
        #self.btn_connect.setIcon(QIcon("Pause.svg"))
        self.btn_stop.setIcon(QIcon("Stop.png"))
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self.on_connect_clicked)
        self.btn_play.clicked.connect(self.on_play_clicked)
        self.btn_stop.clicked.connect(self.on_stop_clicked)


        layout_ctrl.addWidget(self.btn_play)
        layout_ctrl.addWidget(self.btn_stop)
        layout_ctrl.addWidget(self.btn_connect)
        layout_ctrl.addWidget(self.sb_port)
        layout_ctrl.addStretch(1)

        self.speed = QComboBox(self)
        self.speed.addItems(("0.5", "1.0", "1.5", "2.0"))
        self.speed.setCurrentIndex(1)
        self.speed.currentIndexChanged.connect(self.on_speed_changed)
        layout_ctrl.addWidget(self.speed)

        self.volume = QSlider(Qt.Orientation.Horizontal, self)
        self.volume.setMinimum(0)
        self.volume.setMaximum(100)
        self.volume.valueChanged.connect(self.on_volume_changed)
        layout_ctrl.addWidget(self.volume)

        self.current_time = 0
        self.current_speed = 1

        self.createPipeline()
        self.volume.setValue(50)

    def showEvent(self, event):
        super().showEvent(event)
        if(self.pipeline):
            (ok, duration) = self.pipeline.query_duration(Gst.Format.TIME)
            if(ok):
                self.progress.setMaximum(int(duration * 1e-9))
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.timerEvent)
        self.timer.start(100)
    
    def on_progress_changed(self, value):
        pass

    def on_progress_moved(self, value):
        print(f"{value}")
        self.pipeline.seek(self.current_speed, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, Gst.SeekType.SET, value * 1e9, Gst.SeekType.END, 0)

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

    def on_volume_changed(self, value):
        if self.pipeline:
            vol = self.pipeline.get_by_name("vol")
            if(vol):
                vol.set_property("volume", self.volume.value() / 100)

    def on_connect_clicked(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            state = self.pipeline.get_state(1e9)
            print(f'{state}')
            self.createPipeline()
            src = self.pipeline.get_by_name("src")
            src.set_property("port", self.sb_port.value())
            self.pipeline.set_state(Gst.State.PLAYING)
            state = self.pipeline.get_state(5e9)
            print(f'{state}')
    
    def createPipeline(self) -> bool:
        pipeline_str = 'filesrc location="/home/anna/Загрузки/cat.mp4" ! decodebin ! videoconvert ! xvimagesink name=sink'
        
        #"udpsrc port=5000 name=src ! application/x-rtp ! rtph264depay ! h264parse ! avdec_h264 " \
        #    "! videoconvert ! glimagesink name=sink "
        
        self.pipeline = Gst.parse_launch(pipeline_str)

        wnd = get_window_handle(self.screen_wdgt)

        self.videosink = self.pipeline.get_by_name("sink")
        self.videosink.set_window_handle(wnd)
        self.pipeline.set_state(Gst.State.NULL)

        return True

    def on_play_clicked(self):
        #self.createPipeline()  
        if(self.pipeline):
            self.pipeline.set_state(Gst.State.PLAYING)
            state = self.pipeline.get_state(1e9)
            print(f'{state}')

    def on_stop_clicked(self):
        if(self.pipeline):
            self.pipeline.set_state(Gst.State.PAUSED)

    def timerEvent(self):
        if(self.pipeline):
            (ok, current) = self.pipeline.query_position(Gst.Format.TIME)
            if(ok):
                self.current_time = current
                self.progress.setValue(int(current * 1e-9))


