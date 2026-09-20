import sys
import threading
import traceback
import time
import hashlib
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageOps

from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer, QSize, QRect, QEvent
from PySide6.QtGui import QColor, QPainter, QPixmap, QImageReader, QDesktopServices, QIcon
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QFileDialog, QListWidget, QComboBox,
    QProgressBar, QLineEdit, QCheckBox, QSlider, QFrame, QMessageBox,
    QScrollArea, QSizePolicy, QLayout, QPlainTextEdit, QDialog, QTabWidget,
    QSplitter, QStyledItemDelegate, QStyleOptionViewItem)

from engine import ROOT, MODELS, MODEL_DESCRIPTIONS, EXTENSIONS, Cancelled, load_model, upscale, save_output
from monitoring import ResourceMonitor, duration
from help_dialog import HelpDialog

APP_TITLE = 'HMR Studio • Upscale'
APP_ICON = ROOT / 'assets' / 'hmr-upscale.ico'

STYLE = '''
QWidget { background: #101318; color: #e9edf3; font: 10pt 'Segoe UI'; }
QMainWindow { background: #101318; }
QLabel#eyebrow { color: #75e2bf; font-size: 9pt; font-weight: 700; }
QLabel#title { font-size: 27pt; font-weight: 650; }
QLabel#muted { color: #949da9; }
QLabel#section { font-weight: 650; font-size: 11pt; }
QFrame#panel { background: #191e25; border: 1px solid #2a323c; border-radius: 12px; }
QFrame#panel QLabel, QFrame#panel QCheckBox { background: transparent; }
QPushButton { background: #252d38; border: 1px solid #374250; border-radius: 7px; padding: 10px 15px; min-height: 18px; }
QPushButton:hover { background: #344150; }
QPushButton:checked { background: #294b40; border: 1px solid #79e4bf; color: #9aefd2; }
QPushButton:disabled { color: #65707d; background: #1c222a; border-color: #282e36; }
QPushButton#primary { background: #79e4bf; color: #10251e; font-weight: 700; border: 0; }
QPushButton#primary:hover { background: #9aefd2; }
QPushButton#primary:disabled { background: #334b44; color: #79988d; }
QComboBox, QLineEdit { background: #11161c; border: 1px solid #38424f; border-radius: 6px; padding: 9px; min-height: 18px; }
QComboBox QAbstractItemView { background: #202832; selection-background-color: #39574e; }
QListWidget { background: #13181f; border: 1px solid #2a323c; border-radius: 7px; padding: 4px; }
QListWidget::item { padding: 10px; border-bottom: 1px solid #242c36; }
QListWidget::item:selected { background: #29443d; color: #9bf0d2; border-radius: 4px; }
QProgressBar { background: #252d37; border: none; border-radius: 4px; height: 8px; color: transparent; }
QProgressBar::chunk { background: #79e4bf; border-radius: 4px; }
QSlider::groove:horizontal { height: 4px; background: #36414e; }
QSlider::handle:horizontal { background: #79e4bf; width: 14px; margin: -5px 0; border-radius: 7px; }
QToolTip { color: white; background: #293440; border: 1px solid #596575; }
QTabWidget::pane { border: 1px solid #2a323c; border-radius: 8px; }
QTabBar::tab { background: #1b222b; color: #9ca8b5; padding: 11px 17px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { background: #253b34; color: #9aefd2; border-bottom-color: #79e4bf; }
QCheckBox { spacing: 10px; min-height: 26px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #627181; border-radius: 4px; background: #11161c; }
QCheckBox::indicator:checked { background: #79e4bf; border: 3px solid #386a57; }
QCheckBox::indicator:disabled { background: #202831; border-color: #3a424c; }
QScrollBar:vertical { background: #141a21; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #475464; min-height: 35px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
'''

class QueueDelegate(QStyledItemDelegate):
    remove_requested = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.removal_enabled = True

    @staticmethod
    def remove_rect(rect):
        return QRect(rect.right()-29, rect.center().y()-11, 22, 22)

    def paint(self, painter, option, index):
        text_option = QStyleOptionViewItem(option)
        text_option.rect.adjust(0, 0, -30, 0)
        super().paint(painter, text_option, index)
        painter.save()
        painter.setPen(QColor('#aebbc8' if self.removal_enabled else '#495461'))
        painter.drawText(self.remove_rect(option.rect), Qt.AlignCenter, '×')
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(180, 48)

    def editorEvent(self, event, model, option, index):
        if (self.removal_enabled and event.type() == QEvent.MouseButtonRelease
                and event.button() == Qt.LeftButton and self.remove_rect(option.rect).contains(event.pos())):
            self.remove_requested.emit(index.data(Qt.UserRole))
            return True
        return super().editorEvent(event, model, option, index)


