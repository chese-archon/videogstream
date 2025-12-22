import os
import sys
import threading
from datetime import datetime

os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['GDK_BACKEND'] = 'x11'
os.environ['XDG_SESSION_TYPE'] = 'x11'

from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, \
    QComboBox, QMessageBox, QFileDialog, QProgressBar, QGridLayout, QLineEdit
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
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

# convert signals
class ConversionSignals(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        layout_main = QVBoxLayout()
        self.central_widget.setLayout(layout_main)

        self.conversion_thread = None
        self.conversion_signals = ConversionSignals()
        self.source_file = "/home/anna/Загрузки/cat.mp4"
        
        self.conversion_signals.progress.connect(self.on_conversion_progress)
        self.conversion_signals.finished.connect(self.on_conversion_finished)
        self.conversion_signals.error.connect(self.on_conversion_error)

        self.screen_wgt = QLabel(self)
        self.screen_wgt.setStyleSheet("QLabel { background-color: black; color: white }")
        self.screen_wgt.setAlignment(Qt.AlignmentFlag.AlignCenter)# text to center
        
        layout_main.addWidget(self.screen_wgt)

        #procrutka
        self.progress = QSlider(Qt.Orientation.Horizontal, self)
        layout_main.addWidget(self.progress)
        self.progress.sliderMoved.connect(self.on_progress_moved)

        # progress convertatsia
        self.conversion_progress = QProgressBar(self)
        self.conversion_progress.setVisible(False)
        layout_main.addWidget(self.conversion_progress)

        #create btns
        layou_ctrl = QHBoxLayout()
        layout_main.addLayout(layou_ctrl)

        self.btn_play = QPushButton("", self)
        self.btn_pause = QPushButton("", self)
        self.btn_reload = QPushButton("", self)
        
        #image for icons
        self.btn_play.setIcon(QIcon("PlayVideo.png"))
        self.btn_pause.setIcon(QIcon("Pause.png"))
        self.btn_reload.setIcon(QIcon("reload.png"))

        self.btn_play.clicked.connect(self.on_play_clicked)
        self.btn_pause.clicked.connect(self.on_pause_clicked)
        self.btn_reload.clicked.connect(self.on_reload_clicked)

        layou_ctrl.addWidget(self.btn_play)
        layou_ctrl.addWidget(self.btn_pause)
        layou_ctrl.addWidget(self.btn_reload)
        
        #  btn for select another video from local storage
        self.btn_select = QPushButton("Select video", self)
        self.btn_select.clicked.connect(self.on_select_file)
        layou_ctrl.addWidget(self.btn_select)

        layou_ctrl.addStretch(1)# btns to left
        
        
        # TABLITSA
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10) 
        self.grid_layout.setContentsMargins(20, 0, 40, 0)
        
        # tabel text header
        self.label1 = QLabel('Container')
        self.label2 = QLabel('Codec')
        self.label3 = QLabel('Resolution')
        self.label4 = QLabel('Frame rate')
        
        self.grid_layout.addWidget(self.label1, 0, 0)
        self.grid_layout.addWidget(self.label2, 0, 1) 
        self.grid_layout.addWidget(self.label3, 0, 2)
        self.grid_layout.addWidget(self.label4, 0, 3)
        
        # table content (converter functional)
        
        #container
        self.video_type = QComboBox(self)
        self.video_type.addItems(("MP4", "MKV", "MOV", "WebM"))
        self.grid_layout.addWidget(self.video_type, 1, 0)
        
        # codec
        self.codec_type = QComboBox(self)
        self.codec_type.addItems(("H.264", "H.265 (HEVC)", "VP9", "AV1", "MPEG-4", "XviD"))
        self.grid_layout.addWidget(self.codec_type, 1, 1)
        
        # resolution input params        
        self.resolution_input = QLineEdit()
        self.resolution_input.setPlaceholderText("1280x720 or 1080p")
        self.grid_layout.addWidget(self.resolution_input, 1, 2)
        
        # frame rate input params        
        self.frame_rate_input = QLineEdit()
        self.frame_rate_input.setPlaceholderText("30 or 29.97")
        self.grid_layout.addWidget(self.frame_rate_input, 1, 3)
        
        layou_ctrl.addLayout(self.grid_layout)
        
        #convert video
        self.btn_convert = QPushButton("Convert", self)
        self.btn_convert.clicked.connect(self.start_conversion)
        layou_ctrl.addWidget(self.btn_convert)
        
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
        
        self.currunt_time = 0
        self.current_speed = 1.0
        
        self.createPipeline()
        self.sound.setValue(50)

    def parse_resolution(self, resolution_str):
        try:
            clean_str = resolution_str.strip().lower()
            for sep in ['x', '*', 'х']:
                if sep in clean_str:
                    parts = clean_str.split(sep)
                    if len(parts) == 2:
                        width = int(parts[0].strip())
                        height = int(parts[1].strip())
                        if width > 0 and height > 0 and width <= 7680 and height <= 4320:  # 8K max
                            return width, height
                        else:
                            return None, None
        except (ValueError, AttributeError):
            print("parse error")
        return None, None # use resolution from orig

    def parse_frame_rate(self, frame_rate_str):
        if not frame_rate_str or frame_rate_str.strip() == "":
            return None
        
        try:
            clean_str = frame_rate_str.strip().replace(',', '.')
            frame_rate = float(clean_str)
            
            if 0.1 <= frame_rate <= 240.0:  # correct frame_rate дif from 0.1 to 240 frame/sec
                return frame_rate
            else:
                return None
        except (ValueError, AttributeError):
            return None

    def get_video_encoder(self, codec_name, width=None, height=None):
        codec_configs = {
            "h.264": {
                "encoder": "x264enc",
                "params": "bitrate=2000 speed-preset=medium",
            },
            "h.265 (hevc)": {
                "encoder": "x265enc",
                "params": "bitrate=1500 speed-preset=medium",
            },
            "vp9": {
                "encoder": "vp9enc",
                "params": "target-bitrate=2000000 cpu-used=4",
            },
            "av1": {
                "encoder": "av1enc",
                "params": "target-bitrate=1000000 cpu-used=6",
            },
            "mpeg-4": {
                "encoder": "avenc_mpeg4",
                "params": "bitrate=2000",
            },
            "xvid": {
                "encoder": "xvidenc",
                "params": "bitrate=2000",
            },
        }
        
        codec_lower = codec_name.lower()
        for key, config in codec_configs.items():
            if key in codec_lower:
                return f"{config['encoder']} {config['params']}"
        
        # use H.264 by default
        return "x264enc bitrate=2000 speed-preset=medium"

    def get_conversion_pipeline(self, input_file, output_file, target_format, target_codec, target_resolution, target_frame_rate):
        if target_format == "webm":
            vp_encoder = "vp8enc"
            if "vp9" in target_codec.lower():
                vp_encoder = "vp9enc"
            
            return (
                f"filesrc location=\"{input_file}\" ! "
                "decodebin name=dec ! "
                "queue ! "
                "videoconvert ! "
                f"{vp_encoder} target-bitrate=2000000 cpu-used=4 ! "
                "queue ! "
                "webmmux name=mux ! "
                "filesink location=\""
                f"{output_file}\" "
                "dec. ! "
                "queue ! "
                "audioconvert ! "
                "audioresample ! "
                "vorbisenc ! "
                "queue ! "
                "mux."
            )
        else:
            video_encoder = self.get_video_encoder(target_codec)
            
            if target_format == "mp4":
                muxer = "mp4mux name=mux ! filesink location=\""
            elif target_format == "mkv":
                muxer = "matroskamux name=mux ! filesink location=\""
            elif target_format == "mov":
                muxer = "qtmux name=mux ! filesink location=\""
            else:
                return None
            
            return (
                f"filesrc location=\"{input_file}\" ! "
                "decodebin name=dec ! "
                "queue ! "
                "videoconvert ! "
                f"{video_encoder} ! "
                "queue ! "
                "mux. "
                "dec. ! "
                "queue ! "
                "audioconvert ! "
                "audioresample ! "
                "voaacenc bitrate=128000 ! "
                "queue ! "
                "mux. " +
                muxer + f"{output_file}\""
            )

    def on_select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.MOV *.webm *.flv);;All Files (*)"
        )
        
        if file_path and os.path.exists(file_path):
            self.source_file = file_path
            self.pipeline.set_state(Gst.State.NULL)
            self.createPipeline()

    def showEvent(self, event): 
        super().showEvent(event)
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.pipeline.get_state(1e9)
            (ok, duration) = self.pipeline.query_duration (Gst.Format.TIME)
            if (ok):
                self.progress.setMaximum(int(duration * 1e-9))
            
            if not hasattr(self, 'timer') or self.timer is None:
                self.timer = QTimer()
                self.timer.timeout.connect(self.timeEvent)
            self.timer.start(100)

    def on_speed_changed(self, value):
        speed_values = [0.25, 0.5, 1.0, 1.5, 2.0]
        if 0 <= value < len(speed_values):
            self.current_speed = speed_values[value]
            if self.pipeline:
                self.pipeline.seek(self.current_speed, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, Gst.SeekType.SET, self.currunt_time, Gst.SeekType.END, 0)
    
    def on_volume_changed(self, value):
        if self.pipeline:
            sound = self.pipeline.get_by_name("vol")
            sound.set_property("volume", value / 100)
            
    def start_conversion(self):
        
        if not self.source_file or not os.path.exists(self.source_file):
            QMessageBox.warning(self, "Error", "Please select a video file first!")
            return
        
        if self.conversion_thread and self.conversion_thread.is_alive():
            QMessageBox.warning(self, "Error", "Conversion is already in progress!")
            return
        
        # get place for converted video
        target_format = self.video_type.currentText().lower()
        codec_name = self.codec_type.currentText()
        
        # get resolution
        target_resolution = self.resolution_input.text()
        width, height = self.parse_resolution(target_resolution)
        
        # get frame rate
        target_frame_rate = self.frame_rate_input.text()
        frame_rate = self.parse_frame_rate(target_frame_rate)
        
        if width is not None and height is not None:
            resolution_suffix = f"_{width}x{height}"
        else:
            resolution_suffix = "_original"
        
        if frame_rate is not None:
            frame_rate_suffix = f"_{frame_rate}fps"
        else:
            frame_rate_suffix = "_original_fps"
        
        default_name = f"converted_{codec_name.replace(' ', '_')}{resolution_suffix}{frame_rate_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{target_format}"
        
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save as {target_format.upper()} ({codec_name})",
            default_name,
            f"{target_format.upper()} Files (*.{target_format});;All Files (*)"
        )
        
        if not output_path:
            return
        
        # converter progress
        self.conversion_progress.setVisible(True)
        self.conversion_progress.setValue(0)
        self.btn_convert.setEnabled(False)
        self.btn_select.setEnabled(False)
        
        # get codec
        target_codec = self.codec_type.currentText()
        
        self.conversion_thread = threading.Thread(
            target=self.convert_video,
            args=(self.source_file, output_path, target_format, target_codec, target_resolution, target_frame_rate)
        )
        self.conversion_thread.daemon = True
        self.conversion_thread.start()

    def convert_video(self, input_file, output_file, target_format, target_codec, target_resolution, target_frame_rate):
        print(f"Input: {input_file}")
        print(f"Output: {output_file}")
        print(f"Format: {target_format}")
        print(f"Codec: {target_codec}")
        print(f"Resolution: {target_resolution}")
        print(f"Frame rate: {target_frame_rate}")
        
        try:
            pipeline_str = self.get_conversion_pipeline(
                input_file, output_file, target_format, target_codec, target_resolution, target_frame_rate
            )
            
            if not pipeline_str:
                self.conversion_signals.error.emit(f"Unsupported format: {target_format}")
                return
            
            print(f"Conversion pipeline: {pipeline_str}")
            
            pipeline = Gst.parse_launch(pipeline_str)
            
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            
            # start converting
            pipeline.set_state(Gst.State.PLAYING)
            self.conversion_signals.progress.emit(25)
            
            # wait end of converting
            while True:
                msg = bus.timed_pop_filtered(
                    Gst.CLOCK_TIME_NONE,
                    Gst.MessageType.ERROR | Gst.MessageType.EOS | Gst.MessageType.STATE_CHANGED
                )
                
                if msg:
                    if msg.type == Gst.MessageType.ERROR:
                        err, debug = msg.parse_error()
                        self.conversion_signals.error.emit(f"Error: {err}")
                        break
                    elif msg.type == Gst.MessageType.EOS:
                        self.conversion_signals.progress.emit(100)
                        self.conversion_signals.finished.emit(True, output_file)
                        break
                    elif msg.type == Gst.MessageType.STATE_CHANGED:
                        old_state, new_state, pending = msg.parse_state_changed()
                        if new_state == Gst.State.PLAYING:
                            self.conversion_signals.progress.emit(50)
                        elif new_state == Gst.State.PAUSED:
                            self.conversion_signals.progress.emit(75)
            
            pipeline.set_state(Gst.State.NULL)
            
        except Exception as e:
            self.conversion_signals.error.emit(f"Conversion failed: {str(e)}")

    def on_conversion_progress(self, value):
        self.conversion_progress.setValue(value)

    def on_conversion_finished(self, success, output_file):
        self.conversion_progress.setVisible(False)
        self.btn_convert.setEnabled(True)
        self.btn_select.setEnabled(True)
        
        if success:
            QMessageBox.information(
                self, 
                "Success", 
                f"Video converted successfully!\nSaved to: {output_file}"
            )
        else:
            QMessageBox.warning(self, "Error", "Conversion failed!")

    def on_conversion_error(self, error_msg):
        self.conversion_progress.setVisible(False)
        self.btn_convert.setEnabled(True)
        self.btn_select.setEnabled(True)
        QMessageBox.critical(self, "Conversion Error", error_msg)
        
    def createPipeline(self) -> bool:
        self.pipeline = Gst.parse_launch(
            f"filesrc location=\"{self.source_file}\" ! decodebin name=dec ! "
            "videoconvert ! xvimagesink name=sink "
            "dec. ! audioconvert ! audioresample ! volume name=vol ! autoaudiosink"
        )
        
        wnd = get_window_handle(self.screen_wgt)
        self.videosink = self.pipeline.get_by_name("sink")
        self.videosink.set_window_handle(wnd)

        
        if self.pipeline:
            volume = self.pipeline.get_by_name("vol")
            volume.set_property("volume", self.sound.value() / 100)
                
        return True
    
    def on_progress_moved(self, value):
        print(f"{value}")
        self.pipeline.seek(self.current_speed, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, Gst.SeekType.SET, value * 1e9, Gst.SeekType.END, 0)

    def on_reload_clicked(self):
        if(self.pipeline):
            self.pipeline.seek(self.current_speed, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, Gst.SeekType.SET, 0, Gst.SeekType.END, 0)
            self.progress.setValue(0)
            self.pipeline.set_state(Gst.State.PAUSED)
        
    
    def on_play_clicked(self):
        if(self.pipeline):
            self.pipeline.set_state(Gst.State.PLAYING)
            state = self.pipeline.get_state(1e9)
            print(f'{state}')

    def on_pause_clicked(self):
        if(self.pipeline):
            self.pipeline.set_state(Gst.State.PAUSED)
    
    def timeEvent(self):
        (ok, current) = self.pipeline.query_position(Gst.Format.TIME)
        if(ok):
            self.currunt_time = current 
            self.progress.setValue(int(current * 1e-9))
            
    def timerEvent(self):
        if(self.pipeline):
            (ok, current) = self.pipeline.query_position(Gst.Format.TIME)
            if(ok):
                self.current_time = current
                self.progress.setValue(int(current * 1e-9))