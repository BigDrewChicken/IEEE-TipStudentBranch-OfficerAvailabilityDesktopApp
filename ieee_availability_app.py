# To deliver this product as soon as possible and to help IEEE TIP Student Branch as fast as this product could, the code is generated through Claude Sonnet 5 and GPT5.5 
# I laid out the whole system architecture to Claude and ChatGPT letting them write the code for it. - Drew
# This application loads in a formatted csv designed by IEEE TIP STudent Branch's Secretariat Committee, and is compatible to other schedule CSVs following the same format. This is to scale the product to future officers who would like to quickly check officer schedules and availability.
# There's also an executable file for this app in the releases section. :)


"""
IEEE TIP Student Branch — Officer Availability Desktop App
============================================================

Reads the "Officer Non-Availability Timetable" CSV (Time column + one
column per day, each cell containing a newline-separated list of officer
names who are NON-AVAILABLE / busy during that 30-minute slot) and lets
you query officer availability three different ways:

  1. Full Availability Mode — every free window a chosen officer has,
     for one day or the whole week.
  2. Range Mode — "is <officer> free from <time> to <time> on <day>?"
  3. Schedule Mode — every slot an officer is marked non-available
     (i.e. their full busy schedule), across the whole week.

Core rule (as defined by the branch):
    An officer is FREE during a slot if their name does NOT appear in
    that slot's cell. Consecutive free slots are merged into a single
    free window. The reported window runs from the timestamp of the
    last slot the officer WAS listed in, up to the timestamp of the
    next slot they are listed in again (or to the end of the day / from
    the start of the day if there is no bounding slot on one side).

Run with:  python ieee_availability_app.py
Requires:  PyQt6   (pip install PyQt6)
"""

import sys
import csv
import os
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox,
    QHeaderView, QGroupBox,
    QFormLayout, QLineEdit,
    QTextEdit, QSizePolicy,
    QFrame,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView
)
from PyQt6.QtGui import QAction, QFont, QColor
from PyQt6.QtCore import Qt

SLOT_MINUTES = 30
DEFAULT_CSV_NAME = "IEEE_Officer_Timetable_-_Main.csv"


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------

def parse_label_to_minutes(label: str) -> int:
    """Convert a '7:30' / '12:00' / '1:30' style label into minutes,
    treating the label as a simple 12-hour clock value (no AM/PM)."""
    label = label.strip()
    h_str, m_str = label.split(":")
    h = int(h_str) % 12  # 12 -> 0, used only for arithmetic consistency
    m = int(m_str)
    return h * 60 + m


def add_minutes_to_label(label: str, minutes_to_add: int) -> str:
    """Add minutes to a label, wrapping the 12-hour clock the same way
    the source sheet does (…, 11:30, 12:00, 12:30, 1:00, …)."""
    label = label.strip()
    h_str, m_str = label.split(":")
    h = int(h_str) % 12
    m = int(m_str)
    total = h * 60 + m + minutes_to_add
    total %= (12 * 60)
    new_h = total // 60
    new_m = total % 60
    if new_h == 0:
        new_h = 12
    return f"{new_h}:{new_m:02d}"


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class TimetableData:
    times: List[str] = field(default_factory=list)          # ordered slot labels
    days: List[str] = field(default_factory=list)            # ordered day names
    busy: Dict[str, Dict[str, Set[str]]] = field(default_factory=dict)
    # busy[day][time] -> set of officer names NON-AVAILABLE in that slot
    officers: List[str] = field(default_factory=list)
    source_path: str = ""

    def day_end_label(self) -> str:
        return add_minutes_to_label(self.times[-1], SLOT_MINUTES)

    def boundaries(self) -> List[str]:
        """All slot-start labels plus the final end-of-day boundary."""
        return self.times + [self.day_end_label()]


