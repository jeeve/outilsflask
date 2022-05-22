from flask import Flask, render_template, url_for, request
import os
import io
from flask import Response, redirect
from werkzeug.utils import secure_filename
from flask import send_from_directory
import uuid

from gpsapp.suunto import sml2gpx
from gpsapp.fit2gpx import parse_fit_to_gpx

app = Flask(__name__)

# Config options - Make sure you created a 'config.py' file.
app.config.from_object('config')
# To get one variable, tape app.config['MY_VARIABLE']

UPLOAD_FOLDER = "tmp"

app.secret_key = "jvj"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = set(['fit', 'sml'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

filename = ''
file_url = ''
"""
@app.route('/')
def index_form():
   return render_template('index.html')
"""
@app.route('/')
def upload_form():
    return render_template('upload.html')
    
@app.route('/', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return render_template('message.html', message='Aucun fichier')
        file = request.files['file']
        if file.filename == '':
            return render_template('message.html', message='Aucun fichier sélectionné')
        if file and allowed_file(file.filename):
            global filename
            id_session = str(uuid.uuid4())
            filename = id_session + file.filename[-4:] 
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            if filename[-3:].lower() == 'sml':
                sml2gpx(UPLOAD_FOLDER + '/' + filename)
                filename = filename.replace('sml', 'gpx')
                
            if filename[-3:].lower() == 'fit':
                parse_fit_to_gpx(UPLOAD_FOLDER + '/' + filename)
                filename = filename.replace('fit', 'gpx')
                
            #return redirect('/gps/gpx/')
            return redirect('/gps/download/' + filename)
        else:
            return render_template('message.html', message='Fichiers acceptés : FIT, SML')   
        
@app.route('/gpx/')
def gpx_form():
    global filename
    return render_template('gpx.html', file_url="/gps/download/" + filename, filename=filename)        
        
@app.route('/download/<path:filename>')
def download(filename):
    return send_from_directory('../' + app.config['UPLOAD_FOLDER'], filename) 
        
        
    
