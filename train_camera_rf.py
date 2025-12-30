import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import joblib

# Load dataset
data = pd.read_csv("camera_data.csv", header=None)

X = data.iloc[:, :-1]   # 42 features
y = data.iloc[:, -1]    # labels

print("Training feature count:", X.shape[1])

le = LabelEncoder()
y_enc = le.fit_transform(y)

model = RandomForestClassifier(
    n_estimators=200,
    random_state=42
)

model.fit(X, y_enc)

joblib.dump(model, "camera_rf.pkl")
joblib.dump(le, "camera_labels.pkl")

print("Model trained and saved with", X.shape[1], "features")
