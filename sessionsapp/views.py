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

@app.route('/ia/regressionlineaire')
def regression_lineaire():
    fig = plot_regression_lineaire()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')
    
@app.route('/ia/reseauneurones')
def reseau_neurones():
    fig = plot_reseau_neurones()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

def plot_regression_lineaire(): 

    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    fig.suptitle("Vitesse Windfoil")

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

    axis.set_ylabel('Vitesse 100m (kts)')
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    return fig 

def plot_reseau_neurones(): 

    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    fig.suptitle("Vitesse Windfoil")

    axis = fig.add_subplot(1, 1, 1)

    df = pd.read_csv('https://docs.google.com/spreadsheets/d/1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4/export?format=csv', usecols=['Date', 'Pratique', 'V 100m K72'])
    df_windfoil = df[df['Pratique'].eq('Windfoil')]
    df_windfoil["Date"] = pd.to_datetime(df_windfoil["Date"], format='%m/%d/%Y')
    df_windfoil["Date"] = (df_windfoil["Date"] - pd.to_datetime('1/1/2019', format='%m/%d/%Y')).dt.days
    df_windfoil = df_windfoil.dropna()

    X = df_windfoil['Date']
    y = df_windfoil['V 100m K72']

    axis.plot(X, y, '.b')

    import tensorflow as tf
    from tensorflow import keras

    dataset = df_windfoil

    train_dataset = dataset.sample(frac=0.8, random_state=0)

    train_features = dataset.copy()

    train_labels = train_features.pop('V 100m K72')

    date_heure = np.array(train_features['Date'])
    date_heure_normalizer = tf.keras.layers.Normalization(input_shape=[1,], axis=None)
    date_heure_normalizer.adapt(date_heure)

    model = tf.keras.Sequential([date_heure_normalizer,
                                keras.layers.Dense(64, activation='relu'),
                    #           keras.layers.Dense(64, activation='relu'),                             
                                keras.layers.Dense(1)])

    model.compile(loss='mean_absolute_error', optimizer=tf.keras.optimizers.Adam(0.1))

    history = model.fit(train_features['Date'], 
                        train_labels, validation_split=0.2,
                        epochs=10000, 
                        callbacks=[keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True)],
                        verbose=0)

    axis.set_ylabel('Vitesse 100m (kts)')
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    xmin = train_features['Date'].min()
    xmax = 2000 #train_features['Date'].max()
    x = tf.linspace(xmin, xmax, 1000)
    y = model.predict(x)

    axis.set_xlim([xmin, xmax])

    axis.scatter(train_features['Date'], train_labels, label='Data')

    axis.plot(x, y, color='k', label='Predictions')

    axis.set_ylabel('Vitesse 100m (kts)')
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')
    plt.legend()

    return fig 
