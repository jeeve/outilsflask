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
def index(station, variable, date):
    fig = create_plot_date(station, variable, date)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')
    
def create_plot_date(station, variable, date):
    if date == "":
        df = pd.read_csv("https://greduvent.000webhostapp.com/sensations/get-meteo.php")    
    else:                         
        df = pd.read_csv("https://greduvent.000webhostapp.com/sensations/get-meteo.php?date=" + date)
    df.columns = ['date_heure', 'station', 'vent', 'orientation', 'temperature']
    #df["date_heure"] = pd.to_datetime(df["date_heure"], format='%Y-%m-%d %H:%M')

    df["date_heure"] = pd.to_datetime(df["date_heure"]).dt.tz_localize(tz='UTC').dt.tz_convert('Europe/Paris')

    df[["vent", "orientation", "temperature"]] = df[["vent", "orientation", "temperature"]].apply(pd.to_numeric)
    
    df_station = df[df['station'] == station]
    
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    fig.suptitle(station)

    axis = fig.add_subplot(1, 1, 1)
    xs = df_station['date_heure']
    ys = df_station[variable]
    
    axis.set_xlabel('date')
    axis.set_ylabel(variable)
    if variable == "vent":
        axis.set_ylabel("Vent (kts)")
    if variable == "temperature":
        axis.set_ylabel("Température (°C)")         
    if ys.min() < 0:
        axis.set_ylim(ys.min() - 10*ys.min()/100, ys.max() + 10*ys.max()/100)         
    else:   
        axis.set_ylim(0, ys.max() + 10*ys.max()/100) 
    axis.set_ylim(0, ys.max() + 10*ys.max()/100)    
    axis.grid()
    
    axis.xaxis.set_major_locator(mdates.HourLocator())

    if len(date) == 8:
        axis.set_xlabel(date[6:8] + '/' + date[4:6] + '/' + date[0:4])
        xfmt = mdates.DateFormatter("%H:%M")
        axis.xaxis.set_major_formatter(xfmt)
    
    axis.plot(xs, ys)

    return fig 

def create_rose_date(station, date):
    if date == "":
        df = pd.read_csv("https://greduvent.000webhostapp.com/sensations/get-meteo.php")    
    else:                         
        df = pd.read_csv("https://greduvent.000webhostapp.com/sensations/get-meteo.php?date=" + date)
    df.columns = ['date_heure', 'station', 'vent', 'orientation', 'temperature']
    df["date_heure"] = pd.to_datetime(df["date_heure"], format='%Y-%m-%d %H:%M')
    df[["vent", "orientation", "temperature"]] = df[["vent", "orientation", "temperature"]].apply(pd.to_numeric)
    
    df_station = df[df['station'] == station]
    
    fig = Figure()
    fig.set_size_inches(7, 7, forward=True)
    fig.suptitle(station)


    ax = fig.add_subplot(1, 1, 1, projection="windrose")    
    wd = df_station['orientation']
    ws = df_station['vent']
    ax.bar(wd, ws, normed=True, opening=0.8, edgecolor='white')
    ax.set_legend()
    
    return fig
