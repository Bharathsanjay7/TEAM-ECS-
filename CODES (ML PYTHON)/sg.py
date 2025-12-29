import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time
import subprocess
import platform
import webbrowser
from collections import deque

# ===================== CONFIG =====================
pyautogui.FAILSAFE = False

# Performance optimizations
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# Smoothing
SMOOTHING_WINDOW = 3
CLICK_DELAY = 0.5
GESTURE_HOLD = 0.15
FINGER_MARGIN = 0.025

# Cursor speed
CURSOR_SPEED = 1.3

# Blink settings
BLINK_SCROLL_ENABLED = True
BLINK_THRESHOLD = 0.21
BLINK_TIME_WINDOW = 1.2
BLINK_COOLDOWN = 0.25
SCROLL_SPEED = 100

# Special modes
DRAG_MODE = False
DRAG_ACTIVE = False
DRAG_HOLD_TIME = 0.8

DRAWING_MODE = False
drawing_points = []

SCREENSHOT_MODE = False

# Volume control
VOLUME_CONTROL_MODE = False
last_volume_action = 0

# ===================== INIT =====================
screen_w, screen_h = pyautogui.size()

# Hand detection
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6,
    model_complexity=0
)

# Face detection
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=False,
    min_detection_confidence=0.4,
    min_tracking_confidence=0.4
)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

# Buffers
pos_buffer_x = deque(maxlen=SMOOTHING_WINDOW)
pos_buffer_y = deque(maxlen=SMOOTHING_WINDOW)

# Tracking variables
blink_times = []
is_blinking = False
last_blink_complete = 0
scroll_active = False
scroll_direction = None
scroll_start_time = 0

last_action_time = 0
current_gesture = None
gesture_start = None
last_cursor_update = 0

drag_gesture_start = None
drag_start_pos = None

LAST_PINCH_DISTANCE = None
last_hand_y = None

# ===================== HELPER FUNCTIONS =====================

def open_paint():
    """Open MS Paint"""
    try:
        if platform.system() == "Windows":
            subprocess.Popen("mspaint.exe")
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-a", "Preview"])
        else:
            subprocess.Popen(["xdg-open", "drawing"])
        print("✓ Paint opened")
    except Exception as e:
        print(f"✗ Could not open paint: {e}")


def open_browser():
    """Open default web browser"""
    try:
        webbrowser.open('https://www.google.com')
        print("✓ Browser opened")
    except Exception as e:
        print(f"✗ Could not open browser: {e}")


def take_screenshot():
    """Take a screenshot"""
    try:
        screenshot = pyautogui.screenshot()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        screenshot.save(filename)
        print(f"✓ Screenshot saved: {filename}")
        return filename
    except Exception as e:
        print(f"✗ Screenshot failed: {e}")
        return None


def show_active_windows():
    """Show active windows/tabs"""
    try:
        if platform.system() == "Windows":
            pyautogui.hotkey('win', 'tab')
        elif platform.system() == "Darwin":
            pyautogui.hotkey('command', 'tab')
        else:
            pyautogui.hotkey('alt', 'tab')
        print("✓ Showing active windows")
    except Exception as e:
        print(f"✗ Could not show windows: {e}")


def adjust_volume(increase=True):
    """Adjust system volume"""
    try:
        if platform.system() == "Windows":
            for _ in range(2):  # Press multiple times for noticeable change
                pyautogui.press('volumeup' if increase else 'volumedown')
        elif platform.system() == "Darwin":
            import osascript
            direction = 10 if increase else -10
            osascript.run(f"set volume output volume (output volume of (get volume settings) + {direction})")
        else:
            subprocess.run(['amixer', 'set', 'Master', '10%+' if increase else '10%-'])
        print(f"✓ Volume {'UP' if increase else 'DOWN'}")
        return True
    except Exception as e:
        print(f"✗ Volume control failed: {e}")
        return False


def adjust_brightness(increase=True):
    """Adjust screen brightness - simplified method"""
    try:
        if platform.system() == "Windows":
            # Use keyboard shortcuts (works on most laptops)
            # Many laptops use Fn + brightness keys, but we'll try direct keys
            import wmi
            c = wmi.WMI(namespace='wmi')
            methods = c.WmiMonitorBrightnessMethods()[0]
            if increase:
                methods.WmiSetBrightness(100, 0)  # Increase
            else:
                methods.WmiSetBrightness(50, 0)   # Decrease
            print(f"✓ Brightness {'UP' if increase else 'DOWN'}")
            return True
        else:
            print("⚠ Brightness control only available on Windows")
            return False
    except Exception as e:
        # Fallback: just show message
        print(f"⚠ Brightness control not available: {e}")
        print("   Try using your laptop's brightness keys instead")
        return False


