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
#from sklearn import tree
#from sklearn import neighbors

from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.resources import INLINE

matplotlib.rcParams['timezone'] = 'Europe/Paris'

app = Flask(__name__)

# Variable globale pour stocker le DataFrame
_df = None

def get_data(force_reload=False):
    """Charge le CSV une seule fois et retourne le DataFrame."""
    global _df
    if _df is None or force_reload:
        _df = pd.read_csv('https://docs.google.com/spreadsheets/d/1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4/export?format=csv')
    return _df

# Config options - Make sure you created a 'config.py' file.cd
# app.config.from_object('config')
# To get one variable, tape app.config['MY_VARIABLE']

@app.route('/ia')
def upload_form():
    df = get_data()
    df_windfoil = df[df['Pratique'].eq('Windfoil')]
    nb_points = df_windfoil.shape[0]
    return render_template('index.html', nb_points=nb_points)

"""
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
"""

@app.route('/ia/statistique')
def statistique():
    """Retourne une image montrant l'évolution du label par aile."""
    label = request.args.get('label', default='V 100m K72', type=str)
    fig = plot_statistique_par_aile(label)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')


@app.route('/ia/statistique/voile')
def statistique_voile():
    """Retourne une image montrant l'évolution du label par voile."""
    label = request.args.get('label', default='V 100m K72', type=str)
    fig = plot_statistique_par_voile(label)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')


def plot_statistique_par_aile(label):
    """Trace l'évolution de la valeur `label` au fil du temps, une courbe par aile."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    # lire la colonne Aile en plus du label
    df = get_data()
    df_windfoil = df[df['Pratique'].eq('Windfoil')].dropna(subset=[label, 'Aile'])
    df_windfoil['Date'] = pd.to_datetime(df_windfoil['Date'], format='%m/%d/%Y')
    df_windfoil['Date'] = (
        df_windfoil['Date'] - pd.to_datetime('1/1/2019', format='%m/%d/%Y')
    ).dt.days

    # extraction de la partie "aile" (avant le premier espace)
    df_windfoil['Wing'] = df_windfoil['Aile'].astype(str).str.split().str[0]

    # tracer une ligne par aile
    for wing, grp in df_windfoil.groupby('Wing'):
        axis.plot(grp['Date'], grp[label], 'o-', label=wing)

    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')
    axis.legend(title='Aile', loc='best')
    axis.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

    return fig


def plot_statistique_par_voile(label):
    """Trace l'évolution du `label` au fil du temps, une courbe par voile (nom complet)."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
    df_windfoil = df[df['Pratique'].eq('Windfoil')].dropna(subset=[label, 'Voile'])
    df_windfoil['Date'] = pd.to_datetime(df_windfoil['Date'], format='%m/%d/%Y')
    df_windfoil['Date'] = (
        df_windfoil['Date'] - pd.to_datetime('1/1/2019', format='%m/%d/%Y')
    ).dt.days

    # tracer une ligne par voile (nom complet)
    for voile, grp in df_windfoil.groupby('Voile'):
        axis.plot(grp['Date'], grp[label], 'o-', label=voile)

    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')
    axis.legend(title='Voile', loc='best')
    axis.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

    return fig

def plot_bar_year():
    """Trace un graphique en barres du nombre de sessions par année."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
    df_windfoil = df[df['Pratique'].eq('Windfoil')].dropna(subset=['Date'])
    df_windfoil['Date'] = pd.to_datetime(df_windfoil['Date'], format='%m/%d/%Y')
    df_windfoil['Year'] = df_windfoil['Date'].dt.year
    sessions_per_year = df_windfoil.groupby('Year').size().reset_index(name='Count')

    axis.bar(sessions_per_year['Year'], sessions_per_year['Count'], color='skyblue', width=0.8)
    axis.set_xlabel('Année')
    axis.set_ylabel('Nombre de sessions')
    axis.set_title('Nombre de sessions par année')
    axis.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

    return fig

def plot_bar_year_label(label):
    """Trace un graphique en barres de la moyenne du label par année."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
    df_windfoil = df[df['Pratique'].eq('Windfoil')].dropna(subset=[label, 'Date'])
    df_windfoil['Date'] = pd.to_datetime(df_windfoil['Date'], format='%m/%d/%Y')
    df_windfoil['Year'] = df_windfoil['Date'].dt.year
    avg_per_year = df_windfoil.groupby('Year')[label].mean().reset_index()

    axis.bar(avg_per_year['Year'], avg_per_year[label], color='skyblue', width=0.8)
    axis.set_xlabel('Année')
    axis.set_ylabel(f'Moyenne {label}')
    axis.set_title(f'Moyenne {label} par année')
    axis.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

    return fig

