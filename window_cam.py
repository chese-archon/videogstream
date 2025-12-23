import os
import sys
import gi
import time
from datetime import datetime
from enum import Enum
from PyQt6.QtWidgets import (QApplication, QWidget, QMainWindow, QLabel, 
                           QVBoxLayout, QHBoxLayout, QSlider, QPushButton, 
                           QComboBox, QSpinBox, QLineEdit, QFileDialog, 
                           QMessageBox, QGroupBox)
from PyQt6.QtCore import Qt, QTimer, QEvent, QRect
from PyQt6.QtGui import QFont

# === КРИТИЧЕСКИ ВАЖНЫЕ НАСТРОЙКИ ===
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['GDK_BACKEND'] = 'x11'
os.environ['XDG_SESSION_TYPE'] = 'x11'
# os.environ['GST_DEBUG'] = '2'  # Отладка GStreamer

gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib, GstVideo

Gst.init(None)

class VideoSource(Enum):
    UDP_STREAM = "UDP поток"
    FILE = "Файл"
    TEST = "Тестовый источник"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Система видеонаблюдения")
        self.setGeometry(100, 100, 900, 700)
        
        # Переменные для управления видео
        self.pipeline = None
        self.video_sink = None
        self.is_playing = False
        self.zoom_factor = 1.0
        self.pan_x = 0.5
        self.pan_y = 0.5
        self.current_source = VideoSource.UDP_STREAM
        self.video_window_id = None
        
        # Переменные для записи
        self.record_pipeline = None
        self.is_recording = False
        self.record_file = ""
        self.tee_element = None  # Элемент для разделения потока
        
        # Инициализация UI
        self.init_ui()
        
        # Таймер для GLib событий
        self.glib_timer = QTimer()
        self.glib_timer.timeout.connect(self.process_glib_events)
        self.glib_timer.start(100)
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout()
        self.central_widget.setLayout(main_layout)
        
        # === ПАНЕЛЬ ПОДКЛЮЧЕНИЯ ===
        conn_group = QGroupBox("Подключение к видеопотоку")
        conn_layout = QVBoxLayout()
        
        # Выбор источника
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Источник:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems([source.value for source in VideoSource])
        self.source_combo.currentIndexChanged.connect(self.on_source_changed)
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
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        conn_layout.addWidget(self.connect_btn)
        
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)
        
        # === ОБЛАСТЬ ВИДЕО ===
        # Создаем контейнер для видео
        self.video_container = QWidget(self)
        self.video_container.setStyleSheet("""
            QWidget {
                background-color: black;
                border: 2px solid #444;
                min-width: 640px;
                min-height: 480px;
            }
        """)
        
        # QLabel для отображения статуса (будет скрыт при воспроизведении)
        self.video_status_label = QLabel(self.video_container)
        self.video_status_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-family: monospace;
                background-color: transparent;
            }
        """)
        self.video_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_status_label.setText(
            "ОЖИДАНИЕ ПОДКЛЮЧЕНИЯ\n\n"
            "Для запуска:\n"
            "1. Запустите сервер в терминале\n"
            "2. Нажмите 'Подключиться'\n"
            "3. Нажмите 'Воспроизвести'"
        )
        self.video_status_label.setGeometry(0, 0, 640, 480)
        
        main_layout.addWidget(self.video_container)
        
        # === ПАНЕЛЬ УПРАВЛЕНИЯ ===
        control_panel = QHBoxLayout()
        
        # Управление воспроизведением
        self.btn_play = QPushButton("Воспроизвести")
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_play.setEnabled(False)
        
        self.btn_pause = QPushButton("Пауза")
        self.btn_pause.clicked.connect(self.pause)
        self.btn_pause.setEnabled(False)
        
        self.btn_stop = QPushButton("Стоп")
        self.btn_stop.clicked.connect(self.stop)
        self.btn_stop.setEnabled(False)
        
        control_panel.addWidget(self.btn_play)
        control_panel.addWidget(self.btn_pause)
        control_panel.addWidget(self.btn_stop)
        
        control_panel.addStretch()
        
        # Масштабирование
        control_panel.addWidget(QLabel("Масштаб:"))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(50)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        control_panel.addWidget(self.zoom_label)
        
        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_out.setEnabled(False)
        control_panel.addWidget(self.btn_zoom_out)
        
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_in.setEnabled(False)
        control_panel.addWidget(self.btn_zoom_in)
        
        # Панорамирование
        control_panel.addWidget(QLabel("Панорамирование:"))
        self.btn_pan_left = QPushButton("←")
        self.btn_pan_left.clicked.connect(lambda: self.adjust_pan(-0.1, 0))
        self.btn_pan_left.setEnabled(False)
        control_panel.addWidget(self.btn_pan_left)
        
        self.btn_pan_right = QPushButton("→")
        self.btn_pan_right.clicked.connect(lambda: self.adjust_pan(0.1, 0))
        self.btn_pan_right.setEnabled(False)
        control_panel.addWidget(self.btn_pan_right)
        
        self.btn_pan_up = QPushButton("↑")
        self.btn_pan_up.clicked.connect(lambda: self.adjust_pan(0, -0.1))
        self.btn_pan_up.setEnabled(False)
        control_panel.addWidget(self.btn_pan_up)
        
        self.btn_pan_down = QPushButton("↓")
        self.btn_pan_down.clicked.connect(lambda: self.adjust_pan(0, 0.1))
        self.btn_pan_down.setEnabled(False)
        control_panel.addWidget(self.btn_pan_down)
        
        control_panel.addStretch()
        
        # Запись
        self.btn_record = QPushButton("Запись")
        self.btn_record.clicked.connect(self.toggle_record)
        self.btn_record.setEnabled(False)
        self.btn_record.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
        """)
        control_panel.addWidget(self.btn_record)
        
        self.record_label = QLabel("Не активна")
        control_panel.addWidget(self.record_label)
        
        main_layout.addLayout(control_panel)
        
        # === СТАТУСНАЯ СТРОКА ===
        self.status_label = QLabel("Готов к работе")
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: #e0e0e0;
                border-top: 1px solid #ccc;
                font-size: 11px;
                font-family: monospace;
            }
        """)
        main_layout.addWidget(self.status_label)
        
        # Обновляем видимость элементов
        self.on_source_changed(0)
    
    def get_window_handle(self):
        """Получение window handle для видео"""
        # Убеждаемся, что виджет отрисован
        self.video_container.repaint()
        QApplication.processEvents()
        
        # Получаем window handle
        win_id = self.video_container.winId()
        print(f"Window handle получен: {win_id}")
        return int(win_id)
    
    def showEvent(self, event):
        """Обработка события показа окна"""
        super().showEvent(event)
        # Ждем, пока окно будет показано
        QTimer.singleShot(100, self.delayed_init)
    
    def delayed_init(self):
        """Задержанная инициализация после показа окна"""
        self.video_window_id = self.get_window_handle()
        print(f"Window ID инициализирован: {self.video_window_id}")
    
    def on_source_changed(self, index):
        """Обработка изменения источника"""
        source_type = list(VideoSource)[index]
        
        # Показываем/скрываем соответствующие поля
        is_udp = (source_type == VideoSource.UDP_STREAM)
        
        self.udp_ip.setVisible(is_udp)
        self.udp_port.setVisible(is_udp)
        
        # Обновляем подписи
        parent = self.central_widget
        for i in range(parent.layout().count()):
            widget = parent.layout().itemAt(i).widget()
            if isinstance(widget, QLabel):
                if widget.text() == "IP:":
                    widget.setVisible(is_udp)
                elif widget.text() == "Порт:":
                    widget.setVisible(is_udp)
    
    def connect_source(self):
        """Подключение к источнику видео"""
        source_type = list(VideoSource)[self.source_combo.currentIndex()]
        
        if source_type == VideoSource.UDP_STREAM:
            success = self.create_udp_pipeline()
        elif source_type == VideoSource.FILE:
            success = self.create_file_pipeline()
        else:  # TEST
            success = self.create_test_pipeline()
        
        if success:
            self.connect_btn.setEnabled(False)
            self.connect_btn.setText("Подключено")
    
    def create_udp_pipeline(self):
        """Создание пайплайна для UDP потока с xvimagesink"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        
        ip = self.udp_ip.text().strip()
        port = self.udp_port.value()
        
        try:
            # Получаем window handle
            if self.video_window_id is None:
                self.video_window_id = self.get_window_handle()
            
            # Используем более сложный пайплайн с tee для записи и видео
            pipeline_str = (
                f'udpsrc port={port} ! '
                'application/x-rtp ! '
                'rtph264depay ! '
                'h264parse ! '
                'tee name=t ! '
                'queue ! '
                'decodebin ! '
                'videoconvert ! '
                'videoscale ! '
                'xvimagesink name=vsink '
                't. ! queue ! h264parse ! mux. '
                'avimux name=mux ! fakesink'
            )
            
            print("Создаем пайплайн для UDP потока:")
            print(f"   IP: {ip}, Порт: {port}")
            print(f"   Window ID: {self.video_window_id}")
            
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            if not self.pipeline:
                print("Не удалось создать пайплайн")
                self.status_label.setText("Ошибка: не удалось создать пайплайн")
                return False
            
            # Получаем элемент xvimagesink
            self.video_sink = self.pipeline.get_by_name("vsink")
            if self.video_sink:
                # Привязываем к окну PyQt
                self.video_sink.set_property("force-aspect-ratio", True)
                self.video_sink.set_window_handle(self.video_window_id)
                print("Видео привязано к окну PyQt")
            
            # Настраиваем обработку сообщений
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
            
            # Сразу запускаем в PAUSED
            ret = self.pipeline.set_state(Gst.State.PAUSED)
            print(f"Установка состояния PAUSED: {ret}")
            
            # Ждем немного для инициализации
            time.sleep(0.5)
            
            # Проверяем состояние
            state_result = self.pipeline.get_state(Gst.SECOND)
            print(f"Состояние пайплайна: {state_result}")
            
            if (state_result[0] == Gst.StateChangeReturn.SUCCESS or 
                state_result[0] == Gst.StateChangeReturn.NO_PREROLL):
                
                self.btn_play.setEnabled(True)
                self.btn_record.setEnabled(True)
                self.btn_zoom_in.setEnabled(True)
                self.btn_zoom_out.setEnabled(True)
                self.btn_pan_left.setEnabled(True)
                self.btn_pan_right.setEnabled(True)
                self.btn_pan_up.setEnabled(True)
                self.btn_pan_down.setEnabled(True)
                
                # Скрываем текстовый label
                self.video_status_label.hide()
                
                self.status_label.setText(f"Подключено к {ip}:{port}")
                print("Пайплайн успешно создан")
                return True
            else:
                print(f"Ошибка состояния: {state_result}")
                self.status_label.setText(f"Ошибка: {state_result[0]}")
                return False
                
        except Exception as e:
            error_msg = f"Ошибка создания пайплайна: {e}"
            print(f"{error_msg}")
            self.status_label.setText(f"Ошибка: {str(e)}")
            return False
    
    def create_file_pipeline(self):
        """Создание пайплайна для файла"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        
        # Показываем диалог выбора файла
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите видео файл",
            "",
            "Video files (*.mp4 *.avi *.mkv *.mov);;All files (*.*)"
        )
        
        if not filename or not os.path.exists(filename):
            QMessageBox.warning(self, "Ошибка", "Файл не найден")
            return False
        
        try:
            # Получаем window handle
            if self.video_window_id is None:
                self.video_window_id = self.get_window_handle()
            
            pipeline_str = (
                f'filesrc location="{filename}" ! '
                'decodebin ! '
                'videoconvert ! '
                'videoscale ! '
                'xvimagesink name=vsink'
            )
            
            print(f"Создаем файловый пайплайн: {pipeline_str}")
            
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            if not self.pipeline:
                self.status_label.setText("Ошибка: не удалось создать пайплайн")
                return False
            
            # Привязываем к окну
            self.video_sink = self.pipeline.get_by_name("vsink")
            if self.video_sink and self.video_window_id:
                self.video_sink.set_window_handle(self.video_window_id)
            
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
            
            ret = self.pipeline.set_state(Gst.State.PAUSED)
            
            if ret == Gst.StateChangeReturn.FAILURE:
                self.pipeline.set_state(Gst.State.NULL)
                self.pipeline = None
                return False
            
            time.sleep(0.5)
            state_result = self.pipeline.get_state(Gst.SECOND)
            
            if state_result[0] == Gst.StateChangeReturn.SUCCESS:
                self.btn_play.setEnabled(True)
                self.btn_record.setEnabled(False)  # Запись недоступна для файлов
                self.btn_zoom_in.setEnabled(True)
                self.btn_zoom_out.setEnabled(True)
                self.btn_pan_left.setEnabled(True)
                self.btn_pan_right.setEnabled(True)
                self.btn_pan_up.setEnabled(True)
                self.btn_pan_down.setEnabled(True)
                
                # Скрываем текстовый label
                self.video_status_label.hide()
                
                filename_display = os.path.basename(filename)
                self.status_label.setText(f"Загружен файл: {filename_display}")
                return True
            else:
                return False
                
        except Exception as e:
            self.status_label.setText(f"Ошибка: {str(e)}")
            return False
    
    def create_test_pipeline(self):
        """Создание тестового пайплайна"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        
        try:
            # Получаем window handle
            if self.video_window_id is None:
                self.video_window_id = self.get_window_handle()
            
            pipeline_str = (
                'videotestsrc pattern=ball ! '
                'videoconvert ! '
                'videoscale ! '
                'xvimagesink name=vsink'
            )
            
            print(f"Создаем тестовый пайплайн: {pipeline_str}")
            
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            if not self.pipeline:
                self.status_label.setText("Ошибка: не удалось создать пайплайн")
                return False
            
            # Привязываем к окну
            self.video_sink = self.pipeline.get_by_name("vsink")
            if self.video_sink and self.video_window_id:
                self.video_sink.set_window_handle(self.video_window_id)
            
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
            
            ret = self.pipeline.set_state(Gst.State.PAUSED)
            
            if ret == Gst.StateChangeReturn.FAILURE:
                self.pipeline.set_state(Gst.State.NULL)
                self.pipeline = None
                return False
            
            time.sleep(0.5)
            state_result = self.pipeline.get_state(Gst.SECOND)
            
            if state_result[0] == Gst.StateChangeReturn.SUCCESS:
                self.btn_play.setEnabled(True)
                self.btn_record.setEnabled(False)  # Запись недоступна для тестового источника
                self.btn_zoom_in.setEnabled(True)
                self.btn_zoom_out.setEnabled(True)
                self.btn_pan_left.setEnabled(True)
                self.btn_pan_right.setEnabled(True)
                self.btn_pan_up.setEnabled(True)
                self.btn_pan_down.setEnabled(True)
                
                # Скрываем текстовый label
                self.video_status_label.hide()
                
                self.status_label.setText("Тестовый источник активирован")
                return True
            else:
                return False
                
        except Exception as e:
            self.status_label.setText(f"Ошибка: {str(e)}")
            return False
    
    def apply_zoom_and_pan(self):
        """Применение масштаба и панорамирования к видео"""
        if not self.video_sink:
            return
        
        try:
            # Получаем размер контейнера
            container_width = self.video_container.width()
            container_height = self.video_container.height()
            
            if container_width <= 0 or container_height <= 0:
                return
            
            # Рассчитываем размер видео с учетом масштаба
            video_width = int(container_width / self.zoom_factor)
            video_height = int(container_height / self.zoom_factor)
            
            # Ограничиваем панорамирование
            self.pan_x = max(0.0, min(1.0, self.pan_x))
            self.pan_y = max(0.0, min(1.0, self.pan_y))
            
            # Рассчитываем смещение для панорамирования
            pan_offset_x = int((container_width - video_width) * self.pan_x)
            pan_offset_y = int((container_height - video_height) * self.pan_y)
            
            # Применяем к video sink
            self.video_sink.set_property("render-rectangle", 
                                        f"{pan_offset_x},{pan_offset_y},{video_width},{video_height}")
            
            print(f"Применен zoom: {self.zoom_factor:.2f}, pan: ({self.pan_x:.2f}, {self.pan_y:.2f})")
            print(f"  Размер: {video_width}x{video_height}, Смещение: {pan_offset_x},{pan_offset_y}")
            
        except Exception as e:
            print(f"Ошибка применения zoom/pan: {e}")
    
    def zoom_in(self):
        """Увеличение масштаба"""
        if self.zoom_factor < 3.0:
            self.zoom_factor = min(3.0, self.zoom_factor + 0.2)
            self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")
            self.apply_zoom_and_pan()
    
    def zoom_out(self):
        """Уменьшение масштаба"""
        if self.zoom_factor > 1.0:
            self.zoom_factor = max(1.0, self.zoom_factor - 0.2)
            self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")
            self.apply_zoom_and_pan()
    
    def adjust_pan(self, delta_x, delta_y):
        """Регулировка панорамирования"""
        self.pan_x += delta_x
        self.pan_y += delta_y
        self.apply_zoom_and_pan()
    
    def toggle_play(self):
        """Включение/выключение воспроизведения"""
        if not self.pipeline:
            return
        
        if not self.is_playing:
            # Запуск воспроизведения
            print("Запуск воспроизведения...")
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            print(f"   Результат: {ret}")
            
            if ret != Gst.StateChangeReturn.FAILURE:
                self.is_playing = True
                self.btn_play.setText("Пауза")
                self.btn_pause.setEnabled(True)
                self.btn_stop.setEnabled(True)
                self.status_label.setText("Воспроизведение...")
            else:
                print("Не удалось запустить воспроизведение")
                self.status_label.setText("Ошибка запуска")
        else:
            # Пауза
            self.pause()
    
    def pause(self):
        """Пауза воспроизведения"""
        if self.pipeline and self.is_playing:
            print("Пауза...")
            self.pipeline.set_state(Gst.State.PAUSED)
            self.is_playing = False
            self.btn_play.setText("Воспроизвести")
            self.btn_pause.setEnabled(False)
            self.status_label.setText("Пауза")
    
    def stop(self):
        """Остановка воспроизведения"""
        if self.pipeline:
            print("Остановка...")
            self.pipeline.set_state(Gst.State.NULL)
            self.is_playing = False
            self.btn_play.setText("Воспроизвести")
            self.btn_play.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_record.setEnabled(False)
            self.btn_zoom_in.setEnabled(False)
            self.btn_zoom_out.setEnabled(False)
            self.btn_pan_left.setEnabled(False)
            self.btn_pan_right.setEnabled(False)
            self.btn_pan_up.setEnabled(False)
            self.btn_pan_down.setEnabled(False)
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("Подключиться")
            self.status_label.setText("Остановлено")
            
            # Показываем текстовый label снова
            self.video_status_label.show()
            self.video_status_label.setText("Видео остановлено")
    
    def resizeEvent(self, event):
        """Обработка изменения размера окна"""
        super().resizeEvent(event)
        # Применяем масштаб и панорамирование при изменении размера
        if self.video_sink:
            QTimer.singleShot(100, self.apply_zoom_and_pan)
    
    def toggle_record(self):
        """Включение/выключение записи"""
        if not self.pipeline:
            return
        
        if not self.is_recording:
            # Начать запись
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить запись",
                f"record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi",
                "AVI files (*.avi)"
            )
            
            if filename:
                self.start_recording(filename)
        else:
            # Остановить запись
            self.stop_recording()
    
    def start_recording(self, filename):
        """Начать запись видео"""
        try:
            ip = self.udp_ip.text().strip()
            port = self.udp_port.value()
            
            # Создаем пайплайн записи, который читает из того же UDP источника
            # но НЕ останавливает основной пайплайн
            record_pipeline_str = (
                f'udpsrc port={port} ! '
                'application/x-rtp ! '
                'rtph264depay ! '
                'h264parse ! '
                'avimux ! '
                f'filesink location="{filename}"'
            )
            
            print(f"Начинаем запись: {filename}")
            print(f"   Пайплайн записи: {record_pipeline_str}")
            
            self.record_pipeline = Gst.parse_launch(record_pipeline_str)
            self.record_pipeline.set_state(Gst.State.PLAYING)
            
            self.is_recording = True
            self.record_file = filename
            self.btn_record.setText("Стоп запись")
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                }
            """)
            
            filename_display = os.path.basename(filename)
            self.record_label.setText(f"Запись: {filename_display}")
            self.status_label.setText(f"Запись: {filename_display}")
            
            print("Запись начата")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка записи", f"Не удалось начать запись: {e}")
    
    def stop_recording(self):
        """Остановить запись видео"""
        if self.record_pipeline and self.is_recording:
            try:
                print("Остановка записи...")
                # Отправляем EOS и ждем
                self.record_pipeline.send_event(Gst.Event.new_eos())
                
                # Ждем завершения записи
                bus = self.record_pipeline.get_bus()
                bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.EOS)
                
                time.sleep(0.5)
                self.record_pipeline.set_state(Gst.State.NULL)
                self.record_pipeline = None
                
            except Exception as e:
                print(f"Ошибка при остановке записи: {e}")
            
            finally:
                self.is_recording = False
                self.btn_record.setText("Запись")
                self.btn_record.setStyleSheet("""
                    QPushButton {
                        background-color: #f44336;
                        color: white;
                        font-weight: bold;
                    }
                """)
                self.record_label.setText("Не активна")
                self.status_label.setText(f"Запись сохранена: {self.record_file}")
                
                QMessageBox.information(
                    self,
                    "Запись завершена",
                    f"Видео сохранено в файл:\n{self.record_file}"
                )
    
    def on_bus_message(self, bus, message):
        """Обработка сообщений от GStreamer"""
        msg_type = message.type
        
        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            error_msg = f"GStreamer ошибка: {err.message}"
            print(f"{error_msg}")
            if debug:
                print(f"   Отладка: {debug}")
            self.status_label.setText(f"Ошибка: {err.message}")
            self.stop()
            
        elif msg_type == Gst.MessageType.EOS:
            print("Конец потока")
            self.status_label.setText("Конец потока")
            self.stop()
            
        elif msg_type == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            print(f"Предупреждение: {err.message}")
            
        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if isinstance(message.src, Gst.Pipeline):
                old, new, pending = message.parse_state_changed()
                print(f"Состояние пайплайна: {old} -> {new}")
                
        elif msg_type == Gst.MessageType.STREAM_START:
            print("Поток начался")
    
    def process_glib_events(self):
        """Обработка событий GLib (нужно для GStreamer)"""
        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(False)
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        print("Закрытие приложения...")
        
        if self.is_recording:
            self.stop_recording()
        
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        
        self.glib_timer.stop()
        event.accept()
        print("Приложение закрыто")