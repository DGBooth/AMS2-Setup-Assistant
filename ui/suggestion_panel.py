"""
Suggestion panel — shows setup changes for the selected symptom.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from analysis.symptom_detector import Symptom
from analysis.suggestion_table import SuggestionEntry


_CATEGORY_COLOURS = {
    "suspension":   "#44aaff",
    "alignment":    "#88ddaa",
    "aero":         "#dd88ff",
    "differential": "#ffcc44",
    "brakes":       "#ff8844",
    "tyres":        "#44dddd",
}

_CATEGORY_LABELS = {
    "suspension":   "SUSPENSION",
    "alignment":    "ALIGNMENT",
    "aero":         "AERO",
    "differential": "DIFF",
    "brakes":       "BRAKES",
    "tyres":        "TYRES",
}


class _SuggestionItem(QFrame):
    def __init__(self, entry: SuggestionEntry, rank: int, parent=None):
        super().__init__(parent)
        self.setObjectName("suggestionItem")
        self.setStyleSheet(
            "QFrame#suggestionItem {"
            "  background: rgba(25, 35, 50, 160);"
            "  border: 1px solid rgba(45, 106, 159, 80);"
            "  border-radius: 4px;"
            "  padding: 0px;"
            "  margin: 2px 4px;"
            "}"
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(3)

        # Top row: rank + title + category badge
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        rank_label = QLabel(f"{rank}.")
        rank_label.setStyleSheet("color: #555577; font-size: 11px; font-weight: bold;")
        rank_label.setFixedWidth(16)
        top_row.addWidget(rank_label)

        title_label = QLabel(entry.title)
        title_label.setObjectName("suggestionTitle")
        title_label.setStyleSheet("font-weight: bold; color: #e8e8e8; font-size: 12px;")
        title_label.setWordWrap(True)
        top_row.addWidget(title_label, stretch=1)

        cat_colour = _CATEGORY_COLOURS.get(entry.category, "#888888")
        cat_text   = _CATEGORY_LABELS.get(entry.category, entry.category.upper())
        cat_badge  = QLabel(cat_text)
        cat_badge.setObjectName("suggestionCategory")
        cat_badge.setStyleSheet(
            f"background: rgba(45, 106, 159, 60); color: {cat_colour}; "
            f"font-size: 9px; font-weight: bold; border-radius: 2px; padding: 1px 4px;"
        )
        cat_badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        top_row.addWidget(cat_badge)

        outer.addLayout(top_row)

        # Detail text
        detail_label = QLabel(entry.detail)
        detail_label.setObjectName("suggestionDetail")
        detail_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        detail_label.setWordWrap(True)
        detail_label.setContentsMargins(22, 0, 0, 0)  # indent under rank number
        outer.addWidget(detail_label)

        # Condition note (optional)
        if entry.condition:
            cond_label = QLabel(f"Note: {entry.condition}")
            cond_label.setObjectName("suggestionCondition")
            cond_label.setStyleSheet("color: #ffaa00; font-size: 10px; font-style: italic;")
            cond_label.setContentsMargins(22, 0, 0, 0)
            outer.addWidget(cond_label)


class SuggestionPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(0)

        # Divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setObjectName("divider")
        divider.setStyleSheet("background: rgba(80, 80, 100, 80); max-height: 1px; margin: 0px 8px;")
        outer.addWidget(divider)

        # Section header (updates to show selected symptom name)
        self._header = QLabel("SUGGESTIONS")
        self._header.setObjectName("sectionHeader")
        self._header.setStyleSheet(
            "color: #888888; font-size: 10px; font-weight: bold; "
            "letter-spacing: 1px; padding: 6px 8px 2px 8px;"
        )
        outer.addWidget(self._header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 2, 0, 4)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        outer.addWidget(scroll)

        self._placeholder = QLabel("Click a symptom to see suggestions")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "color: #444466; font-size: 11px; padding: 16px;"
        )
        outer.addWidget(self._placeholder)

        self._scroll = scroll

    @pyqtSlot(object, list)
    def show_suggestions(self, symptom: Symptom, suggestions: list[SuggestionEntry]):
        # Clear
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has = bool(suggestions)
        self._scroll.setVisible(has)
        self._placeholder.setVisible(not has)

        if has:
            self._header.setText(f"SUGGESTIONS  —  {symptom.label.upper()}")
        else:
            self._header.setText("SUGGESTIONS")

        for i, entry in enumerate(suggestions, start=1):
            widget = _SuggestionItem(entry, rank=i)
            self._list_layout.insertWidget(self._list_layout.count() - 1, widget)