def load_timetable(path: str) -> TimetableData:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    if not rows:
        raise ValueError("CSV file is empty.")

    header = rows[0]
    time_col = header[0]
    days = [d.strip() for d in header[1:] if d.strip()]

    data = TimetableData()
    data.days = days
    data.source_path = path

    busy: Dict[str, Dict[str, Set[str]]] = {d: {} for d in days}
    officers: Set[str] = set()
    times: List[str] = []

    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        time_label = row[0].strip()
        times.append(time_label)
        for col_idx, day in enumerate(days, start=1):
            cell = row[col_idx] if col_idx < len(row) else ""
            names = {n.strip() for n in cell.splitlines() if n.strip()}
            busy[day][time_label] = names
            officers.update(names)

    data.times = times
    data.busy = busy
    data.officers = sorted(officers)
    return data


# --------------------------------------------------------------------------
# Availability logic
# --------------------------------------------------------------------------

def compute_free_windows(data: TimetableData, day: str, officer: str) -> List[Tuple[str, str]]:
    """Return list of (start_label, end_label) free windows for the
    officer on the given day, per the branch's free/busy rule."""
    times = data.times
    present = [officer in data.busy[day].get(t, set()) for t in times]
    n = len(times)
    windows: List[Tuple[str, str]] = []

    i = 0
    while i < n:
        if not present[i]:
            j = i
            while j < n and not present[j]:
                j += 1
            # free run covers slot indices [i, j-1]
            start_label = times[0] if i == 0 else times[i - 1]
            end_label = data.day_end_label() if j == n else times[j]
            windows.append((start_label, end_label))
            i = j
        else:
            i += 1

    return windows


def intersect_windows(windows_lists):
    """
    Returns the common availability between multiple officers.

    windows_lists:
        [
            [("7:30","9:00"), ("10:00","11:30")],
            [("8:00","9:00"), ("10:30","11:30")]
        ]
    """

    if not windows_lists:
        return []

    def to_minutes(label):
        h, m = map(int, label.split(":"))
        if h == 12:
            h = 0
        return h * 60 + m

    common = windows_lists[0]

    for other in windows_lists[1:]:

        new_common = []

        for s1, e1 in common:
            for s2, e2 in other:

                start = max(to_minutes(s1), to_minutes(s2))
                end = min(to_minutes(e1), to_minutes(e2))

                if start < end:

                    def back(minutes):
                        h = minutes // 60
                        m = minutes % 60

                        if h == 0:
                            h = 12

                        return f"{h}:{m:02d}"

                    new_common.append(
                        (
                            back(start),
                            back(end)
                        )
                    )

        common = new_common

    return common

def is_free_for_range(data: TimetableData, day: str, officer: str,
                       start_label: str, end_label: str) -> Tuple[bool, List[str]]:
    """Check whether officer is free for every slot within
    [start_label, end_label). Returns (is_free, list_of_conflicting_slot_labels)."""
    boundaries = data.boundaries()
    try:
        start_idx = boundaries.index(start_label)
        end_idx = boundaries.index(end_label)
    except ValueError:
        raise ValueError("Selected time is not a valid slot boundary.")

    if end_idx <= start_idx:
        raise ValueError("End time must be after start time.")

    conflicts = []
    for k in range(start_idx, end_idx):
        slot_label = data.times[k]
        if officer in data.busy[day].get(slot_label, set()):
            conflicts.append(slot_label)

    return (len(conflicts) == 0, conflicts)


def check_multiple_officers(data, officers, day, start_label, end_label):
    """
    Returns

    results:
    {
        officer:
        {
            "available": bool,
            "conflicts":[]
        }
    }

    common_available:
        True if ALL officers are available.
    """

    results = {}

    everyone_available = True

    for officer in officers:

        available, conflicts = is_free_for_range(
            data,
            day,
            officer,
            start_label,
            end_label
        )

        results[officer] = {
            "available": available,
            "conflicts": conflicts
        }

        if not available:
            everyone_available = False

    return results, everyone_available


