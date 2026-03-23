"""
Calcule Vmoy (vitesse moyenne des vitesses > 12 noeuds) à partir des fichiers GPX
et met à jour la colonne Vmoy du Google Sheet.
"""

import gspread
import gpxpy
import requests
import time
import os
import json
import base64
import tempfile

SHEET_ID = '1eCnnsOdcwRKJ_kpx1uS-XXJoJGFSvm3l3ez2K9PpPv4'
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'google', 'session-491110-67170a841cac.json')
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


def calcul_vmoy(gpx_url):
    """Télécharge un GPX et retourne la vitesse moyenne des vitesses > 12 noeuds."""
    try:
        r = requests.get(gpx_url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Erreur téléchargement {gpx_url}: {e}")
        return None

    import re
    xml_clean = r.text
    # Nettoyer les valeurs nulles dans le XML (ex: <geoidheight>null</geoidheight>)
    xml_clean = re.sub(r'<(\w+)>null</\1>', '', xml_clean)
    # Supprimer les balises <fix> avec des valeurs non standard
    xml_clean = re.sub(r'<fix>[^<]*</fix>', '', xml_clean)
    # Supprimer les extensions (namespaces non déclarés comme gpxtpx:)
    xml_clean = re.sub(r'<extensions>.*?</extensions>', '', xml_clean, flags=re.DOTALL)

    try:
        gpx = gpxpy.parse(xml_clean)
    except Exception as e:
        print(f"  Erreur parsing GPX: {e}")
        return None

    speeds_knots = []
    for track in gpx.tracks:
        for segment in track.segments:
            points = segment.points
            for i in range(1, len(points)):
                p1, p2 = points[i - 1], points[i]
                if p1.time and p2.time:
                    dt = (p2.time - p1.time).total_seconds()
                    if dt > 0:
                        dist = p1.distance_2d(p2)  # mètres
                        speed_knots = (dist / dt) * 1.94384
                        speeds_knots.append(speed_knots)

    above = [s for s in speeds_knots if s > SEUIL_NOEUDS]
    if not above:
        return 0.0
    return round(sum(above) / len(above), 2)


def main():
    gc = get_gspread_client()
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.sheet1

    headers = ws.row_values(1)
    gpx_col = headers.index('GPX') + 1
    vmoy_col = headers.index('Vmoy') + 1

    all_data = ws.get_all_values()
    rows_to_update = []

    for i, row in enumerate(all_data[1:], start=2):  # start=2 car row 1 = headers
        gpx_val = row[gpx_col - 1] if len(row) >= gpx_col else ''
        vmoy_val = row[vmoy_col - 1] if len(row) >= vmoy_col else ''

        if gpx_val.strip() and not vmoy_val.strip():
            rows_to_update.append((i, gpx_val.strip()))

    print(f"{len(rows_to_update)} lignes à traiter")

    for idx, (row_num, gpx_url) in enumerate(rows_to_update):
        print(f"[{idx + 1}/{len(rows_to_update)}] Ligne {row_num}: {gpx_url}")
        vmoy = calcul_vmoy(gpx_url)
        if vmoy is not None:
            print(f"  Vmoy = {vmoy} noeuds")
            ws.update_cell(row_num, vmoy_col, vmoy)
            # Pause pour respecter les quotas API Google (60 req/min)
            time.sleep(1.5)
        else:
            print("  Skipped")

    print("Terminé !")


if __name__ == '__main__':
    main()
