from flask import Flask, jsonify, render_template_string, request
import base64
from pyngrok import ngrok
import threading
from datetime import datetime, timedelta

app = Flask(__name__)
active_clients = {}  # {client_id: {"name": client_name, "last_seen": timestamp, "file_to_download": {"filename": str, "content": str}}}

# Регистрация клиента
@app.route("/api/register", methods=["POST"])
def register_client():
    data = request.json
    client_id = data.get("client_id")
    client_name = data.get("client_name")
    if client_id and client_name:
        active_clients[client_id] = {
            "name": client_name,
            "last_seen": datetime.now(),
            "file_to_download": None
        }
        return jsonify({"status": "registered"})
    return jsonify({"error": "Invalid data"}), 400

# Проверка статуса клиента и получение файла
@app.route("/api/check/<client_id>", methods=["GET"])
def check_client(client_id):
    if client_id in active_clients:
        active_clients[client_id]["last_seen"] = datetime.now()
        file_to_download = active_clients[client_id].get("file_to_download")
        # Очищаем задание после получения
        active_clients[client_id]["file_to_download"] = None
        return jsonify({"file": file_to_download})
    return jsonify({"error": "Client not found"}), 404

# Получить список активных клиентов
@app.route("/api/clients", methods=["GET"])
def get_clients():
    # Удаляем клиентов, неактивных более 30 секунд
    now = datetime.now()
    expired = [cid for cid, info in active_clients.items() if now - info["last_seen"] > timedelta(seconds=30)]
    for cid in expired:
        active_clients.pop(cid)
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
        # Читаем файл и кодируем в base64
        file_content = file.read()
        file_b64 = base64.b64encode(file_content).decode('utf-8')
        active_clients[client_id]["file_to_download"] = {
            "filename": filename,
            "content": file_b64
        }
        return jsonify({"status": "assigned", "filename": filename})
    return jsonify({"error": "Failed to upload file"}), 500

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
        </div>
        <script>
            const clientSelect = document.getElementById('client');
            const uploadInput = document.getElementById('file-upload');
            const sendBtn = document.getElementById('send');

            // Загрузка списка клиентов
            function loadClients() {
                const currentClient = clientSelect.value; // Сохраняем текущий выбор
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
                        // Восстанавливаем выбор, если клиент все еще в списке
                        if (currentClient && clients.some(c => c.id === currentClient)) {
                            clientSelect.value = currentClient;
                        }
                        sendBtn.disabled = !clientSelect.value || !uploadInput.files[0];
                    });
            }
            loadClients();
            setInterval(loadClients, 5000); // Обновляем каждые 5 секунд

            // Активация кнопки
            clientSelect.addEventListener('change', () => {
                sendBtn.disabled = !clientSelect.value || !uploadInput.files[0];
            });
            uploadInput.addEventListener('change', () => {
                sendBtn.disabled = !clientSelect.value || !uploadInput.files[0];
            });

            // Отправка файла
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
                            uploadInput.value = ''; // Очищаем поле загрузки
                            sendBtn.disabled = true;
                        } else {
                            alert('Error: ' + data.error);
                        }
                    });
            });
        </script>
    </body>
    </html>
    """)

def start_ngrok():
    public_url = ngrok.connect(5000)
    print(f"Public URL: {public_url}")

if __name__ == "__main__":
    threading.Thread(target=start_ngrok, daemon=True).start()
    app.run(port=5000)