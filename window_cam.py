import os
import sys
import gi
import time
from datetime import datetime
from enum import Enum
from PyQt6.QtWidgets import (QApplication, QWidget, QMainWindow, QLabel, 
                           QVBoxLayout, QHBoxLayout, QPushButton, 
                           QComboBox, QSpinBox, QLineEdit, QFileDialog, 
                           QMessageBox, QGroupBox)
from PyQt6.QtCore import Qt, QTimer

# === НАСТРОЙКИ ===
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['GDK_BACKEND'] = 'x11'
os.environ['XDG_SESSION_TYPE'] = 'x11'
os.environ['GST_DEBUG'] = '2'

gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib, GstVideo

Gst.init(None)

class VideoSource(Enum):
    UDP_STREAM = "UDP поток"
    TEST = "Тестовый источник"

def get_window_handle(widget):
    widget.repaint()
    QApplication.processEvents()
    wnd = widget.winId()
    return wnd

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Система видеонаблюдения")
        self.setGeometry(100, 100, 1000, 800)
        
        # Переменные для управления видео
        self.pipeline = None
        self.is_playing = False
        self.videosink = None
        self.screen_wdgt = None
        
        # Запись
        self.record_pipeline = None
        self.is_recording = False
        self.record_file = ""
        
        # Инициализация UI
        self.init_ui()
        
        # Таймер для GLib событий
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_glib_events)
        self.timer.start(100)
    
    def init_ui(self):
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout()
        self.central_widget.setLayout(main_layout)
        
        # ПАНЕЛЬ ПОДКЛЮЧЕНИЯ
        conn_group = QGroupBox("Подключение к видеопотоку")
        conn_layout = QVBoxLayout()
        
        # Выбор источника
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Источник:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems([source.value for source in VideoSource])
        source_layout.addWidget(self.source_combo)
        conn_layout.addLayout(source_layout)
        
        # Параметры UDP
        udp_layout = QHBoxLayout()
        udp_layout.addWidget(QLabel("IP:"))
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
        
        # Кнопка подключения
        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.clicked.connect(self.connect_source)
        conn_layout.addWidget(self.connect_btn)
        
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)
        
        # ОБЛАСТЬ ВИДЕО
        self.screen_wdgt = QWidget()
        self.screen_wdgt.setMinimumSize(640, 480)
        self.screen_wdgt.setStyleSheet("""
            QWidget {
                background-color: black;
                border: 2px solid #444;
                border-radius: 4px;
            }
        """)
        main_layout.addWidget(self.screen_wdgt, 1)
        
        # Информационная метка
        self.video_label = QLabel("Видео будет отображаться здесь", self.screen_wdgt)
        self.video_label.setStyleSheet("color: white; font-size: 16px;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # === ПАНЕЛЬ УПРАВЛЕНИЯ ===
        control_panel = QHBoxLayout()
        
        # Управление воспроизведением
        self.btn_play = QPushButton("Воспроизвести")
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_play.setEnabled(False)
        
        self.btn_stop = QPushButton("Стоп")
        self.btn_stop.clicked.connect(self.stop)
        self.btn_stop.setEnabled(False)
        
        control_panel.addWidget(self.btn_play)
        control_panel.addWidget(self.btn_stop)
        
        control_panel.addStretch()
        
        # Запись
        self.btn_record = QPushButton("Запись")
        self.btn_record.clicked.connect(self.toggle_record)
        self.btn_record.setEnabled(False)
        control_panel.addWidget(self.btn_record)
        
        self.record_label = QLabel("Не активна")
        control_panel.addWidget(self.record_label)
        
        # # Индикатор записи
        # self.record_indicator = QLabel("@")
        # self.record_indicator.setStyleSheet("color: red; font-size: 16px;")
        # self.record_indicator.setVisible(False)
        # control_panel.addWidget(self.record_indicator)
        
        main_layout.addLayout(control_panel)
        
        # СТАТУС СТРОКА
        self.status_label = QLabel("Готов к работе")
        main_layout.addWidget(self.status_label)
    
    def resizeEvent(self, event):
        # Обновление размера видео
        super().resizeEvent(event)
        if hasattr(self, 'video_label'):
            self.video_label.setGeometry(0, 0, self.screen_wdgt.width(), self.screen_wdgt.height())
    
    def create_pipeline_udp(self) -> bool:
        ip = self.udp_ip.text().strip()
        port = self.udp_port.value()
        
        pipeline_str = (
            f'udpsrc port={port} caps="application/x-rtp" ! '
            'rtpjitterbuffer latency=100 ! '
            'rtph264depay ! '
            'h264parse ! '
            'decodebin ! '
            'videoconvert ! '
            'xvimagesink name=sink'
        )
        
        print(f"Создаем UDP пайплайн: {pipeline_str}")
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        
        if not self.pipeline:
            self.status_label.setText("Ошибка: не удалось создать пайплайн")
            return False
        
        wnd = get_window_handle(self.screen_wdgt)
        
        self.videosink = self.pipeline.get_by_name("sink")
        self.videosink.set_window_handle(wnd)
        
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)
        
        self.pipeline.set_state(Gst.State.NULL)
        
        return True
    
    def create_pipeline_test(self) -> bool:
        """Создание тестового пайплайна - АНАЛОГИЧНО ВАШЕМУ ПРИМЕРУ"""
        # Тестовый пайплайн
        pipeline_str = (
            'videotestsrc pattern=ball ! '
            'videoconvert ! '
            'xvimagesink name=sink'
        )
        
        print(f"Создаем тестовый пайплайн: {pipeline_str}")
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        
        if not self.pipeline:
            self.status_label.setText("Ошибка: не удалось создать пайплайн")
            return False
        
        wnd = get_window_handle(self.screen_wdgt)
        
        self.videosink = self.pipeline.get_by_name("sink")
        self.videosink.set_window_handle(wnd)
        
        # Настраиваем bus
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)
        
        # Устанавливаем начальное состояние
        self.pipeline.set_state(Gst.State.NULL)
        
        return True
    
    def connect_source(self):
        # Подключение к серверу 
        source_type = list(VideoSource)[self.source_combo.currentIndex()]
        
        success = False
        if source_type == VideoSource.UDP_STREAM:
            success = self.create_pipeline_udp()
        else:
            success = self.create_pipeline_test()
        
        if success:
            # Скрываем текстовую метку
            self.video_label.hide()
            
            # Обновляем UI
            self.connect_btn.setEnabled(False)
            self.connect_btn.setText("Подключено")
            self.btn_play.setEnabled(True)
            self.btn_record.setEnabled(True)
            
            ip = self.udp_ip.text().strip()
            port = self.udp_port.value()
            self.status_label.setText(f"Подключено к {ip}:{port}")
    
    def toggle_play(self):
        # Включение/выключение воспроизведения
        if not self.pipeline:
            return
        
        if not self.is_playing:
            print("Запуск воспроизведения...")
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            
            if ret != Gst.StateChangeReturn.FAILURE:
                self.is_playing = True
                self.btn_play.setText("Пауза")
                self.btn_stop.setEnabled(True)
                self.status_label.setText("Воспроизведение...")
            else:
                print("Не удалось запустить воспроизведение")
                self.status_label.setText("Ошибка запуска")
        else:
            # Пауза
            self.pipeline.set_state(Gst.State.PAUSED)
            self.is_playing = False
            self.btn_play.setText("Воспроизвести")
            self.status_label.setText("Пауза")
    
    def stop(self):
        if self.pipeline:
            print("Остановка")
            
            # Если идет запись, останавливаем ее
            if self.is_recording:
                self.stop_recording()
            
            self.pipeline.set_state(Gst.State.NULL)
            self.is_playing = False
            self.btn_play.setText("Воспроизвести")
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.btn_record.setEnabled(False)
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("Подключиться")
            self.status_label.setText("Остановлено")
            
            # Показываем текстовую метку снова
            self.video_label.show()
            self.video_label.setText("Видео остановлено")
    
    def toggle_record(self):
        # Включение/выключение записи
        if not self.pipeline:
            return
        
        if not self.is_recording:
            # Начало записи
            if not self.is_playing:
                QMessageBox.warning(self, "Внимание", 
                                  "Сначала запустите воспроизведение видео!")
                return
            
            # Запрашиваем имя файла
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
    
    def create_record_pipeline(self, filename) -> bool:
        port = self.udp_port.value()
        
        pipeline_str = (
            f'udpsrc port={port} caps="application/x-rtp,media=video" ! '
            'rtpjitterbuffer latency=500 ! '
            'rtph264depay ! '
            'h264parse ! '
            'queue max-size-buffers=1000 ! '
            'matroskamux ! '
            f'filesink location="{filename}"'
        )
        
        print(f"Создаем пайплайн записи: {pipeline_str}")
        
        self.record_pipeline = Gst.parse_launch(pipeline_str)
        
        if not self.record_pipeline:
            return False
        
        # bus для записи
        bus = self.record_pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_record_bus_message)
        
        self.record_pipeline.set_state(Gst.State.NULL)
        
        return True
    
    def start_recording(self, filename):
        try:
            print(f"НАЧАЛО ЗАПИСИ")
            print(f"Файл: {filename}")
            
            # Создаем пайплайн записи
            if not self.create_record_pipeline(filename):
                QMessageBox.critical(self, "Ошибка", "Не удалось создать пайплайн записи")
                return
            
            # Запускаем запись
            self.record_pipeline.set_state(Gst.State.PLAYING)
            
            time.sleep(0.5)
            
            self.is_recording = True
            self.record_file = filename
            self.btn_record.setText("Стоп запись")
            self.record_indicator.setVisible(True)
            
            filename_display = os.path.basename(filename)
            self.record_label.setText(f"Запись: {filename_display}")
            self.status_label.setText(f"Идет запись: {filename_display}")
            
            print("ЗАПИСЬ НАЧАТА УСПЕШНО")
            
        except Exception as e:
            error_msg = f"Не удалось начать запись: {e}"
            print(f"ОШИБКА: {error_msg}")
            QMessageBox.critical(self, "Ошибка записи", error_msg)
    
    def stop_recording(self):
        """Остановить запись"""
        if self.record_pipeline and self.is_recording:
            try:
                print("ОСТАНОВКА ЗАПИСИ")
                
                # Останавливаем пайплайн
                self.record_pipeline.set_state(Gst.State.NULL)
                self.record_pipeline = None
                
                print("ЗАПИСЬ ОСТАНОВЛЕНА")
                
            except Exception as e:
                print(f"Ошибка при остановке записи: {e}")
            
            finally:
                self.is_recording = False
                self.btn_record.setText("Запись")
                self.record_indicator.setVisible(False)
                self.record_label.setText("Не активна")
                
                # Проверяем файл
                if os.path.exists(self.record_file):
                    file_size = os.path.getsize(self.record_file) / (1024 * 1024)  # MB
                    
                    if file_size > 0.1:
                        self.status_label.setText(f"Запись сохранена ({file_size:.1f} MB)")
                        print(f"Файл создан, размер: {file_size:.1f} MB")
                    else:
                        self.status_label.setText(f"Файл пустой ({file_size:.1f} MB)")
                        print(f"Внимание: файл пустой")
                else:
                    self.status_label.setText("Запись завершена")
    
    def on_bus_message(self, bus, message):
        msg_type = message.type
        
        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"GStreamer ошибка: {err.message}")
            self.status_label.setText(f"Ошибка: {err.message}")
            self.stop()
            
        elif msg_type == Gst.MessageType.EOS:
            print("Конец потока")
            self.status_label.setText("Конец потока")
            self.stop()
    
    def on_record_bus_message(self, bus, message):
        msg_type = message.type
        
        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Ошибка записи: {err.message}")
            self.stop_recording()
    
    def process_glib_events(self):
        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(False)
    
    def closeEvent(self, event):
        print("Закрытие приложения")
        
        if self.is_recording:
            self.stop_recording()
        
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        
        self.timer.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()