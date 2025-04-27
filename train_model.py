import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib
import random

# Simulate training data
def generate_training_data(n_samples=1000):
    """Generate synthetic training data for donor matching."""
    blood_types = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
    compatibility_matrix = {
        'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],
        'O+': ['O+', 'A+', 'B+', 'AB+'],
        'A-': ['A-', 'A+', 'AB-', 'AB+'],
        'A+': ['A+', 'AB+'],
        'B-': ['B-', 'B+', 'AB-', 'AB+'],
        'B+': ['B+', 'AB+'],
        'AB-': ['AB-', 'AB+'],
        'AB+': ['AB+']
    }
    
    data = []
    for _ in range(n_samples):
        donor_blood = random.choice(blood_types)
        recipient_blood = random.choice(blood_types)
        is_compatible = 1 if recipient_blood in compatibility_matrix[donor_blood] else 0
        distance = random.uniform(0, 50)  # km
        hospital_distance = random.uniform(0, 100) if random.random() > 0.2 else 1000
        urgency = random.randint(1, 10)
        days_since_donation = random.randint(0, 365)
        reliability = max(0, min(1, 1 - (days_since_donation / 365)))
        
        # Target: match quality (higher for compatible, closer, urgent, reliable)
        match_quality = (
            is_compatible * 0.4 +
            (1 - distance / 50) * 0.2 +
            (1 - min(hospital_distance, 100) / 100) * 0.2 +
            (urgency / 10) * 0.1 +
            reliability * 0.1
        )
        if not is_compatible:
            match_quality = 0
        
        data.append([
            is_compatible,
            distance,
            hospital_distance,
            urgency,
            reliability,
            match_quality
        ])
    
    return np.array(data)

def train_model():
    """Train and save a Random Forest model."""
    # Generate training data
    data = generate_training_data(1000)
    X = data[:, :-1]  # All columns except the last (match_quality)
    y = data[:, -1]   # Last column (match_quality)
    
    # Scale distance-based features (indices 1 and 2)
    scaler = StandardScaler()
    X[:, [1, 2]] = scaler.fit_transform(X[:, [1, 2]])
    
    # Train Random Forest model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Save model and scaler
    joblib.dump(model, 'donor_match_model.pkl')
    joblib.dump(scaler, 'scaler.pkl')
    
    print("Model and scaler saved successfully.")

if __name__ == "__main__":
    train_model()