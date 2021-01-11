from flask import Flask, render_template, url_for, request
import os
import io
from flask import Response, redirect

app = Flask(__name__)

# Config options - Make sure you created a 'config.py' file.
app.config.from_object('config')
# To get one variable, tape app.config['MY_VARIABLE']

app.secret_key = "jvj"

"""
@app.route('/')
def index_form():
    return render_template('index.html')
"""
@app.route('/')
def index_form():
    return render_template('index.html')

@app.route('/cleartmp/')
def clear_tmp():
    while len(os.listdir('tmp')) > 0:
        os.remove("tmp/" + os.listdir('tmp')[0])
    return redirect('/')  
