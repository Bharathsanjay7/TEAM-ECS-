#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ---------------------------
# Defaults tuned from your logs
# ---------------------------
DEFAULT_START_MHZ = 2400
DEFAULT_END_MHZ   = 2483
DEFAULT_BIN_HZ    = 1_000_000
DEFAULT_LNA       = 8
DEFAULT_VGA       = 16
DEFAULT_INTERVAL  = 0.5

# Gates (tune if needed)
DEFAULT_POWER_GATE_DB = -20.0   # reject weak background
DEFAULT_DELTA_GATE_DB = 45.0    # require strong delta above noise
DEFAULT_MIN_HOPS      = 25      # lots of different peaks across the band => hopping
DEFAULT_ACTIVE_RISE_DB = 10.0   # bins above (noise + this) are treated "active" for BW calc

# Wi-Fi ignore heuristics
WIFI_CENTERS_MHZ = [2412, 2437, 2462]
WIFI_CENTER_TOL_MHZ = 15.0

# Swarm detection parameters
SEG_WIDTH_MHZ = 5.0          # each segment ~5 MHz wide
MIN_SEG_ACTIVE_BINS = 8      # ignore tiny segments


@dataclass
class SweepPoint:
    freq_hz: float
    p_db: float


def median(xs: List[float]) -> float:
    if not xs:
        return float("nan")
    return statistics.median(xs)


def parse_sweep_line(line: str) -> Optional[Tuple[str, int, int, int, List[float]]]:
    """
    hackrf_sweep output line example:
    2025-12-01, 14:14:28.777402, 2400000000, 2405000000, 1000000.00, 20, -67.71, -65.42, ...
    returns: (ts_str, f_start, f_end, bin_hz, powers[])
    """
    s = line.strip()
    if not s:
        return None
    if s.startswith("call ") or s.startswith("Sweeping") or s.startswith("Stop with") or s.endswith("sweeps/second"):
        return None

    parts = [p.strip() for p in s.split(",")]
    if len(parts) < 7:
        return None

    ts_str = f"{parts[0]} {parts[1]}"

    try:
        f_start = int(parts[2])
        f_end   = int(parts[3])
        bin_hz  = int(float(parts[4]))
        powers = [float(x) for x in parts[6:]]
        return ts_str, f_start, f_end, bin_hz, powers
    except Exception:
        return None


def build_points(f_start: int, f_end: int, bin_hz: int, powers: List[float]) -> List[SweepPoint]:
    span = f_end - f_start
    n = len(powers)
    if n <= 0 or span <= 0:
        return []

    step = span / n
    pts = []
    for i, p in enumerate(powers):
        freq = f_start + (i + 0.5) * step
        pts.append(SweepPoint(freq_hz=freq, p_db=p))
    return pts


def mhz(hz: float) -> float:
    return hz / 1e6


def near_wifi_center(peak_mhz: float) -> bool:
    for c in WIFI_CENTERS_MHZ:
        if abs(peak_mhz - c) <= WIFI_CENTER_TOL_MHZ:
            return True
    return False


def compute_window_metrics(window_points: List[SweepPoint],
                           window_peak_freqs: List[float],
                           power_gate_db: float,
                           active_rise_db: float) -> dict:
    if not window_points:
        return {
            "noise_db": float("nan"),
            "peak_db": float("nan"),
            "peak_freq_hz": float("nan"),
            "delta_db": float("nan"),
            "bw_mhz": 0.0,
            "hops": 0,
            "active_bins": 0,
        }

    all_p = [p.p_db for p in window_points]
    noise_db = median(all_p)

    peak_pt = max(window_points, key=lambda x: x.p_db)
    peak_db = peak_pt.p_db
    peak_freq_hz = peak_pt.freq_hz
    delta_db = peak_db - noise_db

    thr = max(noise_db + active_rise_db, power_gate_db)
    act = [p for p in window_points if p.p_db >= thr]

    active_bins = len(act)
    if active_bins:
        fmin = min(p.freq_hz for p in act)
        fmax = max(p.freq_hz for p in act)
        bw_mhz = max(0.0, (fmax - fmin) / 1e6)
    else:
        bw_mhz = 0.0

    # hops = distinct MHz peaks inside this interval
    hops = len(set(int(round(mhz(f))) for f in window_peak_freqs))

    return {
        "noise_db": noise_db,
        "peak_db": peak_db,
        "peak_freq_hz": peak_freq_hz,
        "delta_db": delta_db,
        "bw_mhz": bw_mhz,
        "hops": hops,
        "active_bins": active_bins,
    }