def plot_bar_year_wind_direction():
    """Trace un graphique en barres cumulées des directions du vent par année."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
    df_windfoil = df[df['Pratique'].eq('Windfoil')].dropna(subset=['Date', 'Vent'])
    df_windfoil['Date'] = pd.to_datetime(df_windfoil['Date'], format='%m/%d/%Y')
    df_windfoil['Year'] = df_windfoil['Date'].dt.year
    
    counts = df_windfoil.groupby(['Year', 'Vent']).size().unstack(fill_value=0)
    
    vent_order = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSO', 'SO', 'OSO', 'O', 'ONO', 'NO', 'NNO']
    vent_columns = [v for v in vent_order if v in counts.columns]
    vent_columns += [v for v in counts.columns if v not in vent_columns]
    counts = counts[vent_columns]

    counts.plot(kind='bar', stacked=True, ax=axis, colormap='tab20')
    
    axis.set_xlabel('Année')
    axis.set_ylabel('Nombre de sessions')
    axis.set_title('Directions du vent par année')
    axis.legend(title='Vent', bbox_to_anchor=(1.05, 1), loc='upper left')
    axis.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)
    
    fig.tight_layout()

    return fig

def plot_pie_aile():
    """Trace un camembert de la répartition des sessions par aile."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
    df_windfoil = df[df['Pratique'].eq('Windfoil')].dropna(subset=['Aile'])
    df_windfoil['Wing'] = df_windfoil['Aile'].astype(str).str.split().str[0]
    sessions_per_wing = df_windfoil.groupby('Wing').size().reset_index(name='Count')

    axis.pie(sessions_per_wing['Count'], autopct='%1.1f%%', startangle=90, textprops={'color':'white', 'fontsize': 14})
    axis.set_title('Répartition des sessions par aile')
    axis.legend(sessions_per_wing['Wing'], loc='best')
    axis.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

    return fig

def plot_pie_voile():
    """Trace un camembert de la répartition des sessions par voile."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
    df_windfoil = df[df['Pratique'].eq('Windfoil')].dropna(subset=['Voile'])
    sessions_per_voile = df_windfoil.groupby('Voile').size().reset_index(name='Count')

    axis.pie(sessions_per_voile['Count'], autopct='%1.1f%%', startangle=90, textprops={'color':'white', 'fontsize': 14})
    axis.set_title('Répartition des sessions par voile')
    axis.legend(sessions_per_voile['Voile'], loc='best')
    axis.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

    return fig

@app.route('/ia/update_vmoy')
def update_vmoy():
    """Calcule les Vmoy manquantes depuis les GPX et met à jour le Google Sheet."""
    from sessionsapp.update_vmoy import calcul_vmoy, SHEET_ID, get_gspread_client
    import time

    gc = get_gspread_client()
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.sheet1

    headers = ws.row_values(1)
    gpx_col = headers.index('GPX') + 1
    vmoy_col = headers.index('Vmoy') + 1

    all_data = ws.get_all_values()
    updated = 0

    for i, row in enumerate(all_data[1:], start=2):
        gpx_val = row[gpx_col - 1] if len(row) >= gpx_col else ''
        vmoy_val = row[vmoy_col - 1] if len(row) >= vmoy_col else ''

        if gpx_val.strip() and not vmoy_val.strip():
            vmoy = calcul_vmoy(gpx_val.strip())
            if vmoy is not None:
                ws.update_cell(i, vmoy_col, vmoy)
                updated += 1
                time.sleep(1.5)

    # Forcer le rechargement du DataFrame au prochain appel
    get_data(force_reload=True)

    return Response('{"updated": %d}' % updated, mimetype='application/json')


@app.route('/ia/bar_year')
def bar_year():
    """Retourne une image montrant le nombre de sessions par année."""
    fig = plot_bar_year()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/ia/bar_year_label')
def bar_year_label():
    """Retourne une image montrant la moyenne du label par année."""
    label = request.args.get('label', default='V 100m K72', type=str)
    fig = plot_bar_year_label(label)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/ia/bar_year_wind_direction')
def bar_year_wind_direction():
    """Retourne une image montrant les directions du vent par année."""
    fig = plot_bar_year_wind_direction()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/ia/pie_aile')
def pie_aile():
    """Retourne une image montrant la répartition des sessions par aile."""
    fig = plot_pie_aile()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/ia/pie_voile')
def pie_voile():
    """Retourne une image montrant la répartition des sessions par voile."""
    fig = plot_pie_voile()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

"""
def plot_regression_lineaire(label): 

    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    #fig.suptitle("Vitesse Windfoil")

    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
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

    axis.plot(X_new, y_predict, "ro-")
    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    return fig 

def plot_arbre_decision(label): 

    from sklearn.ensemble import AdaBoostRegressor
    from sklearn.tree import DecisionTreeRegressor  
    
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)

    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
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

    axis.plot(x_new, y_predict, "ro-")
    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    return fig 

def plot_plus_proche_voisins(label): 

    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)

    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
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

    axis.plot(x_new, y_predict, "ro-")
    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    return fig     

def plot_reseau_neurones(label, nbcouches, nbneuronescouche): 

    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    #fig.suptitle("Vitesse Windfoil")

    axis = fig.add_subplot(1, 1, 1)

    df = get_data()
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
    axis.plot(x, y, 'ro-', label='Predictions')
    axis.set_ylabel(label)
    axis.set_xlabel('Nombre de jours depuis le 01/01/2019')

    return fig
"""

"""
@app.route('/bokeh')
def bokeh():

    p = figure(min_width=600, height=600, x_axis_label="x", y_axis_label="y", active_scroll ="wheel_zoom")
    x = [1, 2, 3, 4, 5]
    y = [4, 5, 5, 7, 2]
    p.scatter(x, y, size=10)

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
"""
