from flask import Flask, render_template, url_for, request
import os
import io
from flask import Response, redirect
from werkzeug.utils import secure_filename
from flask import send_from_directory
import uuid

from suunto import sml2gpx

app = Flask(__name__)

# Config options - Make sure you created a 'config.py' file.
app.config.from_object('config')
# To get one variable, tape app.config['MY_VARIABLE']

UPLOAD_FOLDER = "/uploads"

app.secret_key = "secret key"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = set(['sml'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

filename = ''
file_url = ''

@app.route('/gps/')
def upload_form():
    return render_template('upload.html')
    
@app.route('/gps/', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return render_template('message.html', message='No file part')
        file = request.files['file']
        if file.filename == '':
            return render_template('message.html', message='No file selected for uploading')
        if file and allowed_file(file.filename):
            global filename
            id_session = str(uuid.uuid4())
            filename = id_session + ".gpx" #secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            sml2gpx(UPLOAD_FOLDER + '/' + filename)
            
            filename = filename.replace('sml', 'gpx')
            
            return redirect('/gps/gpx/')
        else:
            return render_template('message.html', message='Allowed file type is sml')   
        
@app.route('/gps/gpx/')
def gpx_form():
    global filename
    return render_template('gpx.html', file_url="/download/" + filename, filename=filename)        
        
@app.route('/gps/download/<path:filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True) 
        
        
    
