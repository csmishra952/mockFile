import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Odisha locations with coordinates
ODISHA_LOCATIONS = {
    'Bhubaneswar': (20.2961, 85.8245),
    'Cuttack': (20.4625, 85.8828),
    'Rourkela': (22.2604, 84.8536),
    'Berhampur': (19.3140, 84.7941),
    'Sambalpur': (21.4669, 83.9757),
    'Puri': (19.8134, 85.8315),
    'Balasore': (21.4940, 86.9427),
    'Bargarh': (21.3353, 83.6161),
    'Angul': (20.8442, 85.1511),
    'Jharsuguda': (21.8553, 84.0062),
    'Dhenkanal': (20.6587, 85.5980),
    'Kendrapara': (20.5002, 86.4166),
    'Jagatsinghpur': (20.2548, 86.1706),
    'Koraput': (18.8110, 82.7105),
    'Rayagada': (19.1711, 83.4160),
    'Bolangir': (20.7074, 83.4843),
    'Sundargarh': (22.1167, 84.0333),
    'Nayagarh': (20.1281, 85.0985),
    'Malkangiri': (18.3650, 82.1367),
    'Khordha': (20.1883, 85.6214)
}

def generate_donors(n=100):
    """Generate synthetic donor data with valid Indian phone numbers."""
    blood_types = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
    # Valid Indian mobile prefixes
    mobile_prefixes = ['7', '8', '9']
    data = []
    for i in range(n):
        location = random.choice(list(ODISHA_LOCATIONS.keys()))
        lat, lon = ODISHA_LOCATIONS[location]
        # Add slight variation to coordinates
        lat += random.uniform(-0.05, 0.05)
        lon += random.uniform(-0.05, 0.05)
        last_donation = datetime.now() - timedelta(days=random.randint(0, 365))
        # Generate valid phone number: +91 followed by 7/8/9 and 9 digits
        prefix = random.choice(mobile_prefixes)
        phone = f"+91{prefix}{random.randint(100000000, 999999999)}"
        # For testing, set one donor to a verified number (uncomment if needed)
        # if i == 0:
        #     phone = "+919876543210"  # Replace with your verified Twilio number
        data.append({
            'id': i + 1,
            'blood_type': random.choice(blood_types),
            'latitude': lat,
            'longitude': lon,
            'last_donation': last_donation.strftime('%Y-%m-%d'),
            'phone': phone
        })
    return pd.DataFrame(data)

def generate_recipients(n=50):
    """Generate synthetic recipient data."""
    blood_types = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
    data = []
    for i in range(n):
        location = random.choice(list(ODISHA_LOCATIONS.keys()))
        lat, lon = ODISHA_LOCATIONS[location]
        lat += random.uniform(-0.05, 0.05)
        lon += random.uniform(-0.05, 0.05)
        data.append({
            'id': i + 1,
            'blood_type': random.choice(blood_types),
            'latitude': lat,
            'longitude': lon,
            'urgency': random.randint(1, 10)
        })
    return pd.DataFrame(data)

def generate_hospitals(n=20):
    """Generate synthetic hospital data with all blood types and low stock."""
    blood_types = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
    data = []
    hospital_id = 1
    for location in ODISHA_LOCATIONS.keys():
        lat, lon = ODISHA_LOCATIONS[location]
        for blood_type in blood_types:
            # Ensure at least some hospitals have low stock
            stock = random.randint(0, 3) if random.random() < 0.4 else random.randint(4, 10)
            data.append({
                'id': hospital_id,
                'name': f"{location} Hospital {blood_type}",
                'latitude': lat + random.uniform(-0.02, 0.02),
                'longitude': lon + random.uniform(-0.02, 0.02),
                'blood_type': blood_type,
                'stock': stock
            })
            hospital_id += 1
    return pd.DataFrame(data)

def main():
    """Generate and save all datasets."""
    donors = generate_donors(100)
    recipients = generate_recipients(50)
    hospitals = generate_hospitals()
    
    donors.to_csv('donors.csv', index=False)
    recipients.to_csv('recipients.csv', index=False)
    hospitals.to_csv('hospitals.csv', index=False)
    
    print(f"Generated: {len(donors)} donors, {len(recipients)} recipients, {len(hospitals)} hospitals")

if __name__ == "__main__":
    main()