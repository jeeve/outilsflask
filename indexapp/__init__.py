import os
from flask import Flask

from .views import app
from . import models

from flask import Flask
from gpsapp import app as gps_app
from indexapp import app as index_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

app = Flask(__name__)

application = DispatcherMiddleware(index_app , {
    '/gps': gps_app
})

