"""
Calcule Vmoy (vitesse moyenne des vitesses > 12 noeuds), Vmax et V100 
à partir des fichiers GPX et met à jour les colonnes du Google Sheet.
"""

import gspread
import gpxpy
import requests
import time
import os
import json
import base64
import tempfile
import math

SHEET_ID = '1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4'
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'google', 'session-491110-c3945511c396.json')
SEUIL_NOEUDS = 12


def get_gspread_client():
    """Retourne un client gspread, via fichier local ou variable d'env."""
    env_creds = os.environ.get('GOOGLE_CREDENTIALS_B64')
    if env_creds:
        creds_json = json.loads(base64.b64decode(env_creds))
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(creds_json, tmp)
        tmp.close()
        return gspread.service_account(filename=tmp.name)
    return gspread.service_account(filename=CREDENTIALS_FILE)


MS_TO_KNOTS = 1.94384


def _distance_km(lat1, lon1, lat2, lon2):
    """Distance haversine en km (identique à GpxService.calculeDistance de visugpx)."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.sin(dlon / 2) ** 2 * math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)))
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _vitesse_point(i, pts):
    """Vitesse en noeuds entre le point i-1 et le point i (GpxService.calculeVitesse)."""
    if i == 0:
        return 0
    dt = pts[i][0] - pts[i - 1][0]
    if dt == 0:
        return 0
    return (_distance_km(pts[i][1], pts[i][2], pts[i - 1][1], pts[i - 1][2]) * 1000 / dt) * MS_TO_KNOTS


def _filtre(pts):
    """Supprime les points d'accélération aberrante (GpxService.filtre).
    Retourne True si au moins un point a été supprimé."""
    SEUIL_ACCELERATION = 1.0
    SEUIL_DECELERATION = -3.5
    k = 1
    erreur = False
    while k < len(pts):
        v0 = _vitesse_point(k - 1, pts)
        v1 = _vitesse_point(k, pts)
        dt = pts[k][0] - pts[k - 1][0]
        if dt != 0:
            acceleration = (v1 - v0) / dt
        else:
            # Même comportement que la division par zéro en JavaScript
            acceleration = math.copysign(math.inf, v1 - v0) if v1 != v0 else math.nan
        if acceleration > SEUIL_ACCELERATION or acceleration < SEUIL_DECELERATION:
            del pts[k]
            erreur = True
        k += 1
    return erreur


def calcul_vitesses(gpx_url):
    """Télécharge un GPX et retourne (vmoy, vmax, v100, distance_km).

    Algorithme identique à visugpx (projet greduvent, sensations/visu-gpx) :
    - filtre des points selon l'accélération (+1 / -3,5 noeuds/s), itéré
    - Vmax     : meilleure vitesse sur 2 s (stat « 2s »)
    - V100     : meilleure vitesse sur 100 m (stat « 100m »)
    - Distance : distance cumulée point à point (dmax)
    - Vmoy     : moyenne des vitesses sur 2 s supérieures au seuil
    """
    try:
        r = requests.get(gpx_url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Erreur téléchargement {gpx_url}: {e}")
        return None

    import re
    xml_clean = r.text
    xml_clean = re.sub(r'<(\w+)>null</\1>', '', xml_clean)
    xml_clean = re.sub(r'<fix>[^<]*</fix>', '', xml_clean)
    xml_clean = re.sub(r'<extensions>.*?</extensions>', '', xml_clean, flags=re.DOTALL)

    try:
        gpx = gpxpy.parse(xml_clean)
    except Exception as e:
        print(f"  Erreur parsing GPX: {e}")
        return None

    # Points (temps en s, lat, lon) de tous les trkpt ayant une date, triés par date
    pts = [(p.time.timestamp(), p.latitude, p.longitude)
           for track in gpx.tracks for segment in track.segments for p in segment.points
           if p.time and p.latitude is not None and p.longitude is not None]
    pts.sort(key=lambda p: p[0])
    if len(pts) < 2:
        return 0.0, 0.0, 0.0, 0.0

    # Filtre des valeurs aberrantes selon l'accélération
    k = 0
    while _filtre(pts) and k < 100:
        k += 1

    # deltad[i] : distance (km) entre le point i-1 et le point i
    n = len(pts)
    deltad = [0.0] + [_distance_km(pts[i][1], pts[i][2], pts[i - 1][1], pts[i - 1][2]) for i in range(1, n)]
    dmax = sum(deltad) - deltad[-1]

    def vitesse_pendant(i0, duree):
        """Vitesse (noeuds) à partir du point i0 sur une durée (s) (StatService.calculeVIndicePendant)."""
        distance = 0.0
        for i in range(i0, n):
            dt = pts[i][0] - pts[i0][0]
            if dt >= duree:
                return (distance * 1000 / dt) * MS_TO_KNOTS if dt != 0 else 0
            if i + 1 < n:
                distance += deltad[i + 1]
        return None

    def vitesse_sur(i0, distance_ref):
        """Vitesse (noeuds) à partir du point i0 sur une distance (km) (StatService.calculeVIndiceSur)."""
        distance = 0.0
        for i in range(i0, n):
            if distance >= distance_ref:
                dt = pts[i][0] - pts[i0][0]
                return (distance * 1000 / dt) * MS_TO_KNOTS if dt != 0 else 0
            if i + 1 < n:
                distance += deltad[i + 1]
        return None

    vitesses_2s = [v for v in (vitesse_pendant(i, 2) for i in range(n)) if v is not None]
    vitesses_100m = [v for v in (vitesse_sur(i, 0.1) for i in range(n)) if v is not None]

    above = [v for v in vitesses_2s if v > SEUIL_NOEUDS]
    vmoy = round(sum(above) / len(above), 2) if above else 0.0
    vmax = round(max(vitesses_2s, default=0.0), 2)
    v100 = round(max(vitesses_100m, default=0.0), 2)
    distance_km = round(dmax, 2)

    return vmoy, vmax, v100, distance_km


def main():
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

    if not gpx_col:
        print("Colonne GPX introuvable")
        return

    all_data = ws.get_all_values()
    rows_to_update = []

    for i, row in enumerate(all_data[1:], start=2):  # start=2 car row 1 = headers
        gpx_val = row[gpx_col - 1] if len(row) >= gpx_col else ''
        vmoy_val = row[vmoy_col - 1] if vmoy_col and len(row) >= vmoy_col else ''
        vmax_val = row[vmax_col - 1] if vmax_col and len(row) >= vmax_col else ''
        v100_val = row[v100_col - 1] if v100_col and len(row) >= v100_col else ''
        distance_val = row[distance_col - 1] if distance_col and len(row) >= distance_col else ''
        distance_simple_val = row[distance_simple_col - 1] if distance_simple_col and len(row) >= distance_simple_col else ''

        if gpx_val.strip() and (not vmoy_val.strip() or not vmax_val.strip() or not v100_val.strip() or not distance_val.strip() or (distance_simple_col and not distance_simple_val.strip())):
            rows_to_update.append((i, gpx_val.strip()))

    print(f"{len(rows_to_update)} lignes à traiter")

    from gspread.cell import Cell
    cells_to_update = []

    for idx, (row_num, gpx_url) in enumerate(rows_to_update):
        print(f"[{idx + 1}/{len(rows_to_update)}] Ligne {row_num}: {gpx_url}")
        res = calcul_vitesses(gpx_url)
        if res is not None:
            vmoy, vmax, v100, distance_km = res
            print(f"  Vmoy = {vmoy}, Vmax = {vmax}, V100 = {v100}, Distance = {distance_km} km")
            if vmoy_col:
                cells_to_update.append(Cell(row_num, vmoy_col, vmoy))
            if vmax_col:
                cells_to_update.append(Cell(row_num, vmax_col, vmax))
            if v100_col:
                cells_to_update.append(Cell(row_num, v100_col, v100))
            if distance_col:
                cells_to_update.append(Cell(row_num, distance_col, distance_km))
            if distance_simple_col:
                cells_to_update.append(Cell(row_num, distance_simple_col, distance_km))
        else:
            print("  Skipped")

    if cells_to_update:
        print("Mise à jour du fichier Google Sheet en un seul appel API...")
        ws.update_cells(cells_to_update)

    print("Terminé !")


if __name__ == '__main__':
    main()
