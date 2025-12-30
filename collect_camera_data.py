import cv2
import mediapipe as mp
import csv
import os

GESTURE_LABEL = "Stop"   # change for 
SAMPLES = 200
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1)
cap = cv2.VideoCapture(0)

data = []

print("Show gesture:", GESTURE_LABEL)
print("Collecting samples...")

while len(data) < SAMPLES:
    ret, frame = cap.read()
    if not ret:
        continue

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    if result.multi_hand_landmarks:
        for hand in result.multi_hand_landmarks:
            features = []
            for lm in hand.landmark:
                features.extend([lm.x, lm.y])

            features.append(GESTURE_LABEL)
            data.append(features)

            cv2.putText(frame, f"Samples: {len(data)}",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0,255,0), 2)

    cv2.imshow("Collecting Camera Data", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()

if len(data) > 0:
    file_exists = os.path.isfile("camera_data.csv")

    with open("camera_data.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)

    print("Saved", len(data), "samples")
else:
    print("No data collected!")