def lock_screen():
    """Lock the computer screen"""
    try:
        if platform.system() == "Windows":
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation")
        elif platform.system() == "Darwin":
            subprocess.Popen(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"])
        else:
            subprocess.Popen(["xdg-screensaver", "lock"])
        print("✓ Screen locked")
    except Exception as e:
        print(f"✗ Could not lock screen: {e}")


def get_distance(p1, p2):
    """Calculate distance between two points"""
    return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)


def get_angle(p1, p2):
    """Get angle of line between two points"""
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    return np.degrees(np.arctan2(dy, dx))


# ===================== DETECTION FUNCTIONS =====================

def get_eye_aspect_ratio(landmarks, eye_indices):
    """Calculate eye aspect ratio"""
    points = [landmarks[i] for i in eye_indices]
    v1 = np.linalg.norm(np.array([points[1].x, points[1].y]) - np.array([points[5].x, points[5].y]))
    v2 = np.linalg.norm(np.array([points[2].x, points[2].y]) - np.array([points[4].x, points[4].y]))
    h = np.linalg.norm(np.array([points[0].x, points[0].y]) - np.array([points[3].x, points[3].y]))
    return (v1 + v2) / (2.0 * h)


def detect_blink(face_landmarks):
    """Detect blinks"""
    global is_blinking, last_blink_complete, blink_times
    
    LEFT_EYE = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]
    
    left_ear = get_eye_aspect_ratio(face_landmarks.landmark, LEFT_EYE)
    right_ear = get_eye_aspect_ratio(face_landmarks.landmark, RIGHT_EYE)
    avg_ear = (left_ear + right_ear) / 2.0
    
    now = time.time()
    
    if avg_ear < BLINK_THRESHOLD and not is_blinking:
        is_blinking = True
    elif avg_ear >= BLINK_THRESHOLD and is_blinking:
        is_blinking = False
        if now - last_blink_complete > BLINK_COOLDOWN:
            blink_times.append(now)
            last_blink_complete = now
            blink_times[:] = [t for t in blink_times if now - t <= BLINK_TIME_WINDOW]
    
    return len(blink_times), avg_ear


def process_blink_scroll(blink_count):
    """Process scroll from blinks"""
    global scroll_active, scroll_direction, scroll_start_time, blink_times
    
    now = time.time()
    
    if blink_count >= 2 and now - last_action_time > 0.4:
        if blink_count == 2:
            scroll_direction = "DOWN"
            scroll_active = True
            scroll_start_time = now
            blink_times.clear()
            pyautogui.scroll(-SCROLL_SPEED)
        elif blink_count >= 3:
            scroll_direction = "UP"
            scroll_active = True
            scroll_start_time = now
            blink_times.clear()
            pyautogui.scroll(SCROLL_SPEED)
    
    if scroll_active and now - scroll_start_time < 0.6:
        pyautogui.scroll(-8 if scroll_direction == "DOWN" else 8)
    elif scroll_active:
        scroll_active = False


def count_total_fingers(hand_landmarks_list):
    """Count fingers across all hands"""
    total = 0
    for hand_landmarks in hand_landmarks_list:
        lm = hand_landmarks.landmark
        
        tips = [8, 12, 16, 20]
        pips = [6, 10, 14, 18]
        for tip, pip in zip(tips, pips):
            if lm[tip].y < lm[pip].y - FINGER_MARGIN:
                total += 1
        
        thumb_up = lm[4].x < lm[3].x - FINGER_MARGIN if lm[4].x < 0.5 else lm[4].x > lm[3].x + FINGER_MARGIN
        if thumb_up:
            total += 1
    
    return total


def fingers_up(lm):
    """Detect extended fingers on one hand"""
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    
    fingers = []
    for tip, pip in zip(tips, pips):
        fingers.append(lm[tip].y < lm[pip].y - FINGER_MARGIN)
    
    thumb_up = lm[4].x < lm[3].x - FINGER_MARGIN if lm[4].x < 0.5 else lm[4].x > lm[3].x + FINGER_MARGIN
    
    return fingers, fingers.count(True), thumb_up


