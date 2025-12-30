import cv2
import mediapipe as mp
import joblib
import os
import traceback
import numpy as np
import pyttsx3

MODEL_FILE = "camera_rf.pkl"
LABEL_FILE = "camera_labels.pkl"

# ===============================
# LOAD MODEL & LABELS (SAFE)
# ===============================
def load_model_and_labels(model_path, label_path):
    if not os.path.exists(model_path) or os.path.getsize(model_path) == 0:
        print(f"ERROR: Model file '{model_path}' missing or empty")
        raise SystemExit(1)
    if not os.path.exists(label_path) or os.path.getsize(label_path) == 0:
        print(f"ERROR: Label file '{label_path}' missing or empty")
        raise SystemExit(1)

    try:
        model = joblib.load(model_path)
        le = joblib.load(label_path)
        print("Model expects features:", model.n_features_in_)
        return model, le
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)

model, le = load_model_and_labels(MODEL_FILE, LABEL_FILE)

# ===============================
# TEXT TO SPEECH
# ===============================
engine = pyttsx3.init()
engine.setProperty("rate", 160)

def speak(text):
    engine.stop()        # 🔑 important
    engine.say(text)
    engine.runAndWait()

last_spoken_text = ""

# ===============================
# MEDIAPIPE
# ===============================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)
mp_draw = mp.solutions.drawing_utils

# ===============================
# CAMERA
# ===============================
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌ Camera not opened")
    exit()

print("✅ Camera started (ESC to exit)")

# ===============================
# MAIN LOOP
# ===============================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    gesture_text = ""

    if result.multi_hand_landmarks:
        for hand in result.multi_hand_landmarks:
            features = []
            for lm in hand.landmark:
                features.extend([lm.x, lm.y])

            if len(features) == model.n_features_in_:
                pred = model.predict([features])
                gesture_text = str(le.inverse_transform(pred)[0])

            mp_draw.draw_landmarks(
                frame,
                hand,
                mp_hands.HAND_CONNECTIONS
            )

    # ===============================
    # TEXT TO SPEECH LOGIC
    # ===============================
    if gesture_text and gesture_text != last_spoken_text:
        speak(gesture_text)
        last_spoken_text = gesture_text

    # ===============================
    # DISPLAY
    # ===============================
    cv2.rectangle(frame, (0, 0), (640, 90), (0, 0, 0), -1)

    cv2.putText(
        frame,
        f"Gesture: {gesture_text}",
        (40, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (0, 255, 0),
        3
    )

    cv2.imshow("Camera Gesture Recognition + Speech", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
