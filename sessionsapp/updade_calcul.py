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


def calcul_vitesses(gpx_url):
    """Télécharge un GPX et retourne (vmoy, vmax, v100, distance_km).

    Algorithme aligné sur GPSar / GPS-Results / GP3S :
    - Vmax  : meilleure vitesse sur fenêtre glissante de 2 s
              (distance cumulée le long du parcours / temps)
    - V100  : meilleure vitesse sur un run >= 100 m de parcours cumulé
    - Vmoy  : moyenne des vitesses (fenêtres 2 s) au-dessus du seuil
    - Distance : distance totale parcourue (somme point à point)
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

    # Dédupliquer les points avec le même timestamp.
    # Certains GPS enregistrent 2 positions à la même seconde,
    # ce qui gonfle les distances et donc les vitesses calculées.
    for track in gpx.tracks:
        for segment in track.segments:
            deduped = []
            for pt in segment.points:
                if deduped and pt.time and deduped[-1].time == pt.time:
                    continue
                deduped.append(pt)
            segment.points = deduped

    all_speeds_2s = []          # échantillons de vitesse sur fenêtres 2 s
    vmax = 0.0
    max_v100 = 0.0
    total_distance = 0.0

    MS_TO_KNOTS = 1.94384
    ACCELERATION_MAX = 4.0     # m/s² — accélération/décélération max réaliste
    BEARING_THRESHOLD = 90     # degrés — changement de cap max à haute vitesse

    # Seuil de glitch adaptatif : basé sur le P95 des vitesses instantanées.
    # Un spike GPS dépasse largement les vitesses normales de la session.
    raw_speeds_kn = []
    for track in gpx.tracks:
        for segment in track.segments:
            pts = segment.points
            for i in range(len(pts) - 1):
                p1, p2 = pts[i], pts[i + 1]
                if p1.time and p2.time:
                    dt = (p2.time - p1.time).total_seconds()
                    if 0 < dt < 60:
                        spd = (p1.distance_2d(p2) / dt) * MS_TO_KNOTS
                        if spd > 1.0:
                            raw_speeds_kn.append(spd)
    raw_speeds_kn.sort()
    p95 = raw_speeds_kn[int(len(raw_speeds_kn) * 0.95)] if raw_speeds_kn else 30
    FILTRE_VITESSE_KN = max(p95 * 1.5, 35)

    def bearing(p1, p2):
        """Cap en degrés de p1 vers p2."""
        lat1 = math.radians(p1.latitude)
        lat2 = math.radians(p2.latitude)
        dlon = math.radians(p2.longitude - p1.longitude)
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        return math.degrees(math.atan2(x, y)) % 360

    def bearing_diff(b1, b2):
        """Différence angulaire entre 2 caps (0-180)."""
        d = abs(b1 - b2) % 360
        return d if d <= 180 else 360 - d

    for track in gpx.tracks:
        for segment in track.segments:
            points = segment.points
            if len(points) < 2:
                continue

            # ── Étape 1 : filtrage des glitchs GPS ──────────────────────
            # Pré-calcul vitesses et caps entre points consécutifs
            inst_speeds = []   # m/s, None si invalide
            bearings = []      # degrés, None si invalide
            for i in range(len(points) - 1):
                p1, p2 = points[i], points[i + 1]
                if p1.time and p2.time:
                    dt = (p2.time - p1.time).total_seconds()
                    dist = p1.distance_2d(p2)
                    if 0 < dt < 60 and dist > 0.5:
                        inst_speeds.append(dist / dt)
                        bearings.append(bearing(p1, p2))
                    elif 0 < dt < 60:
                        inst_speeds.append(dist / dt)
                        bearings.append(None)
                    else:
                        inst_speeds.append(None)
                        bearings.append(None)
                else:
                    inst_speeds.append(None)
                    bearings.append(None)

            valid_segments = []
            current_seg = []

            for i in range(len(points)):
                if not points[i].time:
                    if len(current_seg) >= 2:
                        valid_segments.append(current_seg)
                    current_seg = []
                    continue

                is_glitch = False

                # Vitesse vers les voisins > seuil
                spd_prev = (inst_speeds[i - 1] * MS_TO_KNOTS) if (i > 0 and inst_speeds[i - 1] is not None) else 0
                spd_next = (inst_speeds[i] * MS_TO_KNOTS) if (i < len(inst_speeds) and inst_speeds[i] is not None) else 0
                if spd_prev > FILTRE_VITESSE_KN or spd_next > FILTRE_VITESSE_KN:
                    is_glitch = True

                # Accélération aberrante
                if (i > 0 and i < len(inst_speeds)
                        and inst_speeds[i - 1] is not None and inst_speeds[i] is not None):
                    if i + 1 < len(points) and points[i + 1].time:
                        dt_accel = (points[i + 1].time - points[i - 1].time).total_seconds()
                        if 0 < dt_accel < 30:
                            accel = abs(inst_speeds[i] - inst_speeds[i - 1]) / dt_accel
                            if accel > ACCELERATION_MAX:
                                is_glitch = True

                # Changement de cap brutal à haute vitesse = glitch GPS
                # Un vrai virement prend plusieurs secondes et ralentit ;
                # un saut GPS fait un aller-retour instantané à pleine vitesse.
                if (i > 0 and i < len(bearings)
                        and bearings[i - 1] is not None and bearings[i] is not None):
                    min_spd = min(spd_prev, spd_next)
                    if min_spd > 10 and bearing_diff(bearings[i - 1], bearings[i]) > BEARING_THRESHOLD:
                        is_glitch = True

                if not is_glitch:
                    current_seg.append(points[i])
                else:
                    if len(current_seg) >= 2:
                        valid_segments.append(current_seg)
                    current_seg = []

            if len(current_seg) >= 2:
                valid_segments.append(current_seg)

            if not valid_segments:
                continue

            # ── Étape 2 : métriques sur segments valides ────────────────
            for seg_pts in valid_segments:
                n = len(seg_pts)
                if n < 2:
                    continue

                # Pré-calcul : distances cumulées le long du parcours et temps relatifs
                cum_dist = [0.0] * n
                rel_time = [0.0] * n
                t0 = seg_pts[0].time
                for i in range(1, n):
                    cum_dist[i] = cum_dist[i - 1] + seg_pts[i - 1].distance_2d(seg_pts[i])
                    rel_time[i] = (seg_pts[i].time - t0).total_seconds()

                total_distance += cum_dist[-1]

                # ── Vmax : meilleure vitesse sur fenêtre de 2 s (GP3S standard) ──
                # Distance en ligne droite (déplacement réel) pour éviter
                # que les zigzags GPS gonflent la vitesse via la distance cumulée.
                # Filtre médian (fenêtre 5) + validation vitesse soutenue (~20s).
                speeds_2s = []
                for i in range(n - 1):
                    best_spd = 0.0
                    for j in range(i + 1, n):
                        dt = rel_time[j] - rel_time[i]
                        if dt > 6.0:
                            break
                        if dt >= 2.0:
                            straight_dist = seg_pts[i].distance_2d(seg_pts[j])
                            spd = (straight_dist / dt) * MS_TO_KNOTS
                            if spd > best_spd:
                                best_spd = spd
                    speeds_2s.append(best_spd)

                # Filtre médian glissant (fenêtre de 5)
                smoothed = []
                for i in range(len(speeds_2s)):
                    lo = max(0, i - 2)
                    hi = min(len(speeds_2s), i + 3)
                    window = sorted(speeds_2s[lo:hi])
                    smoothed.append(window[len(window) // 2])

                # Validation vitesse soutenue (contexte ±10 points ~20s)
                for i in range(len(smoothed)):
                    if smoothed[i] <= vmax or smoothed[i] > FILTRE_VITESSE_KN:
                        continue
                    lo = max(0, i - 10)
                    hi = min(len(smoothed), i + 11)
                    ctx_avg = sum(smoothed[lo:hi]) / (hi - lo)
                    if ctx_avg >= smoothed[i] * 0.7:
                        vmax = smoothed[i]

                # ── Vmoy : un échantillon par point (fenêtre 2 s, distance ligne droite) ──
                j_vmoy = 1
                for i in range(n - 1):
                    if j_vmoy <= i:
                        j_vmoy = i + 1
                    while j_vmoy < n - 1 and (rel_time[j_vmoy] - rel_time[i]) < 2.0:
                        j_vmoy += 1
                    if j_vmoy >= n:
                        break
                    dt = rel_time[j_vmoy] - rel_time[i]
                    if dt >= 2.0:
                        straight_dist = seg_pts[i].distance_2d(seg_pts[j_vmoy])
                        speed_kn = (straight_dist / dt) * MS_TO_KNOTS
                        if speed_kn <= FILTRE_VITESSE_KN:
                            all_speeds_2s.append(speed_kn)

                # ── V100 : meilleure vitesse sur run >= 100 m ──
                # Distance cumulée pour détecter les runs de 100 m,
                # distance ligne droite pour calculer la vitesse.
                j_v100 = 1
                for i in range(n - 1):
                    if j_v100 <= i:
                        j_v100 = i + 1
                    while j_v100 < n - 1 and (cum_dist[j_v100] - cum_dist[i]) < 100.0:
                        j_v100 += 1
                    if j_v100 >= n:
                        break
                    if cum_dist[j_v100] - cum_dist[i] >= 100.0:
                        dt = rel_time[j_v100] - rel_time[i]
                        if dt > 0:
                            straight_dist = seg_pts[i].distance_2d(seg_pts[j_v100])
                            speed_kn = (straight_dist / dt) * MS_TO_KNOTS
                            if speed_kn <= FILTRE_VITESSE_KN and speed_kn > max_v100:
                                max_v100 = speed_kn

    above = [s for s in all_speeds_2s if s > SEUIL_NOEUDS]
    vmoy = round(sum(above) / len(above), 2) if above else 0.0
    vmax = round(vmax, 2)
    v100 = round(max_v100, 2)
    distance_km = round(total_distance / 1000, 2)

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