def compute_schedule(data: TimetableData, officer: str) -> List[Tuple[str, str]]:
    """Return every (day, time) instance the officer is marked non-available."""
    results = []
    for day in data.days:
        for t in data.times:
            if officer in data.busy[day].get(t, set()):
                results.append((day, t))
    return results


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------

STYLE_SHEET = STYLE_SHEET = """
QMainWindow {
    background: #f4f6f8;
    color: black;
}

QLabel {
    color: black;
}

QGroupBox {
    color: black;
    font-weight: 600;
    border: 1px solid #d0d5da;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 14px;
    background: white;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #00629B;
}

QTabWidget::pane {
    border: 1px solid #d0d5da;
    background: white;
    border-radius: 6px;
}

QTabBar::tab {
    background: #e9edf1;
    color: #3c4650;
    padding: 10px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: white;
    color: #00629B;
    border-bottom: 3px solid #00629B;
}

QPushButton {
    background: #00629B;
    color: white;
    border-radius: 5px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background: #004d7a;
}

QPushButton:disabled {
    background: #a9b4bd;
}

QComboBox,
QLineEdit,
QTextEdit {
    background: white;
    color: black;
    border: 1px solid #c3cad1;
    border-radius: 4px;
    padding: 5px;
}

QTableWidget {
    background: white;
    color: black;
    gridline-color: #e2e6ea;
    selection-background-color: #00629B;
    selection-color: white;
}

QHeaderView::section {
    background: #00629B;
    color: white;
    padding: 6px;
    border: none;
    font-weight: 600;
}

QMenuBar {
    background: white;
    color: black;
}

QMenuBar::item:selected {
    background: #00629B;
    color: white;
}

QMenu {
    background: white;
    color: black;
}

QMenu::item:selected {
    background: #00629B;
    color: white;
}

QLabel[role="status"] {
    font-weight: 600;
    padding: 6px;
    border-radius: 4px;
}

QComboBox {
    background: white;
    color: black;
    border: 1px solid #c3cad1;
    border-radius: 4px;
    padding: 5px;
}

QComboBox::drop-down {
    border: none;
    background: white;
}

QComboBox::down-arrow {
    image: none;
}

QComboBox QAbstractItemView {
    background: white;
    color: black;
    selection-background-color: #00629B;
    selection-color: white;
    outline: 0;
}
"""

class OfficerSelector(QWidget):
    """
    Reusable widget that allows selecting one or more officers.
    Used in:
        • Full Availability
        • Range Mode
    """

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.list = QListWidget()
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )

        layout.addWidget(self.list)

        btn_layout = QHBoxLayout()

        self.select_all_btn = QPushButton("Select All")
        self.clear_btn = QPushButton("Clear")

        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        self.select_all_btn.clicked.connect(self.select_all)
        self.clear_btn.clicked.connect(self.clear_all)

    def load_officers(self, officers):

        self.list.clear()

        for officer in officers:

            item = QListWidgetItem(officer)

            item.setFlags(
                item.flags() |
                Qt.ItemFlag.ItemIsUserCheckable
            )

            item.setCheckState(Qt.CheckState.Unchecked)

            self.list.addItem(item)

    def get_selected(self):

        selected = []

        for i in range(self.list.count()):

            item = self.list.item(i)

            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())

        return selected

    def select_all(self):

        for i in range(self.list.count()):

            self.list.item(i).setCheckState(
                Qt.CheckState.Checked
            )

    def clear_all(self):

        for i in range(self.list.count()):

            self.list.item(i).setCheckState(
                Qt.CheckState.Unchecked
            )

class BaseTab(QWidget):
    """Shared behavior: tabs need access to the currently loaded data,
    which can change from the Settings tab, so we expose a refresh hook."""

    def __init__(self, get_data_callback):
        super().__init__()
        self.get_data = get_data_callback

    def on_data_changed(self):
        pass


