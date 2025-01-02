#! /usr/bin/env python
#from gpsapp import app

from gpsapp import app as gps_app
from indexapp import app as index_app
from sessionsapp import app as sessions_app
from meteoapp import app as meteo_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

application = DispatcherMiddleware(index_app , {
    '/gps': gps_app,
    '/sessions': sessions_app,
    '/meteo': meteo_app
})

if __name__ == '__main__':
    run_simple(
        hostname='localhost',
        port=5000,
        application=application,
        use_reloader=True,
        use_debugger=False,
        use_evalex=True) 