import requests

BASE_URL = "http://127.0.0.1:5000"
response = requests.post(
    f"{BASE_URL}/hospital/login",
    json={"hospital_id": "hospital1", "password": "password123"}
)
print(response.json())