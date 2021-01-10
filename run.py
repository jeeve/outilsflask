#! /usr/bin/env python
#from gpsapp import app

from flask import Flask
from gpsapp import app as gps_app
from indexapp import app as index_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app = Flask(__name__)

app.wsgi_app = DispatcherMiddleware(index_app , {
    '/gps': gps_app
})

if __name__ == "__main__":
    app.run(debug=True)
