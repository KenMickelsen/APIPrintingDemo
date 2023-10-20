from flask import Flask, render_template, request, jsonify, Response, current_app, redirect, url_for
from functools import wraps
from logging.config import dictConfig
from collections import deque
from datetime import datetime
import requests, uuid, urllib3, json, os, socket, logging

logging.basicConfig(filename='app.log', level=logging.DEBUG)

#Get local IP address
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't need to be reachable, the OS just uses this to determine the most
        # appropriate network interface to use.
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

#Get files from static folder to be available for printing
def get_static_files():
    static_dir = "static"
    valid_extensions = [".pdf"]
    return [f for f in os.listdir(static_dir) if os.path.splitext(f)[1] in valid_extensions]

def save_jobs_to_file(jobs):
    with open('static/jobs.json', 'w') as f:
        json.dump(jobs, f)

def load_jobs_from_file():
    try:
        with open('static/jobs.json', 'r') as f:
            jobs_list = json.load(f)
            return deque(jobs_list, maxlen=20)  # Convert the loaded list into a deque with a max length of 20
    except (FileNotFoundError, json.JSONDecodeError):
        return deque([], maxlen=20)  # Return an empty deque with a maximum length of 20 if the file is not found or is empty.
    
def get_api_endpoint():
    try:
        with open('static/settings.json', 'r') as file:
            data = json.load(file)
            endpoint = data.get('apiEndpoint', "https://VasionEBC-SC:31990/v1/print")  # Default value if not found
            current_app.logger.info(f"API Endpoint loaded: {endpoint}")
            return endpoint
    except (FileNotFoundError, json.JSONDecodeError) as e:
        default_endpoint = "https://VasionEBC-SC:31990/v1/print"
        current_app.logger.error(f"Error reading API endpoint from settings.json: {e}. Defaulting to: {default_endpoint}")
        return default_endpoint

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
        'level': 'DEBUG',
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

API_ENDPOINT = "https://VasionEBC-SC:31990/v1/print"

#Load list of program participants from programParticipants.json 
@app.route('/get-applicants', methods=['GET'])
def get_applicants():
    with open('static/programParticipants.json', 'r') as file:
        data = json.load(file)
    return jsonify(data)

#Save edited data from program participants to programParticipants.json
@app.route('/save-applicants', methods=['POST'])
def save_applicants():
    data = request.get_json()  # Use get_json() to parse incoming JSON data
    with open('static/programParticipants.json', 'w') as file:
        json.dump(data, file)
    return jsonify({"status": "success"})

#Load list of printers and settings from settings.json 
@app.route('/get-settings', methods=['GET'])
def get_settings():
    with open('static/settings.json', 'r') as file:
        data = json.load(file)
    return jsonify(data)

#Save edited settings to settings.json
@app.route('/save-settings', methods=['POST'])
def save_printers():
    data = request.get_json()  # Use get_json() to parse incoming JSON data
    with open('static/settings.json', 'w') as file:
        json.dump(data, file)
    return jsonify({"status": "success"})

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

#marketing page to list files for printing
@app.route('/marketing', methods=['GET'])
def marketing_page():
    #Get files in static folder for printing
    files = get_static_files()
    return render_template('marketing.html', files=files)

#marketing page to list files for printing
@app.route('/applicantlist', methods=['GET'])
def applicantlist():
    #Get files in static folder for printing
    files = get_static_files()
    return render_template('applicantlist.html', files=files)

#Portal page for applicants
@app.route('/applicants', methods=['GET'])
def application_portal():
    return render_template('application_portal.html')

#Settings page for changing values and settings
@app.route('/settings', methods=['GET'])
def settings():
    return render_template('settings.html')

@app.route('/upload-default-job', methods=['POST'])
def upload_default_job():
    file = request.files.get('file')
    if file:
        # Save the file to a specific location.
        file.save(os.path.join("static", "check.pdf"))
    return redirect(url_for('settings'))  # Redirect back to settings page.

#Send print job
@app.route('/send-print-job', methods=['POST'])
def send_print_job():
    file = request.files.get('file')
    filename = request.form.get('filename')

    # Get the local IP address
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()

    statusURL = f"http://{local_ip}:5000/print-job-status"

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
    #statusURL = request.form.get('statusURL')

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
        'file': (filename, file_content)
    }

    response = requests.post(get_api_endpoint(), data=data, files=files, verify=False)  # verify=False is to bypass SSL verification if your local server has a self-signed cert
    logging.debug(f"HTTP Status Code: {response.status_code}")

    print("API Response:", response.text)
    
    #logging.debug('Files being sent: %s', files)
    logging.debug('Data being sent: %s', data)
    logging.debug('Filename: %s', filename)
    logging.debug('API Response: %s', response.text)
    logging.debug(f"All Headers: {response.headers}")


    if 200 <= response.status_code < 300:  # Successful 2xx status codes
        return jsonify({"status": "success", "message": "Job successfully sent!"})
    elif 400 <= response.status_code < 500:  # Client error 4xx status codes
        return jsonify({"status": "error", "message": "Client error. Please check your request."}), response.status_code
    elif 500 <= response.status_code < 600:  # Server error 5xx status codes
        return jsonify({"status": "error", "message": "Server error. Please try again later."}), response.status_code
    else:
        # For any other unexpected status codes
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
    app.run(host=get_local_ip(), port=5000, debug=True)