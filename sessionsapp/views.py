from flask import Flask, render_template, url_for, request
from flask import Response
import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

import io
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from dateutil.relativedelta import relativedelta
import matplotlib.dates as mdates
import numpy as np

matplotlib.rcParams['timezone'] = 'Europe/Paris'

app = Flask(__name__)

# Config options - Make sure you created a 'config.py' file.
app.config.from_object('config')
# To get one variable, tape app.config['MY_VARIABLE']

@app.route('/')
@app.route('/index/')
def index():
    fig = create_plot_date()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')
    
def create_plot_date(): 
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    fig.suptitle("Vitesse 100m")

    axis = fig.add_subplot(1, 1, 1)
    xs = np.array([4,7,9])
    ys = np.array([40,20,5])
        
    axis.plot(xs, ys)

    return fig 
