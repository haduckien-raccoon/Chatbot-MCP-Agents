import requests

API_KEY = "AIzaSyAAXDVG9xkoU9aTeVlgbxU0-uOGTb7rxAw"  # Thay bằng API key của bạn
url = "https://generativelanguage.googleapis.com/v1beta/models"

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

response = requests.get(url, headers=headers)
data = response.json()

# in ra tất cả model và phương thức hỗ trợ
for model in data.get("models", []):
    print(model["name"], model.get("supportedMethods", []))