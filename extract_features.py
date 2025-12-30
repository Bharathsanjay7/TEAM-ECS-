def extract_landmarks(hand_landmarks):
    features = []
    for lm in hand_landmarks.landmark:
        features.append(lm.x)
        features.append(lm.y)
    return features
