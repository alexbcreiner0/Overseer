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
        print(f"LogViewer logfile: {self.log_file=}")

        layout = qw.QVBoxLayout(self)

        top_bar = qw.QHBoxLayout()
        self.title = qw.QLabel(f"Current log: {self.log_file.name}")

        self.refresh_button = qw.QPushButton("Refresh")

        self.level_filter = qw.QComboBox()
        self.level_filter.addItems([
            "All",
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ])
        self.level_filter.setToolTip("Show only log records at this level")

        self.title.setTextInteractionFlags(qc.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.level_filter.setFixedWidth(100)
        self.refresh_button.setFixedWidth(80)

        self.word_wrap_check = qw.QCheckBox("Word wrap")
        self.word_wrap_check.setChecked(False)

        self.auto_scroll_check = qw.QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)

        top_bar.addWidget(self.title, 1)
        top_bar.addWidget(qw.QLabel("Level:"))
        top_bar.addWidget(self.level_filter)
        top_bar.addWidget(self.word_wrap_check)
        top_bar.addWidget(self.auto_scroll_check)
        top_bar.addWidget(self.refresh_button)

        self.text = qw.QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(qw.QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setTextInteractionFlags(
            qc.Qt.TextInteractionFlag.TextSelectableByMouse
            | qc.Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        self.word_wrap_check.stateChanged.connect(self._on_word_wrap_changed)
        self.level_filter.currentTextChanged.connect(self.refresh)

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
        selected_level = self.level_filter.currentText()

        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                # Only show non-JSON fallback lines when not filtering.
                if selected_level == "All":
                    blocks.append(stripped)
                continue

            if isinstance(obj, dict):
                record_level = str(obj.get("level", ""))

                if selected_level != "All" and record_level != selected_level:
                    continue

                blocks.append(self._format_log_record(obj))
            else:
                if selected_level == "All":
                    blocks.append(self._format_value(obj))

        sep = ""
        return "\n".join(f"{block}\n{sep}" for block in blocks)

    def _format_log_record(self, obj: dict) -> str:
        lines = []

        level = obj.get("level", "")
        timestamp = obj.get("timestamp", "")
        logger = obj.get("logger", "")
        message = obj.get("message", "")

        header_parts = []
        if timestamp:
            header_parts.append(str(timestamp))
        if level:
            header_parts.append(str(level))
        if logger:
            header_parts.append(str(logger))

        if header_parts:
            lines.append(" | ".join(header_parts))

        if message:
            lines.append(f"message: {message}")

        preferred_skip = {"timestamp", "level", "logger", "message"}

        for key, value in obj.items():
            if key in preferred_skip:
                continue

            rendered = self._format_value(value, indent=2)

            if "\n" in rendered:
                lines.append(f"{key}:")
                lines.append(rendered)
            else:
                lines.append(f"{key}: {rendered}")

        return "\n".join(lines)


    def _format_value(self, value, indent: int = 0) -> str:
        pad = " " * indent

        if isinstance(value, dict):
            lines = []

            for key, child in value.items():
                rendered = self._format_value(child, indent=indent + 2)

                if "\n" in rendered:
                    lines.append(f"{pad}{key}:")
                    lines.append(rendered)
                else:
                    lines.append(f"{pad}{key}: {rendered}")

            return "\n".join(lines)

        if isinstance(value, list):
            # Important special case:
            # traceback / exc_info is usually a list of strings.
            # Joining with commas destroys the traceback formatting.
            if all(isinstance(item, str) for item in value):
                return "\n".join(f"{pad}{item}" for item in value)

            lines = []

            for item in value:
                rendered = self._format_value(item, indent=indent + 2)

                if "\n" in rendered:
                    lines.append(f"{pad}-")
                    lines.append(rendered)
                else:
                    lines.append(f"{pad}- {rendered}")

            return "\n".join(lines)

        return f"{value}"

    def _on_word_wrap_changed(self, state: int) -> None:
        scrollbar = self.text.verticalScrollBar()

        old_max = scrollbar.maximum()
        old_value = scrollbar.value()

        if old_max > 0:
            old_ratio = old_value / old_max
        else:
            old_ratio = 0.0

        if state == qc.Qt.CheckState.Checked.value:
            self.text.setLineWrapMode(qw.QPlainTextEdit.LineWrapMode.WidgetWidth)
        else:
            self.text.setLineWrapMode(qw.QPlainTextEdit.LineWrapMode.NoWrap)

        def restore_scroll():
            scrollbar = self.text.verticalScrollBar()
            new_max = scrollbar.maximum()
            scrollbar.setValue(round(old_ratio * new_max))

        qc.QTimer.singleShot(0, restore_scroll)

    def sizeHint(self) -> qc.QSize:
        return qc.QSize(400, 300)

    def minimumSizeHint(self) -> qc.QSize:
        return qc.QSize(50, 50)