class FullAvailabilityTab(BaseTab):
    def __init__(self, get_data_callback):
        super().__init__(get_data_callback)

        layout = QVBoxLayout(self)

        box = QGroupBox("Find every free window for one or more officers")
        form = QFormLayout()

        self.officer_selector = OfficerSelector()

        self.day_combo = QComboBox()
        self.day_combo.addItem("All Days")

        form.addRow("Officer(s):", self.officer_selector)
        form.addRow("Day:", self.day_combo)

        box.setLayout(form)

        self.compute_btn = QPushButton("Show Free Times")
        self.compute_btn.clicked.connect(self.compute)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Officer", "Day", "Free From", "Free To"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(box)
        layout.addWidget(self.compute_btn)
        layout.addWidget(self.table)

    def on_data_changed(self):
        data = self.get_data()

        self.day_combo.clear()
        self.day_combo.addItem("All Days")

        self.table.setRowCount(0)

        if data:
            self.officer_selector.load_officers(data.officers)
            self.day_combo.addItems(data.days)

    def compute(self):

        data = self.get_data()

        if not data:
            QMessageBox.warning(
                self,
                "No data",
                "Load a timetable CSV first."
            )
            return

        officers = self.officer_selector.get_selected()

        if not officers:
            QMessageBox.warning(
                self,
                "No officers",
                "Select at least one officer."
            )
            return

        day_selection = self.day_combo.currentText()

        days = (
            data.days
            if day_selection == "All Days"
            else [day_selection]
        )

        rows = []

        for officer in officers:

            for day in days:

                windows = compute_free_windows(
                    data,
                    day,
                    officer
                )

                for start, end in windows:

                    rows.append(
                        (
                            officer,
                            day,
                            start,
                            end
                        )
                    )

        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):

            for c, value in enumerate(row):

                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(value)
                )

        if not rows:

            QMessageBox.information(
                self,
                "No free time",
                "No free windows found."
            )


class RangeModeTab(BaseTab):

    def __init__(self, get_data_callback):

        super().__init__(get_data_callback)

        layout = QVBoxLayout(self)

        box = QGroupBox(
            "Check Multiple Officer Availability"
        )

        form = QFormLayout()

        self.officer_selector = OfficerSelector()

        self.day_combo = QComboBox()

        self.start_combo = QComboBox()

        self.end_combo = QComboBox()

        self.start_combo.currentIndexChanged.connect(
            self.refresh_end_options
        )

        form.addRow(
            "Officers:",
            self.officer_selector
        )

        form.addRow(
            "Day:",
            self.day_combo
        )

        form.addRow(
            "From:",
            self.start_combo
        )

        form.addRow(
            "To:",
            self.end_combo
        )

        box.setLayout(form)

        layout.addWidget(box)

        self.check_btn = QPushButton(
            "Check Availability"
        )

        self.check_btn.clicked.connect(
            self.check_range
        )

        layout.addWidget(
            self.check_btn
        )

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)

        layout.addWidget(
            self.result_text
        )

        self.conflict_table = QTableWidget()

        self.conflict_table.setColumnCount(3)

        self.conflict_table.setHorizontalHeaderLabels(

            [
                "Officer",
                "Day",
                "Conflict Time"
            ]

        )

        self.conflict_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        layout.addWidget(
            self.conflict_table
        )

    def on_data_changed(self):

        data = self.get_data()

        self.day_combo.clear()
        self.start_combo.clear()
        self.end_combo.clear()

        self.result_text.clear()

        self.conflict_table.setRowCount(0)

        if data:

            self.officer_selector.load_officers(
                data.officers
            )

            self.day_combo.addItems(
                data.days
            )

            self.start_combo.addItems(
                data.boundaries()[:-1]
            )

            self.refresh_end_options()

    def refresh_end_options(self):

        data = self.get_data()

        if not data:
            return

        boundaries = data.boundaries()

        start = self.start_combo.currentText()

        if start not in boundaries:
            return

        idx = boundaries.index(start)

        self.end_combo.clear()

        self.end_combo.addItems(

            boundaries[idx + 1:]

        )

    def check_range(self):

        data = self.get_data()

        if not data:

            QMessageBox.warning(
                self,
                "No data",
                "Please import a timetable."
            )

            return

        officers = self.officer_selector.get_selected()

        if len(officers) == 0:

            QMessageBox.warning(
                self,
                "No officers",
                "Please select at least one officer."
            )

            return

        day = self.day_combo.currentText()

        start = self.start_combo.currentText()

        end = self.end_combo.currentText()

        results, everyone_available = check_multiple_officers(

            data,
            officers,
            day,
            start,
            end

        )

        summary = []

        rows = []

        for officer in officers:

            available = results[officer]["available"]

            conflicts = results[officer]["conflicts"]

            if available:

                summary.append(

                    f"✅ {officer} IS FREE "
                    f"from {start} to {end}"

                )

            else:

                summary.append(

                    f"❌ {officer} is NOT FREE\n"
                    f"Busy at: {', '.join(conflicts)}"

                )

                for conflict in conflicts:

                    rows.append(

                        (
                            officer,
                            day,
                            conflict
                        )

                    )

        summary.append("\n")

        if everyone_available:

            summary.append(
                "🎉 ALL SELECTED OFFICERS ARE AVAILABLE."
            )

        else:

            summary.append(
                "⚠ NOT EVERYONE IS AVAILABLE."
            )

        self.result_text.setPlainText(

            "\n\n".join(summary)

        )

        self.conflict_table.setRowCount(

            len(rows)

        )

        for r, row in enumerate(rows):

            for c, value in enumerate(row):

                self.conflict_table.setItem(

                    r,
                    c,
                    QTableWidgetItem(value)

                )


