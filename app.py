from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from functools import wraps
from base64 import b64decode
from logging.config import dictConfig
from collections import deque
from datetime import datetime
import requests
import uuid
import urllib3
import json
import os

#Get files from static folder to be available for printing
def get_static_files():
    static_dir = "static"
    valid_extensions = [".pdf"]
    return [f for f in os.listdir(static_dir) if os.path.splitext(f)[1] in valid_extensions]

def save_jobs_to_file(jobs):
    with open('jobs.json', 'w') as f:
        json.dump(jobs, f)

def load_jobs_from_file():
    try:
        with open('jobs.json', 'r') as f:
            jobs_list = json.load(f)
            return deque(jobs_list, maxlen=20)  # Convert the loaded list into a deque with a max length of 20
    except (FileNotFoundError, json.JSONDecodeError):
        return deque([], maxlen=20)  # Return an empty deque with a maximum length of 20 if the file is not found or is empty.

#Load print job history from jobs.json
PRINT_JOBS = load_jobs_from_file()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

app = Flask(__name__)

# Basic Auth functions
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated

def check_auth(username, password):
    """This function is called to check if a username/password combination is valid."""
    # OM Username/pass field for status updates
    return username == 'admin' and password == 'secret'

API_ENDPOINT = "https://192.168.1.166:31990/v1/print"

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

#marketing page to list files for printing
@app.route('/marketing', methods=['GET'])
def marketing_page():
    #Get files in static folder for printing
    files = get_static_files()
    return render_template('marketing.html', files=files)

#Portal page for applicants
@app.route('/application-portal', methods=['GET'])
def application_portal():
    return render_template('application_portal.html')

#Settings page for changing values and settings
@app.route('/settings', methods=['GET'])
def settings():
    return render_template('settings.html')

#Send print job
@app.route('/send-print-job', methods=['POST'])
def send_print_job():
    file = request.files.get('file')
    filename = request.form.get('filename')

    # If a filename is provided, it's a prestored file, so set the file path accordingly
    if filename:
        file_path = os.path.join("static", filename)
        with open(file_path, 'rb') as f:
            file_content = f.read()
    elif file:
        file_content = file.read()
        filename = file.filename
    else:
        return jsonify({"status": "error", "message": "No file provided."})

    # Extract data from the form
    queue = request.form.get('queue')
    username = request.form.get('username')
    copies = int(request.form.get('copies', 1))
    jobID = str(uuid.uuid4())  # Generate a new UUID
    deviceName = request.form.get('deviceName')
    duplex = request.form.get('duplex') == 'true'
    color = request.form.get('color') == 'true'
    paperSource = request.form.get('paperSource')
    statusURL = request.form.get('statusURL')

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # This will give a timestamp in 'YYYY-MM-DD HH:MM:SS' format

    new_job = {
    'jobID': jobID,
    'timestamp': timestamp,
    'printer': queue,
    'filename': filename,
    'username': username,
    'status': 'Pending'
    }

    PRINT_JOBS.appendleft(new_job)  # Add new job to the beginning of the deque

    save_jobs_to_file(list(PRINT_JOBS))  # Save updated list to file

    # Prepare multipart/form-data POST request
    data = {
        'queue': queue,
        'username': username,
        'copies': copies,
        'jobID': jobID,
        'deviceName': deviceName,
        'duplex': duplex,
        'color': color,
        'paperSource': paperSource,
        'statusURL': statusURL
    }
   
    files = {
        'file': file_content
    }
    
    response = requests.post(API_ENDPOINT, data=data, files=files, verify=False)  # verify=False is to bypass SSL verification if your local server has a self-signed cert
    print("API Response:", response.text)

    if response.headers.get('Content-Type') and 'application/json' in response.headers.get('Content-Type'):
        return jsonify({"status": "success", "data": response.json()})
    else:
        return jsonify({"status": "error", "message": "Unexpected response: " + response.text}), response.status_code

@app.route('/print-job-status', methods=['POST'])
@requires_auth #require auth for status replies. Username/pass must be set and matching in PL
def print_job_status():
    # Extract data from the request
    data = request.json
    jobID = data.get('jobID')
    status = data.get('status')
    message = data.get('message', '')  # Optional message

    print(f"Received status update for job {jobID}. Status: {status}. Message: {message}")
    
    # Iterate through the PRINT_JOBS to find the relevant job and update its status
    for job in PRINT_JOBS:
        if job['jobID'] == jobID:
            job['status'] = f"{status} - {message}"
        break

    save_jobs_to_file(list(PRINT_JOBS))  # Save updated list to file

    # Return a simple acknowledgement response
    return Response("Status received.", status=200)


@app.route('/get-jobs', methods=['GET'])
def get_jobs():
    jobs_list = list(PRINT_JOBS)
    return jsonify(jobs_list)


if __name__ == '__main__':
    app.run(debug=True)