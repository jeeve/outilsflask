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
import threading
#from sklearn import tree
#from sklearn import neighbors

from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.resources import INLINE, CDN
from bokeh.models import ColumnDataSource, AdaptiveTicker, CustomJSTickFormatter
from bokeh.palettes import Category10, Category20
from bokeh.transform import cumsum
import math

matplotlib.rcParams['timezone'] = 'Europe/Paris'

app = Flask(__name__)

# Variable globale pour stocker le DataFrame
_df = None

def calculate_missing_speeds_async():
    """Calcule les vitesses manquantes en arrière-plan (thread)."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from sessionsapp.updade_calcul import calcul_vitesses, SHEET_ID, get_gspread_client
        
        logger.info("Démarrage du calcul en arrière-plan...")
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1

        headers = ws.row_values(1)
        gpx_col = headers.index('GPX') + 1 if 'GPX' in headers else None
        vmoy_col = headers.index('Vmoy') + 1 if 'Vmoy' in headers else None
        vmax_col = headers.index('Vmax') + 1 if 'Vmax' in headers else None
        v100_col = headers.index('V100') + 1 if 'V100' in headers else None
        distance_col = headers.index('Distance (km)') + 1 if 'Distance (km)' in headers else None
        distance_simple_col = headers.index('Distance') + 1 if 'Distance' in headers else None

        if not (gpx_col and vmoy_col and vmax_col and v100_col and distance_col):
            return

        all_data = ws.get_all_values()
        updated = 0
        
        for i, row in enumerate(all_data[1:], start=2):
            try:
                gpx_val = row[gpx_col - 1].strip() if len(row) >= gpx_col and row[gpx_col - 1] else ''
                vmoy_val = row[vmoy_col - 1].strip() if len(row) >= vmoy_col and row[vmoy_col - 1] else ''
                vmax_val = row[vmax_col - 1].strip() if len(row) >= vmax_col and row[vmax_col - 1] else ''
                v100_val = row[v100_col - 1].strip() if len(row) >= v100_col and row[v100_col - 1] else ''
                distance_val = row[distance_col - 1].strip() if len(row) >= distance_col and row[distance_col - 1] else ''
                distance_simple_val = row[distance_simple_col - 1].strip() if distance_simple_col and len(row) >= distance_simple_col and row[distance_simple_col - 1] else ''

                if gpx_val and (not vmoy_val or not vmax_val or not v100_val or not distance_val or (distance_simple_col and not distance_simple_val)):
                    res = calcul_vitesses(gpx_val)
                    if res is not None:
                        vmoy, vmax, v100, distance_km = res
                        if not vmoy_val:
                            ws.update_cell(i, vmoy_col, str(vmoy))
                        if not vmax_val:
                            ws.update_cell(i, vmax_col, str(vmax))
                        if not v100_val:
                            ws.update_cell(i, v100_col, str(v100))
                        if not distance_val:
                            ws.update_cell(i, distance_col, str(distance_km))
                        if distance_simple_col and not distance_simple_val:
                            ws.update_cell(i, distance_simple_col, str(distance_km))
                        updated += 1
                        logger.info(f"Ligne {i} mise à jour en arrière-plan")
            except Exception as e:
                logger.warning(f"Erreur ligne {i} (background): {e}")
                continue
        
        if updated > 0:
            logger.info(f"Calcul en arrière-plan terminé: {updated} vitesses écrites")
            get_data(force_reload=True)
    except Exception as e:
        logger.warning(f"Erreur calcul background: {e}")

def get_data(force_reload=False):
    """Charge le CSV une seule fois et retourne le DataFrame."""
    global _df
    if _df is None or force_reload:
        _df = pd.read_csv('https://docs.google.com/spreadsheets/d/1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4/export?format=csv')
        if 'Vmoy' in _df.columns:
            _df['Vmoy_raw'] = _df['Vmoy']
        
        # S"assurer que V100 et Vmax sont reconnues
        numeric_cols = ['V 100m', 'V 100m K72', 'VMax K72 (noeuds)', 'Vmoy', 'Distance (km)', 'Vmax', 'V100']
        for col in numeric_cols:
            if col in _df.columns:
                _df[col] = pd.to_numeric(_df[col], errors='coerce')
    return _df

# Config options - Make sure you created a 'config.py' file.cd
# app.config.from_object('config')
# To get one variable, tape app.config['MY_VARIABLE']

@app.route('/ia')
def upload_form():
    """Affiche la page et lance le calcul des vitesses en arrière-plan."""
    # Lancer le calcul en background sans bloquer la page
    thread = threading.Thread(target=calculate_missing_speeds_async, daemon=True)
    thread.start()
    
    # Afficher la page immédiatement, avec les données à jour du Google Sheet
    # (sinon les sessions ajoutées depuis le démarrage du serveur n'apparaissent pas)
    df = get_data(force_reload=True)
    df_windfoil = df[df['Pratique'].eq('Windfoil')]
    nb_points = df_windfoil.shape[0]
    total_km = df_windfoil['Distance (km)'].sum()
    return render_template('index.html', nb_points=nb_points, total_km=total_km)

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
    label = request.args.get('label', default='V100', type=str)
    fig = plot_statistique_par_aile(label)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')


@app.route('/ia/statistique/voile')
def statistique_voile():
    """Retourne une image montrant l'évolution du label par voile."""
    label = request.args.get('label', default='V100', type=str)
    fig = plot_statistique_par_voile(label)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')


