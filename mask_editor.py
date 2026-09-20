"""Per-image damage masks: paint white to repair, erase to protect."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QPixmap
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QCheckBox, QFileDialog, QMessageBox)


class MaskCanvas(QWidget):
    def __init__(self, image, mask=None):
        super().__init__()
        self.image = image
        self.mask = mask.convertToFormat(QImage.Format_RGB32) if mask else QImage(image.size(), QImage.Format_RGB32)
        if mask is None:
            self.mask.fill(Qt.black)
        self.brush = 25
        self.erase = False
        self.previous = None
        self.history = []
        self.setMinimumSize(450, 320)

    def image_rect(self):
        size = self.image.size().scaled(self.size(), Qt.KeepAspectRatio)
        return QRectF((self.width()-size.width())/2, (self.height()-size.height())/2, size.width(), size.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#11161c'))
        rect = self.image_rect()
        painter.drawImage(rect, self.image)
        overlay = self.mask.convertToFormat(QImage.Format_ARGB32)
        # Grayscale mask drives alpha, so untouched areas remain visible.
        overlay.setAlphaChannel(self.mask)
        painter.setOpacity(.5)
        painter.drawImage(rect, overlay)

    def position(self, event):
        rect = self.image_rect()
        point = event.position()
        if not rect.contains(point):
            return None
        return QPointF((point.x()-rect.x())*self.image.width()/rect.width(),
                       (point.y()-rect.y())*self.image.height()/rect.height())

    def snapshot(self):
        self.history.append(self.mask.copy())
        self.history = self.history[-8:]

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.position(event) is not None:
            self.snapshot()
            self.previous = self.position(event)
            self.paint_stroke(self.previous)

    def mouseMoveEvent(self, event):
        if self.previous is not None and event.buttons() & Qt.LeftButton:
            point = self.position(event)
            if point is not None:
                self.paint_stroke(point)

    def mouseReleaseEvent(self, event):
        self.previous = None

    def paint_stroke(self, point):
        painter = QPainter(self.mask)
        painter.setPen(QPen(Qt.black if self.erase else Qt.white, self.brush, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if self.previous == point:
            painter.drawPoint(point)
        else:
            painter.drawLine(self.previous, point)
        painter.end()
        self.previous = point
        self.update()

    def clear(self):
        self.snapshot()
        self.mask.fill(Qt.black)
        self.update()

    def undo(self):
        if self.history:
            self.mask = self.history.pop()
            self.update()


class MaskEditor(QDialog):
    def __init__(self, image, mask_path=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Mark damage · white areas will be repaired')
        self.resize(950, 730)
        layout = QVBoxLayout(self)
        instructions = QLabel('Paint over tears, scratches and missing regions. Leave undamaged areas unmarked.\nBrush size is measured in source pixels; import a same-size black/white mask if preferred.')
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        mask = QImage(mask_path) if mask_path else None
        if mask is not None and (mask.isNull() or mask.size() != image.size()):
            mask = None
        self.canvas = MaskCanvas(image, mask)
        layout.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(3, 250)
        self.size.setValue(25)
        self.size.valueChanged.connect(lambda value: setattr(self.canvas, 'brush', value))
        row.addWidget(QLabel('Brush'))
        row.addWidget(self.size, 1)
        erase = QCheckBox('Erase')
        erase.toggled.connect(lambda checked: setattr(self.canvas, 'erase', checked))
        row.addWidget(erase)
        for title, action in [('Undo', self.canvas.undo), ('Clear', self.canvas.clear), ('Import mask', self.import_mask),
                              ('Cancel', self.reject), ('Save mask', self.accept)]:
            button = QPushButton(title)
            button.clicked.connect(action)
            row.addWidget(button)
        layout.addLayout(row)

    def import_mask(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import damage mask', '', 'Masks (*.png *.bmp *.tif *.tiff)')
        if not path:
            return
        mask = QImage(path)
        if mask.isNull() or mask.size() != self.canvas.image.size():
            QMessageBox.warning(self, 'Mask size', 'Choose a readable mask matching the source image dimensions.')
            return
        self.canvas.snapshot()
        self.canvas.mask = mask.convertToFormat(QImage.Format_Grayscale8).convertToFormat(QImage.Format_RGB32)
        self.canvas.update()
