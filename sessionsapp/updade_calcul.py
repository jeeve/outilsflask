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

    for track in gpx.tracks:
        for segment in track.segments:
            points = segment.points
            if len(points) < 2:
                continue

            # 1. Filtrage strict des points aberrants (glitch GPS)
            # Un point est considéré aberrant si son déplacement depuis/vers ses voisins est > VITESSE_MAX_REALISTE
            valid_points = []
            for i in range(len(points)):
                p = points[i]
                if not p.time:
                    continue
                
                # Vérifier la vitesse par rapport au point précédent
                speed_prev = 0
                if i > 0 and points[i-1].time:
                    dt = (p.time - points[i-1].time).total_seconds()
                    if dt > 0:
                        speed_prev = (points[i-1].distance_2d(p) / dt) * 1.94384
                
                # Vérifier la vitesse par rapport au point suivant
                speed_next = 0
                if i < len(points) - 1 and points[i+1].time:
                    dt = (points[i+1].time - p.time).total_seconds()
                    if dt > 0:
                        speed_next = (p.distance_2d(points[i+1]) / dt) * 1.94384

                # Si l'une des vitesses instantanées est totalement aberrante (> 40nds), le point est un "saut"
                # Sauf si c'est le tout premier/dernier point avec un grand laps de temps
                if (speed_prev > VITESSE_MAX_REALISTE and speed_next > VITESSE_MAX_REALISTE):
                    continue # On élimine le point
                    
                # Si speed_prev est aberrante mais speed_next est normale, le point est quand même suspect
                # On va appliquer une règle stricte : un point connecté par une vitesse aberrante à son voisin immédiat de temps court est un glitch.
                is_glitch = False
                for p_adj in [points[i-1] if i>0 else None, points[i+1] if i<len(points)-1 else None]:
                    if p_adj and p_adj.time:
                        dt = abs((p.time - p_adj.time).total_seconds())
                        if dt > 0 and dt < 10: # On check seulement sur des temps courts (10 sec max)
                            if (p.distance_2d(p_adj) / dt) * 1.94384 > VITESSE_MAX_REALISTE:
                                is_glitch = True
                
                if not is_glitch:
                    valid_points.append(p)

            if len(valid_points) < 2:
                continue

            # Calcul de la distance totale du segment
            for i in range(1, len(valid_points)):
                p1, p2 = valid_points[i - 1], valid_points[i]
                total_distance += p1.distance_2d(p2)

            # 2. Calcul Vmoy (instantané)
            for i in range(1, len(valid_points)):
                p1, p2 = valid_points[i - 1], valid_points[i]
                dt = (p2.time - p1.time).total_seconds()
                if dt > 0 and dt < 5: # Seulement des segments continus
                    dist = p1.distance_2d(p2)
                    speed_knots = (dist / dt) * 1.94384
                    if speed_knots <= VITESSE_MAX_REALISTE:
                        speeds_knots.append(speed_knots)
            
            # 3. Calcul Vmax (Vitesse glissante sur ~2 secondes)
            for i in range(len(valid_points) - 1):
                p1 = valid_points[i]
                for j in range(i + 1, len(valid_points)):
                    p2 = valid_points[j]
                    dt = (p2.time - p1.time).total_seconds()
                    if dt >= 2.0:
                        if dt < 6.0: # Fenêtre valide (2s à 6s)
                            dist = p1.distance_2d(p2)
                            speed_knots = (dist / dt) * 1.94384
                            if speed_knots <= VITESSE_MAX_REALISTE and speed_knots > vmax:
                                vmax = speed_knots
                        break 
            
            # 4. Calcul V100 (meilleure vitesse sur ligne droite >= 100m)
            for i in range(len(valid_points) - 1):
                p1 = valid_points[i]
                for j in range(i + 1, len(valid_points)):
                    p2 = valid_points[j]
                    dist = p1.distance_2d(p2)
                    if dist >= 100.0:
                        dt = (p2.time - p1.time).total_seconds()
                        if dt > 0 and dt >= 5.0:  # Ajouter minimum 5 secondes pour 100m
                            speed_knots = (dist / dt) * 1.94384
                            if speed_knots <= VITESSE_MAX_REALISTE and speed_knots > max_v100:
                                max_v100 = speed_knots
                        break # Fin de la ligne droite de 100m

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