class ScheduleModeTab(BaseTab):
    def __init__(self, get_data_callback):
        super().__init__(get_data_callback)
        layout = QVBoxLayout(self)

        box = QGroupBox("View an officer's full non-availability schedule")
        form = QFormLayout()
        self.officer_combo = QComboBox()
        form.addRow("Officer:", self.officer_combo)
        box.setLayout(form)

        btn_row = QHBoxLayout()
        self.show_btn = QPushButton("Show Schedule")
        self.show_btn.clicked.connect(self.show_schedule)
        btn_row.addStretch()
        btn_row.addWidget(self.show_btn)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Day", "Time (Non-Available)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(box)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

    def on_data_changed(self):
        data = self.get_data()
        self.officer_combo.clear()
        if data:
            self.officer_combo.addItems(data.officers)
        self.table.setRowCount(0)

    def show_schedule(self):
        data = self.get_data()
        if not data:
            QMessageBox.warning(self, "No data", "Load a timetable CSV first (Settings tab).")
            return
        officer = self.officer_combo.currentText()
        if not officer:
            QMessageBox.warning(self, "No officer", "Please select an officer.")
            return

        rows = compute_schedule(data, officer)
        self.table.setRowCount(len(rows))
        for r, (day, time_label) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(day))
            self.table.setItem(r, 1, QTableWidgetItem(time_label))

        if not rows:
            QMessageBox.information(self, "Fully free", f"{officer} has no recorded non-availability at all.")


