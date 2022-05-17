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
    fig.suptitle("Vitesse Windfoil 100m depuis le 01/01/2019")

    axis = fig.add_subplot(1, 1, 1)

    df = pd.read_csv('https://docs.google.com/spreadsheets/d/1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4/export?format=csv', usecols=['Date', 'Pratique', 'V 100m K72'])
    df_windfoil = df[df['Pratique'].eq('Windfoil')]
    df_windfoil["Date"] = pd.to_datetime(df_windfoil["Date"], format='%m/%d/%Y')
    df_windfoil["Date"] = (df_windfoil["Date"] - pd.to_datetime('1/1/2019', format='%m/%d/%Y')).dt.days
    df_windfoil = df_windfoil.dropna()

    X = df_windfoil['Date']
    y = df_windfoil['V 100m K72']

    axis.plot(X, y, '.b')

    X_b = np.c_[np.ones((X.shape[0], 1)), X]
    theta_best = np.linalg.inv(X_b.T @ X_b) @ X_b.T @ y
    X_new = np.array([[0], [2000]])
    X_new_b = np.c_[np.ones((2, 1)), X_new]
    y_predict = X_new_b @ theta_best

    axis.plot(X_new, y_predict, "r-")

    return fig 