# ── Préparation des données (communes aux graphiques PNG et interactifs) ──

def _windfoil(colonnes):
    """Sessions Windfoil ayant toutes les `colonnes` renseignées.
    Ajoute Year si Date est demandée et Wing (taille de l'aile) si Aile est demandée."""
    df = get_data()
    df_windfoil = df[df['Pratique'].eq('Windfoil')].dropna(subset=colonnes).copy()
    if 'Date' in colonnes:
        df_windfoil['Date'] = pd.to_datetime(df_windfoil['Date'], format='%m/%d/%Y')
        df_windfoil['Year'] = df_windfoil['Date'].dt.year
    if 'Aile' in colonnes:
        # extraction de la partie "aile" (avant le premier espace)
        df_windfoil['Wing'] = df_windfoil['Aile'].astype(str).str.split().str[0]
    return df_windfoil


VENT_ORDER = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSO', 'SO', 'OSO', 'O', 'ONO', 'NO', 'NNO']


def _sessions_par_annee(colonne, groupe=None):
    """Nombre de sessions par année (lignes) et par valeur de `groupe` (colonnes)."""
    groupe = groupe or colonne
    counts = _windfoil(['Date', colonne]).groupby(['Year', groupe]).size().unstack(fill_value=0)
    if colonne == 'Vent':
        vent_columns = [v for v in VENT_ORDER if v in counts.columns]
        vent_columns += [v for v in counts.columns if v not in vent_columns]
        counts = counts[vent_columns]
    return counts


def _km_par_annee_spot():
    """Distance (km) par année (lignes) et par spot (colonnes)."""
    df_windfoil = _windfoil(['Date', 'Spot', 'Distance (km)'])
    return df_windfoil.groupby(['Year', 'Spot'])['Distance (km)'].sum().unstack(fill_value=0)


def _moyenne_par_annee(label):
    """Moyenne du label par année."""
    return _windfoil([label, 'Date']).groupby('Year')[label].mean().reset_index()


def _repartition(colonne, groupe=None):
    """Nombre de sessions par valeur de `groupe` (colonnes nom, Count)."""
    groupe = groupe or colonne
    return _windfoil([colonne]).groupby(groupe).size().reset_index(name='Count').rename(columns={groupe: 'nom'})


def _sessions_ordonnees(label, colonne):
    """Sessions triées par date, avec une position par session (index 0..n-1)."""
    df_windfoil = _windfoil([label, colonne, 'Date'])
    return df_windfoil.sort_values('Date', kind='stable').reset_index(drop=True)


# ── Graphiques PNG (matplotlib) ──

