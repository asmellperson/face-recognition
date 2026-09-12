APP_STYLE = """
QMainWindow, QWidget {
    background: #f5f7fa;
    color: #1f2937;
    font-family: "Microsoft YaHei UI";
    font-size: 14px;
}
QFrame#Sidebar {
    background: #172033;
}
QLabel#Brand {
    color: white;
    font-size: 20px;
    font-weight: 700;
    padding: 22px 14px;
}
QPushButton#NavButton {
    color: #cbd5e1;
    background: transparent;
    border: 0;
    border-radius: 6px;
    text-align: left;
    padding: 12px 18px;
}
QPushButton#NavButton:hover {
    background: #26334d;
    color: white;
}
QPushButton#NavButton:checked {
    background: #2563eb;
    color: white;
}
QLabel#PageTitle {
    font-size: 24px;
    font-weight: 700;
}
QFrame#Card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
QPushButton {
    background: #2563eb;
    color: white;
    border: 0;
    border-radius: 5px;
    padding: 8px 15px;
    min-height: 20px;
}
QPushButton:hover { background: #1d4ed8; }
QPushButton:disabled { background: #9ca3af; }
QPushButton[secondary="true"] {
    background: #64748b;
}
QPushButton[danger="true"] {
    background: #dc2626;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: white;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 7px;
    min-height: 22px;
}
QTableWidget {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    gridline-color: #eef2f7;
}
QHeaderView::section {
    background: #eef2f7;
    padding: 9px;
    border: 0;
    border-right: 1px solid #dbe2ea;
    font-weight: 600;
}
QTableWidget::item { padding: 6px; }
QProgressDialog { min-width: 420px; }
"""