def classify(metrics: dict,
             power_gate_db: float,
             delta_gate_db: float,
             min_hops: int) -> str:
    """
    Returns one of: 
    - "FRIENDLY (RadioLink)" (Wide)
    - "FOE (FlySky)"         (Narrow)
    - "WIFI/WIDE (ignored)"
    - "NOISE/OTHER"
    """
    peak_db = metrics["peak_db"]
    delta_db = metrics["delta_db"]
    peak_mhz = mhz(metrics["peak_freq_hz"])
    bw_mhz = metrics["bw_mhz"]
    hops = metrics["hops"]

    if peak_db != peak_db:  # NaN
        return "NO DATA"

    # 1. WiFi filtering (Very wide, low hopping)
    wifi_like = near_wifi_center(peak_mhz) and (bw_mhz >= 12.0) and (hops <= 10)
    if wifi_like:
        return "WIFI/WIDE (ignored)"

    # 2. RC-Link Logic
    # Must meet basic signal strength and hopping requirements
    rc_like = (peak_db >= power_gate_db) and (delta_db >= delta_gate_db) and (hops >= min_hops)
    
    if rc_like:
        # --- NEW LOGIC: Bandwidth Classification ---
        # RadioLink AT10 = DSSS (>2 MHz width)
        if bw_mhz > 2.0:
            return "FRIENDLY (RadioLink)"
        
        # FlySky = FHSS (Very Narrow, <1 MHz width)
        # We default anything else RC-like to Foe
        else:
            return "FOE (FlySky)"

    return "NOISE/OTHER"


