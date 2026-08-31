"""
Train AEGIS Neural v3 (52 -> 32 -> 16 -> 3, tanh/tanh/linear+softmax)
directly in NumPy, so the trained weights can be exported byte-for-byte
into the JSON format neural_service_v3.py expects - no translation
layer between "what we trained" and "what production loads".

Usage: python3 train_v3_numpy.py
Outputs:
  aegis_neural_v3.json        - production-ready weights
  training_report_v3.json     - metrics for the integration doc
"""
import json
import numpy as np
import pandas as pd

rng = np.random.RandomState(42)

df = pd.read_csv("/home/claude/pipeline/labeled_v3_production.csv")
X = np.load("/home/claude/pipeline/feature_matrix_v3.npy")
y_labels = df["LABEL"].values
CLASSES = ["HOLD", "SELL", "BUY"]
y_idx = np.array([CLASSES.index(l) for l in y_labels])

n, d = X.shape
print(f"Dataset: {n} rows, {d} features")
print("Label counts:", dict(zip(*np.unique(y_labels, return_counts=True))))

# ------------------------------------------------------------------
# Normalize
# ------------------------------------------------------------------
mean = X.mean(axis=0)
std = X.std(axis=0)
std[std < 1e-6] = 1e-6
Xn = (X - mean) / std

# ------------------------------------------------------------------
# One-hot targets, class-weighted (HOLD is ~83% of rows; without
# weighting the network can minimize loss by mostly predicting HOLD)
# ------------------------------------------------------------------
Y = np.eye(3)[y_idx]
class_counts = np.bincount(y_idx, minlength=3)
class_weight = (n / (3.0 * np.maximum(class_counts, 1)))
sample_weight = class_weight[y_idx]
sample_weight = sample_weight / sample_weight.mean()

# ------------------------------------------------------------------
# Time-respecting split for the headline metric (first 80% train,
# last 20% test) PLUS stratified k-fold for a more informative read
# on the rare classes, exactly like the sklearn version - see
# training_report_v3.json / integration doc for why both are reported.
# ------------------------------------------------------------------
split = int(n * 0.8)


