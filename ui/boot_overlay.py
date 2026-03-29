"""
Alliance Terminal Version 3 — Boot Overlay Widget
Full-screen sci-fi boot sequence with large fonts and fade-out animation.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QScrollArea, QFrame, QSizePolicy, QPushButton, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QLinearGradient, QPainterPath
from .theme import *


class BootOverlay(QWidget):
    """Full-screen boot overlay — large centered layout, staggered log lines, fade-out."""
    requisition_accepted = pyqtSignal()
    requisition_cancelled = pyqtSignal()
    core_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(60, 50, 60, 50)
        root.setSpacing(0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ── Centre column ──
        center = QWidget()
        center.setMaximumWidth(680)
        center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        c_lay = QVBoxLayout(center)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(10)

        # Main title
        title = QLabel("ALLIANCE TERMINAL V3")
        title.setFont(font_orbitron(32, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_CYAN}; letter-spacing: 10px; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_lay.addWidget(title)

        # Subtitle
        sub = QLabel("SYSTEMS BOOT  ·  v3")
        sub.setFont(font_orbitron(10))
        sub.setStyleSheet(f"color: {C_TEXT_DIM}; letter-spacing: 4px; background: transparent;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_lay.addWidget(sub)

        c_lay.addSpacing(20)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background: {C_BORDER_LIT}; min-height: 1px; max-height: 1px;")
        c_lay.addWidget(div)

        c_lay.addSpacing(20)

        # Log scroll
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedHeight(260)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent; border: none;")

        self._log_container = QWidget()
        self._log_container.setStyleSheet("background: transparent;")
        self._log_layout = QVBoxLayout(self._log_container)
        self._log_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._log_layout.setSpacing(4)
        self._log_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._log_container)
        c_lay.addWidget(self._scroll)

        c_lay.addSpacing(20)

        # Spinner dots row
        dots_row = QWidget()
        dr_lay = QHBoxLayout(dots_row)
        dr_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dr_lay.setSpacing(12)
        dots_row.setStyleSheet("background: transparent;")
        self._dots = []
        for _ in range(5):
            d = QLabel("◈")
            d.setFont(font_orbitron(14))
            d.setStyleSheet(f"color: {C_TEXT_DIM}; background: transparent;")
            dr_lay.addWidget(d)
            self._dots.append(d)
        c_lay.addWidget(dots_row)
        
        # ── Requisition Panel (Hidden by default) ──
        self._req_panel = QWidget()
        self._req_panel.setVisible(False)
        rp_lay = QVBoxLayout(self._req_panel)
        rp_lay.setContentsMargins(0, 0, 0, 0)
        rp_lay.setSpacing(15)
        
        self._req_msg = QLabel("AI CORE MISSING. INITIATE TACTICAL REQUISITION?")
        self._req_msg.setFont(font_orbitron(12, QFont.Weight.Bold))
        self._req_msg.setStyleSheet(f"color: {C_GOLD};")
        self._req_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rp_lay.addWidget(self._req_msg)
        
        btn_row = QWidget()
        br_lay = QHBoxLayout(btn_row)
        br_lay.setSpacing(20)
        
        self._btn_init = QPushButton("INITIATE")
        self._btn_init.setFont(font_orbitron(10, QFont.Weight.Bold))
        self._btn_init.setFixedSize(140, 40)
        self._btn_init.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_init.setStyleSheet(f"""
            QPushButton {{
                background: {QColor(0, 180, 255, 30).name(QColor.NameFormat.HexArgb)};
                border: 1px solid {C_CYAN};
                color: {C_CYAN};
            }}
            QPushButton:hover {{
                background: {QColor(0, 180, 255, 60).name(QColor.NameFormat.HexArgb)};
            }}
        """)
        self._btn_init.clicked.connect(self.requisition_accepted.emit)
        
        self._btn_cancel = QPushButton("CANCEL")
        self._btn_cancel.setFont(font_orbitron(10, QFont.Weight.Bold))
        self._btn_cancel.setFixedSize(140, 40)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 10);
                border: 1px solid {C_BORDER};
                color: {C_TEXT_DIM};
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 20);
            }}
        """)
        self._btn_cancel.clicked.connect(self.requisition_cancelled.emit)
        
        br_lay.addWidget(self._btn_init)
        br_lay.addWidget(self._btn_cancel)
        rp_lay.addWidget(btn_row)
        c_lay.addWidget(self._req_panel)
        
        # ── Progress Section (Hidden) ──
        self._progress_section = QWidget()
        self._progress_section.setVisible(False)
        ps_lay = QVBoxLayout(self._progress_section)
        ps_lay.setContentsMargins(0, 0, 0, 0)
        
        self._bar = QProgressBar()
        self._bar.setFixedHeight(4)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background: {QColor(255, 255, 255, 10).name(QColor.NameFormat.HexArgb)};
                border: none;
            }}
            QProgressBar::chunk {{
                background: {C_CYAN};
            }}
        """)
        ps_lay.addWidget(self._bar)
        
        self._progress_text = QLabel("Downloading Core...")
        self._progress_text.setFont(font_mono(9))
        self._progress_text.setStyleSheet(f"color: {C_CYAN_DIM};")
        self._progress_text.setAlignment(Qt.AlignmentFlag.AlignRight)
        ps_lay.addWidget(self._progress_text)
        
        c_lay.addWidget(self._progress_section)

        # ── Selection Overlay (Hidden) ──
        self._selection_overlay = QWidget()
        self._selection_overlay.setVisible(False)
        sel_lay = QVBoxLayout(self._selection_overlay)
        sel_lay.setContentsMargins(0, 0, 0, 0)
        sel_lay.setSpacing(10)
        
        sel_title = QLabel("TACTICAL CORE SELECTION")
        sel_title.setFont(font_orbitron(14, QFont.Weight.Bold))
        sel_title.setStyleSheet(f"color: {C_CYAN}; letter-spacing: 2px;")
        sel_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sel_lay.addWidget(sel_title)
        
        self._core_list_layout = QVBoxLayout()
        self._core_list_layout.setSpacing(8)
        sel_lay.addLayout(self._core_list_layout)
        
        c_lay.addWidget(self._selection_overlay)

        root.addWidget(center)
        self.layout().setAlignment(center, Qt.AlignmentFlag.AlignHCenter)

        # ── Spinner timer ──
        self._phase = 0
        self._spin_t = QTimer(self)
        self._spin_t.timeout.connect(self._spin)
        self._spin_t.start(200)

        # ── Fade-out animation on windowOpacity ──
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(800)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QEasingCurve.Type.InQuad)
        self._fade.finished.connect(self.hide)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        r = 10  # Match main window radius
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), r, r)
        
        # Fill background
        p.fillPath(path, BG)
        
        # Subtle horizontal scan lines (clipped to path)
        p.setClipPath(path)
        p.setPen(QColor(0, 180, 255, 5))
        for y in range(0, self.height(), 3):
            p.drawLine(0, y, self.width(), y)
            
        # Vignette gradient (darker edges)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(0, 0, 0, 80))
        grad.setColorAt(0.4, QColor(0, 0, 0, 0))
        grad.setColorAt(0.6, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, 80))
        p.fillPath(path, grad)
        
        p.end()

    def append_line(self, text: str, kind: str = "info"):
        colours = {
            "ok":    C_GREEN,
            "warn":  C_GOLD,
            "error": C_RED,
            "info":  C_TEXT,
        }
        col = colours.get(kind, C_TEXT)

        lbl = QLabel(text)
        lbl.setFont(font_mono(10))
        lbl.setStyleSheet(f"color: {col}; background: transparent; padding: 1px 0;")
        lbl.setWordWrap(False)
        self._log_layout.addWidget(lbl)

        # Auto-scroll after slight delay so the widget has settled
        QTimer.singleShot(30, self._scroll_bottom)

    def _scroll_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _spin(self):
        for i, d in enumerate(self._dots):
            dist = abs(i - self._phase % len(self._dots))
            dist = min(dist, len(self._dots) - dist)
            if dist == 0:
                col = C_CYAN
            elif dist == 1:
                col = C_CYAN_DIM
            else:
                col = C_TEXT_DIM
            d.setStyleSheet(f"color: {col}; background: transparent;")
        self._phase += 1

    def show_requisition(self, core_name: str):
        """Deprecated in favor of show_core_selection, but kept for fallback."""
        self._req_msg.setText(f"AI CORE '{core_name}' MISSING. INITIATE TACTICAL REQUISITION?")
        self._req_panel.setVisible(True)
        # Hide dots while prompting
        for d in self._dots: d.setVisible(False)

    def show_core_selection(self, models_dict: dict, recommended_key: str = "qwen-2.5-7b"):
        """Show a list of available AI cores to pick from."""
        # Clear existing buttons
        while self._core_list_layout.count():
            item = self._core_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        for key, info in models_dict.items():
            is_rec = (key == recommended_key)
            name = info.get("display_name", key)
            
            btn = QPushButton()
            btn.setFixedSize(600, 50)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            btn_lay = QHBoxLayout(btn)
            btn_lay.setContentsMargins(20, 0, 20, 0)
            
            name_lbl = QLabel(name.upper())
            name_lbl.setFont(font_orbitron(10, QFont.Weight.Bold))
            name_lbl.setStyleSheet("color: inherit; background: transparent;")
            btn_lay.addWidget(name_lbl)
            
            if is_rec:
                rec_lbl = QLabel("[ ALLIANCE RECOMMENDED ]")
                rec_lbl.setFont(font_orbitron(8, QFont.Weight.Bold))
                rec_lbl.setStyleSheet(f"color: {C_CYAN}; background: transparent;")
                btn_lay.addStretch()
                btn_lay.addWidget(rec_lbl)
            
            # Styling
            style = f"""
                QPushButton {{
                    background: {QColor(0, 180, 255, 20).name(QColor.NameFormat.HexArgb)};
                    border: 1px solid {C_BORDER if not is_rec else C_CYAN};
                    color: {C_TEXT if not is_rec else C_TEXT_BRIGHT};
                    font-family: {S_MONTSERRAT};
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: {QColor(0, 180, 255, 50).name(QColor.NameFormat.HexArgb)};
                    border-color: {C_CYAN};
                }}
            """
            btn.setStyleSheet(style)
            btn.clicked.connect(lambda checked, k=key: self.core_selected.emit(k))
            self._core_list_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)

        # Cancel button at the bottom
        c_btn = QPushButton("PROCEED OFFLINE")
        c_btn.setFixedSize(200, 30)
        c_btn.setStyleSheet(f"color: {C_TEXT_DIM}; border: 1px solid {C_BORDER};")
        c_btn.clicked.connect(self.requisition_cancelled.emit)
        self._core_list_layout.addSpacing(10)
        self._core_list_layout.addWidget(c_btn, 0, Qt.AlignmentFlag.AlignCenter)

        self._selection_overlay.setVisible(True)
        # Hide dots
        for d in self._dots: d.setVisible(False)

    def set_requisition_progress(self, val: int, status: str = ""):
        """Show progress and update bar."""
        self._req_panel.setVisible(False)
        self._progress_section.setVisible(True)
        self._bar.setValue(val)
        if status:
            self._progress_text.setText(status)

    def fade_out(self):
        self._spin_t.stop()
        self._fade.start()
