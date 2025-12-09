# import sys
# from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QComboBox
# from PyQt6.QtCore import Qt, QTimer
# from PyQt6.QtGui import QIcon
# import gi
# gi.require_version('Gst', '1.0')
# gi.require_version('GstVideo', '1.0')
# from gi.repository import Gst, GObject, GstVideo

import os
import sys

# Настройки окружения ДО импортов GStreamer
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['GDK_BACKEND'] = 'x11'
os.environ['XDG_SESSION_TYPE'] = 'x11'

from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QComboBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GObject, GstVideo

Gst.init(None)

def get_window_handle(widget):
    if widget.windowHandle() is None:
        widget.winId()

    hangle = widget.windowHandle().winId()
    return int(hangle)

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

        #self.progress.valueChanged.connect(self.on_progress_changed)
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
        self.speed.addItems(("0.25", "0.5", "1.0", "1.5", "2.0"))
        self.speed.setCurrentIndex(2)
        self.speed.currentIndexChanged.connect(self.on_speed_changed)

        layou_ctrl.addWidget(self.speed)

        #zvuk
        self.sound = QSlider(Qt.Orientation.Horizontal, self)
        self.sound.setMinimum(0)
        self.sound.setMaximum(100)
        self.sound.valueChanged.connect(self.on_volume_changed)
        layou_ctrl.addWidget(self.sound)
        
        self.currunt_time=0
        self.current_speed=1

        #self.sound.valueChanged.connect(self.on_progress_changed)
        self.pipeline = Gst.parse_launch("filesrc location=\"/home/anna/Загрузки/cat.mp4\" ! decodebin name=dec ! videoconvert ! xvimagesink name=sink "\
            "dec. ! audioconvert ! audioresample ! volume name=vol ! autoaudiosink"#"dec. ! audioconvert ! audioresample ! volume name=vol ! autovideosink"
            )
        #self.pipeline = Gst.parse_launch("filesrc location=\"/home/anna/Загрузки/cat.mp4\" ! decodebin ! videoconvert ! xvimagesink name=sink")
        
        #self.pipeline = Gst.parse_launch("filesrc location=\"C:/Users/dns/Desktop/28 ноября/Гусейн-Бала Алиев.mp4\" ! decodebin ! videoconvert ! glimagesink name=sink")
        
        #self.pipeline.set_state(Gst.State.PLAYING) 

        wnd = get_window_handle(self.screen_wgt)

        # self.volume = self.pipeline.get_by_name("vol")
        # self.volume.set_property("volume", self.volume.value())
        
        self.videosink = self.pipeline.get_by_name("sink")
        self.videosink.set_window_handle(wnd)
        #self.sound.setValue(50)#default

    def showEvent(self,event): 
            super().showEvent(event)
            self.pipeline.set_state(Gst.State.PLAYING)
            self.pipeline.get_state(1e9)
            (ok, duration) = self.pipeline.query_duration (Gst.Format.TIME)
            if (ok):
                 self.progress.setMaximum(int(duration * 1e-9))
            self.timer= QTimer()
            self.timer.timeout.connect(self.timeEvent)
            self.timer.start(100)

    def on_progress_moved(self, value):
        print(f"value") 
        self.pipeline.seek(self.current_speed, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, Gst.SeekType.SET, value * 1e9, Gst.SeekType.END,0)
        # pass

    def on_speed_changed(self, value):
        if value ==0:
              self.current_speed = 0.25
        elif value == 1:
              self.current_speed = 0.5
        elif value ==2:
            self.current_speed = 1.0
        elif value ==3:
            self.current_speed = 1.5
        else:
            self.current_speed = 2.0
        self.pipeline.seek(self.current_speed, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, Gst.SeekType.SET, self.current_time, Gst.SeekType.END,0)
    
    def on_volume_changed(self, value):
        if self.pipeline:
            sound = self.pipeline.get_by_name("vol")
            sound.set_property("volume", self.sound.value() / 100)
    
    def timeEvent(self):
         (ok, current)=self.pipeline.query_position(Gst.Format.TIME)
         if(ok):
            self.current_time=current 
            self.progress.setValue(int(current * 1e-9))
            #self.progress.selValue(self.current_time)

 
"""        
print("window.py выполнился")  
"""     