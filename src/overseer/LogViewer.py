# widgets/LogViewer.py
import json
from pathlib import Path

from PyQt6 import QtWidgets as qw
from PyQt6 import QtGui as qg
from PyQt6 import QtCore as qc


class LogViewer(qw.QWidget):
    def __init__(self, log_file: Path, parent=None):
        super().__init__(parent)
        self.log_file = Path(log_file)

        layout = qw.QVBoxLayout(self)

        top_bar = qw.QHBoxLayout()
        self.title = qw.QLabel(f"Current log: {self.log_file.name}")
        self.refresh_button = qw.QPushButton("Refresh")
        self.auto_scroll_check = qw.QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)

        top_bar.addWidget(self.title)
        top_bar.addStretch()
        top_bar.addWidget(self.auto_scroll_check)
        top_bar.addWidget(self.refresh_button)

        self.text = qw.QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(qw.QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setTextInteractionFlags(
            qc.Qt.TextInteractionFlag.TextSelectableByMouse
            | qc.Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        font = qg.QFontDatabase.systemFont(qg.QFontDatabase.SystemFont.FixedFont)
        self.text.setFont(font)

        layout.addLayout(top_bar)
        layout.addWidget(self.text)

        self.refresh_button.clicked.connect(self.refresh)

        self.timer = qc.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

        self._last_rendered = None
        self.refresh()

    def refresh(self):
        if not self.log_file.exists():
            self.text.setPlainText(f"Log file does not exist yet:\n{self.log_file}")
            return

        try:
            raw = self.log_file.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self.text.setPlainText(f"Could not read log file:\n{e}")
            return

        pretty = self._prettify_json_lines(raw)

        if pretty == self._last_rendered:
            return

        self._last_rendered = pretty
        self.text.setPlainText(pretty)

        if self.auto_scroll_check.isChecked():
            scrollbar = self.text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _prettify_json_lines(self, raw: str) -> str:
        blocks = []

        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                blocks.append(stripped)
                continue

            blocks.append(json.dumps(obj, indent=2, default=str, ensure_ascii=False))

        return "\n\n".join(blocks)