class Preview(QWidget):
    def __init__(self):
        super().__init__()
        self.before = QPixmap()
        self.after = QPixmap()
        self.split = .5
        self.setMinimumSize(350, 180)

    def read(self, path):
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            size.scale(1800, 1800, Qt.KeepAspectRatio)
            reader.setScaledSize(size)
        return QPixmap.fromImage(reader.read())

    def show_images(self, source=None, result=None):
        self.before = self.read(source) if source else QPixmap()
        self.after = self.read(result) if result else QPixmap()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor('#141a21'))
        if self.before.isNull():
            painter.setPen(QColor('#8c99a9'))
            painter.drawText(self.rect(), Qt.AlignCenter, 'A little more detail.\nA lot more possibility.\n\nDrop images here or choose Add images')
            return
        size = self.before.size()
        size.scale(self.size(), Qt.KeepAspectRatio)
        x, y = (self.width()-size.width())//2, (self.height()-size.height())//2
        from PySide6.QtCore import QRect
        rect = QRect(x, y, size.width(), size.height())
        painter.drawPixmap(rect, self.before)
        if not self.after.isNull():
            # Slider value is the proportion of the upscaled image revealed.
            divider = x + int(size.width() * (1 - self.split))
            painter.save()
            painter.setClipRect(divider, y, x+size.width()-divider, size.height())
            painter.drawPixmap(rect, self.after)
            painter.restore()
            if 0 < self.split < 1:
                painter.setPen(QColor('#79e4bf'))
                painter.drawLine(divider, y, divider, y+size.height())

class DeviceProbe(QThread):
    ready = Signal(bool, str)
    def run(self):
        try:
            import torch
            available = torch.cuda.is_available()
            self.ready.emit(available, torch.cuda.get_device_name(0) if available else 'CUDA unavailable · CPU mode')
        except Exception as error:
            self.ready.emit(False, str(error))

class Worker(QThread):
    status = Signal(str)
    progress = Signal(int)
    completed = Signal(str, str)
    failed = Signal(str, str)
    summary = Signal(str)
    detail = Signal(dict)
    diagnostic = Signal(str)
    def __init__(self, files, options):
        super().__init__()
        self.files, self.options = files, options
        self.cancel = threading.Event()

    def run(self):
        successes = failures = 0
        model = None
        portrait = None
        colorizer = repair = protector = None
        try:
            o = self.options
            from restoration import Colorizer, DamageRepair, FaceProtector, enhance_detail
            if o.get('upscale_enabled', True):
                model = load_model(o['model'], o['device'], o['half'], self.status.emit, self.cancel.is_set)
            if o.get('colorize'):
                colorizer = Colorizer(o['device'], self.status.emit, self.cancel.is_set)
            if o.get('repair'):
                repair = DamageRepair(o['device'], self.status.emit, self.cancel.is_set)
            if o.get('detail') or o.get('hyper'):
                protector = FaceProtector(o['device'], self.status.emit, self.cancel.is_set)
            if o.get('portrait', 0):
                from portrait import PortraitRestorer
                portrait = PortraitRestorer(o['device'], self.status.emit, self.cancel.is_set)
            for index, source in enumerate(self.files):
                if self.cancel.is_set():
                    raise Cancelled()
                self.status.emit(f'{index+1} / {len(self.files)} · {source.name}')
                self.detail.emit(dict(stage='Reading image', file=index+1, count=len(self.files), eta=None))
                try:
                    with Image.open(source) as original:
                        if original.mode.startswith('I') or original.mode == 'F':
                            raise ValueError('16-bit/float images are not supported. Convert to 8-bit RGB first.')
                        working = ImageOps.exif_transpose(original)
                        working.load()
                    if working.width * working.height > 120_000_000:
                        raise ValueError('Source exceeds the 120 MP processing limit.')
                    def stage(message):
                        self.status.emit(message)
                        self.detail.emit(dict(stage=message, file=index+1, count=len(self.files), eta=None))
                    if repair is not None:
                        mask_path = o.get('masks', {}).get(str(source))
                        if not mask_path:
                            raise ValueError('No damage mask for this image. Select it and choose Edit damage mask.')
                        stage('Repairing marked tears, scratches and missing regions…')
                        with Image.open(mask_path) as mask:
                            working = repair.apply(working, mask, self.cancel.is_set)
                    if colorizer is not None:
                        stage('Colorizing image…')
                        working = colorizer.apply(working, self.cancel.is_set)
                    tile_started = None
                    def report(info):
                        nonlocal tile_started
                        now = time.monotonic()
                        if info['stage'] == 'Upscaling' and info['done'] == 0:
                            tile_started = now
                        done, total = info['done'], info['total']
                        eta = ((now-tile_started) / done * (total-done)
                               if tile_started is not None and 0 < done < total else None)
                        self.detail.emit(dict(info, file=index+1, count=len(self.files), eta=eta))
                    if model is not None:
                        result = upscale(working, model, o['scale'], o['tile'],
                            lambda p: self.progress.emit(min(99, int(100 * (index+p) / len(self.files)))),
                            self.cancel.is_set, report, cleanup=o.get('cleanup', False))
                    else:
                        result = working.copy()
                    if self.cancel.is_set():
                        raise Cancelled()
                    if protector is not None:
                        stage('Enhancing texture outside detected faces…')
                        protected = protector.mask(result, self.status.emit, self.cancel.is_set)
                        result = enhance_detail(result, protected, hyper=o.get('hyper', False))
                    if portrait is not None:
                        self.detail.emit(dict(stage='Restoring portrait', file=index+1, count=len(self.files), eta=None))
                        result = portrait.restore(working, result, o['portrait'], self.status.emit, self.cancel.is_set)
                    if self.cancel.is_set():
                        raise Cancelled()
                    self.status.emit(f'Saving {source.name}…')
                    self.detail.emit(dict(stage='Saving image', file=index+1, count=len(self.files), eta=None))
                    saved = save_output(result, source, o['folder'], o['scale'], o['format'],
                                        metadata={**{k: v for k, v in o.items() if k != 'masks'},
                                                  'source': source.name, 'repair_mask': o.get('masks', {}).get(str(source)),
                                                  'engine_revision': 4})
                    self.completed.emit(str(source), str(saved))
                    successes += 1
                except Cancelled:
                    raise
                except Exception as error:
                    self.diagnostic.emit(traceback.format_exc())
                    failures += 1
                    message = str(error)
                    if 'out of memory' in message.lower():
                        message = 'GPU memory is full. Choose a smaller tile size (128 or 64) and retry.'
                    self.failed.emit(str(source), message)
                self.progress.emit(int(100 * (index+1) / len(self.files)))
            self.summary.emit(f'Finished · {successes} saved' + (f' · {failures} failed (select a file for details)' if failures else ''))
        except Cancelled:
            self.summary.emit(f'Cancelled · {successes} saved')
        except Exception as error:
            self.diagnostic.emit(traceback.format_exc())
            self.summary.emit(f'Unable to start: {error}')
        finally:
            del model
            del portrait
            del colorizer, repair, protector
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

