#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AURORA COMMAND – TACTICAL RF WATCH
- FINAL FIXED VERSION
- Updates: Added Threat Level Waveform (Oscilloscope) below Map.
"""

import os
import sys
import math
import re
import time
import random
import numpy as np

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWebEngineWidgets import QWebEngineView
import pyqtgraph as pg

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RC_DETECT_PATH = os.path.join(BASE_DIR, "rc_detect.py")
MAP_FILE = os.path.join(BASE_DIR, "templates", "map.html")

# ----------------------------------------------------------------------
# VISUAL ASSETS (Colors & Styles)
# ----------------------------------------------------------------------
C_BG_DARK     = "#020205"
C_BG_PANEL    = "#0b0f19"
C_BORDER      = "#1f293a"
C_ACCENT_CYAN = "#00f0ff"
C_ACCENT_GOLD = "#ffae00"
C_ACCENT_RED  = "#ff2a2a"
C_ACCENT_GREEN = "#00ff41" # Matrix/Military Green for Friendly
C_TEXT_MAIN   = "#e0e6ed"
C_TEXT_DIM    = "#5c6b7f"

STYLESHEET_GLOBAL = f"""
    QMainWindow {{
        background-color: {C_BG_DARK};
    }}
    QWidget {{
        font-family: 'Consolas', 'Roboto Mono', monospace;
        color: {C_TEXT_MAIN};
    }}
    QFrame {{
        border: none;
    }}
    QScrollBar:vertical {{
        border: none;
        background: #0b0f19;
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: #2d3b50;
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
"""

STYLESHEET_PANEL = f"""
    QFrame {{
        background-color: {C_BG_PANEL};
        border: 1px solid {C_BORDER};
        border-radius: 4px;
    }}
"""

STYLESHEET_BUTTON = f"""
    QPushButton {{
        background-color: rgba(255, 42, 42, 0.15);
        border: 1px solid {C_ACCENT_RED};
        color: {C_ACCENT_RED};
        border-radius: 4px;
        padding: 6px 12px;
        font-weight: bold;
        letter-spacing: 1px;
    }}
    QPushButton:hover {{
        background-color: {C_ACCENT_RED};
        color: #000000;
    }}
"""

class AuroraCommand(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # Window identity
        self.setWindowTitle("AURORA COMMAND • TACTICAL RF WATCH")
        self.resize(1600, 900)
        self.setStyleSheet(STYLESHEET_GLOBAL)

        # State
        self.sweep_deg = 0.0
        self.last_metrics = None
        self.power_hist = []
        self.delta_hist = []
        self.max_hist = 240
        self.threat_wave_data = [0] * 200 # Data for the new waveform
        self.freq_min = 2400.0
        self.freq_max = 2483.0
        self.active_track = None 
        self.blink_state = False
        self.demo_mode = False 

        # ------------------------------------------------------------------
        # Backend
        # ------------------------------------------------------------------
        self.proc = QtCore.QProcess(self)
        self.proc.setProgram(sys.executable)
        self.proc.setArguments([RC_DETECT_PATH])
        self.proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.on_backend_output)
        self.proc.errorOccurred.connect(self.on_backend_error)
        self.proc.start()

        # ------------------------------------------------------------------
        # UI
        # ------------------------------------------------------------------
        self.main_container = QtWidgets.QFrame()
        self.setCentralWidget(self.main_container)
        
        self.main_layout = QtWidgets.QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        self._build_header(self.main_layout)

        middle = QtWidgets.QHBoxLayout()
        middle.setSpacing(10)
        self.main_layout.addLayout(middle, 1)

        self._build_left_sidebar(middle)
        self._build_center_panel(middle)
        self._build_right_panel(middle)

        self._build_footer(self.main_layout)

        # Timers
        self.radar_timer = QtCore.QTimer(self)
        self.radar_timer.timeout.connect(self.animate_radar)
        self.radar_timer.start(50)

        self.clock_timer = QtCore.QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()
        
        self.alert_timer = QtCore.QTimer(self)
        self.alert_timer.timeout.connect(self.toggle_alert_state)

    # ---------------- HEADER ----------------
    def _build_header(self, layout):
        frame = QtWidgets.QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {C_BG_PANEL};
                border-bottom: 2px solid {C_ACCENT_CYAN};
            }}
        """)
        h = QtWidgets.QHBoxLayout(frame)
        h.setContentsMargins(15, 10, 15, 10)
        
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(0)
        
        t1 = QtWidgets.QLabel("AURORA COMMAND")
        t1.setStyleSheet(f"font-size: 22px; font-weight: 900; color: {C_TEXT_MAIN}; letter-spacing: 2px;")
        t2 = QtWidgets.QLabel("TACTICAL RF SURVEILLANCE SYSTEM")
        t2.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {C_ACCENT_CYAN}; letter-spacing: 4px;")
        
        title_box.addWidget(t1)
        title_box.addWidget(t2)
        h.addLayout(title_box)

        h.addStretch(1)

        def stat_block(label, val, color):
            v = QtWidgets.QVBoxLayout()
            v.setSpacing(2)
            l = QtWidgets.QLabel(label)
            l.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:9px; font-weight:bold;")
            d = QtWidgets.QLabel(val)
            d.setStyleSheet(f"color:{color}; font-size:12px; font-weight:bold;")
            v.addWidget(l, 0, QtCore.Qt.AlignRight)
            v.addWidget(d, 0, QtCore.Qt.AlignRight)
            return v

        h.addLayout(stat_block("BAND", "2.4 GHz ISM", C_ACCENT_GOLD))
        h.addSpacing(20)
        h.addLayout(stat_block("BASE", "SPECTRE-ALPHA", "#ffffff"))
        h.addSpacing(20)
        
        self.clock_label = QtWidgets.QLabel("00:00:00 Z")
        self.clock_label.setStyleSheet(f"""
            color: {C_TEXT_MAIN}; font-size: 18px; font-weight: bold; 
            border: 1px solid {C_BORDER}; padding: 5px 10px; border-radius: 4px;
        """)
        h.addWidget(self.clock_label)

        layout.addWidget(frame)

    # ---------------- LEFT SIDEBAR ----------------
    def _build_left_sidebar(self, parent_layout):
        side = QtWidgets.QVBoxLayout()
        side.setSpacing(10)
        parent_layout.addLayout(side, 3)

        mission_frame = QtWidgets.QFrame()
        mission_frame.setStyleSheet(STYLESHEET_PANEL)
        v = QtWidgets.QVBoxLayout(mission_frame)
        
        lbl = QtWidgets.QLabel("/// MISSION PROFILE")
        lbl.setStyleSheet(f"color: {C_ACCENT_CYAN}; font-weight: bold; font-size: 11px;")
        v.addWidget(lbl)
        
        desc = QtWidgets.QLabel(
            "ROLE  : RF AIRSPACE WATCH\n"
            "TASK  : DETECT RC UPLINKS\n"
            "RULES : PASSIVE / NO JAM\n\n"
            "ENGINE: HACKRF_SWEEP\n"
            "RANGE : 2400-2483 MHZ"
        )
        desc.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 11px; line-height: 16px;")
        v.addWidget(desc)
        side.addWidget(mission_frame, 2)

        # --- DEMO SLIDER SECTION ---
        demo_frame = QtWidgets.QFrame()
        demo_frame.setStyleSheet(f"QFrame {{ background-color: #1a1a00; border: 1px solid {C_ACCENT_GOLD}; border-radius: 4px; }}")
        dv = QtWidgets.QVBoxLayout(demo_frame)
        
        dl = QtWidgets.QLabel("/// SYSTEM TEST / DEMO")
        dl.setStyleSheet(f"color: {C_ACCENT_GOLD}; font-weight: bold; font-size: 11px;")
        dv.addWidget(dl)

        self.demo_check = QtWidgets.QCheckBox("[TEST] ENABLE SIMULATION")
        self.demo_check.setStyleSheet(f"color: #fff; font-size: 10px;")
        self.demo_check.stateChanged.connect(self.toggle_demo_mode)
        dv.addWidget(self.demo_check)

        self.bw_slider_label = QtWidgets.QLabel("SIGNAL BANDWIDTH: 0.0 MHz")
        self.bw_slider_label.setStyleSheet("color: #aaa; font-size: 10px;")
        dv.addWidget(self.bw_slider_label)

        self.demo_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.demo_slider.setRange(0, 50) # 0.0 to 5.0 MHz
        self.demo_slider.setValue(14)    # Default to 1.4MHz (Foe)
        self.demo_slider.setEnabled(False)
        self.demo_slider.valueChanged.connect(self.on_demo_slider_change)
        
        self.demo_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height: 4px; background: #333; }}
            QSlider::handle:horizontal {{ background: {C_ACCENT_GOLD}; width: 14px; margin: -5px 0; border-radius: 7px; }}
        """)
        dv.addWidget(self.demo_slider)
        
        side.addWidget(demo_frame, 2)
        # ---------------------------

        log_frame = QtWidgets.QFrame()
        log_frame.setStyleSheet(STYLESHEET_PANEL)
        lv = QtWidgets.QVBoxLayout(log_frame)
        lv.setContentsMargins(0,0,0,0)
        
        header = QtWidgets.QLabel("  CHANNEL SNAPSHOT_LOG")
        header.setStyleSheet(f"background: {C_BORDER}; color: {C_TEXT_DIM}; font-size: 10px; padding: 4px;")
        lv.addWidget(header)

        self.snap_list = QtWidgets.QListWidget()
        self.snap_list.setStyleSheet(f"""
            QListWidget {{
                background-color: transparent;
                border: none;
                font-size: 10px;
            }}
            QListWidget::item {{
                padding: 4px;
                border-bottom: 1px solid #151a25;
            }}
        """)
        lv.addWidget(self.snap_list)
        side.addWidget(log_frame, 6)

        ctrl_frame = QtWidgets.QFrame()
        ctrl_frame.setStyleSheet(STYLESHEET_PANEL)
        cv = QtWidgets.QVBoxLayout(ctrl_frame)
        self.arm_check = QtWidgets.QCheckBox("[ARM] HOSTILE ALERTS")
        self.arm_check.setChecked(True)
        self.arm_check.setStyleSheet(f"""
            QCheckBox {{ color: {C_ACCENT_RED}; font-weight: bold; font-size: 11px; }}
            QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {C_ACCENT_RED}; background: transparent; }}
            QCheckBox::indicator:checked {{ background: {C_ACCENT_RED}; }}
        """)
        cv.addWidget(self.arm_check)
        side.addWidget(ctrl_frame, 1)

    # ---------------- CENTER PANEL ----------------
    def _build_center_panel(self, parent_layout):
        center = QtWidgets.QVBoxLayout()
        center.setSpacing(10)
        parent_layout.addLayout(center, 7)

        # STATUS BANNER
        self.status_label = QtWidgets.QLabel("STATUS: SCANNING AIRSPACE")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet(f"""
            background: {C_BG_PANEL}; border: 1px solid {C_ACCENT_CYAN}; 
            color: {C_ACCENT_CYAN}; font-size: 14px; font-weight: 900; 
            padding: 8px; border-radius: 4px; letter-spacing: 2px;
        """)
        center.addWidget(self.status_label)

        # RADAR SCOPE
        radar_cont = QtWidgets.QFrame()
        radar_cont.setStyleSheet(f"""
            QFrame {{
                background-color: #000000;
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)
        rv = QtWidgets.QVBoxLayout(radar_cont)
        rv.setContentsMargins(4,4,4,4)

        mv = QtWidgets.QHBoxLayout()
        mv.setSpacing(4)
        
        self.delta_val = self._add_hud_metric(mv, "DELTA (dB)", "#00ff9d")
        self.freq_val  = self._add_hud_metric(mv, "FREQ (MHz)", C_ACCENT_GOLD)
        self.bw_val    = self._add_hud_metric(mv, "B-WIDTH", "#d08aff")
        self.hops_val  = self._add_hud_metric(mv, "HOPS", C_ACCENT_CYAN)
        
        rv.addLayout(mv)

        self.radar = pg.PlotWidget()
        self.radar.setBackground('k')
        self.radar.setAspectLocked()
        self.radar.hideAxis('bottom')
        self.radar.hideAxis('left')
        self.radar.setRange(xRange=[-1.1, 1.1], yRange=[-1.1, 1.1])
        
        for r in [0.33, 0.66, 1.0]:
            circle = pg.QtWidgets.QGraphicsEllipseItem(-r, -r, r*2, r*2)
            circle.setPen(pg.mkPen((30, 45, 60), width=1))
            self.radar.addItem(circle)
        
        self.radar.plot([-1.1, 1.1], [0, 0], pen=pg.mkPen((30, 45, 60), width=1))
        self.radar.plot([0, 0], [-1.1, 1.1], pen=pg.mkPen((30, 45, 60), width=1))

        self.sweep_line = pg.PlotCurveItem(pen=pg.mkPen(C_ACCENT_CYAN, width=2))
        self.radar.addItem(self.sweep_line)

        # Target Dot
        self.target_dot = pg.ScatterPlotItem(
            size=15, 
            brush=pg.mkBrush(C_ACCENT_RED), 
            pen=pg.mkPen('w', width=1),
            pxMode=True
        )
        self.radar.addItem(self.target_dot)
        
        rv.addWidget(self.radar, 1)
        center.addWidget(radar_cont, 8)

        # SPECTRUM HISTORY
        graph_cont = QtWidgets.QFrame()
        graph_cont.setStyleSheet(STYLESHEET_PANEL)
        gv = QtWidgets.QVBoxLayout(graph_cont)
        gv.setContentsMargins(5,5,5,5)
        
        lbl = QtWidgets.QLabel("SIGNAL DELTA HISTORY")
        lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 9px; font-weight: bold;")
        gv.addWidget(lbl)

        self.timeline = pg.PlotWidget()
        self.timeline.setBackground(C_BG_PANEL)
        self.timeline.showGrid(x=True, y=True, alpha=0.1)
        self.timeline.getAxis('bottom').setPen((60,70,80))
        self.timeline.getAxis('left').setPen((60,70,80))
        
        self.timeline.setMaximumHeight(250) 
        self.timeline.setMinimumHeight(150)
        
        self.timeline_curve = self.timeline.plot(
            pen=pg.mkPen(C_ACCENT_CYAN, width=2), 
            fillLevel=-10, 
            brush=(0, 240, 255, 30)
        )
        gv.addWidget(self.timeline)
        center.addWidget(graph_cont, 4)

    def _add_hud_metric(self, layout, label, color):
        frame = QtWidgets.QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(0,0,0,0.3);
                border: 1px solid {C_BORDER};
                border-radius: 4px;
            }}
        """)
        v = QtWidgets.QVBoxLayout(frame)
        v.setContentsMargins(8,8,8,8)
        v.setSpacing(2)
        
        l = QtWidgets.QLabel(label)
        l.setAlignment(QtCore.Qt.AlignCenter)
        l.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px; font-weight:bold;")
        
        val = QtWidgets.QLabel("--")
        val.setAlignment(QtCore.Qt.AlignCenter)
        val.setStyleSheet(f"color: {color}; font-size: 32px; font-weight: 900; font-family: 'Roboto Mono';")
        
        v.addWidget(l)
        v.addWidget(val)
        layout.addWidget(frame)
        return val

    # ---------------- RIGHT PANEL ----------------
    def _build_right_panel(self, parent_layout):
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(10)
        parent_layout.addLayout(right, 4)

        t_frame = QtWidgets.QFrame()
        t_frame.setStyleSheet(STYLESHEET_PANEL)
        tv = QtWidgets.QVBoxLayout(t_frame)
        
        tl = QtWidgets.QLabel("THREAT ANALYSIS")
        tl.setStyleSheet(f"color: {C_ACCENT_RED}; font-weight: bold; font-size: 11px;")
        tv.addWidget(tl)

        self.threat_bar = QtWidgets.QProgressBar()
        self.threat_bar.setRange(0, 100)
        self.threat_bar.setValue(0)
        self.threat_bar.setTextVisible(False)
        self.threat_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #000000;
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                height: 12px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C_ACCENT_CYAN}, stop:0.7 {C_ACCENT_GOLD}, stop:1 {C_ACCENT_RED});
                border-radius: 2px;
            }}
        """)
        tv.addWidget(self.threat_bar)
        
        self.threat_text = QtWidgets.QLabel("NO THREAT")
        self.threat_text.setAlignment(QtCore.Qt.AlignCenter)
        self.threat_text.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 10px; font-weight: bold;")
        tv.addWidget(self.threat_text)
        right.addWidget(t_frame, 1)

        map_frame = QtWidgets.QFrame()
        map_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {C_BG_PANEL};
                border: 1px solid {C_ACCENT_CYAN};
                border-radius: 4px;
            }}
        """)
        mv = QtWidgets.QVBoxLayout(map_frame)
        mv.setContentsMargins(2,2,2,2)
        mv.setSpacing(0)

        mh = QtWidgets.QHBoxLayout()
        ml = QtWidgets.QLabel("GEOSPATIAL TARGETING")
        ml.setStyleSheet(f"background: {C_ACCENT_CYAN}; color: #000; font-weight: bold; font-size: 10px; padding: 2px 4px;")
        mh.addWidget(ml)
        mh.addStretch(1)
        
        self.clear_btn = QtWidgets.QPushButton("CLEAR TARGET")
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_ACCENT_CYAN}; border: 1px solid {C_ACCENT_CYAN};
                font-size: 9px; padding: 2px 8px;
            }}
            QPushButton:hover {{ background: {C_ACCENT_CYAN}; color: #000; }}
        """)
        self.clear_btn.clicked.connect(self.manual_clear_track)
        mh.addWidget(self.clear_btn)
        
        mv.addLayout(mh)

        self.web = QWebEngineView()
        self.web.setStyleSheet("background: #000;")
        if os.path.exists(MAP_FILE):
            url = QtCore.QUrl.fromLocalFile(os.path.abspath(MAP_FILE))
            self.web.load(url)
        else:
            self.web.setHtml("<h3 style='color:white'>MAP FILE MISSING</h3>")
        
        mv.addWidget(self.web)
        right.addWidget(map_frame, 8) # Weight for map

        # --- NEW WAVEFORM PANEL ---
        wave_frame = QtWidgets.QFrame()
        wave_frame.setStyleSheet(STYLESHEET_PANEL)
        wv = QtWidgets.QVBoxLayout(wave_frame)
        wv.setContentsMargins(5,5,5,5)
        wv.setSpacing(0)

        w_label = QtWidgets.QLabel("THREAT LEVEL OSCILLOSCOPE")
        w_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 9px; font-weight: bold; margin-bottom: 2px;")
        wv.addWidget(w_label)

        self.threat_plot = pg.PlotWidget()
        self.threat_plot.setBackground(C_BG_PANEL)
        self.threat_plot.hideAxis('bottom')
        self.threat_plot.hideAxis('left')
        self.threat_plot.setYRange(0, 100)
        self.threat_plot.showGrid(x=True, y=True, alpha=0.1)
        self.threat_plot.setMaximumHeight(120)

        self.threat_curve = self.threat_plot.plot(
            pen=pg.mkPen(C_ACCENT_CYAN, width=2), 
            fillLevel=0, 
            brush=(0, 240, 255, 20)
        )
        wv.addWidget(self.threat_plot)
        
        right.addWidget(wave_frame, 3) # Weight for waveform

    # ---------------- FOOTER ----------------
    def _build_footer(self, layout):
        frame = QtWidgets.QFrame()
        frame.setStyleSheet(STYLESHEET_PANEL)
        h = QtWidgets.QHBoxLayout(frame)
        h.setContentsMargins(10, 5, 10, 5)

        lbl = QtWidgets.QLabel("SYSTEM LOG >>")
        lbl.setStyleSheet(f"color: {C_ACCENT_CYAN}; font-weight: bold; font-size: 10px;")
        h.addWidget(lbl)

        self.ticker_label = QtWidgets.QLabel("INITIALIZING BACKEND LINK...")
        self.ticker_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 10px;")
        h.addWidget(self.ticker_label, 1)

        self.stop_btn = QtWidgets.QPushButton("EMERGENCY STOP")
        self.stop_btn.clicked.connect(self.stop_rf)
        self.stop_btn.setStyleSheet(STYLESHEET_BUTTON)
        h.addWidget(self.stop_btn)

        layout.addWidget(frame)

    # ==================================================================
    # DEMO / SIMULATION LOGIC
    # ==================================================================
    def toggle_demo_mode(self, state):
        self.demo_mode = (state == QtCore.Qt.Checked)
        self.demo_slider.setEnabled(self.demo_mode)
        
        if self.demo_mode:
            self.on_demo_slider_change() # Trigger initial update
        else:
            self.manual_clear_track()
            self._set_status_style("idle")

    def on_demo_slider_change(self):
        if not self.demo_mode: return
        
        val = self.demo_slider.value()
        bw_mhz = val / 10.0
        self.bw_slider_label.setText(f"SIGNAL BANDWIDTH: {bw_mhz:.1f} MHz")
        
        if bw_mhz > 2.0:
            sim_label = "FRIENDLY SIGNAL"
            sim_delta = 25.0
            sim_hops  = 45
        elif bw_mhz > 0.5:
            sim_label = "HOSTILE SIGNAL"
            sim_delta = 55.0
            sim_hops  = 30
        else:
            sim_label = "NOISE"
            sim_delta = 5.0
            sim_hops  = 5

        fake_metrics = {
            "peak_db": -20.0,
            "freq_mhz": 2445.0 + random.uniform(-10, 10),
            "noise_db": -80.0,
            "delta_db": sim_delta,
            "bw_mhz":   bw_mhz,
            "hops":     sim_hops,
            "label":    sim_label,
        }
        self.update_from_metrics(fake_metrics)

    # ==================================================================
    # DATA PROCESSING LOGIC (FIXED)
    # ==================================================================
    def on_backend_error(self, err):
        self.ticker_label.setText(f"[BACKEND ERROR] {err}")
        self._set_status_style("error")

    def on_backend_output(self):
        if self.demo_mode: 
            while self.proc.canReadLine(): self.proc.readLine()
            return

        while self.proc.canReadLine():
            raw = bytes(self.proc.readLine()).decode("utf-8", errors="ignore").strip()
            if not raw: continue
            self.ticker_label.setText(raw)
            metrics = self.parse_metrics(raw)
            if metrics:
                self.last_metrics = metrics
                self.update_from_metrics(metrics)

    def parse_metrics(self, line: str):
        if "peak=" not in line or "=>" not in line: return None
        try:
            peak_m  = re.search(r"peak=\s*([-\d\.]+)\s*dB", line)
            freq_m  = re.search(r"@\s*([\d\.]+)\s*MHz", line)
            noise_m = re.search(r"noise=\s*([-\d\.]+)", line)
            delta_m = re.search(r"Δ=\s*([-\d\.]+)", line)
            bw_m    = re.search(r"BW=\s*([-\d\.]+)\s*MHz", line)
            hops_m  = re.search(r"hops=\s*(\d+)", line)
            label_m = re.search(r"=>\s*(.+)$", line)

            if not all([peak_m, freq_m, noise_m, delta_m, bw_m, hops_m, label_m]): return None

            return {
                "peak_db":  float(peak_m.group(1)),
                "freq_mhz": float(freq_m.group(1)),
                "noise_db": float(noise_m.group(1)),
                "delta_db": float(delta_m.group(1)),
                "bw_mhz":   float(bw_m.group(1)),
                "hops":     int(hops_m.group(1)),
                "label":    label_m.group(1).strip(),
            }
        except Exception:
            return None

    def freq_to_bearing(self, f_mhz: float) -> float:
        f = max(self.freq_min, min(self.freq_max, f_mhz))
        span = self.freq_max - self.freq_min
        if span <= 0: return 0.0
        frac = (f - self.freq_min) / span
        return (frac * 360.0) % 360.0

    def update_from_metrics(self, m):
        now   = time.time()
        peak  = m["peak_db"]
        freq  = m["freq_mhz"]
        delta = m["delta_db"]
        bw    = m["bw_mhz"]
        hops  = m["hops"]
        label = m["label"]

        # History Update (Spectrum)
        self.power_hist.append(peak)
        self.delta_hist.append(delta)
        if len(self.power_hist) > self.max_hist: self.power_hist.pop(0)
        if len(self.delta_hist) > self.max_hist: self.delta_hist.pop(0)
        self.timeline_curve.setData(list(range(len(self.delta_hist))), self.delta_hist)

        self.delta_val.setText(f"{delta:.1f}")
        self.freq_val.setText(f"{freq:.1f}")
        self.bw_val.setText(f"{bw:.1f}")
        self.hops_val.setText(str(hops))
        
        # --- CLEAN LABELS ---
        if "FRIENDLY" in label or bw > 2.0:
            is_friendly = True
            is_foe = False
            clean_label = "FRIENDLY SIGNAL"
            wave_score = 30 # Gentle wave for friendly
        elif "FOE" in label or ("HOSTILE" in label) or (bw < 2.0 and bw > 0.5):
            is_friendly = False
            is_foe = True
            clean_label = "HOSTILE SIGNAL"
            wave_score = 90 # High wave for foe
        else:
            is_friendly = False
            is_foe = False
            clean_label = "NOISE"
            wave_score = 5 # Low noise

        # --- UPDATE THREAT WAVEFORM ---
        self.threat_wave_data.append(wave_score + random.uniform(-5, 5)) # Add some jitter
        if len(self.threat_wave_data) > 200: self.threat_wave_data.pop(0)
        self.threat_curve.setData(self.threat_wave_data)
        
        # Dynamic Wave Color
        if is_friendly:
            self.threat_curve.setPen(pg.mkPen(C_ACCENT_GREEN, width=2))
            self.threat_curve.setBrush((0, 255, 65, 50))
        elif is_foe:
            self.threat_curve.setPen(pg.mkPen(C_ACCENT_RED, width=2))
            self.threat_curve.setBrush((255, 42, 42, 50))
        else:
            self.threat_curve.setPen(pg.mkPen(C_ACCENT_CYAN, width=1))
            self.threat_curve.setBrush((0, 240, 255, 20))

        # --- CRITICAL FIX: FORCE KILL RED ALERT ---
        if is_friendly:
            self.alert_timer.stop()
            self.blink_state = False
            self.main_container.setStyleSheet(f"background-color: transparent;")
            
            self.status_label.setStyleSheet(f"background: #003300; border: 1px solid {C_ACCENT_GREEN}; color: {C_ACCENT_GREEN}; font-size: 14px; font-weight: 900; padding: 8px; border-radius: 4px;")
            self.status_label.setText("AUTHORIZED TRAFFIC (FRIENDLY)")
            
            self.threat_text.setText("FRIENDLY SIGNAL DETECTED")
            self.threat_text.setStyleSheet(f"color: {C_ACCENT_GREEN}; font-size: 11px; font-weight: bold;")
            self.threat_bar.setValue(100)
            self.threat_bar.setStyleSheet(f"QProgressBar {{ background: black; border: 1px solid {C_BORDER}; }} QProgressBar::chunk {{ background: {C_ACCENT_GREEN}; }}")
            
            rng = 100 
            self.active_track = {"last_seen": now, "range_m": rng, "type": "FRIENDLY"}
            self.add_log(f"{clean_label} | {freq:.1f} MHz", C_ACCENT_GREEN)

        elif is_foe and self.arm_check.isChecked():
            if not self.alert_timer.isActive(): self.alert_timer.start(500)
            
            self.threat_text.setText("HOSTILE DETECTED")
            self.threat_text.setStyleSheet(f"color: {C_ACCENT_RED}; font-size: 11px; font-weight: bold;")
            self.threat_bar.setValue(100)
            self.threat_bar.setStyleSheet(f"QProgressBar {{ background: black; border: 1px solid {C_BORDER}; }} QProgressBar::chunk {{ background: {C_ACCENT_RED}; }}")
            
            rng = 250 + 10 * max(0, delta)
            self.active_track = {"last_seen": now, "range_m": rng, "type": "FOE"}
            self.add_log(f"{clean_label} | {freq:.1f} MHz", C_ACCENT_RED)

        else:
            if self.active_track is not None:
                if now - self.active_track["last_seen"] > 5.0:
                    self.active_track = None
                    self.alert_timer.stop()
                    self.clear_map()
                    self._set_status_style("idle")
                    self.target_dot.setData([], [])

        # MAP RENDER
        if self.active_track is not None:
            bearing_deg = self.freq_to_bearing(freq)
            rng = self.active_track["range_m"]
            
            if self.active_track["type"] == "FRIENDLY":
                self.target_dot.setBrush(pg.mkBrush(C_ACCENT_GREEN))
                self.set_map_threat(delta, rng, bearing_deg, "FRIENDLY")
            else:
                self.target_dot.setBrush(pg.mkBrush(C_ACCENT_RED))
                self.set_map_threat(delta, rng, bearing_deg, "HOSTILE")

    def add_log(self, text, color):
        ts = time.strftime("%H:%M:%S")
        card = f"[{ts}] {text}"
        item = QtWidgets.QListWidgetItem(card)
        item.setForeground(QtGui.QColor(color))
        self.snap_list.insertItem(0, item)
        while self.snap_list.count() > 30: self.snap_list.takeItem(self.snap_list.count() - 1)

    # ==================================================================
    # BLINKING LOGIC
    # ==================================================================
    def trigger_alert(self, active: bool):
        if active:
            if not self.alert_timer.isActive():
                self.alert_timer.start(500)
        else:
            self.alert_timer.stop()
            self.main_container.setStyleSheet(f"background-color: transparent;")
            if self.active_track is None:
                 self.status_label.setStyleSheet(f"background: {C_BG_PANEL}; border: 1px solid {C_ACCENT_CYAN}; color: {C_ACCENT_CYAN}; font-size: 14px; font-weight: 900; padding: 8px; border-radius: 4px;")
                 self.status_label.setText("AIRSPACE STATUS: SCANNING")

    def toggle_alert_state(self):
        self.blink_state = not self.blink_state
        
        if self.blink_state:
            self.main_container.setStyleSheet(f"background-color: rgba(50, 0, 0, 0.3); border: 2px solid {C_ACCENT_RED};")
            self.status_label.setStyleSheet(f"background: {C_ACCENT_RED}; color: #ffffff; border: 2px solid #ffffff; font-size: 16px; font-weight: 900; padding: 8px; border-radius: 4px;")
            self.status_label.setText("!!! HOSTILE SIGNAL LOCKED !!!")
        else:
            self.main_container.setStyleSheet(f"background-color: transparent; border: none;")
            self.status_label.setStyleSheet(f"background: #330000; color: {C_ACCENT_RED}; border: 2px solid {C_ACCENT_RED}; font-size: 16px; font-weight: 900; padding: 8px; border-radius: 4px;")

    def _set_status_style(self, mode: str):
        if mode == "idle":
             self.status_label.setStyleSheet(f"background: {C_BG_PANEL}; border: 1px solid {C_ACCENT_CYAN}; color: {C_ACCENT_CYAN}; font-size: 14px; font-weight: 900; padding: 8px; border-radius: 4px;")
             self.status_label.setText("AIRSPACE STATUS: SCANNING")
        elif mode == "friendly":
             self.status_label.setStyleSheet(f"background: #003300; border: 1px solid {C_ACCENT_GREEN}; color: {C_ACCENT_GREEN}; font-size: 14px; font-weight: 900; padding: 8px; border-radius: 4px;")
             self.status_label.setText("AUTHORIZED TRAFFIC (FRIENDLY)")
        elif mode == "hostile":
             self.status_label.setStyleSheet(f"background: #330000; border: 1px solid {C_ACCENT_RED}; color: {C_ACCENT_RED}; padding: 8px;")
        elif mode == "error":
            self.status_label.setText("SYSTEM ERROR")
            self.status_label.setStyleSheet(f"background: #330000; border: 1px solid {C_ACCENT_RED}; color: {C_ACCENT_RED}; padding: 8px;")

    def animate_radar(self):
        self.sweep_deg = (self.sweep_deg + 8) % 360.0
        a = math.radians(self.sweep_deg)
        self.sweep_line.setData([0, 1.1*math.cos(a)], [0, 1.1*math.sin(a)])

        if self.active_track is None or self.last_metrics is None:
            self.target_dot.setData([], [])
            return

        f = self.last_metrics["freq_mhz"]
        delta = self.last_metrics["delta_db"]
        bearing_deg = self.freq_to_bearing(f)

        strength = max(0.0, min(1.0, delta / 30.0))
        r = 0.3 + 0.6 * strength
        ta = math.radians(bearing_deg)
        self.target_dot.setData([r * math.cos(ta)], [r * math.sin(ta)])

    def clear_map(self):
        try: self.web.page().runJavaScript("if(window.clearThreat)window.clearThreat();")
        except Exception: pass

    def manual_clear_track(self):
        self.active_track = None
        self.trigger_alert(False)
        self.clear_map()
        self._set_status_style("idle")
        self.target_dot.setData([], [])

    def set_map_threat(self, delta_db, range_m, bearing_deg, type_str):
        js = f"if(window.setThreatType)window.setThreatType(1, {delta_db}, {range_m}, {bearing_deg}, '{type_str}');"
        try: self.web.page().runJavaScript(js)
        except Exception: pass

    def update_clock(self):
        self.clock_label.setText(time.strftime("%H:%M:%S Z"))

    def stop_rf(self):
        if self.proc.state() != QtCore.QProcess.NotRunning:
            self.proc.kill()
            self.ticker_label.setText("PROCESS TERMINATED BY USER")
            self.trigger_alert(False)
            self.active_track = None
            self.clear_map()

    def closeEvent(self, event):
        try:
            if self.proc.state() != QtCore.QProcess.NotRunning:
                self.proc.kill()
        except Exception: pass
        super().closeEvent(event)

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = AuroraCommand()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()