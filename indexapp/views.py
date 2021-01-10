from flask import Flask, render_template, url_for, request
import os
import io
from flask import Response, redirect

from suunto import sml2gpx

app = Flask(__name__)

# Config options - Make sure you created a 'config.py' file.
app.config.from_object('config')
# To get one variable, tape app.config['MY_VARIABLE']

app.secret_key = "secret key"

"""
@app.route('/')
def index_form():
    return render_template('index.html')
"""
@app.route('/')
def upload_form():
    return render_template('index.html')
    