def label(text, kind=None):
    item = QLabel(text)
    if kind:
        item.setObjectName(kind)
    item.setWordWrap(True)
    item.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    return item

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.resize(1440, 920)
        self.setMinimumSize(1160, 760)
        self.setAcceptDrops(True)
        self.worker = None
        self.damage_masks = {}
        self.portrait_snapshot = None
        self.started_at = None
        self.latest_detail = {}
        self.results, self.errors = {}, {}
        self.settings = QSettings('HMR Technologies', 'HMR Upscale')
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        header = QHBoxLayout()
        header.addWidget(label(APP_TITLE, 'section'), 1)
        self.gpu = label('Checking graphics card…', 'muted')
        header.addWidget(self.gpu)
        self.help_button = QPushButton('Help')
        self.help_button.setShortcut('F1')
        self.help_button.setToolTip('Documentation and About HMR Studio (F1)')
        self.help_button.clicked.connect(self.show_help)
        header.addWidget(self.help_button)
        outer.addLayout(header)
        resources = QHBoxLayout()
        self.cpu_readout = label('CPU  ·  measuring…', 'eyebrow')
        self.gpu_readout = label('GPU  ·  measuring…', 'eyebrow')
        self.vram_readout = label('VRAM  ·  measuring…', 'eyebrow')
        self.ram_readout = label('RAM  ·  measuring…', 'eyebrow')
        for readout in (self.cpu_readout, self.gpu_readout, self.vram_readout, self.ram_readout):
            readout.setToolTip('Live system-wide usage, including other applications. GPU readings refer to NVIDIA GPU 0.')
            resources.addWidget(readout, 1)
        outer.addLayout(resources)
        self.columns = QSplitter(Qt.Horizontal)
        self.columns.setChildrenCollapsible(False)
        self.columns.setHandleWidth(10)
        outer.addWidget(self.columns, 1)
        preview_column = QWidget()
        preview_column.setMinimumWidth(350)
        left = QVBoxLayout(preview_column)
        left.setContentsMargins(0, 0, 8, 0)
        left.setSpacing(12)
        self.columns.addWidget(preview_column)
        left.addWidget(label('01  /  ORIGINAL & UPSCALED', 'section'))
        queue_column = QWidget()
        queue_column.setMinimumWidth(230)
        middle = QVBoxLayout(queue_column)
        middle.setContentsMargins(8, 0, 8, 0)
        middle.setSpacing(12)
        self.columns.addWidget(queue_column)
        self.queue_title = label('02  /  IMAGES · 0', 'section')
        middle.addWidget(self.queue_title)
        bar = QHBoxLayout()
        self.add_button = QPushButton('+  Add images')
        self.add_button.clicked.connect(self.add_dialog)
        self.clear_button = QPushButton('Clear')
        self.clear_button.clicked.connect(self.clear)
        bar.addWidget(self.add_button)
        bar.addWidget(self.clear_button)
        middle.addLayout(bar)
        self.preview = Preview()
        left.addWidget(self.preview, 1)
        compare = QHBoxLayout()
        compare.addWidget(label('ORIGINAL', 'muted'))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.setEnabled(False)
        self.slider.setToolTip('Left: original only. Right: upscaled only. Middle: compare both.')
        self.slider.valueChanged.connect(self.slide)
        compare.addWidget(self.slider, 1)
        compare.addWidget(label('UPSCALED', 'eyebrow'))
        left.addLayout(compare)
        self.detail = label('PNG, JPG, WebP, BMP, TIFF · drag and drop supported', 'muted')
        self.detail.setMaximumHeight(55)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        left.addWidget(self.detail)
        self.queue = QListWidget()
        self.queue.setMinimumHeight(120)
        self.queue.setTextElideMode(Qt.ElideMiddle)
        self.queue_delegate = QueueDelegate(self.queue)
        self.queue.setItemDelegate(self.queue_delegate)
        self.queue_delegate.remove_requested.connect(self.remove_image)
        self.queue.currentRowChanged.connect(self.selection)
        middle.addWidget(self.queue, 1)
        middle.addWidget(label('Click × to remove from the list.\nOriginal files are kept.', 'muted'))
        settings_column = QWidget()
        settings_column.setMinimumWidth(350)
        settings_layout = QVBoxLayout(settings_column)
        settings_layout.setContentsMargins(8, 0, 0, 0)
        settings_layout.setSpacing(12)
        settings_layout.addWidget(label('03  /  FEATURES', 'section'))
        self.settings_tabs = QTabWidget()
        settings_layout.addWidget(self.settings_tabs, 1)
        self.columns.addWidget(settings_column)
        self.columns.setStretchFactor(0, 3)
        self.columns.setStretchFactor(1, 1)
        self.columns.setStretchFactor(2, 1)
        self.columns.setSizes([650, 300, 390])

        def page(title):
            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setContentsMargins(16, 18, 16, 18)
            layout.setSpacing(9)
            layout.setSizeConstraint(QLayout.SetMinimumSize)
            scroller = QScrollArea()
            scroller.setWidgetResizable(True)
            scroller.setFrameShape(QFrame.NoFrame)
            scroller.setWidget(content)
            self.settings_tabs.addTab(scroller, title)
            return layout

        def section(layout, title):
            heading = label(title, 'eyebrow')
            layout.addWidget(heading)

        def field(layout, title, widget):
            if isinstance(widget, QComboBox):
                widget.setMinimumContentsLength(12)
                widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            row = QHBoxLayout()
            caption = label(title, 'muted')
            caption.setFixedWidth(78)
            row.addWidget(caption)
            row.addWidget(widget, 1)
            layout.addLayout(row)

        enhance = page('Enhance')
        faces = page('Faces')
        restore = page('Restore')
        output = page('Output')
        section(faces, 'PORTRAIT')
        self.portrait_preset = QPushButton('Portrait preset · OFF')
        self.portrait_preset.setCheckable(True)
        self.portrait_preset.toggled.connect(self.toggle_portrait_preset)
        self.portrait_preset.setToolTip('Enable recommended portrait settings. Disable to restore your previous settings.')
        faces.addWidget(self.portrait_preset)
        self.face_enhancer = QCheckBox('Face enhancer')
        self.face_enhancer.setToolTip('GFPGAN face restoration can reconstruct or change facial features.')
        faces.addWidget(self.face_enhancer)
        self.portrait_strength = QComboBox()
        for title, strength in [('Off', 0), ('Gentle · 60%', .6), ('Strong · 85%', .85), ('Maximum · 100%', 1.0)]:
            self.portrait_strength.addItem(title, strength)
        self.portrait_strength.setCurrentIndex(2)
        field(faces, 'Face restoration strength', self.portrait_strength)

        faces.addWidget(label('Face restoration may reconstruct or change features. Compare with your original.', 'muted'))
        faces.addStretch()

        section(enhance, 'UPSCALE')
        self.upscale_enabled = QCheckBox('AI upscaling')
        self.upscale_enabled.setChecked(True)
        enhance.addWidget(self.upscale_enabled)
        self.model = QComboBox()
        self.model.addItems(MODELS)
        for index, name in enumerate(MODELS):
            self.model.setItemData(index, MODEL_DESCRIPTIONS[name], Qt.ToolTipRole)
        field(enhance, 'Model', self.model)
        self.model_hint = QLabel(MODEL_DESCRIPTIONS[self.model.currentText()])
        self.model_hint.setWordWrap(True)
        self.model_hint.setObjectName('muted')
        enhance.addWidget(self.model_hint)
        self.model.currentTextChanged.connect(lambda name: self.model_hint.setText(MODEL_DESCRIPTIONS[name]))
        self.scale = QComboBox()
        self.scale.addItems(['2×', '3×', '4×'])
        self.scale.setCurrentIndex(2)
        self.scale.setToolTip('A scale different from the model’s native scale is resized after AI enhancement.')
        field(enhance, 'Output size', self.scale)
        self.cleanup = QCheckBox('Clean compressed input')
        self.cleanup.setToolTip('Processes a 50% resized source to reduce old compression artifacts. Can soften detail; leave off for clean originals.')
        enhance.addWidget(self.cleanup)

        section(enhance, 'TEXTURE')
        self.detail_enabled = QCheckBox('Detail enhancement')
        self.hyper = QCheckBox('Hyper-realistic detail')
        self.detail_enabled.setToolTip('Enhances texture outside detected faces.')
        self.hyper.setToolTip('Stronger texture and local contrast outside detected faces. Does not generate missing objects.')
        enhance.addWidget(self.detail_enabled)
        enhance.addWidget(self.hyper)
        enhance.addWidget(label('Both detail modes protect detected faces.', 'muted'))
        enhance.addStretch()

        section(restore, 'COLOR')
        self.colorize = QCheckBox('Colorization preset')
        self.colorize.setToolTip('Predict colors for black-and-white images. Replaces existing colors.')
        restore.addWidget(self.colorize)
        restore.addWidget(label('Adds predicted colors to black-and-white photos.', 'muted'))
        section(restore, 'DAMAGE REPAIR')
        self.repair_enabled = QCheckBox('Repair tears, scratches and holes')
        restore.addWidget(self.repair_enabled)
        self.mask_button = QPushButton('Edit damage mask')
        self.mask_button.setToolTip('Paint damage on the selected image. Each queued image needs its own mask.')
        self.mask_button.clicked.connect(self.edit_damage_mask)
        restore.addWidget(self.mask_button)
        restore.addWidget(label('Select an image, then paint over the areas to repair. Unmarked areas are preserved by this stage.', 'muted'))
        restore.addWidget(label('Large missing regions may need further editing.', 'muted'))
        restore.addStretch()

        section(output, 'PROCESSING')
        self.device = QComboBox()
        self.device.addItems(['NVIDIA CUDA', 'CPU (slower)'])
        field(output, 'Device', self.device)
        self.tile = QComboBox()
        self.tile.addItems(['64', '128', '256', '512'])
        self.tile.setCurrentText('256')
        self.tile.setToolTip('Smaller tiles use less GPU memory. Start at 256; try 128 or 64 if memory fills up.')
        field(output, 'Tile size', self.tile)
        self.half = QCheckBox('FP16 acceleration')
        self.half.setToolTip('Faster half-precision processing for supported CUDA upscaling models.')
        self.half.setChecked(True)
        output.addWidget(self.half)
        section(output, 'SAVE RESULTS')
        self.format = QComboBox()
        self.format.addItems(['PNG · preserve transparency', 'JPEG · white background'])
        field(output, 'File format', self.format)
        self.folder = QLineEdit(self.settings.value('folder', str(ROOT / 'output')))
        self.folder.setCursorPosition(0)
        self.folder.setToolTip(self.folder.text())
        self.folder.textChanged.connect(self.folder.setToolTip)
        field(output, 'Output folder', self.folder)
        self.browse = QPushButton('Browse folder…')
        self.browse.clicked.connect(self.choose_folder)
        output.addWidget(self.browse)
        output.addWidget(label('Originals are kept. Existing files are never overwritten.', 'muted'))
        output.addStretch()
        self.status = label('Ready when you are. Add an image to get started.', 'muted')
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.status)
        self.timing = label('Queue 0%  ·  Elapsed 00m 00s  ·  Image ETA —', 'muted')
        self.timing.setToolTip('ETA estimates remaining AI tile processing for the current image. Model loading, final resizing and saving are not included.')
        outer.addWidget(self.timing)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.progress.setTextVisible(False)
        outer.addWidget(self.progress)
        self.activity = QPlainTextEdit()
        self.activity.setReadOnly(True)
        self.activity.setMaximumBlockCount(2000)
        self.activity.setFixedHeight(100)
        self.activity.setPlaceholderText('Activity and errors appear here. Select text to copy details.')
        self.activity.setStyleSheet('QPlainTextEdit { background: #13181f; border: 1px solid #2a323c; border-radius: 6px; padding: 6px; }')
        outer.addWidget(self.activity)
        footer = QHBoxLayout()
        self.open_button = QPushButton('Open output folder')
        self.open_button.clicked.connect(self.open_folder)
        footer.addWidget(self.open_button)
        footer.addStretch()
        self.stop = QPushButton('Cancel')
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.cancel)
        footer.addWidget(self.stop)
        self.start = QPushButton('Process images  ↗')
        self.start.setObjectName('primary')
        self.start.setMinimumWidth(210)
        self.start.setEnabled(False)
        self.start.clicked.connect(self.run_batch)
        footer.addWidget(self.start)
        outer.addLayout(footer)
        self.probe = DeviceProbe()
        self.probe.ready.connect(self.device_ready)
        self.probe.start()
        self.monitor = ResourceMonitor()
        self.monitor.reading.connect(self.resource_reading)
        self.monitor.start()
        self.clock = QTimer(self)
        self.clock.setInterval(500)
        self.clock.timeout.connect(self.update_timing)
        for feature in [self.upscale_enabled, self.face_enhancer, self.repair_enabled]:
            feature.toggled.connect(self.refresh_feature_controls)
        self.refresh_feature_controls()

    def resource_reading(self, data):
        cpu, gpu = data.get('cpu'), data.get('gpu')
        self.cpu_readout.setText(f'CPU  ·  {cpu:.0f}%' if cpu is not None else 'CPU  ·  unavailable')
        gpu_text = f'GPU  ·  {gpu:.0f}%' if gpu is not None else 'GPU  ·  unavailable'
        used, total = data.get('vram_used'), data.get('vram_total')
        self.vram_readout.setText(f'VRAM  ·  {used/1024:.1f}/{total/1024:.1f} GB'
                                  if used is not None and total is not None else 'VRAM  ·  unavailable')
        self.gpu_readout.setText(gpu_text)
        self.ram_readout.setText(f'RAM  ·  {data["ram"]:.0f}%  ·  {data["ram_used"]:.1f}/{data["ram_total"]:.1f} GB'
                                 if 'ram' in data else 'RAM  ·  unavailable')

    def log(self, message):
        self.activity.appendPlainText(f'[{datetime.now():%H:%M:%S}] {message}')

    def status_update(self, message):
        self.status.setText(message)
        self.log(message)

    def diagnostic(self, text):
        try:
            with (ROOT / 'error.log').open('a', encoding='utf-8') as output:
                output.write(f'\n[{datetime.now().isoformat()}]\n{text}')
        except OSError:
            self.log('Could not write error.log; error details remain in this window.')

    def processing_detail(self, info):
        old_stage = self.latest_detail.get('stage')
        self.latest_detail = dict(info, received=time.monotonic())
        if info['stage'] != old_stage:
            self.log(f'Image {info["file"]}/{info["count"]}: {info["stage"]}')
        self.update_timing()

    def update_timing(self):
        if self.started_at is None:
            return
        info = self.latest_detail
        elapsed = duration(time.monotonic() - self.started_at)
        eta = info.get('eta')
        eta_text = 'calculating…' if info.get('stage') == 'Upscaling' else '—'
        if eta is not None:
            remaining = max(0, eta - (time.monotonic() - info['received']))
            eta_text = ('~' + duration(remaining)) if remaining >= 1 else 'finishing tile…'
        stage = info.get('stage', 'Preparing model')
        tiles = f' · Tile {info["done"]}/{info["total"]}' if 'total' in info else ''
        file = f' · Image {info["file"]}/{info["count"]}' if 'file' in info else ''
        self.timing.setText(f'Queue {self.progress.value()}%{file} · {stage}{tiles} · Elapsed {elapsed} · Image ETA {eta_text}')

    def batch_summary(self, message):
        self.clock.stop()
        self.status_update(message)
        elapsed = duration(time.monotonic() - self.started_at) if self.started_at else '00m 00s'
        self.timing.setText(f'Elapsed {elapsed} · {len(self.results)} saved · {len(self.errors)} failed · Image ETA —')
        failed = bool(self.errors) or message.startswith('Unable')
        self.status.setStyleSheet('color: #ffac9f;' if failed else '')
        self.progress.setStyleSheet('QProgressBar::chunk { background: #ffac9f; }' if failed else '')

    def show_help(self):
        if not hasattr(self, 'help_dialog'):
            self.help_dialog = HelpDialog(self)
        self.help_dialog.show()
        self.help_dialog.raise_()
        self.help_dialog.activateWindow()

    def portrait_settings(self):
        return dict(model=self.model.currentIndex(), scale=self.scale.currentIndex(),
                    tile=self.tile.currentIndex(), format=self.format.currentIndex(), half=self.half.isChecked(),
                    cleanup=self.cleanup.isChecked(), face=self.face_enhancer.isChecked(),
                    strength=self.portrait_strength.currentIndex(), upscale=self.upscale_enabled.isChecked())

    def toggle_portrait_preset(self, checked):
        if checked:
            self.portrait_snapshot = self.portrait_settings()
            self.apply_portrait_preset()
        elif self.portrait_snapshot is not None:
            saved = self.portrait_snapshot
            for key, widget in [('model', self.model), ('scale', self.scale), ('tile', self.tile),
                                ('format', self.format), ('strength', self.portrait_strength)]:
                widget.setCurrentIndex(saved[key])
            for key, widget in [('half', self.half), ('cleanup', self.cleanup),
                                ('face', self.face_enhancer), ('upscale', self.upscale_enabled)]:
                widget.setChecked(saved[key])
            self.portrait_snapshot = None
            self.status_update('Portrait preset disabled; previous portrait/upscale settings restored.')
        self.portrait_preset.setText('Portrait preset · ON' if checked else 'Portrait preset · OFF')
        self.refresh_feature_controls()

    def apply_portrait_preset(self):
        if not self.portrait_preset.isChecked():
            self.portrait_preset.setChecked(True)
            return
        self.upscale_enabled.setChecked(True)
        self.face_enhancer.setChecked(True)
        self.model.setCurrentText('General photo · Real-ESRGAN v3')
        self.cleanup.setChecked(True)
        self.portrait_strength.setCurrentIndex(2)
        self.scale.setCurrentIndex(0)
        self.half.setChecked(False)
        self.tile.setCurrentText('256')
        self.format.setCurrentIndex(0)
        self.status_update('Portrait preset: General v3 · cleanup · GFPGAN 85% · 2× PNG · FP32')

    def refresh_feature_controls(self, *_):
        busy = self.worker is not None and self.worker.isRunning()
        for widget in [self.model, self.scale, self.cleanup, self.tile, self.half]:
            widget.setEnabled(not busy and self.upscale_enabled.isChecked())
        self.portrait_strength.setEnabled(not busy and self.face_enhancer.isChecked())
        self.mask_button.setEnabled(not busy and self.queue.currentRow() >= 0)

    def edit_damage_mask(self):
        item = self.queue.currentItem()
        if item is None:
            return
        from mask_editor import MaskEditor
        source = item.data(Qt.UserRole)
        reader = QImageReader(source)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.width() * size.height() > 30_000_000:
            QMessageBox.warning(self, 'Image too large for mask editor', 'Resize the source below 30 megapixels before painting a damage mask.')
            return
        image = reader.read()
        if image.isNull():
            QMessageBox.warning(self, 'Cannot open image', reader.errorString())
            return
        editor = MaskEditor(image, self.damage_masks.get(source), self)
        if editor.exec() == QDialog.Accepted:
            folder = ROOT / 'masks'
            folder.mkdir(exist_ok=True)
            path = folder / (hashlib.sha256(source.encode('utf-8')).hexdigest()[:20] + '.png')
            if not editor.canvas.mask.save(str(path)):
                QMessageBox.warning(self, 'Cannot save mask', 'Choose a writable project folder.')
                return
            self.damage_masks[source] = str(path)
            self.repair_enabled.setChecked(True)
            self.log(f'Damage mask saved for {Path(source).name}')

    def device_ready(self, available, name):
        self.gpu.setText(('CUDA  /  ' if available else '') + name)
        if not available:
            self.device.setCurrentIndex(1)

    def slide(self, value):
        self.preview.split = value / 100
        self.preview.update()

    def add_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Add images', '', 'Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)')
        self.add_files(paths)

    def add_files(self, paths):
        if self.worker and self.worker.isRunning():
            return
        existing = {self.queue.item(i).data(Qt.UserRole) for i in range(self.queue.count())}
        from PySide6.QtWidgets import QListWidgetItem
        for path in paths:
            path = Path(path).resolve()
            if path.suffix.lower() in EXTENSIONS and path.is_file() and str(path) not in existing:
                item = QListWidgetItem(path.name)
                item.setData(Qt.UserRole, str(path))
                item.setToolTip(str(path))
                self.queue.addItem(item)
                mask_path = ROOT / 'masks' / (hashlib.sha256(str(path).encode('utf-8')).hexdigest()[:20] + '.png')
                if mask_path.exists():
                    self.damage_masks[str(path)] = str(mask_path)
                existing.add(str(path))
        if self.queue.count() and self.queue.currentRow() < 0:
            self.queue.setCurrentRow(0)
        self.start.setEnabled(self.queue.count() > 0)
        self.queue_title.setText(f'02  /  IMAGES · {self.queue.count()}')
        self.status.setText(f'{self.queue.count()} image(s) queued · first use downloads the selected model')

    def remove_image(self, source):
        if self.worker and self.worker.isRunning():
            return
        for row in range(self.queue.count()):
            item = self.queue.item(row)
            if item.data(Qt.UserRole) == source:
                self.queue.takeItem(row)
                self.results.pop(source, None)
                self.errors.pop(source, None)
                self.damage_masks.pop(source, None)
                break
        self.queue_title.setText(f'02  /  IMAGES · {self.queue.count()}')
        self.start.setEnabled(self.queue.count() > 0)
        self.selection(self.queue.currentRow())
        self.refresh_feature_controls()
        self.status.setText(f'{self.queue.count()} image(s) queued')

    def clear(self):
        self.queue.clear()
        self.queue_title.setText('02  /  IMAGES · 0')
        self.results.clear()
        self.errors.clear()
        self.preview.show_images()
        self.damage_masks.clear()
        self.start.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText('Ready when you are. Add an image to get started.')
        self.status.setStyleSheet('')
        self.progress.setStyleSheet('')
        self.timing.setText('Queue 0% · Elapsed 00m 00s · Image ETA —')
        self.refresh_feature_controls()

    def selection(self, row):
        if row < 0:
            self.preview.show_images()
            self.slider.setEnabled(False)
            self.detail.setText('Select an image to preview it.')
            return
        source = self.queue.item(row).data(Qt.UserRole)
        self.preview.show_images(source, self.results.get(source))
        self.slider.setEnabled(not self.preview.after.isNull())
        self.detail.setText(self.errors.get(source) or self.results.get(source) or source)
        self.detail.setToolTip(self.detail.text())
        self.refresh_feature_controls()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Save results to', self.folder.text())
        if folder:
            self.folder.setText(folder)

    def open_folder(self):
        try:
            folder = Path(self.folder.text().strip())
            folder.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))
        except OSError as error:
            QMessageBox.warning(self, 'Cannot open folder', str(error))

    def set_busy(self, busy):
        self.queue_delegate.removal_enabled = not busy
        self.queue.viewport().update()
        for widget in [self.add_button, self.clear_button, self.model, self.scale, self.device,
                       self.tile, self.half, self.format, self.folder, self.browse, self.cleanup,
                       self.portrait_strength, self.portrait_preset, self.face_enhancer,
                       self.colorize, self.detail_enabled, self.hyper, self.repair_enabled,
                       self.mask_button, self.upscale_enabled]:
            widget.setEnabled(not busy)
        self.start.setEnabled(not busy and self.queue.count() > 0)
        self.stop.setEnabled(busy)
        if not busy:
            self.refresh_feature_controls()

    def run_batch(self):
        folder = self.folder.text().strip()
        if not folder:
            QMessageBox.warning(self, 'Output folder', 'Choose an output folder first.')
            return
        self.settings.setValue('folder', folder)
        options = dict(model=self.model.currentText(), scale=int(self.scale.currentText()[0]) if self.upscale_enabled.isChecked() else 1,
            device='cuda' if self.device.currentIndex() == 0 else 'cpu', tile=int(self.tile.currentText()),
            half=self.half.isChecked(), format='png' if self.format.currentIndex() == 0 else 'jpg', folder=folder,
            cleanup=self.cleanup.isChecked() and self.upscale_enabled.isChecked(),
            portrait=self.portrait_strength.currentData() if self.face_enhancer.isChecked() else 0,
            upscale_enabled=self.upscale_enabled.isChecked(), colorize=self.colorize.isChecked(),
            detail=self.detail_enabled.isChecked(), hyper=self.hyper.isChecked(),
            repair=self.repair_enabled.isChecked(), masks=dict(self.damage_masks))
        files = [Path(self.queue.item(i).data(Qt.UserRole)) for i in range(self.queue.count())]
        if options['repair'] and any(str(path) not in self.damage_masks for path in files):
            QMessageBox.warning(self, 'Damage masks needed', 'Repair is enabled. Select each image and edit its damage mask before starting, or disable repair.')
            return
        self.errors.clear()
        self.results.clear()
        for i, path in enumerate(files):
            self.queue.item(i).setText(path.name)
            self.queue.item(i).setForeground(QColor('#e9edf3'))
        self.selection(self.queue.currentRow())
        self.worker = Worker(files, options)
        self.worker.status.connect(self.status_update)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.completed.connect(self.completed)
        self.worker.failed.connect(self.failed)
        self.worker.summary.connect(self.batch_summary)
        self.worker.detail.connect(self.processing_detail)
        self.worker.diagnostic.connect(self.diagnostic)
        self.worker.finished.connect(lambda: self.set_busy(False))
        self.set_busy(True)
        self.progress.setValue(0)
        self.progress.setStyleSheet('')
        self.status.setStyleSheet('')
        self.started_at = time.monotonic()
        self.latest_detail = {}
        self.status_update(f'Starting {len(files)} image(s) · {options["model"]} · {options["device"].upper()} · {options["scale"]}× · tile {options["tile"]}')
        self.log(f'Precision: {"FP16 requested" if options["half"] else "FP32"} · source cleanup: {"50%" if options["cleanup"] else "off"}')
        self.log(f'Face restoration: {options["portrait"]:.0%}')
        self.log(f'Colorization: {options["colorize"]} · Detail: {options["detail"]} · Hyper detail: {options["hyper"]} · Repair: {options["repair"]}')
        self.clock.start()
        self.update_timing()
        self.worker.start()

    def completed(self, source, result):
        self.results[source] = result
        self.log(f'SAVED · {result}')
        self.mark(source, '✓', '#79e4bf')

    def failed(self, source, error):
        self.errors[source] = error
        self.log(f'ERROR · {Path(source).name} · {error}')
        self.mark(source, '!', '#ffac9f')

    def mark(self, source, prefix, color):
        for index in range(self.queue.count()):
            item = self.queue.item(index)
            if item.data(Qt.UserRole) == source:
                item.setText(f'{prefix}  {Path(source).name}')
                item.setForeground(QColor(color))
                item.setToolTip(self.errors.get(source) or self.results.get(source) or source)
        self.selection(self.queue.currentRow())

    def cancel(self):
        if self.worker:
            self.worker.cancel.set()
            self.stop.setEnabled(False)
            self.status.setText('Cancelling after the current tile or download block…')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.cancel()
            self.status.setText('Cancelling… Please close the window again once processing stops.')
            event.ignore()
        elif self.probe.isRunning():
            event.ignore()
        else:
            self.monitor.stop.set()
            self.monitor.wait(3500)
            event.accept()

def main():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('HMRStudio.Upscale')
    app = QApplication(sys.argv)
    app.setApplicationDisplayName(APP_TITLE)
    app.setWindowIcon(QIcon(str(APP_ICON)))
    def report_error(kind, value, tb):
        details = ''.join(traceback.format_exception(kind, value, tb))
        try:
            with (ROOT / 'error.log').open('a', encoding='utf-8') as log:
                log.write(details + '\n')
        except OSError:
            pass
        QMessageBox.critical(None, APP_TITLE, str(value) + '\n\nDetails are saved in error.log when possible.')
    sys.excepthook = report_error
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
