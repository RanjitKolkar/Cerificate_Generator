"""
detection_demo.py
Educational deepfake detection demo using simple image features and RandomForest.
* Requires a dataset folder with two subfolders:
    data/real/   -> real images (jpg/png)
    data/fake/   -> manipulated images (jpg/png)
* Run: python detection_demo.py
"""

import os
import cv2
import numpy as np
import pandas as pd
from glob import glob
from tqdm import tqdm
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score, roc_curve, auc
import matplotlib.pyplot as plt
from scipy import fftpack

# ---------- feature functions ----------

def laplacian_variance(img_gray):
    """Measure blur: variance of Laplacian."""
    return cv2.Laplacian(img_gray, cv2.CV_64F).var()

def color_histogram_features(img, bins=16):
    """Return normalized color histogram concatenated for three channels (flattened)."""
    chans = cv2.split(img)
    feats = []
    for ch in chans:
        hist = cv2.calcHist([ch], [0], None, [bins], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        feats.extend(hist)
    return np.array(feats)

def high_frequency_energy(img_gray):
    """Estimate proportion of high-frequency energy via FFT."""
    f = fftpack.fft2(img_gray.astype(float))
    fshift = fftpack.fftshift(f)
    magnitude = np.abs(fshift)
    total = magnitude.sum()
    # mask out low frequencies (center)
    h, w = magnitude.shape
    cy, cx = h//2, w//2
    radius = min(h, w) // 10  # tuneable
    y, x = np.ogrid[:h, :w]
    mask = (x - cx)**2 + (y - cy)**2 > radius**2
    hf = magnitude[mask].sum()
    return float(hf / (total + 1e-12))

def jpeg_quality_estimate(img_path):
    """Simple proxy: if file is JPEG, read quantization from image (OpenCV does not expose quantization).
       As a fallback, return -1. This placeholder is here to show where compression features would be computed.
    """
    ext = os.path.splitext(img_path)[1].lower()
    return 1.0 if ext in (".jpg", ".jpeg") else 0.0

def extract_features(img_path, resize_to=256):
    """Load image, compute features vector."""
    try:
        img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            # fallback using cv2.imread
            img = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not read image")
        # resize to fixed size for stability
        img = cv2.resize(img, (resize_to, resize_to))
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        f1 = laplacian_variance(img_gray)
        f2 = high_frequency_energy(img_gray)
        f3 = color_histogram_features(img, bins=16)  # length 48
        f4 = jpeg_quality_estimate(img_path)

        feats = np.hstack([f1, f2, f3, f4])
        return feats
    except Exception as e:
        print(f"Error extracting features from {img_path}: {e}")
        return None

# ---------- dataset loader ----------

def load_dataset(real_dir="data/real", fake_dir="data/fake", limit_per_class=None):
    files = []
    labels = []
    for p in glob(os.path.join(real_dir, "*")):
        files.append(p); labels.append(0)  # 0 -> real
    for p in glob(os.path.join(fake_dir, "*")):
        files.append(p); labels.append(1)  # 1 -> fake
    # Optional shuffle
    combined = list(zip(files, labels))
    np.random.shuffle(combined)
    files, labels = zip(*combined) if combined else ([], [])
    if limit_per_class:
        # apply per-class limit
        new_files, new_labels = [], []
        counts = {0:0, 1:0}
        for f,l in zip(files, labels):
            if counts[l] < limit_per_class:
                new_files.append(f); new_labels.append(l); counts[l]+=1
        files, labels = new_files, new_labels
    return list(files), list(labels)

# ---------- main ----------

def main():
    real_dir = "data/real"
    fake_dir = "data/fake"

    files, labels = load_dataset(real_dir, fake_dir, limit_per_class=None)
    if len(files) == 0:
        print("No images found. Please prepare folders: data/real/ and data/fake/ with images.")
        return

    print(f"Found {len(files)} images ({sum(1 for l in labels if l==0)} real, {sum(1 for l in labels if l==1)} fake).")
    feature_list = []
    valid_labels = []
    valid_files = []
    for f, l in tqdm(zip(files, labels), total=len(files)):
        feats = extract_features(f)
        if feats is None:
            continue
        feature_list.append(feats)
        valid_labels.append(l)
        valid_files.append(f)

    X = np.vstack(feature_list)
    y = np.array(valid_labels)

    # Simple train/test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    # Train RandomForest
    clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)

    # Evaluate
    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:,1]
    print("\nClassification report:\n", classification_report(y_test, y_pred))
    try:
        auc_score = roc_auc_score(y_test, y_proba)
        print(f"AUC: {auc_score:.4f}")
    except Exception:
        auc_score = None

    # Plot ROC
    if auc_score is not None:
        fpr, tpr, _ = roc_curve(y_test, y_proba)
        plt.figure()
        plt.plot(fpr, tpr, label=f"AUC={auc_score:.3f}")
        plt.plot([0,1],[0,1],'--', color='gray')
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title("ROC Curve")
        plt.legend()
        plt.show()

    # Show some example predictions
    print("\nSample predictions on test set:")
    for i in range(min(10, len(X_test))):
        idx = i
        print(f"File: {valid_files[idx]} -> predicted={clf.predict([X_test[idx]])[0]}, prob={clf.predict_proba([X_test[idx]])[0][1]:.3f}")

if __name__ == "__main__":
    main()