def smooth_position(x, y):
    """Smooth cursor movement"""
    pos_buffer_x.append(x)
    pos_buffer_y.append(y)
    
    if len(pos_buffer_x) > 0:
        return sum(pos_buffer_x) / len(pos_buffer_x), sum(pos_buffer_y) / len(pos_buffer_y)
    return x, y


def stable_gesture(gesture):
    """Check gesture stability"""
    global current_gesture, gesture_start
    now = time.time()
    
    if gesture != current_gesture:
        current_gesture = gesture
        gesture_start = now
        return None
    
    if now - gesture_start >= GESTURE_HOLD:
        return gesture
    return None

# ===================== MAIN LOOP =====================

print("🚀 ADVANCED GESTURE CONTROL v2.0")
print("\n⌨️  KEYBOARD SHORTCUTS:")
print("  ESC - Exit")
print("  P   - Open Paint")
print("  B   - Toggle blink scroll")
print("  D   - Toggle drag mode")
print("  V   - Toggle volume control")
print("  W   - Open browser")
print("  S   - Toggle screenshot mode")
print("  R   - Toggle drawing mode")
print("  L   - Lock screen")
print("\n✋ HAND GESTURES:")
print("  1 finger   → Move cursor")
print("  2 fingers  → Right click")
print("  3 fingers  → Left click")
print("  4 fingers  → Switch tab")
print("  5 fingers  → Pause/Play")
print("  10 fingers → Show all windows")
print("  Fist       → Idle")
print("\n👁️  BLINK CONTROLS:")
print("  2x blink   → Scroll down")
print("  3x blink   → Scroll up")
print("\n🎯 DRAG MODE (Press D):")
print("  1 finger hold 1sec → Start drag")
print("  Move hand          → Drag")
print("  Fist               → Drop")
print("\n🔊 VOLUME MODE (Press V):")
print("  Hand UP    → Volume UP")
print("  Hand DOWN  → Volume DOWN")
print("\n📸 SCREENSHOT MODE (Press S):")
print("  Peace sign (2 fingers) → Take screenshot")
print("\n🎨 DRAWING MODE (Press R):")
print("  1 finger   → Draw on screen")
print("  Fist       → Clear drawing")

frame_count = 0
fps_start_time = time.time()
fps = 0

