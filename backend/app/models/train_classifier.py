"""
Module 4: SIF Classification — baseline model training.

Trains TF-IDF + Logistic Regression on the synthetic dataset per spec
section 14 (AI/ML strategy: start with classical ML, not a huge LLM).

Run:
    python -m app.models.train_classifier

Produces: app/models/sif_classifier.joblib
Prints accuracy / precision / recall / F1 (recall is the priority metric
per spec section 30 — missing a real SIF precursor is worse than a
false alarm).
"""
import os
import sys
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_reports.csv")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "sif_classifier.joblib")


def main():
    df = pd.read_csv(DATA_PATH)
    X = df["report_text"]
    y = df["sif_potential"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=5000)),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])

    pipeline.fit(X_train, y_train)
    preds = pipeline.predict(X_test)

    acc = accuracy_score(y_test, preds)
    prec = precision_score(y_test, preds)
    rec = recall_score(y_test, preds)
    f1 = f1_score(y_test, preds)
    cm = confusion_matrix(y_test, preds)

    print("=== SIF Classifier Evaluation (held-out synthetic test set) ===")
    print(f"Accuracy:  {acc:.3f}")
    print(f"Precision: {prec:.3f}")
    print(f"Recall:    {rec:.3f}  <- prioritized per spec (missing a SIF precursor is costlier than a false alarm)")
    print(f"F1:        {f1:.3f}")
    print(f"Confusion matrix [[TN FP] [FN TP]]:\n{cm}")

    joblib.dump(pipeline, MODEL_PATH)
    print(f"\nSaved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
