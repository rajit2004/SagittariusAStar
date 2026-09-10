
import os
import sys

import numpy as np
import xgboost as xgb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def generate_synthetic_data(n_samples: int = 10000, seed: int = 42) -> tuple:
    rng = np.random.default_rng(seed)

    n_cycles = rng.integers(3, 7, size=n_samples)

    features = []

    for i in range(n_samples):
        nc = n_cycles[i]

        base_length = rng.normal(28, 3, size=nc)
        irregularity = rng.exponential(1.5, size=nc)
        lengths = base_length + irregularity * rng.choice([-1, 1], size=nc) * rng.uniform(0.5, 2)
        lengths = np.clip(lengths, 18, 55)

        flows = rng.normal(5, 1.5, size=nc)
        flows = np.clip(flows, 1, 10)

        stresses = rng.uniform(1, 5, size=nc)

        sleeps = rng.uniform(4, 10, size=nc)

        agg = [
            float(np.mean(lengths)),
            float(np.std(lengths)),
            float(np.mean(flows)),
            float(np.std(flows)),
            float(np.max(lengths) - np.min(lengths)),
            float(np.mean(stresses)),
            float(np.mean(sleeps)),
            float(nc),
        ]
        features.append(agg)

    features = np.array(features)

    std_len = features[:, 1]
    range_len = features[:, 4]
    std_flow = features[:, 3]
    stress = features[:, 5]
    sleep = features[:, 6]

    base_cvi = std_len * 8 + 30
    range_boost = np.maximum(0, range_len - 10) * 0.5
    flow_boost = std_flow * 2
    stress_penalty = (stress - 2.5) * 2
    sleep_penalty = (7.0 - sleep) * 1.5

    targets = base_cvi + range_boost + flow_boost + stress_penalty + sleep_penalty
    targets = np.clip(targets, 0, 100)
    targets = np.round(targets, 1)

    return features, targets

def main():
    print("Generating synthetic training data...")
    X, y = generate_synthetic_data(20000, seed=42)

    print(f"Training set: {X.shape[0]} samples, {X.shape[1]} features")
    print(f"Target range: {y.min():.1f} - {y.max():.1f}, mean: {y.mean():.1f}")

    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=2.0,
        random_state=42,
        verbosity=0,
    )

    model.fit(X, y)

    preds = model.predict(X)
    mae = np.mean(np.abs(preds - y))
    print(f"Training MAE: {mae:.3f}")

    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "models",
        "cvi_model.joblib",
    )
    import joblib
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

    model = joblib.load(model_path)
    sample = np.array([[28.0, 2.0, 5.0, 0.5, 6.0, 2.5, 7.0, 4.0]])
    pred = float(model.predict(sample)[0])
    print(f"Sample prediction (regular cycles): {pred:.1f} (expected ~40-50)")

    sample = np.array([[28.0, 12.0, 5.0, 1.5, 35.0, 4.0, 5.0, 6.0]])
    pred = float(model.predict(sample)[0])
    print(f"Sample prediction (irregular cycles): {pred:.1f} (expected ~80+)")

    print("Training complete.")

if __name__ == "__main__":
    main()
