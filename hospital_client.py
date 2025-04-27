import requests
import time

# Hospital credentials
HOSPITAL_ID = "hospital1"
PASSWORD = "password123"
BASE_URL = "http://127.0.0.1:5000"

def get_jwt_token():
    response = requests.post(
        f"{BASE_URL}/hospital/login",
        json={"hospital_id": HOSPITAL_ID, "password": PASSWORD}
    )
    if response.status_code == 200:
        return response.json()['token']
    else:
        raise Exception("Authentication failed")

def update_inventory(token, hospital_data):
    response = requests.post(
        f"{BASE_URL}/hospital/update",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=hospital_data
    )
    if response.status_code == 200:
        print("Update successful:", response.json())
    else:
        print("Update failed:", response.json())

def main():
    # Get JWT token
    token = get_jwt_token()
    
    # Simulate periodic updates
    hospital_data = {
        "name": "Bhubaneswar Hospital O-",
        "blood_type": "O-",
        "stock": 3,
        "latitude": 20.304440234294752,
        "longitude": 85.84096574982654
    }
    
    for i in range(3):  # Simulate 3 updates
        hospital_data["stock"] = hospital_data["stock"] + i
        update_inventory(token, hospital_data)
        time.sleep(10)  # Wait 10 seconds between updates

if __name__ == "__main__":
    main()