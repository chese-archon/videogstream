import os
import sys

# Настройки окружения ДО импортов GStreamer
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['GDK_BACKEND'] = 'x11'
os.environ['XDG_SESSION_TYPE'] = 'x11'

# Импортируем PyQt
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QComboBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GObject, GstVideo

Gst.init(None)

def get_window_handle(widget):
    # Ждем пока виджет будет полностью создан
    QApplication.processEvents()
    
    # Пробуждаем windowHandle если нужно
    if widget.windowHandle() is None:
        # Вызываем winId() чтобы создать window handle
        widget.winId()
        QApplication.processEvents()
    
    # Проверяем еще раз
    if widget.windowHandle() is None:
        return 0
    
    return int(widget.windowHandle().winId())

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        layout_main = QVBoxLayout()
        self.central_widget.setLayout(layout_main)

        self.screen_wgt = QLabel(self)
        self.screen_wgt.setStyleSheet("QLabel { background-color: black; color: white }")
        self.screen_wgt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fnt = self.screen_wgt.font()
        fnt.setPointSizeF(72)
        self.screen_wgt.setFont(fnt)
        layout_main.addWidget(self.screen_wgt)

        # Прогресс
        self.progress = QSlider(Qt.Orientation.Horizontal, self)
        layout_main.addWidget(self.progress)

        self.progress.valueChanged.connect(self.on_progress_changed)
        self.progress.sliderMoved.connect(self.on_progress_moved)
        
        # Кнопки
        layou_ctrl = QHBoxLayout()
        layout_main.addLayout(layou_ctrl)

        self.btn_play = QPushButton("", self)
        self.btn_pause = QPushButton("", self)
        self.btn_stop = QPushButton("", self)
        
        self.btn_play.setIcon(QIcon("PlayVideo.png"))
        self.btn_pause.setIcon(QIcon("Pause.png"))
        self.btn_stop.setIcon(QIcon("Stop.png"))

        layou_ctrl.addWidget(self.btn_play)
        layou_ctrl.addWidget(self.btn_pause)
        layou_ctrl.addWidget(self.btn_stop)

        layou_ctrl.addStretch(1)

        self.speed = QComboBox(self)
        self.speed.addItems(("0.5", "1.0", "1.5", "2.0"))
        self.speed.setCurrentIndex(1)
        self.speed.currentIndexChanged.connect(self.on_speed_changed)
        layou_ctrl.addWidget(self.speed)

        # Звук
        self.sound = QSlider(Qt.Orientation.Horizontal, self)
        layou_ctrl.addWidget(self.sound)
        
        self.current_time = 0
        self.current_speed = 1
        
        # Инициализация GStreamer с задержкой
        self.pipeline = None
        self.videosink = None
        
        # Подключаем кнопки
        self.btn_play.clicked.connect(self.play_video)
        self.btn_pause.clicked.connect(self.pause_video)
        self.btn_stop.clicked.connect(self.stop_video)

    def init_gstreamer(self):
        """Инициализация GStreamer после показа окна"""
        try:
            # Используем xvimagesink вместо glimagesink
            #pipeline_str = "videotestsrc pattern=ball ! videoconvert ! xvimagesink name=sink"
            
            # Или для файла:
            pipeline_str = 'filesrc location="/home/anna/Загрузки/cat.mp4" ! decodebin ! videoconvert ! xvimagesink name=sink'
            
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            # Получаем handle окна
            wnd = get_window_handle(self.screen_wgt)
            if wnd == 0:
                print("Не удалось получить handle окна, пробуем позже...")
                QTimer.singleShot(100, self.retry_init)
                return
            
            print(f"Handle окна: {wnd}")
            
            self.videosink = self.pipeline.get_by_name("sink")
            if self.videosink:
                self.videosink.set_window_handle(wnd)
                print("Окно установлено в GStreamer")
            
            # Устанавливаем начальное состояние
            self.pipeline.set_state(Gst.State.PAUSED)
            
            # Запрашиваем длительность
            QTimer.singleShot(100, self.query_duration)
            
        except Exception as e:
            print(f"Ошибка инициализации GStreamer: {e}")
            import traceback
            traceback.print_exc()
    
    def retry_init(self):
        """Повторная попытка инициализации"""
        self.init_gstreamer()

    def query_duration(self):
        """Запрос длительности видео"""
        if self.pipeline:
            ok, state, pending = self.pipeline.get_state(50000000)  # 50ms timeout
            
            if ok == Gst.StateChangeReturn.SUCCESS and state == Gst.State.PAUSED:
                ok, duration = self.pipeline.query_duration(Gst.Format.TIME)
                if ok:
                    self.progress.setMaximum(int(duration / Gst.SECOND))
                    print(f"Длительность: {duration / Gst.SECOND} секунд")
                
                # Запускаем таймер обновления
                self.timer = QTimer()
                self.timer.timeout.connect(self.timerEvent)
                self.timer.start(100)

    def showEvent(self, event):
        """Обработка показа окна - инициализация GStreamer"""
        super().showEvent(event)
        # Ждем пока окно будет показано и готово
        QTimer.singleShot(100, self.init_gstreamer)
        
    def play_video(self):
        """Воспроизведение"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)
            if hasattr(self, 'timer'):
                self.timer.start(100)
    
    def pause_video(self):
        """Пауза"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
            if hasattr(self, 'timer'):
                self.timer.stop()
    
    def stop_video(self):
        """Остановка"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            if hasattr(self, 'timer'):
                self.timer.stop()
            self.progress.setValue(0)
    
    def on_progress_moved(self, value):
        """Перемещение слайдера"""
        if self.pipeline:
            print(f"Перемещение на {value} секунд")
            # Используем seek_simple для удобства
            self.pipeline.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                value * Gst.SECOND
            )
    
    def on_progress_changed(self, value):
        """Изменение значения слайдера"""
        # Можно оставить пустым или добавить логику
        pass
        
    def timerEvent(self):
        """Обновление таймера"""
        if self.pipeline:
            ok, state, pending = self.pipeline.get_state(0)
            if ok == Gst.StateChangeReturn.SUCCESS and state == Gst.State.PLAYING:
                ok, current = self.pipeline.query_position(Gst.Format.TIME)
                if ok:
                    self.current_time = current
                    self.progress.setValue(int(current / Gst.SECOND))
            
    def on_speed_changed(self, index):
        """Изменение скорости"""
        speeds = [0.5, 1.0, 1.5, 2.0]
        if index < len(speeds):
            self.current_speed = speeds[index]
            if self.pipeline and self.current_time > 0:
                # Изменение скорости воспроизведения
                self.pipeline.seek(
                    self.current_speed,
                    Gst.Format.TIME,
                    Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                    Gst.SeekType.SET,
                    self.current_time,
                    Gst.SeekType.END,
                    0
                )
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        if hasattr(self, 'timer'):
            self.timer.stop()
        event.accept()        