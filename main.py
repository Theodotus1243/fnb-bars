import sys
import os
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QPushButton, QProgressBar, QMessageBox, QColorDialog, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor, QPalette

from core import create_spectrum_video_generator

class RenderWorker(QThread):
    progress = Signal(int, int) # current, total
    status = Signal(str) # analyzing, rendering, done
    error = Signal(str)
    finished_render = Signal(str) # output_path

    def __init__(self, input_path, width, height, fps, n_bars, color_hex):
        super().__init__()
        self.input_path = input_path
        self.width = width
        self.height = height
        self.fps = fps
        self.n_bars = n_bars
        self.color_hex = color_hex

    def run(self):
        try:
            generator = create_spectrum_video_generator(
                input_path=self.input_path,
                width=self.width,
                height=self.height,
                fps=self.fps,
                n_bars=self.n_bars,
                preview=False, # Hardcoded to False as per architecture
                color_hex=self.color_hex
            )
            for status_update in generator:
                if status_update["status"] == "error":
                    self.error.emit(status_update["error_message"])
                    return
                elif status_update["status"] == "analyzing":
                    self.status.emit("Analyzing audio...")
                elif status_update["status"] == "rendering":
                    self.status.emit("Rendering video...")
                    self.progress.emit(status_update["progress"], status_update["total"])
                elif status_update["status"] == "done":
                    self.finished_render.emit(status_update["output_path"])
        except Exception as e:
            self.error.emit(str(e))

class DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setLineWidth(2)
        
        layout = QVBoxLayout()
        self.label = QLabel("Drag & Drop\nAudio File Here\n(.mp3 or .wav)")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("font-size: 16pt; color: gray;")
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.setStyleSheet("DropZone { background-color: #f0f0f0; border: 2px dashed #aaa; border-radius: 10px; }")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) > 1:
                event.ignore()
                return
            
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.mp3', '.wav')):
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) > 1:
            QMessageBox.warning(self, "Error", "Please drop only one file at a time.")
            return

        file_path = urls[0].toLocalFile()
        if file_path.lower().endswith(('.mp3', '.wav')):
            self.file_dropped.emit(file_path)
        else:
            QMessageBox.warning(self, "Error", "Unsupported file type. Please drop an .mp3 or .wav file.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Load version
        try:
            with open("VERSION", "r") as f:
                self.version = f.read().strip()
        except:
            self.version = "dev"
        
        # Build number (will be injected by GitHub Actions or show 'local')
        self.build_num = os.getenv("GITHUB_RUN_NUMBER", "local")
        
        self.setWindowTitle(f"F&B's Bars v{self.version}-b{self.build_num}")
        self.setMinimumSize(600, 400)

        # Default settings
        self.current_color = "#FFD700"

        # Main Widget and Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Left Side - Settings Panel
        settings_layout = QVBoxLayout()
        settings_layout.setAlignment(Qt.AlignTop)
        
        settings_label = QLabel("<b>Settings</b>")
        settings_layout.addWidget(settings_label)

        # Width
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))
        self.spin_width = QSpinBox()
        self.spin_width.setRange(100, 3840)
        self.spin_width.setValue(800)
        width_layout.addWidget(self.spin_width)
        settings_layout.addLayout(width_layout)

        # Height
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height:"))
        self.spin_height = QSpinBox()
        self.spin_height.setRange(100, 2160)
        self.spin_height.setValue(600)
        height_layout.addWidget(self.spin_height)
        settings_layout.addLayout(height_layout)

        # FPS
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 144)
        self.spin_fps.setValue(30)
        fps_layout.addWidget(self.spin_fps)
        settings_layout.addLayout(fps_layout)

        # Number of Bars
        bars_layout = QHBoxLayout()
        bars_layout.addWidget(QLabel("Bars:"))
        self.spin_bars = QSpinBox()
        self.spin_bars.setRange(1, 128)
        self.spin_bars.setValue(16)
        bars_layout.addWidget(self.spin_bars)
        settings_layout.addLayout(bars_layout)

        # Color Picker
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(30, 30)
        self.update_color_button()
        self.btn_color.clicked.connect(self.choose_color)
        color_layout.addWidget(self.btn_color)
        color_layout.addStretch()
        settings_layout.addLayout(color_layout)

        main_layout.addLayout(settings_layout, 1)

        # Right Side - Drag & Drop and Progress
        right_layout = QVBoxLayout()
        
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.start_processing)
        right_layout.addWidget(self.drop_zone, 3)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        right_layout.addWidget(self.progress_bar)
        
        self.eta_label = QLabel("")
        self.eta_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.eta_label)

        main_layout.addLayout(right_layout, 3)

        self.worker = None
        self.start_time = 0

    def update_color_button(self):
        self.btn_color.setStyleSheet(f"background-color: {self.current_color}; border: 1px solid black;")

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.current_color), self, "Select Bar Color")
        if color.isValid():
            self.current_color = color.name()
            self.update_color_button()

    def start_processing(self, file_path):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(self, "Warning", "A file is already being processed.")
            return

        # Disable inputs
        self.spin_width.setEnabled(False)
        self.spin_height.setEnabled(False)
        self.spin_fps.setEnabled(False)
        self.spin_bars.setEnabled(False)
        self.btn_color.setEnabled(False)
        self.drop_zone.setEnabled(False)

        self.progress_bar.setValue(0)
        self.eta_label.setText("")
        self.status_label.setText("Starting...")
        self.start_time = time.time()

        self.worker = RenderWorker(
            input_path=file_path,
            width=self.spin_width.value(),
            height=self.spin_height.value(),
            fps=self.spin_fps.value(),
            n_bars=self.spin_bars.value(),
            color_hex=self.current_color
        )
        self.worker.status.connect(self.update_status)
        self.worker.progress.connect(self.update_progress)
        self.worker.error.connect(self.handle_error)
        self.worker.finished_render.connect(self.handle_finished)
        self.worker.start()

    @Slot(str)
    def update_status(self, text):
        self.status_label.setText(text)
        if text == "Analyzing audio...":
            self.progress_bar.setRange(0, 0) # Indeterminate progress

    @Slot(int, int)
    def update_progress(self, current, total):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)

        # Calculate ETA
        elapsed = time.time() - self.start_time
        if current > 0:
            rate = current / elapsed
            remaining_frames = total - current
            eta_seconds = remaining_frames / rate
            mins, secs = divmod(int(eta_seconds), 60)
            self.eta_label.setText(f"ETA: {mins:02d}:{secs:02d}")

    @Slot(str)
    def handle_error(self, error_msg):
        self.reset_ui()
        QMessageBox.critical(self, "Error", error_msg)

    @Slot(str)
    def handle_finished(self, output_path):
        self.reset_ui()
        self.status_label.setText("Ready")
        self.progress_bar.setValue(self.progress_bar.maximum())
        QMessageBox.information(self, "Success", f"Video successfully created:\n{output_path}")

    def reset_ui(self):
        self.spin_width.setEnabled(True)
        self.spin_height.setEnabled(True)
        self.spin_fps.setEnabled(True)
        self.spin_bars.setEnabled(True)
        self.btn_color.setEnabled(True)
        self.drop_zone.setEnabled(True)
        self.eta_label.setText("")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
