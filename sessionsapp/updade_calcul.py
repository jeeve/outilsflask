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


def calcul_vitesses(gpx_url):
    """Télécharge un GPX et retourne (vmoy, vmax, v100)."""
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
    vmax = 0.0
    max_v100 = 0.0
    total_distance = 0.0  # Distance totale en mètres

    VITESSE_MAX_REALISTE = 30 # Max réaliste pour le windfoil: 30 noeuds
    ACCELERATION_MAX = 4.0  # Max réaliste en m/s² (accélération/décélération)

    for track in gpx.tracks:
        for segment in track.segments:
            points = segment.points
            if len(points) < 2:
                continue

            # 1. Filtrage strict des points aberrants (glitch GPS)
            # Un point est considéré aberrant si son déplacement depuis/vers ses voisins est > VITESSE_MAX_REALISTE
            # OU si l'accélération entre lui et ses voisins est > ACCELERATION_MAX
            valid_segments = []
            current_segment = []

            # Pré-calculer les vitesses instantanées entre tous les points consécutifs
            speeds = []  # speeds[i] = vitesse en m/s de points[i] vers points[i+1]
            for i in range(len(points) - 1):
                p1, p2 = points[i], points[i+1]
                if p1.time and p2.time:
                    dt = (p2.time - p1.time).total_seconds()
                    if dt > 0 and dt < 60:  # Valider que le temps est cohérent
                        dist = p1.distance_2d(p2)
                        speed_ms = dist / dt  # vitesse en m/s
                        speeds.append(speed_ms)
                    else:
                        speeds.append(None)
                else:
                    speeds.append(None)

            for i in range(len(points)):
                p = points[i]
                if not p.time:
                    if len(current_segment) >= 2:
                        valid_segments.append(current_segment)
                    current_segment = []
                    continue

                is_glitch = False

                # Vérifier les accélérations par rapport aux points adjacents
                if i > 0 and speeds[i-1] is not None and i < len(speeds) and speeds[i] is not None:
                    v1_ms = speeds[i-1]
                    if i + 1 < len(points) and points[i+1].time:
                        v2_ms = speeds[i]
                        dt_accel = (points[i+1].time - points[i-1].time).total_seconds()
                        if dt_accel > 0 and dt_accel < 30:
                            accel = abs(v2_ms - v1_ms) / dt_accel
                            if accel > ACCELERATION_MAX:
                                is_glitch = True

                speed_prev = speeds[i-1] * 1.94384 if i > 0 and speeds[i-1] is not None else 0
                speed_next = speeds[i] * 1.94384 if i < len(speeds) and speeds[i] is not None else 0

                if speed_prev > VITESSE_MAX_REALISTE or speed_next > VITESSE_MAX_REALISTE:
                    is_glitch = True

                for adj_idx in [i-1, i+1]:
                    if 0 <= adj_idx < len(points):
                        p_adj = points[adj_idx]
                        if p_adj.time:
                            dt = abs((p.time - p_adj.time).total_seconds())
                            if dt > 0 and dt < 10:
                                if (p.distance_2d(p_adj) / dt) * 1.94384 > VITESSE_MAX_REALISTE:
                                    is_glitch = True

                if not is_glitch:
                    current_segment.append(p)
                elif len(current_segment) >= 2:
                    valid_segments.append(current_segment)
                    current_segment = []

            if len(current_segment) >= 2:
                valid_segments.append(current_segment)

            if not valid_segments:
                continue

            # Calcul des distances et vitesses uniquement sur les segments valides
            for segment_points in valid_segments:
                if len(segment_points) < 2:
                    continue

                for i in range(1, len(segment_points)):
                    p1, p2 = segment_points[i - 1], segment_points[i]
                    total_distance += p1.distance_2d(p2)

                # 2. Calcul Vmoy (instantané)
                for i in range(1, len(segment_points)):
                    p1, p2 = segment_points[i - 1], segment_points[i]
                    dt = (p2.time - p1.time).total_seconds()
                    if dt > 0 and dt < 5:
                        dist = p1.distance_2d(p2)
                        speed_knots = (dist / dt) * 1.94384
                        if speed_knots <= VITESSE_MAX_REALISTE:
                            speeds_knots.append(speed_knots)

                # 3. Calcul Vmax (Vitesse glissante sur ~2 secondes)
                for i in range(len(segment_points) - 1):
                    p1 = segment_points[i]
                    for j in range(i + 1, len(segment_points)):
                        p2 = segment_points[j]
                        dt = (p2.time - p1.time).total_seconds()
                        if dt > 6.0:
                            break
                        if dt >= 2.0:
                            dist = p1.distance_2d(p2)
                            speed_knots = (dist / dt) * 1.94384
                            if speed_knots <= VITESSE_MAX_REALISTE and speed_knots > vmax:
                                vmax = speed_knots

                # 4. Calcul V100 (meilleure vitesse sur ligne droite >= 100m)
                for i in range(len(segment_points) - 1):
                    p1 = segment_points[i]
                    for j in range(i + 1, len(segment_points)):
                        p2 = segment_points[j]
                        dt = (p2.time - p1.time).total_seconds()
                        if dt > 30.0:
                            break
                        dist = p1.distance_2d(p2)
                        if dist >= 100.0 and dt >= 5.0:
                            speed_knots = (dist / dt) * 1.94384
                            if speed_knots <= VITESSE_MAX_REALISTE and speed_knots > max_v100:
                                max_v100 = speed_knots

    above = [s for s in speeds_knots if s > SEUIL_NOEUDS]
    vmoy = round(sum(above) / len(above), 2) if above else 0.0
    vmax = round(vmax, 2)
    v100 = round(max_v100, 2)
    distance_km = round(total_distance / 1000, 2)  # Convertir en km

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