class SettingsTab(BaseTab):
    def __init__(self, get_data_callback, load_callback):
        super().__init__(get_data_callback)
        self.load_callback = load_callback
        layout = QVBoxLayout(self)

        box = QGroupBox("Data Source")
        form = QFormLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse)
        reload_btn = QPushButton("Reload Current File")
        reload_btn.clicked.connect(self.reload_current)

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)

        form.addRow("CSV File:", path_row)
        box.setLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addWidget(reload_btn)
        btn_row.addStretch()

        info_box = QGroupBox("Loaded Data Summary")
        info_layout = QVBoxLayout()
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        info_layout.addWidget(self.info_text)
        info_box.setLayout(info_layout)

        rule_box = QGroupBox("Free / Busy Rule")
        rule_layout = QVBoxLayout()
        rule_label = QLabel(
            "An officer is considered FREE during a 30-minute slot if their name "
            "does NOT appear in that slot's cell for the given day.\n\n"
            "Consecutive free slots are merged into one window, reported from the "
            "last time the officer WAS listed, to the next time they are listed "
            "again (or the start/end of the day if there is no bound on one side)."
        )
        rule_label.setWordWrap(True)
        rule_layout.addWidget(rule_label)
        rule_box.setLayout(rule_layout)

        layout.addWidget(box)
        layout.addLayout(btn_row)
        layout.addWidget(info_box)
        layout.addWidget(rule_box)
        layout.addStretch()

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Timetable CSV", "", "CSV Files (*.csv)")
        if path:
            self.load_callback(path)

    def reload_current(self):
        data = self.get_data()
        if data and data.source_path:
            self.load_callback(data.source_path)
        else:
            QMessageBox.information(self, "No file", "No CSV has been loaded yet. Use Browse to pick one.")

    def on_data_changed(self):
        data = self.get_data()
        if data:
            self.path_edit.setText(data.source_path)
            summary = (
                f"File: {os.path.basename(data.source_path)}\n"
                f"Days: {', '.join(data.days)}\n"
                f"Time slots per day: {len(data.times)}  "
                f"({data.times[0]} - {data.day_end_label()})\n"
                f"Officers found ({len(data.officers)}): {', '.join(data.officers)}"
            )
            self.info_text.setPlainText(summary)
        else:
            self.path_edit.setText("")
            self.info_text.setPlainText("No data loaded.")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IEEE TIP Student Branch — Officer Availability")
        self.resize(950, 650)
        self.data: Optional[TimetableData] = None

        self.tabs = QTabWidget()
        self.full_tab = FullAvailabilityTab(self.get_data)
        self.range_tab = RangeModeTab(self.get_data)
        self.schedule_tab = ScheduleModeTab(self.get_data)
        self.settings_tab = SettingsTab(self.get_data, self.load_file)

        self.tabs.addTab(self.full_tab, "Full Availability")
        self.tabs.addTab(self.range_tab, "Range Mode")
        self.tabs.addTab(self.schedule_tab, "Schedule Mode")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.setCentralWidget(self.tabs)
        self._build_menu()
        self._auto_load_default()

    def get_data(self) -> Optional[TimetableData]:
        return self.data

    def _build_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        open_action = QAction("&Open CSV...", self)
        open_action.triggered.connect(self._open_dialog)
        file_menu.addAction(open_action)

        reload_action = QAction("&Reload Current File", self)
        reload_action.triggered.connect(self._reload_current)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Timetable CSV", "", "CSV Files (*.csv)")
        if path:
            self.load_file(path)

    def _reload_current(self):
        if self.data and self.data.source_path:
            self.load_file(self.data.source_path)

    def _show_about(self):
        QMessageBox.information(
            self, "About",
            "IEEE TIP Student Branch\nOfficer Availability Tool\n\n"
            "Loads the officer non-availability timetable CSV and lets you check "
            "full availability, a specific time range, or an officer's full schedule."
        )

    def _auto_load_default(self):
        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(here, DEFAULT_CSV_NAME)
        if os.path.exists(candidate):
            self.load_file(candidate)

    def load_file(self, path: str):
        try:
            self.data = load_timetable(path)
        except Exception as e:
            QMessageBox.critical(self, "Error Loading File", f"Could not load CSV:\n{e}")
            return

        for tab in (self.full_tab, self.range_tab, self.schedule_tab, self.settings_tab):
            tab.on_data_changed()

        self.statusBar().showMessage(f"Loaded: {os.path.basename(path)}", 5000)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()