import os

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QCheckBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
    )
except ImportError:  # Krita 6 may expose PySide6 in some builds.
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QCheckBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
    )

from .exporter import ExportSettings, SpineExporter, SpineExportError


class SpineExportDialog(QDialog):
    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.setWindowTitle("Export to Spine")
        self.setMinimumWidth(520)
        self._build_ui()

    def _default_base_dir(self):
        filename = self.document.fileName() or ""
        if filename:
            return os.path.dirname(filename)
        return os.path.expanduser("~")

    def _default_json_path(self):
        filename = self.document.fileName() or self.document.name() or "krita-spine"
        stem = os.path.splitext(os.path.basename(filename))[0] or "krita-spine"
        return os.path.join(self._default_base_dir(), stem + ".json")

    def _build_ui(self):
        root = QVBoxLayout(self)

        form = QFormLayout()
        self.json_path = QLineEdit(self._default_json_path())
        self.images_dir = QLineEdit(os.path.join(self._default_base_dir(), "images"))

        json_row = QHBoxLayout()
        json_row.addWidget(self.json_path)
        json_btn = QPushButton("Browse")
        json_btn.clicked.connect(self._browse_json)
        json_row.addWidget(json_btn)
        form.addRow("Spine JSON", json_row)

        image_row = QHBoxLayout()
        image_row.addWidget(self.images_dir)
        image_btn = QPushButton("Browse")
        image_btn.clicked.connect(self._browse_images)
        image_row.addWidget(image_btn)
        form.addRow("Images folder", image_row)

        self.scale = QSpinBox()
        self.scale.setRange(1, 1000)
        self.scale.setValue(100)
        self.scale.setSuffix("%")
        form.addRow("Scale", self.scale)

        self.padding = QSpinBox()
        self.padding.setRange(0, 512)
        self.padding.setValue(1)
        self.padding.setSuffix(" px")
        form.addRow("Padding", self.padding)

        root.addLayout(form)

        self.trim_whitespace = QCheckBox("Trim whitespace")
        self.trim_whitespace.setChecked(True)
        self.ignore_hidden = QCheckBox("Ignore hidden layers")
        self.ignore_hidden.setChecked(False)
        self.write_json = QCheckBox("Write Spine JSON")
        self.write_json.setChecked(True)
        self.write_images = QCheckBox("Write PNG images")
        self.write_images.setChecked(True)
        self.write_template = QCheckBox("Write template image")
        self.write_template.setChecked(False)
        self.legacy_json = QCheckBox("Legacy Spine skin JSON")
        self.legacy_json.setChecked(True)

        for widget in (
            self.trim_whitespace,
            self.ignore_hidden,
            self.write_json,
            self.write_images,
            self.write_template,
            self.legacy_json,
        ):
            root.addWidget(widget)

        note = QLabel(
            "Layer tags match PhotoshopToSpine where Krita exposes equivalent data."
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignLeft)
        root.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(export_btn)
        root.addLayout(buttons)

    def _browse_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Spine JSON", self.json_path.text(), "Spine JSON (*.json)"
        )
        if path:
            self.json_path.setText(path)

    def _browse_images(self):
        path = QFileDialog.getExistingDirectory(
            self, "Images folder", self.images_dir.text()
        )
        if path:
            self.images_dir.setText(path)

    def _export(self):
        settings = ExportSettings(
            json_path=self.json_path.text().strip(),
            images_dir=self.images_dir.text().strip(),
            scale=self.scale.value() / 100.0,
            padding=self.padding.value(),
            trim_whitespace=self.trim_whitespace.isChecked(),
            ignore_hidden_layers=self.ignore_hidden.isChecked(),
            write_json=self.write_json.isChecked(),
            write_images=self.write_images.isChecked(),
            write_template=self.write_template.isChecked(),
            legacy_json=self.legacy_json.isChecked(),
        )
        try:
            result = SpineExporter(self.document, settings).export()
        except SpineExportError as exc:
            QMessageBox.critical(self, "Spine export failed", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(
                self, "Spine export failed", "Unexpected error: {0}".format(exc)
            )
            return

        QMessageBox.information(
            self,
            "Spine export complete",
            "Exported {0} attachment(s).\nJSON: {1}\nImages: {2}".format(
                result.attachment_count,
                result.json_path or "not written",
                result.images_dir or "not written",
            ),
        )
        self.accept()
