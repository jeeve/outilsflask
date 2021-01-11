from flask import Flask
from run import app

application = Flask(__name__)
application = app.wsgi_app