def _axe_sessions(fig, axis, dates, nb_libelles=40):
    """Axe des abscisses en sessions équidistantes, libellées par leur date."""
    pas = max(1, -(-len(dates) // nb_libelles))
    positions = list(range(0, len(dates), pas))
    axis.set_xticks(positions)
    axis.set_xticklabels([dates.iloc[i].strftime('%d/%m/%Y') for i in positions], rotation=90)
    axis.set_xlim(-1, len(dates))
    fig.subplots_adjust(bottom=0.18)


def _plot_statistique(label, colonne, groupe, titre_legende):
    """Évolution de `label` au fil des sessions, une courbe par valeur de `groupe`."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    df_windfoil = _sessions_ordonnees(label, colonne)
    for nom, grp in df_windfoil.groupby(groupe):
        axis.plot(grp.index, grp[label], 'o-', label=nom)

    axis.set_ylabel(label)
    _axe_sessions(fig, axis, df_windfoil['Date'])
    axis.legend(title=titre_legende, loc='best')
    axis.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

    return fig


def plot_statistique_par_aile(label):
    """Trace l'évolution de la valeur `label` au fil du temps, une courbe par aile."""
    return _plot_statistique(label, 'Aile', 'Wing', 'Aile')


def plot_statistique_par_voile(label):
    """Trace l'évolution du `label` au fil du temps, une courbe par voile (nom complet)."""
    return _plot_statistique(label, 'Voile', 'Voile', 'Voile')


def plot_bar_year_label(label):
    """Trace un graphique en barres de la moyenne du label par année."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    avg_per_year = _moyenne_par_annee(label)

    axis.bar(avg_per_year['Year'], avg_per_year[label], color='skyblue', width=0.8)
    axis.set_xlabel('Année')
    axis.set_ylabel(f'Moyenne {label}')
    axis.set_title(f'Moyenne {label} par année')
    axis.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

    return fig


def _plot_barres_cumulees(table, ylabel, titre, titre_legende):
    """Barres cumulées par année d'une table (lignes = années, colonnes = catégories)."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    table.plot(kind='bar', stacked=True, ax=axis, colormap='tab20')

    axis.set_xlabel('Année')
    axis.set_ylabel(ylabel)
    axis.set_title(titre)
    axis.legend(title=titre_legende, bbox_to_anchor=(1.05, 1), loc='upper left')
    axis.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

    fig.tight_layout()

    return fig


def plot_bar_year_wind_direction():
    """Trace un graphique en barres cumulées des directions du vent par année."""
    return _plot_barres_cumulees(_sessions_par_annee('Vent'), 'Nombre de sessions', 'Directions du vent par année', 'Vent')


def plot_bar_year_spot():
    """Trace un graphique en barres cumulées des spots par année."""
    return _plot_barres_cumulees(_sessions_par_annee('Spot'), 'Nombre de sessions', 'Spots par année', 'Spot')


def plot_bar_km_spot():
    """Trace un graphique en barres cumulées des km par spot et par année."""
    return _plot_barres_cumulees(_km_par_annee_spot(), 'Distance (km)', 'Nombre de km par spot', 'Spot')


def plot_bar_year_aile():
    """Trace un graphique en barres cumulées des ailes par année."""
    return _plot_barres_cumulees(_sessions_par_annee('Aile', 'Wing'), 'Nombre de sessions', 'Ailes utilisées par année', 'Aile')


def plot_bar_year_voile():
    """Trace un graphique en barres cumulées des voiles par année."""
    return _plot_barres_cumulees(_sessions_par_annee('Voile'), 'Nombre de sessions', 'Voiles utilisées par année', 'Voile')


def _plot_camembert(repartition, titre):
    """Camembert de la répartition des sessions."""
    fig = Figure()
    fig.set_size_inches(10, 7, forward=True)
    axis = fig.add_subplot(1, 1, 1)

    axis.pie(repartition['Count'], autopct='%1.1f%%', startangle=90, textprops={'color':'white', 'fontsize': 14})
    axis.set_title(titre)
    axis.legend(repartition['nom'], loc='best')
    axis.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

    return fig


def plot_pie_spot():
    """Trace un camembert de la répartition des sessions par spot."""
    return _plot_camembert(_repartition('Spot'), 'Répartition des sessions par spot')


def plot_pie_aile():
    """Trace un camembert de la répartition des sessions par aile."""
    return _plot_camembert(_repartition('Aile', 'Wing'), 'Répartition des sessions par aile')


def plot_pie_voile():
    """Trace un camembert de la répartition des sessions par voile."""
    return _plot_camembert(_repartition('Voile'), 'Répartition des sessions par voile')


# ── Graphiques interactifs (Bokeh), ouverts au clic sur une image ──

def _palette(n, base=Category20[20]):
    return [base[i % len(base)] for i in range(n)]


def _bokeh_figure(titre, **kwargs):
    return figure(title=titre, sizing_mode='stretch_both',
                  tools='pan,wheel_zoom,box_zoom,reset,save', active_scroll='wheel_zoom', **kwargs)


def _bokeh_legende_dehors(p, titre, cliquable=True):
    """Place la légende à droite, cliquable pour masquer une série."""
    legende = p.legend[0]
    legende.title = titre
    if cliquable:
        legende.click_policy = 'hide'
    p.add_layout(legende, 'right')


def _bokeh_barres_cumulees(table, ylabel, titre, titre_legende):
    table = table.copy()
    table.columns = [str(c) for c in table.columns]
    table.index = [str(a) for a in table.index]
    categories = list(table.columns)
    source = ColumnDataSource(table.rename_axis('Year').reset_index())

    p = _bokeh_figure(titre, x_range=list(table.index), y_axis_label=ylabel, x_axis_label='Année',
                      tooltips=[('Année', '@Year'), (titre_legende, '$name'), (ylabel, '@$name{0.[0]}')])
    p.vbar_stack(categories, x='Year', width=0.8, color=_palette(len(categories)), source=source,
                 legend_label=categories)
    p.y_range.start = 0
    p.xgrid.grid_line_color = None
    _bokeh_legende_dehors(p, titre_legende)
    return p


def _bokeh_camembert(repartition, titre):
    data = repartition.copy()
    data['nom'] = data['nom'].astype(str)
    data['angle'] = data['Count'] / data['Count'].sum() * 2 * math.pi
    data['pct'] = data['Count'] / data['Count'].sum() * 100
    data['color'] = _palette(len(data), Category10[10])

    p = _bokeh_figure(titre, x_range=(-1, 1), y_range=(-1, 1), match_aspect=True,
                      tooltips=[('', '@nom'), ('Sessions', '@Count'), ('Part', '@pct{0.0} %')])
    p.wedge(x=0, y=0, radius=0.9, start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
            line_color='white', fill_color='color', legend_field='nom', source=ColumnDataSource(data))
    p.axis.visible = False
    p.grid.grid_line_color = None
    # toutes les parts forment un seul tracé : un clic masquerait tout le camembert
    _bokeh_legende_dehors(p, '', cliquable=False)
    return p


def _bokeh_moyenne_par_annee(label):
    data = _moyenne_par_annee(label)
    data['Year'] = data['Year'].astype(str)
    data['valeur'] = data[label]
    p = _bokeh_figure(f'Moyenne {label} par année', x_range=list(data['Year']), x_axis_label='Année',
                      y_axis_label=f'Moyenne {label}', tooltips=[('Année', '@Year'), (label, '@valeur{0.00}')])
    p.vbar(x='Year', top='valeur', width=0.8, color='skyblue', source=ColumnDataSource(data[['Year', 'valeur']]))
    p.y_range.start = 0
    p.xgrid.grid_line_color = None
    return p


def _bokeh_statistique(label, colonne, groupe, titre_legende):
    df_windfoil = _sessions_ordonnees(label, colonne)
    df_windfoil['x'] = df_windfoil.index
    df_windfoil['date_txt'] = df_windfoil['Date'].dt.strftime('%d/%m/%Y')
    df_windfoil['valeur'] = df_windfoil[label]
    for c in ('Aile', 'Voile', 'Spot'):
        df_windfoil[c] = df_windfoil[c].fillna('').astype(str) if c in df_windfoil else ''

    p = _bokeh_figure(f'{label} par {titre_legende.lower()}', y_axis_label=label,
                      tooltips=[('Date', '@date_txt'), (label, '@valeur{0.00}'), ('Aile', '@Aile'),
                                ('Voile', '@Voile'), ('Spot', '@Spot')])
    groupes = list(df_windfoil.groupby(groupe))
    for (nom, grp), couleur in zip(groupes, _palette(len(groupes), Category10[10])):
        source = ColumnDataSource(grp[['x', 'valeur', 'date_txt', 'Aile', 'Voile', 'Spot']])
        p.line('x', 'valeur', source=source, color=couleur, legend_label=str(nom))
        p.scatter('x', 'valeur', source=source, color=couleur, size=7, legend_label=str(nom))

    # sessions équidistantes, libellées par leur date
    p.xaxis.ticker = AdaptiveTicker(min_interval=1, mantissas=[1, 2, 5], desired_num_ticks=25)
    p.xaxis.formatter = CustomJSTickFormatter(args=dict(dates=list(df_windfoil['date_txt'])),
                                              code="return dates[tick] || '';")
    p.xaxis.major_label_orientation = math.pi / 2
    _bokeh_legende_dehors(p, titre_legende)
    return p


GRAPHIQUES_INTERACTIFS = {
    'bar_year_wind_direction': lambda label: _bokeh_barres_cumulees(_sessions_par_annee('Vent'), 'Nombre de sessions', 'Directions du vent par année', 'Vent'),
    'bar_year_spot': lambda label: _bokeh_barres_cumulees(_sessions_par_annee('Spot'), 'Nombre de sessions', 'Spots par année', 'Spot'),
    'bar_km_spot': lambda label: _bokeh_barres_cumulees(_km_par_annee_spot(), 'Distance (km)', 'Nombre de km par spot', 'Spot'),
    'bar_year_aile': lambda label: _bokeh_barres_cumulees(_sessions_par_annee('Aile', 'Wing'), 'Nombre de sessions', 'Ailes utilisées par année', 'Aile'),
    'bar_year_voile': lambda label: _bokeh_barres_cumulees(_sessions_par_annee('Voile'), 'Nombre de sessions', 'Voiles utilisées par année', 'Voile'),
    'pie_spot': lambda label: _bokeh_camembert(_repartition('Spot'), 'Répartition des sessions par spot'),
    'pie_aile': lambda label: _bokeh_camembert(_repartition('Aile', 'Wing'), 'Répartition des sessions par aile'),
    'pie_voile': lambda label: _bokeh_camembert(_repartition('Voile'), 'Répartition des sessions par voile'),
    'bar_year_label': lambda label: _bokeh_moyenne_par_annee(label),
    'statistique': lambda label: _bokeh_statistique(label, 'Aile', 'Wing', 'Aile'),
    'statistique_voile': lambda label: _bokeh_statistique(label, 'Voile', 'Voile', 'Voile'),
}


@app.route('/ia/interactif/<nom>')
def graphique_interactif(nom):
    """Page avec la version interactive (zoom, infobulles) d'un graphique."""
    if nom not in GRAPHIQUES_INTERACTIFS:
        return Response('Graphique inconnu', status=404)
    label = request.args.get('label', default='V100', type=str)
    p = GRAPHIQUES_INTERACTIFS[nom](label)
    script, div = components(p)
    return render_template('interactif.html', titre=p.title.text, plot_script=script, plot_div=div,
                           js_resources=CDN.render_js(), css_resources=CDN.render_css())


@app.route('/ia/update_vmoy')
def update_vmoy():
    """Calcule les Vmoy, Vmax et V100 manquantes depuis les GPX et met à jour le Google Sheet."""
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    try:
        from sessionsapp.updade_calcul import calcul_vitesses, SHEET_ID, get_gspread_client

        logger.info("Connexion au Google Sheet...")
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1

        headers = ws.row_values(1)
        logger.info(f"Headers trouvés: {headers}")
        
        # Trouver les indices des colonnes
        gpx_col = headers.index('GPX') + 1 if 'GPX' in headers else None
        vmoy_col = headers.index('Vmoy') + 1 if 'Vmoy' in headers else None
        vmax_col = headers.index('Vmax') + 1 if 'Vmax' in headers else None
        v100_col = headers.index('V100') + 1 if 'V100' in headers else None
        distance_col = headers.index('Distance (km)') + 1 if 'Distance (km)' in headers else None
        distance_simple_col = headers.index('Distance') + 1 if 'Distance' in headers else None

        logger.info(f"Colonnes trouvées: GPX={gpx_col}, Vmoy={vmoy_col}, Vmax={vmax_col}, V100={v100_col}, Distance_km={distance_col}, Distance={distance_simple_col}")
        
        if not gpx_col or not vmoy_col or not vmax_col or not v100_col or not distance_col:
            return Response('{"error": "Colonnes manquantes", "headers": %s}' % headers, mimetype='application/json')

        all_data = ws.get_all_values()
        logger.info(f"Nombre de lignes: {len(all_data)}")
        updated = 0

        from gspread.cell import Cell

        for i, row in enumerate(all_data[1:], start=2):
            try:
                # Accès sécurisé aux valeurs de la ligne
                gpx_val = row[gpx_col - 1].strip() if len(row) >= gpx_col and row[gpx_col - 1] else ''
                vmoy_val = row[vmoy_col - 1].strip() if len(row) >= vmoy_col and row[vmoy_col - 1] else ''
                vmax_val = row[vmax_col - 1].strip() if len(row) >= vmax_col and row[vmax_col - 1] else ''
                v100_val = row[v100_col - 1].strip() if len(row) >= v100_col and row[v100_col - 1] else ''
                distance_val = row[distance_col - 1].strip() if len(row) >= distance_col and row[distance_col - 1] else ''
                distance_simple_val = row[distance_simple_col - 1].strip() if distance_simple_col and len(row) >= distance_simple_col and row[distance_simple_col - 1] else ''

                # Traiter les lignes qui ont un GPX mais manquent d'au moins une vitesse ou distance
                if gpx_val and (not vmoy_val or not vmax_val or not v100_val or not distance_val or (distance_simple_col and not distance_simple_val)):
                    logger.info(f"Ligne {i}: GPX={gpx_val[:50]}... Vmoy={vmoy_val}, Vmax={vmax_val}, V100={v100_val}, Distance_km={distance_val}, Distance={distance_simple_val}")
                    res = calcul_vitesses(gpx_val)
                    if res is not None:
                        vmoy, vmax, v100, distance_km = res
                        logger.info(f"Ligne {i}: Calculé -> Vmoy={vmoy}, Vmax={vmax}, V100={v100}, Distance={distance_km} km")
                        
                        # Écrire les valeurs immédiatement dans le sheet
                        try:
                            if not vmoy_val:
                                ws.update_cell(i, vmoy_col, str(vmoy))
                                logger.info(f"Ligne {i}: Vmoy écrite")
                            if not vmax_val:
                                ws.update_cell(i, vmax_col, str(vmax))
                                logger.info(f"Ligne {i}: Vmax écrite")
                            if not v100_val:
                                ws.update_cell(i, v100_col, str(v100))
                                logger.info(f"Ligne {i}: V100 écrite")
                            if not distance_val:
                                ws.update_cell(i, distance_col, str(distance_km))
                                logger.info(f"Ligne {i}: Distance (km) écrite")
                            if distance_simple_col and not distance_simple_val:
                                ws.update_cell(i, distance_simple_col, str(distance_km))
                                logger.info(f"Ligne {i}: Distance écrite")
                            updated += 1
                        except Exception as e:
                            logger.exception(f"Erreur lors de l'écriture ligne {i}: {e}")
                    else:
                        logger.warning(f"Ligne {i}: calcul_vitesses retourné None")
            except Exception as e:
                logger.exception(f"Erreur lors du traitement de la ligne {i}: {e}")
                continue
                    
        logger.info(f"Total écrit: {updated} lignes")

        # Forcer le rechargement du DataFrame au prochain appel
        get_data(force_reload=True)

        return Response('{"updated": %d}' % updated, mimetype='application/json')
    
    except Exception as e:
        logger.exception(f"Erreur générale: {e}")
        return Response('{"error": "%s"}' % str(e), mimetype='application/json')


@app.route('/ia/bar_year_label')
def bar_year_label():
    """Retourne une image montrant la moyenne du label par année."""
    label = request.args.get('label', default='V100', type=str)
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

@app.route('/ia/bar_year_spot')
def bar_year_spot():
    """Retourne une image montrant les spots par année."""
    fig = plot_bar_year_spot()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/ia/bar_km_spot')
def bar_km_spot():
    """Retourne une image montrant les km par spot et par année."""
    fig = plot_bar_km_spot()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/ia/bar_year_aile')
def bar_year_aile():
    """Retourne une image montrant les ailes par année."""
    fig = plot_bar_year_aile()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/ia/bar_year_voile')
def bar_year_voile():
    """Retourne une image montrant les voiles par année."""
    fig = plot_bar_year_voile()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

@app.route('/ia/pie_spot')
def pie_spot():
    """Retourne une image montrant la répartition des sessions par spot."""
    fig = plot_pie_spot()
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
