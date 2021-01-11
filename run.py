#! /usr/bin/env python
#from gpsapp import app

from gpsapp import app as gps_app
from indexapp import app as index_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

application = DispatcherMiddleware(index_app , {
    '/gps': gps_app
})

if __name__ == '__main__':
    run_simple(
        hostname='localhost',
        port=5000,
        application=application,
        use_reloader=True,
        use_debugger=True,
        use_evalex=True)