def segment_id_for_freq(freq_hz: float, start_mhz: float) -> int:
    """Bucket a frequency into a segment index (0,1,2,...) for swarm detection."""
    f_mhz = mhz(freq_hz)
    rel = f_mhz - start_mhz
    if rel < 0:
        return -1
    return int(rel // SEG_WIDTH_MHZ)


def run():
    ap = argparse.ArgumentParser(description="2.4 GHz RC-like FHSS detector (HackRF + hackrf_sweep)")
    ap.add_argument("--start-mhz", type=float, default=DEFAULT_START_MHZ)
    ap.add_argument("--end-mhz", type=float, default=DEFAULT_END_MHZ)
    ap.add_argument("--bin-hz", type=int, default=DEFAULT_BIN_HZ)
    ap.add_argument("--lna", type=int, default=DEFAULT_LNA)
    ap.add_argument("--vga", type=int, default=DEFAULT_VGA)
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    ap.add_argument("--power-gate", type=float, default=DEFAULT_POWER_GATE_DB)
    ap.add_argument("--delta-gate", type=float, default=DEFAULT_DELTA_GATE_DB)
    ap.add_argument("--min-hops", type=int, default=DEFAULT_MIN_HOPS)
    ap.add_argument("--active-rise", type=float, default=DEFAULT_ACTIVE_RISE_DB)
    ap.add_argument("--amp", action="store_true", help="Enable HackRF amp (only if needed)")
    args = ap.parse_args()

    f_arg = f"{args.start_mhz}:{args.end_mhz}"

    cmd = [
        "hackrf_sweep",
        "-f", f_arg,
        "-w", str(args.bin_hz),
        "-l", str(args.lna),
        "-g", str(args.vga),
    ]
    if args.amp:
        cmd += ["-a", "1"]

    print("[*] Starting:", " ".join(cmd), flush=True)
    print(
        f"[*] Output every {args.interval:.1f}s | power_gate={args.power_gate} dB | "
        f"delta_gate={args.delta_gate} dB | min_hops={args.min_hops}",
        flush=True
    )

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
    except FileNotFoundError:
        print("[!] hackrf_sweep not found. Install HackRF tools: sudo apt install hackrf", flush=True)
        sys.exit(1)

    window_points: List[SweepPoint] = []
    window_peak_freqs: List[float] = []

    next_tick = time.time() + args.interval
    last_ts_str = ""
    last_print = 0.0
    start_mhz = args.start_mhz

    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            parsed = parse_sweep_line(raw)
            if parsed is None:
                now = time.time()
                if now - last_print > max(2.0, args.interval * 4):
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  waiting for sweep data...", flush=True)
                    last_print = now
                continue

            ts_str, f_start, f_end, bin_hz, powers = parsed
            last_ts_str = ts_str

            pts = build_points(f_start, f_end, bin_hz, powers)
            if not pts:
                continue

            window_points.extend(pts)

            peak_pt = max(pts, key=lambda x: x.p_db)
            window_peak_freqs.append(peak_pt.freq_hz)

            now = time.time()
            if now >= next_tick:
                # ---- swarm segmentation ----
                seg_points = {}
                seg_line_peaks = {}

                for p in window_points:
                    sid = segment_id_for_freq(p.freq_hz, start_mhz)
                    if sid < 0:
                        continue
                    seg_points.setdefault(sid, []).append(p)

                for f in window_peak_freqs:
                    sid = segment_id_for_freq(f, start_mhz)
                    if sid < 0:
                        continue
                    seg_line_peaks.setdefault(sid, []).append(f)

                rc_links = []  # (metrics, label, sid)
                primary = None

                for sid, pts_seg in seg_points.items():
                    if len(pts_seg) < MIN_SEG_ACTIVE_BINS:
                        continue

                    m_seg = compute_window_metrics(
                        pts_seg,
                        seg_line_peaks.get(sid, []),
                        power_gate_db=args.power_gate,
                        active_rise_db=args.active_rise,
                    )
                    label_seg = classify(
                        m_seg,
                        power_gate_db=args.power_gate,
                        delta_gate_db=args.delta_gate,
                        min_hops=args.min_hops,
                    )

                    # Updated check for new FRIENDLY/FOE labels
                    if "FRIENDLY" in label_seg or "FOE" in label_seg:
                        rc_links.append((m_seg, label_seg, sid))
                        if primary is None or m_seg["delta_db"] > primary[0]["delta_db"]:
                            primary = (m_seg, label_seg, sid)

                swarm_size = len(rc_links)

                if primary is None:
                    metrics = compute_window_metrics(
                        window_points,
                        window_peak_freqs,
                        power_gate_db=args.power_gate,
                        active_rise_db=args.active_rise,
                    )
                    label = classify(
                        metrics,
                        power_gate_db=args.power_gate,
                        delta_gate_db=args.delta_gate,
                        min_hops=args.min_hops,
                    )
                else:
                    metrics, label, _sid = primary

                print(
                    f"{last_ts_str}  "
                    f"peak={metrics['peak_db']:6.1f} dB @ {mhz(metrics['peak_freq_hz']):7.1f} MHz | "
                    f"noise={metrics['noise_db']:6.1f} | Δ={metrics['delta_db']:5.1f} | "
                    f"BW={metrics['bw_mhz']:5.1f} MHz | hops={metrics['hops']:2d} | "
                    f"swarm={swarm_size:2d}  => {label}",
                    flush=True
                )

                if swarm_size > 1:
                    for idx, (m_seg, _lab, sid) in enumerate(rc_links, start=1):
                        print(
                            f"[SWARM] link#{idx} seg={sid:02d} "
                            f"peak={m_seg['peak_db']:5.1f} dB @ {mhz(m_seg['peak_freq_hz']):7.1f} MHz | "
                            f"Δ={m_seg['delta_db']:5.1f} | BW={m_seg['bw_mhz']:5.1f} MHz | "
                            f"hops={m_seg['hops']:2d}",
                            flush=True
                        )

                window_points.clear()
                window_peak_freqs.clear()
                next_tick = now + args.interval
                last_print = now

        rc = proc.wait(timeout=1)
        print(f"[!] hackrf_sweep exited with code {rc}", flush=True)

    except KeyboardInterrupt:
        print("\n[*] Stopping...", flush=True)
        try:
            proc.terminate()
        except Exception:
            pass
    except Exception as e:
        print(f"[!] Error: {e}", flush=True)
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    run()