while True:
    success, frame = cap.read()
    if not success:
        break
    
    frame_count += 1
    if frame_count % 30 == 0:
        fps = 30 / (time.time() - fps_start_time)
        fps_start_time = time.time()
    
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    hand_result = hands.process(rgb)
    face_result = face_mesh.process(rgb) if frame_count % 2 == 0 else None
    
    status = "NO HAND"
    now = time.time()
    
    # ========== BLINK DETECTION ==========
    if BLINK_SCROLL_ENABLED and face_result and face_result.multi_face_landmarks:
        face = face_result.multi_face_landmarks[0]
        current_blink_count, ear = detect_blink(face)
        process_blink_scroll(current_blink_count)
        
        if scroll_active:
            color = (0, 255, 255) if scroll_direction == "UP" else (255, 0, 255)
            arrow = "↑↑↑ UP ↑↑↑" if scroll_direction == "UP" else "↓↓↓ DOWN ↓↓↓"
            cv2.putText(frame, arrow, (w//2 - 100, h//2), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)
    
    # ========== HAND GESTURE PROCESSING ==========
    if hand_result.multi_hand_landmarks:
        num_hands = len(hand_result.multi_hand_landmarks)
        total_fingers = count_total_fingers(hand_result.multi_hand_landmarks)
        
        # 10 FINGERS - SHOW WINDOWS
        if total_fingers >= 9:
            status = "10 FINGERS - SHOW WINDOWS"
            if stable_gesture("10FINGER") and now - last_action_time > 1.0:
                show_active_windows()
                last_action_time = now
                cv2.putText(frame, "🗔 WINDOWS", (w//2 - 80, h//2), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)
        
        else:
            hand = hand_result.multi_hand_landmarks[0]
            lm = hand.landmark
            
            fingers, count, thumb_up = fingers_up(lm)
            
            index_x = int(lm[8].x * w)
            index_y = int(lm[8].y * h)
            
            screen_x = np.interp(index_x, (w * 0.1, w * 0.9), (0, screen_w)) * CURSOR_SPEED
            screen_y = np.interp(index_y, (h * 0.1, h * 0.9), (0, screen_h)) * CURSOR_SPEED
            screen_x = max(0, min(screen_w - 1, screen_x))
            screen_y = max(0, min(screen_h - 1, screen_y))
            
            smooth_x, smooth_y = smooth_position(screen_x, screen_y)
            
            # Get hand center Y position for volume control
            hand_center_y = lm[9].y  # Middle of palm
            
            # ========== DRAWING MODE ==========
            if DRAWING_MODE:
                if count == 1 and fingers[0]:
                    drawing_points.append((index_x, index_y))
                    status = "🎨 DRAWING"
                    cv2.circle(frame, (index_x, index_y), 5, (255, 0, 255), -1)
                elif count == 0:
                    drawing_points.clear()
                    status = "🎨 CLEARED"
                
                # Draw all points
                for i in range(1, len(drawing_points)):
                    cv2.line(frame, drawing_points[i-1], drawing_points[i], (255, 0, 255), 3)
            
            # ========== SCREENSHOT MODE ==========
            elif SCREENSHOT_MODE:
                if count == 2 and fingers[0] and fingers[1]:
                    status = "📸 PEACE SIGN"
                    if stable_gesture("SCREENSHOT") and now - last_action_time > 1.5:
                        filename = take_screenshot()
                        if filename:
                            status = f"✓ SAVED: {filename}"
                        last_action_time = now
                        # Flash effect
                        cv2.rectangle(frame, (0, 0), (w, h), (255, 255, 255), 50)
            
            # ========== VOLUME CONTROL MODE ==========
            elif VOLUME_CONTROL_MODE:
                if last_hand_y is not None and now - last_volume_action > 0.3:
                    movement = hand_center_y - last_hand_y
                    
                    if movement < -0.03:  # Hand moved UP
                        if adjust_volume(True):
                            status = "🔊 VOLUME UP"
                            last_volume_action = now
                            cv2.putText(frame, "▲ VOLUME UP ▲", (w//2 - 120, h//2), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
                    
                    elif movement > 0.03:  # Hand moved DOWN
                        if adjust_volume(False):
                            status = "🔉 VOLUME DOWN"
                            last_volume_action = now
                            cv2.putText(frame, "▼ VOLUME DOWN ▼", (w//2 - 150, h//2), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 100, 255), 3)
                
                last_hand_y = hand_center_y
                
                # Draw hand position indicator
                indicator_y = int(hand_center_y * h)
                cv2.circle(frame, (w - 30, indicator_y), 15, (0, 255, 0), -1)
                cv2.line(frame, (w - 30, 50), (w - 30, h - 50), (255, 255, 255), 2)
            
            # ========== DRAG MODE ==========
            elif DRAG_MODE:
                if count == 1 and fingers[0]:
                    if drag_gesture_start is None:
                        drag_gesture_start = now
                    
                    hold_time = now - drag_gesture_start
                    
                    if not DRAG_ACTIVE and hold_time >= DRAG_HOLD_TIME:
                        DRAG_ACTIVE = True
                        drag_start_pos = (smooth_x, smooth_y)
                        pyautogui.mouseDown()
                        status = "🎯 DRAG ACTIVE"
                        cv2.circle(frame, (w//2, h//2), 60, (0, 255, 0), 5)
                    elif DRAG_ACTIVE:
                        pyautogui.moveTo(smooth_x, smooth_y, _pause=False)
                        status = "🎯 DRAGGING"
                        cv2.circle(frame, (index_x, index_y), 15, (0, 255, 0), -1)
                    else:
                        status = f"HOLD ({hold_time:.1f}s)"
                        progress = int((hold_time / DRAG_HOLD_TIME) * 100)
                        cv2.rectangle(frame, (w//2 - 50, h - 50), 
                                    (w//2 - 50 + progress, h - 30), (0, 255, 0), -1)
                
                elif count == 0 and DRAG_ACTIVE:
                    pyautogui.mouseUp()
                    DRAG_ACTIVE = False
                    drag_gesture_start = None
                    status = "✓ DROPPED"
                    cv2.circle(frame, (w//2, h//2), 60, (0, 0, 255), 5)
                    time.sleep(0.2)
                
                else:
                    drag_gesture_start = None
                    if not DRAG_ACTIVE:
                        status = "DRAG MODE"
            
            # ========== NORMAL MODE ==========
            else:
                if count == 0:
                    status = "IDLE"
                    pos_buffer_x.clear()
                    pos_buffer_y.clear()
                
                elif count == 1 and fingers[0]:
                    status = "MOVING"
                    if now - last_cursor_update > 0.008:
                        pyautogui.moveTo(smooth_x, smooth_y, _pause=False)
                        last_cursor_update = now
                    cv2.circle(frame, (index_x, index_y), 8, (0, 255, 0), -1)
                
                elif count == 2 and fingers[0] and fingers[1]:
                    status = "RIGHT CLICK"
                    if stable_gesture("RIGHT") and now - last_action_time > CLICK_DELAY:
                        pyautogui.rightClick()
                        last_action_time = now
                
                elif count == 3 and fingers[0] and fingers[1] and fingers[2]:
                    status = "LEFT CLICK"
                    if stable_gesture("LEFT") and now - last_action_time > CLICK_DELAY:
                        pyautogui.click()
                        last_action_time = now
                
                elif count == 4:
                    status = "SWITCH TAB"
                    if stable_gesture("TAB") and now - last_action_time > CLICK_DELAY:
                        pyautogui.hotkey('alt', 'tab')
                        last_action_time = now
                
                elif count == 4 and thumb_up:
                    status = "PAUSE/PLAY"
                    if stable_gesture("SPACE") and now - last_action_time > CLICK_DELAY:
                        pyautogui.press('space')
                        last_action_time = now
    
    # ========== UI ==========
    bar_height = 130
    cv2.rectangle(frame, (0, 0), (w, bar_height), (0, 0, 0), -1)
    
    cv2.putText(frame, f"STATUS: {status}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(frame, f"FPS: {int(fps)}", (w - 100, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Mode indicators
    mode_text = []
    if DRAG_MODE:
        mode_text.append("DRAG")
    if VOLUME_CONTROL_MODE:
        mode_text.append("VOLUME")
    if BLINK_SCROLL_ENABLED:
        mode_text.append("BLINK")
    if DRAWING_MODE:
        mode_text.append("DRAW")
    if SCREENSHOT_MODE:
        mode_text.append("SCREENSHOT")
    
    cv2.putText(frame, " | ".join(mode_text) if mode_text else "NORMAL MODE", 
               (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
    
    cv2.putText(frame, "P:Paint W:Web D:Drag V:Vol R:Draw S:Screenshot L:Lock", 
               (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    
    cv2.imshow("Advanced Gesture Control v2.0", frame)
    
    # ========== KEYBOARD INPUT ==========
    key = cv2.waitKey(1) & 0xFF
    if key == 27:  # ESC
        break
    elif key == ord('p') or key == ord('P'):
        open_paint()
    elif key == ord('w') or key == ord('W'):
        open_browser()
    elif key == ord('l') or key == ord('L'):
        lock_screen()
    elif key == ord('d') or key == ord('D'):
        DRAG_MODE = not DRAG_MODE
        DRAG_ACTIVE = False
        drag_gesture_start = None
        print(f"{'✓' if DRAG_MODE else '✗'} Drag mode: {DRAG_MODE}")
    elif key == ord('v') or key == ord('V'):
        VOLUME_CONTROL_MODE = not VOLUME_CONTROL_MODE
        last_hand_y = None
        print(f"{'✓' if VOLUME_CONTROL_MODE else '✗'} Volume control: {VOLUME_CONTROL_MODE}")
    elif key == ord('b') or key == ord('B'):
        BLINK_SCROLL_ENABLED = not BLINK_SCROLL_ENABLED
        blink_times.clear()
        print(f"{'✓' if BLINK_SCROLL_ENABLED else '✗'} Blink scroll: {BLINK_SCROLL_ENABLED}")
    elif key == ord('r') or key == ord('R'):
        DRAWING_MODE = not DRAWING_MODE
        drawing_points.clear()
        print(f"{'✓' if DRAWING_MODE else '✗'} Drawing mode: {DRAWING_MODE}")
    elif key == ord('s') or key == ord('S'):
        SCREENSHOT_MODE = not SCREENSHOT_MODE
        print(f"{'✓' if SCREENSHOT_MODE else '✗'} Screenshot mode: {SCREENSHOT_MODE}")

# ===================== CLEANUP =====================
if DRAG_ACTIVE:
    pyautogui.mouseUp()

cap.release()
cv2.destroyAllWindows()
hands.close()
face_mesh.close()
print("✓ Stopped")