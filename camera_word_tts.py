import cv2
import mediapipe as mp
import joblib
import pyttsx3

# ===============================
# LOAD MODEL
# ===============================
model = joblib.load("camera_rf.pkl")
le = joblib.load("camera_labels.pkl")

# ===============================
# TEXT TO SPEECH
# ===============================
engine = pyttsx3.init()
engine.setProperty("rate", 160)

def speak(text):
    engine.stop()
    engine.say(str(text))
    engine.runAndWait()

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

            mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

    # 🔊 CONTINUOUS SPEECH (NO BLOCKING)
    if gesture_text:
        speak(gesture_text)

    # DISPLAY
    cv2.putText(
        frame,
        f"Gesture: {gesture_text}",
        (30, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (0, 255, 0),
        3
    )

    cv2.imshow("Gesture → Text → Speech (Continuous)", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
