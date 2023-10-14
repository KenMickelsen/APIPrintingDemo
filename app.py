from flask import Flask, render_template, request, jsonify, Response
from functools import wraps
from base64 import b64decode
from logging.config import dictConfig
from collections import deque
import requests
import uuid
import urllib3
import json

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


#Track print jobs sent
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
    # TODO: Replace with your desired credentials or implement a more robust authentication mechanism
    return username == 'admin' and password == 'secret'

API_ENDPOINT = "https://192.168.1.166:31990/v1/print"

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

#Send print job API
@app.route('/send-print-job', methods=['POST'])
def send_print_job():
    # Extract data from the form
    file = request.files['file']
    queue = request.form.get('queue')
    username = request.form.get('username')
    copies = int(request.form.get('copies', 1))
    jobID = str(uuid.uuid4())  # Generate a new UUID
    deviceName = request.form.get('deviceName')
    duplex = request.form.get('duplex') == 'true'
    color = request.form.get('color') == 'true'
    paperSource = request.form.get('paperSource')
    statusURL = request.form.get('statusURL')

    new_job = {
    'jobID': jobID,
    'filename': file.filename,
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
        'file': file.read()
    }
    
    response = requests.post(API_ENDPOINT, data=data, files=files, verify=False)  # verify=False is to bypass SSL verification if your local server has a self-signed cert
    print("API Response:", response.text)

    if response.headers.get('Content-Type') and 'application/json' in response.headers.get('Content-Type'):
        return jsonify({"status": "success", "data": response.json()})
    else:
        return jsonify({"status": "error", "message": "Unexpected response: " + response.text}), response.status_code

@app.route('/print-job-status', methods=['POST'])
@requires_auth
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