class MLP:
    """52 -> h1 -> h2 -> 3, tanh/tanh/linear, softmax+cross-entropy."""

    def __init__(self, d_in, h1, h2, d_out, seed=0):
        r = np.random.RandomState(seed)
        lim1 = np.sqrt(6.0 / (d_in + h1))
        lim2 = np.sqrt(6.0 / (h1 + h2))
        lim3 = np.sqrt(6.0 / (h2 + d_out))
        self.W1 = r.uniform(-lim1, lim1, (d_in, h1))
        self.b1 = np.zeros(h1)
        self.W2 = r.uniform(-lim2, lim2, (h1, h2))
        self.b2 = np.zeros(h2)
        self.W3 = r.uniform(-lim3, lim3, (h2, d_out))
        self.b3 = np.zeros(d_out)

    def forward(self, X):
        z1 = X @ self.W1 + self.b1
        a1 = np.tanh(z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = np.tanh(z2)
        z3 = a2 @ self.W3 + self.b3
        z3 = z3 - z3.max(axis=1, keepdims=True)
        e = np.exp(z3)
        probs = e / e.sum(axis=1, keepdims=True)
        cache = (X, z1, a1, z2, a2, z3, probs)
        return probs, cache

    def backward(self, cache, Y, sample_w, l2=1e-3):
        X, z1, a1, z2, a2, z3, probs = cache
        m = X.shape[0]
        sw = sample_w.reshape(-1, 1)

        dz3 = (probs - Y) * sw / m
        dW3 = a2.T @ dz3 + l2 * self.W3
        db3 = dz3.sum(axis=0)

        da2 = dz3 @ self.W3.T
        dz2 = da2 * (1 - a2 ** 2)
        dW2 = a1.T @ dz2 + l2 * self.W2
        db2 = dz2.sum(axis=0)

        da1 = dz2 @ self.W2.T
        dz1 = da1 * (1 - a1 ** 2)
        dW1 = X.T @ dz1 + l2 * self.W1
        db1 = dz1.sum(axis=0)

        return dW1, db1, dW2, db2, dW3, db3

    def step(self, grads, lr):
        dW1, db1, dW2, db2, dW3, db3 = grads
        self.W1 -= lr * dW1; self.b1 -= lr * db1
        self.W2 -= lr * dW2; self.b2 -= lr * db2
        self.W3 -= lr * dW3; self.b3 -= lr * db3

    def to_json(self, classes, mean, std, version, meta):
        return {
            "version": version,
            "feature_dim": self.W1.shape[0],
            "classes": classes,
            "normalization": {"mean": mean.tolist(), "std": std.tolist()},
            "layers": [
                {"weight": self.W1.T.tolist(), "bias": self.b1.tolist(), "activation": "tanh"},
                {"weight": self.W2.T.tolist(), "bias": self.b2.tolist(), "activation": "tanh"},
                {"weight": self.W3.T.tolist(), "bias": self.b3.tolist(), "activation": None},
            ],
            "meta": meta,
        }


def train(Xtr, Ytr, sw_tr, epochs=4000, lr=0.03, seed=0):
    model = MLP(d, 32, 16, 3, seed=seed)
    for ep in range(epochs):
        probs, cache = model.forward(Xtr)
        grads = model.backward(cache, Ytr, sw_tr)
        model.step(grads, lr)
    return model


def cross_entropy(probs, Y):
    eps = 1e-9
    return float(-np.mean(np.sum(Y * np.log(probs + eps), axis=1)))


def evaluate(model, X, y_idx_true, classes):
    probs, _ = model.forward(X)
    pred = probs.argmax(axis=1)
    acc = float((pred == y_idx_true).mean())
    # per-class precision/recall
    report = {}
    for ci, cname in enumerate(classes):
        tp = int(((pred == ci) & (y_idx_true == ci)).sum())
        fp = int(((pred == ci) & (y_idx_true != ci)).sum())
        fn = int(((pred != ci) & (y_idx_true == ci)).sum())
        support = int((y_idx_true == ci).sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        report[cname] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    cm = np.zeros((3, 3), dtype=int)
    for t, p in zip(y_idx_true, pred):
        cm[t, p] += 1
    return acc, report, cm.tolist()


# ---- Eval 1: time-respecting holdout ----
Xtr, Xte = Xn[:split], Xn[split:]
Ytr, Yte = Y[:split], Y[split:]
sw_tr = sample_weight[:split]
yidx_te = y_idx[split:]

model_holdout = train(Xtr, Ytr, sw_tr)
probs_te, _ = model_holdout.forward(Xte)
acc, report, cm = evaluate(model_holdout, Xte, yidx_te, CLASSES)
print("\n=== Time-respecting holdout (train=first 80%, test=last 20%) ===")
print("Test label counts:", dict(zip(*np.unique(y_labels[split:], return_counts=True))))
print("Accuracy:", acc)
print(json.dumps(report, indent=2))
print("Confusion matrix", CLASSES, cm)

# ---- Eval 2: stratified k-fold (optimistic upper bound, same caveat as before) ----
from collections import defaultdict
k = 5
idx_by_class = defaultdict(list)
for i, c in enumerate(y_idx):
    idx_by_class[c].append(i)
folds = [[] for _ in range(k)]
for c, idxs in idx_by_class.items():
    rng.shuffle(idxs)
    for j, i in enumerate(idxs):
        folds[j % k].append(i)

all_true, all_pred = [], []
for fi in range(k):
    test_idx = np.array(folds[fi])
    train_idx = np.array([i for j in range(k) if j != fi for i in folds[j]])
    m = train(Xn[train_idx], Y[train_idx], sample_weight[train_idx], seed=fi)
    probs, _ = m.forward(Xn[test_idx])
    all_true.extend(y_idx[test_idx].tolist())
    all_pred.extend(probs.argmax(axis=1).tolist())

all_true = np.array(all_true); all_pred = np.array(all_pred)
cv_acc, cv_report, cv_cm = evaluate(type("M", (), {"forward": lambda self, x: (np.eye(3)[all_pred], None)})(),
                                     None, all_true, CLASSES)
print("\n=== Stratified 5-fold CV (optimistic upper bound - autocorrelated frames) ===")
print("Accuracy:", cv_acc)
print(json.dumps(cv_report, indent=2))
print("Confusion matrix", CLASSES, cv_cm)

# ---- Final model: train on ALL data for delivery ----
final_model = train(Xn, Y, sample_weight, seed=123)
final_probs, _ = final_model.forward(Xn)
final_loss = cross_entropy(final_probs, Y)
print(f"\nFinal model (trained on all {n} rows) train cross-entropy: {final_loss:.4f}")

meta = {
    "trained_on": "313 supplied screenshots -> 276 usable frames after OCR/pixel-extraction validation",
    "labels_from": "app.services.signal_rule_engine_v3.SignalRuleEngineV3 (production rule engine, not a re-implementation)",
    "features_from": "app.services.neural_features_v3.extract_feature_vector (production feature extractor)",
    "label_counts": {k: int(v) for k, v in zip(*np.unique(y_labels, return_counts=True))},
    "holdout_accuracy": acc,
    "holdout_report": report,
    "cv_accuracy": cv_acc,
    "cv_report": cv_report,
}

model_json = final_model.to_json(CLASSES, mean, std, "AEGIS_NEURAL_V3", meta)
with open("/home/claude/pipeline/aegis_neural_v3.json", "w") as f:
    json.dump(model_json, f, indent=2)

with open("/home/claude/pipeline/training_report_v3.json", "w") as f:
    json.dump(meta, f, indent=2)

print("\nSaved aegis_neural_v3.json + training_report_v3.json")
