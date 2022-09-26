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
from sklearn import tree
from sklearn import neighbors

from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.resources import INLINE

matplotlib.rcParams['timezone'] = 'Europe/Paris'

app = Flask(__name__)

# Config options - Make sure you created a 'config.py' file.cd
# app.config.from_object('config')
# To get one variable, tape app.config['MY_VARIABLE']

@app.route('/ia')
def upload_form():
    df = pd.read_csv('https://docs.google.com/spreadsheets/d/1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4/export?format=csv', usecols=['Date', 'Pratique', 'V 100m K72', 'VMax K72 (noeuds)', 'Distance (km)'])
    df_windfoil = df[df['Pratique'].eq('Windfoil')]
    nb_points = df_windfoil.shape[0]
    return render_template('index.html', nb_points=nb_points)

@app.route('/ia/regressionlineaire')
def regression_lineaire():
    label = request.args.get('label', default='V 100m K72', type=str) 
    fig = plot_regression_lineaire(label)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/ia/arbredecision')
def arbre_decision():
    label = request.args.get('label', default='V 100m K72', type=str) 
    fig = plot_arbre_decision(label)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')    

@app.route('/ia/plusprochevoisins')
def plus_proche_voisins():
    label = request.args.get('label', default='V 100m K72', type=str) 
    fig = plot_plus_proche_voisins(label)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')      
    
@app.route('/ia/reseauneurones')
def reseau_neurones():
    label = request.args.get('label', default='V 100m K72', type=str) 
    nbcouches = request.args.get('nbcouches', default=2, type=int)  
    nbneuronescouche = request.args.get('nbneuronescouche', default=64, type=int)  
    fig = plot_reseau_neurones(label, nbcouches, nbneuronescouche)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

def plot_regression_lineaire(label): 

    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    #fig.suptitle("Vitesse Windfoil")

    axis = fig.add_subplot(1, 1, 1)

    df = pd.read_csv('https://docs.google.com/spreadsheets/d/1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4/export?format=csv', usecols=['Date', 'Pratique', label])
    df_windfoil = df[df['Pratique'].eq('Windfoil')]
    df_windfoil["Date"] = pd.to_datetime(df_windfoil["Date"], format='%m/%d/%Y')
    df_windfoil["Date"] = (df_windfoil["Date"] - pd.to_datetime('1/1/2019', format='%m/%d/%Y')).dt.days
    df_windfoil = df_windfoil.dropna()

    X = df_windfoil['Date']
    y = df_windfoil[label]

    axis.plot(X, y, '.b')

    X_b = np.c_[np.ones((X.shape[0], 1)), X]
    theta_best = np.linalg.inv(X_b.T @ X_b) @ X_b.T @ y
    xmin = df_windfoil["Date"].min()
    xmax = df_windfoil["Date"].max() + 1000
    X_new = np.array([[xmin], [xmax]])
    X_new_b = np.c_[np.ones((2, 1)), X_new]
    y_predict = X_new_b @ theta_best


    axis.plot(X_new, y_predict, "r-")
    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    return fig 

def plot_arbre_decision(label): 

    from sklearn.ensemble import AdaBoostRegressor
    from sklearn.tree import DecisionTreeRegressor  
    
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)

    axis = fig.add_subplot(1, 1, 1)

    df = pd.read_csv('https://docs.google.com/spreadsheets/d/1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4/export?format=csv', usecols=['Date', 'Pratique', label])
    df_windfoil = df[df['Pratique'].eq('Windfoil')]
    df_windfoil["Date"] = pd.to_datetime(df_windfoil["Date"], format='%m/%d/%Y')
    df_windfoil["Date"] = (df_windfoil["Date"] - pd.to_datetime('1/1/2019', format='%m/%d/%Y')).dt.days
    df_windfoil = df_windfoil.dropna()

    x = df_windfoil['Date']
    X = np.expand_dims(x, axis=1)
    y = df_windfoil[label]

    axis.plot(X, y, '.b')

    rng = np.random.RandomState(1)
    clf = AdaBoostRegressor(DecisionTreeRegressor(max_depth=4), n_estimators=300, random_state=rng)
    x_new = np.linspace(0, 2000, 2001)
    X_new = np.expand_dims(x_new, axis=1)

    y_predict = clf.fit(X, y).predict(X_new)

    axis.plot(x_new, y_predict, "r-")
    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    return fig 

