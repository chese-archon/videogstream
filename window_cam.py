import os
import sys
import gi
import time
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QMainWindow, QLabel, 
                           QVBoxLayout, QHBoxLayout, QPushButton, 
                           QSpinBox, QLineEdit, QFileDialog, 
                           QMessageBox, QGroupBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['GDK_BACKEND'] = 'x11'
os.environ['XDG_SESSION_TYPE'] = 'x11'

gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib, GstVideo

Gst.init(None)

class MainWindow(QMainWindow):
    update_status_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Видеонаблюдение с зумом")
        self.setGeometry(100, 100, 1000, 700)
        
        self.pipeline = None
        self.is_playing = False
        self.videosink = None
        
        self.record_pipeline = None
        self.is_recording = False
        self.record_file = ""
        
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        
        self.update_status_signal.connect(self._update_status)
        
        self.init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_glib_events)
        self.timer.start(100)
    
    def _update_status(self, text):
        self.status_label.setText(text)
    
    def init_ui(self):
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout()
        self.central_widget.setLayout(main_layout)
        
        conn_group = QGroupBox("Подключение к UDP потоку")
        conn_layout = QVBoxLayout()
        
        udp_layout = QHBoxLayout()
        udp_layout.addWidget(QLabel("IP сервера:"))
        self.udp_ip = QLineEdit("127.0.0.1")
        self.udp_ip.setFixedWidth(120)
        udp_layout.addWidget(self.udp_ip)
        
        udp_layout.addWidget(QLabel("Порт:"))
        self.udp_port = QSpinBox()
        self.udp_port.setRange(1, 65535)
        self.udp_port.setValue(5000)
        self.udp_port.setFixedWidth(80)
        udp_layout.addWidget(self.udp_port)
        conn_layout.addLayout(udp_layout)
        
        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.clicked.connect(self.connect_to_stream)
        conn_layout.addWidget(self.connect_btn)
        
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)
        
        self.video_widget = QWidget()
        self.video_widget.setMinimumSize(640, 480)
        self.video_widget.setStyleSheet("background-color: black; border: 2px solid #444;")
        main_layout.addWidget(self.video_widget, 1)
        
        self.video_label = QLabel("Подключитесь к видеопотоку", self.video_widget)
        self.video_label.setStyleSheet("color: white; font-size: 16px;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        control_panel = QHBoxLayout()
        
        self.btn_play = QPushButton("Воспроизвести")
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_play.setEnabled(False)
        
        self.btn_stop = QPushButton("Стоп")
        self.btn_stop.clicked.connect(self.stop)
        self.btn_stop.setEnabled(False)
        
        control_panel.addWidget(self.btn_play)
        control_panel.addWidget(self.btn_stop)
        control_panel.addStretch()
        
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        
        self.btn_zoom_in = QPushButton("Увеличить")
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_in.setEnabled(False)
        
        self.btn_zoom_out = QPushButton("Уменьшить")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_out.setEnabled(False)
        
        self.btn_reset_zoom = QPushButton("Сброс")
        self.btn_reset_zoom.clicked.connect(self.reset_zoom)
        self.btn_reset_zoom.setEnabled(False)
        
        zoom_layout.addWidget(self.btn_zoom_in)
        zoom_layout.addWidget(self.btn_zoom_out)
        zoom_layout.addWidget(self.btn_reset_zoom)
        
        control_panel.addLayout(zoom_layout)
        control_panel.addStretch()
        
        pan_layout = QHBoxLayout()
        pan_layout.addWidget(QLabel("Перемещение:"))
        
        self.btn_left = QPushButton("←")
        self.btn_left.clicked.connect(self.move_left)
        self.btn_left.setEnabled(False)
        self.btn_left.setFixedWidth(40)
        
        self.btn_right = QPushButton("→")
        self.btn_right.clicked.connect(self.move_right)
        self.btn_right.setEnabled(False)
        self.btn_right.setFixedWidth(40)
        
        self.btn_up = QPushButton("↑")
        self.btn_up.clicked.connect(self.move_up)
        self.btn_up.setEnabled(False)
        self.btn_up.setFixedWidth(40)
        
        self.btn_down = QPushButton("↓")
        self.btn_down.clicked.connect(self.move_down)
        self.btn_down.setEnabled(False)
        self.btn_down.setFixedWidth(40)
        
        self.btn_center = QPushButton("Центр")
        self.btn_center.clicked.connect(self.reset_position)
        self.btn_center.setEnabled(False)
        
        pan_layout.addWidget(self.btn_left)
        pan_layout.addWidget(self.btn_right)
        pan_layout.addWidget(self.btn_up)
        pan_layout.addWidget(self.btn_down)
        pan_layout.addWidget(self.btn_center)
        
        control_panel.addLayout(pan_layout)
        control_panel.addStretch()
        
        self.btn_record = QPushButton("Запись")
        self.btn_record.clicked.connect(self.toggle_record)
        self.btn_record.setEnabled(False)
        control_panel.addWidget(self.btn_record)
        
        self.record_label = QLabel("Запись не активна")
        control_panel.addWidget(self.record_label)
        
        self.record_indicator = QLabel("●")
        self.record_indicator.setStyleSheet("color: red; font-size: 16px;")
        self.record_indicator.setVisible(False)
        control_panel.addWidget(self.record_indicator)
        
        main_layout.addLayout(control_panel)
        
        self.status_label = QLabel("Готов к подключению")
        main_layout.addWidget(self.status_label)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'video_label'):
            self.video_label.setGeometry(0, 0, self.video_widget.width(), self.video_widget.height())
    
    def get_window_handle(self, widget):
        widget.repaint()
        QApplication.processEvents()
        return widget.winId()
    
    def create_pipeline(self):
        try:
            ip = self.udp_ip.text().strip()
            port = self.udp_port.value()
            
            if not ip:
                QMessageBox.warning(self, "ОШИБКА", "Введите IP адрес сервера")
                return False
            
            pipeline_str = (
                f'udpsrc address={ip} port={port} caps="application/x-rtp" ! '
                'rtpjitterbuffer latency=100 ! '
                'rtph264depay ! '
                'h264parse ! '
                'decodebin ! '
                'videoconvert ! '
                'videoscale ! '
                'videocrop name=crop_filter ! '
                'videoconvert ! '
                'xvimagesink name=sink'
            )
            
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            if not self.pipeline:
                QMessageBox.critical(self, "ОШИБКА", "Не удалось создать пайплайн")
                return False
            
            wnd = self.get_window_handle(self.video_widget)
            self.videosink = self.pipeline.get_by_name("sink")
            if not self.videosink:
                QMessageBox.critical(self, "ОШИБКА", "Не найден videosink элемент")
                return False
                
            self.videosink.set_window_handle(wnd)
            
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
            
            self.pipeline.set_state(Gst.State.NULL)
            
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "ОШИБКА", f"Ошибка создания пайплайна: {str(e)}")
            return False
    
    def apply_crop(self):
        try:
            if not self.pipeline or not self.is_playing:
                return
            
            crop_filter = self.pipeline.get_by_name("crop_filter")
            if not crop_filter:
                return
            
            video_width = 320
            video_height = 240
            
            if self.zoom_factor <= 1.0:
                crop_width = video_width
                crop_height = video_height
            else:
                crop_width = max(10, int(video_width / self.zoom_factor))
                crop_height = max(10, int(video_height / self.zoom_factor))
            
            max_pan_x = max(0, (video_width - crop_width) // 2)
            max_pan_y = max(0, (video_height - crop_height) // 2)
            
            self.pan_x = max(-max_pan_x, min(max_pan_x, self.pan_x))
            self.pan_y = max(-max_pan_y, min(max_pan_y, self.pan_y))
            
            center_x = (video_width - crop_width) // 2
            center_y = (video_height - crop_height) // 2
            
            left = center_x + self.pan_x
            top = center_y + self.pan_y
            
            crop_filter.set_property("left", left)
            crop_filter.set_property("top", top)
            crop_filter.set_property("right", video_width - crop_width - left)
            crop_filter.set_property("bottom", video_height - crop_height - top)
            
            status_text = "Воспроизведение"
            if self.zoom_factor > 1.0:
                status_text += f" Zoom: {self.zoom_factor:.1f}x"
                if self.pan_x != 0 or self.pan_y != 0:
                    status_text += f" Смещение: X:{self.pan_x} Y:{self.pan_y}"
            
            self.update_status_signal.emit(status_text)
                
        except Exception as e:
            print(f"ОШИБКА ПРИМЕНЕНИЯ ОБРЕЗКИ: {e}")
    
    def zoom_in(self):
        try:
            if self.zoom_factor < 4.0:
                self.zoom_factor += 0.5
                self.apply_crop()
                self.update_pan_buttons_state()
        except Exception as e:
            print(f"ОШИБКА УВЕЛИЧЕНИЯ ЗУМА: {e}")
    
    def zoom_out(self):
        try:
            if self.zoom_factor > 1.0:
                self.zoom_factor -= 0.5
                if self.zoom_factor <= 1.0:
                    self.reset_position()
                self.apply_crop()
                self.update_pan_buttons_state()
        except Exception as e:
            print(f"ОШИБКА УМЕНЬШЕНИЯ ЗУМА: {e}")
    
    def reset_zoom(self):
        try:
            self.zoom_factor = 1.0
            self.reset_position()
        except Exception as e:
            print(f"ОШИБКА СБРОСА ЗУМА: {e}")
    
    def move_left(self):
        try:
            if self.zoom_factor > 1.0:
                self.pan_x -= 10
                self.apply_crop()
        except Exception as e:
            print(f"ОШИБКА ДВИЖЕНИЯ ВЛЕВО: {e}")
    
    def move_right(self):
        try:
            if self.zoom_factor > 1.0:
                self.pan_x += 10
                self.apply_crop()
        except Exception as e:
            print(f"ОШИБКА ДВИЖЕНИЯ ВПРАВО: {e}")
    
    def move_up(self):
        try:
            if self.zoom_factor > 1.0:
                self.pan_y -= 10
                self.apply_crop()
        except Exception as e:
            print(f"ОШИБКА ДВИЖЕНИЯ ВВЕРХ: {e}")
    
    def move_down(self):
        try:
            if self.zoom_factor > 1.0:
                self.pan_y += 10
                self.apply_crop()
        except Exception as e:
            print(f"ОШИБКА ДВИЖЕНИЯ ВНИЗ: {e}")
    
    def reset_position(self):
        try:
            self.pan_x = 0
            self.pan_y = 0
            self.apply_crop()
        except Exception as e:
            print(f"ОШИБКА СБРОСА ПОЗИЦИИ: {e}")
    
    def update_pan_buttons_state(self):
        can_pan = self.zoom_factor > 1.0 and self.is_playing
        self.btn_left.setEnabled(can_pan)
        self.btn_right.setEnabled(can_pan)
        self.btn_up.setEnabled(can_pan)
        self.btn_down.setEnabled(can_pan)
        self.btn_center.setEnabled(can_pan)
    
    def connect_to_stream(self):
        try:
            ip = self.udp_ip.text().strip()
            port = self.udp_port.value()
            
            if not ip:
                QMessageBox.warning(self, "ОШИБКА", "Введите IP адрес сервера")
                return
            
            self.update_status_signal.emit(f"Подключение к {ip}:{port}...")
            
            if self.create_pipeline():
                self.video_label.hide()
                self.connect_btn.setEnabled(False)
                self.connect_btn.setText("Подключено")
                self.btn_play.setEnabled(True)
                self.btn_record.setEnabled(True)
                self.btn_zoom_in.setEnabled(True)
                self.btn_zoom_out.setEnabled(True)
                self.btn_reset_zoom.setEnabled(True)
                self.update_pan_buttons_state()
                self.update_status_signal.emit(f"Подключено. Нажмите 'Воспроизвести'")
            else:
                self.update_status_signal.emit("ОШИБКА ПОДКЛЮЧЕНИЯ")
                
        except Exception as e:
            QMessageBox.critical(self, "ОШИБКА", f"Ошибка подключения: {str(e)}")
    
    def toggle_play(self):
        if not self.pipeline:
            return
        
        try:
            if not self.is_playing:
                ret = self.pipeline.set_state(Gst.State.PLAYING)
                
                if ret != Gst.StateChangeReturn.FAILURE:
                    self.is_playing = True
                    self.btn_play.setText("Пауза")
                    self.btn_stop.setEnabled(True)
                    self.update_pan_buttons_state()
                    self.apply_crop()
                else:
                    self.update_status_signal.emit("ОШИБКА ЗАПУСКА")
            else:
                self.pipeline.set_state(Gst.State.PAUSED)
                self.is_playing = False
                self.btn_play.setText("Воспроизвести")
                self.update_status_signal.emit("Пауза")
                self.update_pan_buttons_state()
                
        except Exception as e:
            QMessageBox.critical(self, "ОШИБКА", f"Ошибка переключения воспроизведения: {str(e)}")
    
    def stop(self):
        try:
            if self.pipeline:
                if self.is_recording:
                    self.stop_recording()
                
                self.pipeline.set_state(Gst.State.NULL)
                self.is_playing = False
                self.btn_play.setText("Воспроизвести")
                self.btn_play.setEnabled(True)
                self.btn_stop.setEnabled(False)
                self.btn_record.setEnabled(False)
                self.btn_zoom_in.setEnabled(False)
                self.btn_zoom_out.setEnabled(False)
                self.btn_reset_zoom.setEnabled(False)
                self.connect_btn.setEnabled(True)
                self.connect_btn.setText("Подключиться")
                self.update_status_signal.emit("Остановлено")
                self.update_pan_buttons_state()
                
                self.video_label.show()
                self.video_label.setText("Видео остановлено")
                self.zoom_factor = 1.0
                self.reset_position()
                
        except Exception as e:
            QMessageBox.critical(self, "ОШИБКА", f"Ошибка остановки: {str(e)}")
    
    def toggle_record(self):
        if not self.pipeline:
            return
        
        try:
            if not self.is_recording:
                if not self.is_playing:
                    QMessageBox.warning(self, "ОШИБКА", "Сначала запустите воспроизведение видео!")
                    return
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                default_dir = os.path.expanduser("~/Videos")
                if not os.path.exists(default_dir):
                    default_dir = os.path.expanduser("~/")
                
                filename, _ = QFileDialog.getSaveFileName(
                    self,
                    "Сохранить запись",
                    os.path.join(default_dir, f"record_{timestamp}.mkv"),
                    "MKV files (*.mkv);;All files (*.*)"
                )
                
                if filename:
                    if not filename.lower().endswith('.mkv'):
                        filename = filename + '.mkv'
                    
                    self.start_recording(filename)
            else:
                self.stop_recording()
                
        except Exception as e:
            QMessageBox.critical(self, "ОШИБКА", f"Ошибка переключения записи: {str(e)}")
    
    def create_record_pipeline(self, filename):
        try:
            ip = self.udp_ip.text().strip()
            port = self.udp_port.value()
            
            pipeline_str = (
                f'udpsrc address={ip} port={port} caps="application/x-rtp,media=video" ! '
                'rtpjitterbuffer latency=500 ! '
                'rtph264depay ! '
                'h264parse ! '
                'queue ! '
                'matroskamux ! '
                f'filesink location="{filename}"'
            )
            
            self.record_pipeline = Gst.parse_launch(pipeline_str)
            
            if not self.record_pipeline:
                return False
            
            bus = self.record_pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_record_bus_message)
            
            self.record_pipeline.set_state(Gst.State.NULL)
            
            return True
            
        except Exception as e:
            print(f"ОШИБКА СОЗДАНИЯ ПАЙПЛАЙНА ЗАПИСИ: {e}")
            return False
    
    def start_recording(self, filename):
        try:
            if not self.create_record_pipeline(filename):
                QMessageBox.critical(self, "ОШИБКА", "Не удалось создать пайплайн записи")
                return
            
            ret = self.record_pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                QMessageBox.critical(self, "ОШИБКА", "Не удалось запустить запись")
                return
                
            time.sleep(0.1)
            
            self.is_recording = True
            self.record_file = filename
            self.btn_record.setText("Стоп запись")
            self.record_indicator.setVisible(True)
            
            filename_display = os.path.basename(filename)
            self.record_label.setText(f"Запись: {filename_display}")
            self.update_status_signal.emit(f"Идет запись")
            
        except Exception as e:
            QMessageBox.critical(self, "ОШИБКА", f"Не удалось начать запись: {str(e)}")
    
    def stop_recording(self):
        try:
            if self.record_pipeline and self.is_recording:
                self.record_pipeline.set_state(Gst.State.NULL)
                self.record_pipeline = None
                
        except Exception as e:
            print(f"ОШИБКА ОСТАНОВКИ ЗАПИСИ: {e}")
            
        finally:
            self.is_recording = False
            self.btn_record.setText("Запись")
            self.record_indicator.setVisible(False)
            self.record_label.setText("Запись не активна")
            
            if os.path.exists(self.record_file):
                file_size = os.path.getsize(self.record_file) / (1024 * 1024)
                self.update_status_signal.emit(f"Запись сохранена ({file_size:.1f} MB)")
            else:
                self.update_status_signal.emit("Запись завершена")
    
    def on_bus_message(self, bus, message):
        msg_type = message.type
        
        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"ОШИБКА GSTREAMER: {err.message}")
            self.update_status_signal.emit(f"Ошибка: {err.message}")
            self.stop()
            
        elif msg_type == Gst.MessageType.EOS:
            self.update_status_signal.emit("КОНЕЦ ПОТОКА")
            self.stop()
    
    def on_record_bus_message(self, bus, message):
        msg_type = message.type
        
        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"ОШИБКА ЗАПИСИ: {err.message}")
            self.update_status_signal.emit(f"Ошибка записи")
            self.stop_recording()
            
        elif msg_type == Gst.MessageType.EOS:
            self.stop_recording()
    
    def process_glib_events(self):
        try:
            context = GLib.MainContext.default()
            while context.pending():
                context.iteration(False)
        except:
            pass
    
    def closeEvent(self, event):
        try:
            if self.is_recording:
                self.stop_recording()
            
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
            
            self.timer.stop()
            
        except Exception as e:
            print(f"ОШИБКА ПРИ ЗАКРЫТИИ: {e}")
            
        event.accept()

def main():
    app = QApplication(sys.argv)
    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "ОШИБКА", f"Критическая ошибка: {str(e)}")

if __name__ == "__main__":
    main()