def plot_plus_proche_voisins(label): 

    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)

    axis = fig.add_subplot(1, 1, 1)

    df = pd.read_csv('https://docs.google.com/spreadsheets/d/1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4/export?format=csv', usecols=['Date', 'Pratique', label])
    df_windfoil = df[df['Pratique'].eq('Windfoil')]
    df_windfoil["Date"] = pd.to_datetime(df_windfoil["Date"], format='%m/%d/%Y')
    df_windfoil["Date"] = (df_windfoil["Date"] - pd.to_datetime('1/1/2019', format='%m/%d/%Y')).dt.days
    df_windfoil = df_windfoil.dropna()

    x = df_windfoil['Date']
    X = np.expand_dims(x, axis=1)
    y = df_windfoil[label]

    axis.plot(X, y, '.b')

    knn = neighbors.KNeighborsRegressor(5, weights='distance')
    x_new = np.linspace(0, 2000, 2001)
    X_new = np.expand_dims(x_new, axis=1)

    y_predict = knn.fit(X, y).predict(X_new)

    axis.plot(x_new, y_predict, "r-")
    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    return fig     


def plot_reseau_neurones(label, nbcouches, nbneuronescouche): 

    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    #fig.suptitle("Vitesse Windfoil")

    axis = fig.add_subplot(1, 1, 1)

    df = pd.read_csv('https://docs.google.com/spreadsheets/d/1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4/export?format=csv', usecols=['Date', 'Pratique', label])
    df_windfoil = df[df['Pratique'].eq('Windfoil')]
    df_windfoil["Date"] = pd.to_datetime(df_windfoil["Date"], format='%m/%d/%Y')
    df_windfoil["Date"] = (df_windfoil["Date"] - pd.to_datetime('1/1/2019', format='%m/%d/%Y')).dt.days
    df_windfoil = df_windfoil.dropna()

    X = df_windfoil['Date']
    y = df_windfoil[label]

    axis.plot(X, y, '.b')

    import tensorflow as tf
    from tensorflow import keras

    df_windfoil["Date"] = df_windfoil["Date"].astype(float, errors = 'raise')
    train_dataset = df_windfoil.sample(frac=0.8, random_state=0)
    train_features = train_dataset.copy()
    train_labels = train_dataset.pop(label)

    couches = [keras.layers.BatchNormalization()]
    for x in range(nbcouches):
        couches.append(keras.layers.Dense(nbneuronescouche, activation='relu'))
        couches.append(keras.layers.Dense(nbneuronescouche, activation='relu'))
    couches.append(keras.layers.Dense(1))

    model = tf.keras.Sequential(couches)

    model.compile(loss='mean_absolute_error', optimizer=tf.keras.optimizers.Adam(0.1))

    model.fit(train_features['Date'], 
        train_labels, validation_split=0.2,
        epochs=10000, 
        callbacks=[keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True)],
        verbose=0)

    xmin = train_features['Date'].min()
    xmax = train_features['Date'].max() + 1000
    x = tf.linspace(xmin, xmax, 1000)
    y = model.predict(x)

#    axis.set_xlim([xmin, xmax])
    axis.plot(train_features['Date'], train_labels, '.b')
    axis.plot(x, y, 'r-', label='Predictions')
    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    return fig

@app.route('/bokeh')
def bokeh():

    p = figure(plot_width=600, plot_height=600, x_axis_label="x", y_axis_label="y", active_scroll ="wheel_zoom")
    x = [1, 2, 3, 4, 5]
    y = [4, 5, 5, 7, 2]
    p.circle(x, y)

    # grab the static resources
    js_resources = INLINE.render_js()
    css_resources = INLINE.render_css()

    # render template
    script, div = components(p)
    html = render_template(
        'bokeh.html',
        plot_script=script,
        plot_div=div,
        js_resources=js_resources,
        css_resources=css_resources,
    )

    return html