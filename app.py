import re
import dash
from dash import dcc
from dash import html
from dash import dash_table
import pandas as pd
import requests
import plotly.express as px
from dash.dependencies import Input, Output, State
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy import Point
import folium
import pytz
from pyroutelib3 import Router

adresse_depart='14 rue bayard, 31000, Toulouse'

###################################################  PARKINGS #####################################################


# Récupérer les données des parkings indigo et TM via un fichier csv
link_csv_parking_indigo = "https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/parcs-de-stationnement/exports/csv?lang=fr&timezone=Europe%2FBerlin&use_labels=true&delimiter=%3B"
df_parking_indigo = pd.read_csv(link_csv_parking_indigo,sep=";")

# Garder uniquement certaines colonnes
colonne_a_garder = ['xlong', 'ylat', 'nom', 'nb_places', 'adresse', 'type_ouvrage', 'gestionnaire', 'gratuit', 'nb_voitures', 'nb_velo']
df_parking_indigo_nettoye = df_parking_indigo.loc[:, colonne_a_garder]

# Remplacer les données de la colonne gratuit
df_parking_indigo_nettoye['gratuit'] = df_parking_indigo_nettoye['gratuit'].replace({'F': 'non', 'T': 'oui'})

# Concaténer la latitude avec la longitude
df_parking_indigo_nettoye['lat&lon'] = df_parking_indigo_nettoye.apply(lambda x: f"{x['ylat']}, {x['xlong']}", axis=1)

# Rajout de la colonne "Relais ?"
df_parking_indigo_nettoye['relais ?'] = 'non'


# Récupérer les données des parkings relais via l'API de Toulouse Métropole
link_parking_relais = "https://data.toulouse-metropole.fr/api/records/1.0/search/?dataset=parkings-relais&q=&facet=commune"
response = requests.get(link_parking_relais)
data = response.json()
df_parking_relais = pd.DataFrame(data['records'])

# Nous récupérons les données de la colonne 'fields'
df_parking_relais_nettoye = pd.json_normalize(df_parking_relais['fields'])
df_parking_relais_nettoye = df_parking_relais_nettoye[['nom', 'nb_places', 'xlong', 'ylat', 'adresse','type_ouvrage', 'gratuit', 'nb_voitures', 'nb_velo', 'geo_point_2d']]

# Remplacer les valeurs de la colonne gratuit
df_parking_relais_nettoye['gratuit'] = df_parking_relais_nettoye['gratuit'].replace('F', 'non').replace('T', 'oui')
# Renommer la colonne geo_point_2d
df_parking_relais_nettoye = df_parking_relais_nettoye.rename(columns={'geo_point_2d':'lat&lon'})
# Passer la colonne lat&lon en string et retirer premier et dernier crochet de la colonne lat&lon
df_parking_relais_nettoye['lat&lon'] = df_parking_relais_nettoye['lat&lon'].astype(str).apply(lambda x : x[1:]).apply(lambda x : x[:-1])

# Ajout de la colonne "Relais"
df_parking_relais_nettoye['relais ?'] = 'oui'

# Rajouter une colonne qui précise le gestionnaire des parkings relais
df_parking_relais_nettoye['gestionnaire'] = 'Tisseo'

# Concaténer les deux dataframes
df_parking_global = pd.concat([df_parking_relais_nettoye, df_parking_indigo_nettoye], ignore_index=True)


################################################################ VÉLOS ##############################################################

# IMPORTER LES DONNEES DE L'API VELOS DE TOULOUSE ET LES STOCKER DANS UN DF

lien_information = "https://transport.data.gouv.fr/gbfs/toulouse/station_information.json"
lien_status = "https://transport.data.gouv.fr/gbfs/toulouse/station_status.json"

# Charger le fichier JSON en tant que DataFrame
df_info = pd.read_json(lien_information)
df_statut = pd.read_json(lien_status)

# Affichage de l'ensemble des données de la colonne Data pour récupérer les stations
stations_list = df_info['data'][0]

# Convertir la liste de dictionnaires en DataFrame
df_stations = pd.DataFrame(stations_list)

# Affichage de l'ensemble des données de la colonne Data pour récupérer les disponibilités
statut_list = df_statut['data'][0]

# Convertir la liste de dictionnaires en DataFrame
df_disponibilites = pd.DataFrame(statut_list)

# Convertir la colonne last_reported en objets datetime au fuseau horaire UTC
df_disponibilites['last_reported'] = pd.to_datetime(df_disponibilites['last_reported'], unit='s').dt.tz_localize('UTC')

# Convertir la colonne last_reported en heure locale Paris
paris_tz = pytz.timezone('Europe/Paris')
df_disponibilites['last_reported'] = df_disponibilites['last_reported'].dt.tz_convert(paris_tz)

# Formater la colonne last_reported en une chaîne de caractères sans indication de fuseau horaire
df_disponibilites['last_reported'] = df_disponibilites['last_reported'].dt.strftime('%d/%m/%Y %H:%M:%S')

# Merge des deux DF stations et disponibilités
df_velo_temps_reel = pd.merge(df_stations,
        df_disponibilites,
        how="left",
        left_on='station_id',
        right_on='station_id')

# Supprimer le code station de la colonne 'name' => démarrer au 8ème caractère
df_velo_temps_reel['name'] = df_velo_temps_reel['name'].apply(lambda x : x[8:])

# Créer une colonne adresse complete pour avoir l'adresse et le nom de la ville (utile pour la suite)
df_velo_temps_reel['adresse_complete'] = df_velo_temps_reel['address']+", , Toulouse"

# concatener la latitude avec la longitude
df_velo_temps_reel['lat&lon'] = df_velo_temps_reel.apply(lambda x: f"{x['lat']}, {x['lon']}", axis=1)

# POUR LE RESTE
adresse_du_parking_choisi = 'Place Jeanne d\'arc, 31000 Toulouse'
# Adresse de référence
address_reference = adresse_du_parking_choisi

# Liste des coordonnées à comparer
coordinates_to_compare = df_velo_temps_reel['lat&lon']

# Initialisation du géocodeur
geolocator = Nominatim(user_agent="my_app")

# Géocodage de l'adresse de référence
location_reference = geolocator.geocode(address_reference)

# Extraction des coordonnées de l'adresse de référence
coordinates_reference = (location_reference.latitude, location_reference.longitude)

# Initialisation des variables pour le calcul de la distance minimale
min_distance = float('inf')
closest_address = None

# Parcours des adresses à comparer
for coordinate_to_compare in coordinates_to_compare:
    distance = geodesic(coordinates_reference, coordinate_to_compare).meters

    # Vérification si la distance est plus petite que la distance minimale actuelle
    if distance < min_distance:
        min_distance = distance
        closest_address = coordinate_to_compare

# Affichage des éléments suivants :
list_1 = []
list_2 = []
list_3 = []
list_4 = []
list_5 = []
Station_velo_la_plus_proche = df_velo_temps_reel['name'][df_velo_temps_reel['lat&lon'] == (closest_address)].item()
list_1.append(Station_velo_la_plus_proche)
nb_velos_dispos = df_velo_temps_reel['num_bikes_available'][df_velo_temps_reel['lat&lon'] == (closest_address)].item()
list_2.append(nb_velos_dispos)
nb_bornes_dispos = df_velo_temps_reel['num_docks_available'][df_velo_temps_reel['lat&lon'] == (closest_address)].item()
list_3.append(nb_bornes_dispos)
adresse_de_la_station = df_velo_temps_reel['address'][df_velo_temps_reel['lat&lon'] == (closest_address)].item()
list_4.append(adresse_de_la_station)
list_5.append(min_distance)


df_station_velo_plus_proche = pd.concat([pd.Series(list_1), pd.Series(list_2), pd.Series(list_3), pd.Series(list_4),pd.Series(list_5)], axis=1)
df_station_velo_plus_proche = df_station_velo_plus_proche.rename(columns = {0 : 'Nom station', 1 : 'Nombre de vélos disponibles', 2 : 'Nombre de bornes disponibles', 3 : 'Adresse' , 4 : 'Distance'})
df_station_velo_plus_proche['Distance'] = df_station_velo_plus_proche['Distance'].astype(int)


###################################################  CRÉATION DU DF DES 5 PARKINGS LES PLUS PROCHES #####################################################

# Liste des coordonnées à comparer
coordinates_to_compare = df_parking_global['lat&lon']

# Initialisation du géocodeur
geolocator = Nominatim(user_agent="my_app")

# Géocodage de l'adresse renseignée par l'utilisateur
location_reference = geolocator.geocode(adresse_depart)

# Vérification des coordonnées géographiques
if location_reference is not None:

    # Extraction des coordonnées de l'adresse de référence
    coordinates_reference = (location_reference.latitude, location_reference.longitude)

    # Initialisation du dictionnaire pour stocker les distances et les adresses
    distances = {}

    # Parcours des adresses à comparer
    for coordinate_to_compare in coordinates_to_compare:
        distance = geodesic(coordinates_reference, coordinate_to_compare).meters

        # Stockage de la distance et de l'adresse dans le dictionnaire
        distances[coordinate_to_compare] = distance

    # Tri du dictionnaire par distance et récupération des 5 Parkings les plus proches
    closest_parkings = sorted(distances, key=distances.get)[:5]

    if closest_parkings:
        # Création du DataFrame pour stocker les données des 5 parkings les plus proches
        df_5_parkings_proches = pd.DataFrame(columns=['Parkings', 'Type de parking', 'Gratuit', 'Nb_places_totales', 'Adresse', 'Distance(m)', 'lat', 'lon'])

        # Parcours des parkings les plus proches
        for parking in closest_parkings:
            # Récupération des données du parking
            parking_data = df_parking_global[df_parking_global['lat&lon'] == parking]

            # Récupération des valeurs spécifiques
            nom = parking_data['nom'].values[0]
            type_parking = parking_data['type_ouvrage'].values[0]
            gratuit = parking_data['gratuit'].values[0]
            nb_places = parking_data['nb_voitures'].values[0]
            adresse = parking_data['adresse'].values[0]
            lat = parking_data['ylat'].values[0]
            lon = parking_data['xlong'].values[0]

            # Affichage de la distance
            distance = distances[parking]
            # print("{:.0f} mètres".format(distance))

            # Ajout du parking au DataFrame
            df_5_parkings_proches = pd.concat([df_5_parkings_proches, pd.DataFrame({
                'Parkings': [nom],
                'Type de parking': [type_parking],
                'Gratuit': [gratuit],
                'Nb_places_totales': [nb_places],
                'Adresse': [adresse],
                'lat': [lat],
                'lon': [lon],
                'Distance(m)': [round(distance)]
            })], ignore_index=True)


        # Stocker les 5 parkings les plus proches dans une liste pour créer une menu déroulant
        menu_deroulant_parkings = df_parking_global[df_parking_global['lat&lon'].isin(closest_parkings)]['nom'].tolist()
        # print("Parkings les plus proches :", nom_parking)


# Nous supprimons les deux colonnes lat & lon 
df_5_parkings_proches_dash = df_5_parkings_proches.drop(columns=['lon', 'lat'], axis=1)

# Faire démarrer l'indexation à 1 au lieu de 0   
df_5_parkings_proches_dash = df_5_parkings_proches_dash.reset_index(drop=True)
df_5_parkings_proches_dash.index = df_5_parkings_proches_dash.index + 1



##################################################### CRÉATION DU DF DES 5 STATIONS LES PLUS PROCHE #####################################################

service_name = 'stop_areas'
format_type = 'json'
parameters = 'displayCoordXY'
api_key = '15cbfcdf-76bb-4136-980a-6dc1f1d96cd5'

url_avec_parametre = f"https://api.tisseo.fr/v2/{service_name}.{format_type}?displayLines=1&displayCoordXY=1&key={api_key}"
response = requests.get(url_avec_parametre)
data = response.json()

df_stop_areas_coordonnees = pd.DataFrame(data)
df_stop_areas_list_coordonnees = df_stop_areas_coordonnees['stopAreas'].values[0]
df_arrets_coordonnees = pd.DataFrame(df_stop_areas_list_coordonnees)

# MODIFIER NOTRE DATAFRAME

# Suppression des dix premiers caractères de la colonne "id"
df_arrets_coordonnees['id'] = df_arrets_coordonnees['id'].apply(lambda x : x[10:])
# renommage des colonnes du df
df_arrets_coordonnees=df_arrets_coordonnees.rename(columns={"id": "id_stop_area"})
df_arrets_coordonnees=df_arrets_coordonnees.rename(columns={"x": "lon"})
df_arrets_coordonnees=df_arrets_coordonnees.rename(columns={"y": "lat"})

df_arrets_coordonnees['index_arrets'] = df_arrets_coordonnees.index
df_line = df_arrets_coordonnees.explode('line')
df_line = pd.concat([df_line.drop('line', axis=1), df_line['line'].apply(pd.Series)], axis=1)
df_line['index_arrets'] = df_arrets_coordonnees['index_arrets']
df_line_propre = df_line.drop(columns = ['index_arrets','bgXmlColor', 'color', 'fgXmlColor', 'network', 'reservationMandatory', 'id' ])
df_line_propre['transportmode'] = df_line_propre['transportMode'].apply(lambda x: x['name'])

df_line_final = df_line_propre.drop(columns = ['transportMode'])
df_line_final = df_line_final.reset_index(drop=True)
df_line_final.columns = ['arret' if name == 'name' and index == 2 else name for index, name in enumerate(df_line_final.columns)]
df_line_final.rename(columns = {"name":"line"}, inplace=True)

# concatener la latitude avec la longitude
df_line_final['lat&lon'] = df_line_final.apply(lambda x: f"{x['lat']}, {x['lon']}", axis=1)

# Supprimer les lignes en doublons pour avoir une ligne par arrêt : garder les colonnes arrêts, id_stop_area, lat&lon
df_stop_area_unique = df_line_final.drop_duplicates(subset = "id_stop_area")

# Garder uniquement les colonnes souhaitées
df_stop_area_unique = df_stop_area_unique[['cityName', 'id_stop_area', 'arret',  'lat&lon' ]]

##################################################### AFFICHER LES 5 STATIONS LES PLUS PROCHES DU PARKING #####################################################

# Adresse de référence
address_reference = df_5_parkings_proches_dash['Adresse'][1]

# Liste des coordonnées à comparer
coordinates_to_compare = df_stop_area_unique['lat&lon']

# Initialisation du géocodeur
geolocator = Nominatim(user_agent="my_app")

# Géocodage de l'adresse de référence
location_reference = geolocator.geocode(address_reference)


# Vérification des coordonnées géographiques
if location_reference is not None:

   # Extraction des coordonnées de l'adresse de référence
   coordinates_reference = (location_reference.latitude, location_reference.longitude)

   # Initialisation du dictionnaire pour stocker les distances et les adresses
   distances = {}

   # Parcours des adresses à comparer
   for coordinate_to_compare in coordinates_to_compare:
      distance = geodesic(coordinates_reference, coordinate_to_compare).meters

      # Stockage de la distance et de l'adresse dans le dictionnaire
      distances[coordinate_to_compare] = distance

   # Tri du dictionnaire par distance et récupération des 5 arrêts les plus proches
   closest_stations = sorted(distances, key=distances.get)[:5]

   if closest_stations :

      # Affichage des éléments suivants :

      closest_stops = df_stop_area_unique[df_stop_area_unique['lat&lon'].isin(closest_stations)]['arret'].tolist()
      closest_stops_id = df_stop_area_unique[df_stop_area_unique['lat&lon'].isin(closest_stations)]['id_stop_area'].tolist()
      LatLon_closest_stops = df_stop_area_unique[df_stop_area_unique['lat&lon'].isin(closest_stations)]['lat&lon'].tolist()
      print("Arrêts les plus proches :", closest_stops)
      print("id les plus proches :", closest_stops_id)
      print("lat&lon les plus proches :", LatLon_closest_stops)

      print("Distances :")
      list_distance = []
      for station in closest_stations:
          distance = distances[station]
          print("{:.0f} mètres".format(distance))
          list_distance.append(distances[station])  

   else:
      print("Aucune adresse trouvée parmi la liste")
else:
    print("Adresse de référence introuvable")

# Création du dataframe des arrêts les plus proches

df_arrets_plus_proche = pd.concat([pd.Series(closest_stops), pd.Series(closest_stops_id), pd.Series(list_distance), pd.Series(LatLon_closest_stops)], axis=1)
df_arrets_plus_proche = df_arrets_plus_proche.rename(columns = {0 : 'Nom station', 1 : 'ID de la station', 2 : 'Distance en mètres', 3 : 'Coordonnées GPS'})
df_arrets_plus_proche['Distance en mètres'] = df_arrets_plus_proche['Distance en mètres'].astype(int)
df_arrets_plus_proche[['lat', 'lon']] = df_arrets_plus_proche['Coordonnées GPS'].str.split(', ', expand=True).astype(float)



###################################################  CRÉATION DES CARTES #####################################################

# Créer une carte folium avec les 5 parkings de notre DF df_5_parkings_proches
carte_5_parkings_les_plus_proches = folium.Map(location=[lat, lon], zoom_start=15)

for i in range(5):
    lat_parking = df_5_parkings_proches['lat'][i]
    lon_parking = df_5_parkings_proches['lon'][i]
    nom_parking = f'PARKING_{i + 1}'

    folium.Marker(location=[lat_parking, lon_parking], popup="<i>Nom du parking :\n</i>"+df_5_parkings_proches['Parkings'][i]).add_to(carte_5_parkings_les_plus_proches)

carte_5_parkings_les_plus_proches.save('carte_5_parkings_les_plus_proches.html')


# Créer une carte folium avec les 5 stations de notre DF df_arrets_plus_proche
carte_tisseo = folium.Map(location=[lat, lon], zoom_start=15)

for i in range(5):
    lat_station = df_arrets_plus_proche['lat'][i]
    lon_station = df_arrets_plus_proche['lon'][i]
    nom_station = f'STATION_{i + 1}'

    folium.Marker(location=[lat_station, lon_station], popup="<i>Nom de la station :\n</i>"+df_arrets_plus_proche['Nom station'][i]).add_to(carte_tisseo)

carte_tisseo.save('carte_tisseo.html')



######################################## AFFICHER LA BORNE LA PLUS PROCHE ET LE PARCOURS POUR ALLER A LA BORNE LA PLUS PROCHE DU PARKING CHOISI ########################################

# Création de l'objet Router
router = Router("foot")

# EN AMONT NOUS AVONS RECUPERE LE PARKING CHOISI : ici pour l'exemple
nom_du_parking_choisi = 'Jeanne d\'Arc'

# Sélection des noms de départ et d'arrivée (exemple)
depart_name = nom_du_parking_choisi
arrivee_name = Station_velo_la_plus_proche

# Rechercher les lignes correspondant aux noms de départ et d'arrivée dans le DataFrame (df)
#depart_row = df_parking_global[df_parking_global['Parkings'] == depart_name].iloc[0]
arrivee_row = df_velo_temps_reel[df_velo_temps_reel['name'] == arrivee_name].iloc[0]

# Récupérer les coordonnées latitude/longitude du point de départ :
#depart_lat = depart_row['ylat']
#depart_lon = depart_row['xlong']

# POUR L'EXEMPLE ici et ne pas être obligé de recharger tout le DF parking global sur l'autre notebook
depart_lat = df_5_parkings_proches['lat'][0]
depart_lon = df_5_parkings_proches['lon'][0]

# Récupérer les coordonnées latitude/longitude du point d'arrivée
arrivee_lat = arrivee_row['lat']
arrivee_lon = arrivee_row['lon']

# Rechercher les nœuds de départ et d'arrivée
depart = router.findNode(depart_lat, depart_lon)
arrivee = router.findNode(arrivee_lat, arrivee_lon)

# Calculer l'itinéraire
status, itineraire = router.doRoute(depart, arrivee)

if status == 'success':
    # Convertir les coordonnées des nœuds en latitude/longitude
    itineraire_coordonnees = [router.nodeLatLon(node) for node in itineraire]

    # Créer la carte avec le point de départ, le point d'arrivée et l'itinéraire
    carte = folium.Map(location=[depart_lat, depart_lon], zoom_start=13)

    # Ajouter le marqueur pour le point de départ
    folium.Marker([depart_lat, depart_lon], popup="Point de départ").add_to(carte)

    # Ajouter le marqueur pour le point d'arrivée
    folium.Marker([arrivee_lat, arrivee_lon], popup="Point d'arrivée").add_to(carte)

    # Ajouter le tracé de l'itinéraire à la carte
    folium.PolyLine(
        locations=itineraire_coordonnees,
        color="blue",
        weight=2.5,
        opacity=1
    ).add_to(carte)

    # Afficher la carte dans la cellule Colab
    carte.save('carte_itineraire.html')
else:
    print("Impossible de trouver un itinéraire pour les points spécifiés.")




############################################### Création de l'application Dash ###############################################
app = dash.Dash(__name__, suppress_callback_exceptions=True, meta_tags=[{'name': 'viewport','content': 'width=device-width, initial-scale=1.0'}]) # permet a notre app d'etre responsive, s'adapter a lecran utilise)
server = app.server

######################################### Styles CSS personnalisés #########################################
styles = {
    'backgroundColor': '#a5282b',
    'color': '#ffc12b',
    'textAlign': 'center',
    'padding': '20px'
}

page_style = {
        'backgroundColor': '#a5282b',
        'width': '100%',
        'height': '100%',  # 'vh' signifie viewport height (hauteur de la fenêtre du navigateur)
        'display': 'flex',  # Utiliser flexbox pour aligner et centrer le contenu
        'flexDirection': 'column',  # Aligner le contenu en colonne
        'alignItems': 'center',  # Centrer horizontalement le contenu
    }

active_tab_style = {
    'backgroundColor': '#ffc12b',
    'color': '#a5282b',
    'fontWeight': 'bold'
}

inactive_tab_style = {
    'backgroundColor': '#a5282b',
    'color': '#ffc12b',
    'fontWeight': 'bold'
}

line_style = {
    'width': '100%',
    'borderTop': '1px #ffc12b solid',
    'margin': '10px 0'
}

input_style = {
    'width': '60%', 'margin': '10px'
    }

button_style = {
            'margin': '10px auto',
            'backgroundColor': '#ffc12b',
            'color': '#a5282b',
            'border': 'none',
            'padding': '10px 20px',
            'font-size': '18px',
            'cursor': 'pointer'
        }


###################################################  LAYOUT #####################################################

app.layout =html.Div(style=page_style, children=[html.H1(children="Transports Toulouse VCA", style=styles),
html.Hr(style=line_style),
html.H3(children='Entrez votre adresse de départ et cliquez sur le bouton pour trouver le parking le plus proche.', style=styles),
html.Div(style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center'},children=[
    html.Label("Numéro:", style=styles),dcc.Input(id='numero',placeholder='Entrez le numéro',type='text',style=input_style),
    html.Label("Voie:", style=styles),dcc.Input(id='voie', placeholder='Entrez la voie',type='text',style=input_style),
    html.Label("Code postal:", style=styles),dcc.Input(id='code-postal',placeholder='Entrez le code postal',type='number',value='31000',style=input_style),
    html.Label("Ville:", style=styles),dcc.Input(id='ville',placeholder='Entrez la ville',type='text',value='Toulouse',style=input_style)]),
dcc.Input(id="adresse-depart", type="text", disabled=True),
html.Button('Rechercher',id='submit-button',style=button_style),
html.Div([html.Iframe(id='carte_5_parkings_les_plus_proches', srcDoc=open('carte_5_parkings_les_plus_proches.html', 'r').read(),width='450', height='450')]),
html.Div([html.Hr(style={'width': '100%', 'margin': '5px 0'})]),             
html.Div([dash_table.DataTable(id='df_5_parkings_proches_dash', data=df_5_parkings_proches_dash.to_dict('records'),
                        style_data={'color': '#ffc12b','backgroundColor': '#a5282b', 'border': '1px solid #ffc12b'},
                        style_cell={'textAlign': 'center'})]),
html.Hr(style=line_style),
html.H3(children='Sélectionnez le parking dans lequel vous souhaitez vous garer.', style=styles),
dcc.Dropdown(menu_deroulant_parkings, id='parking-dropdown', value='Choisissez votre parking', style = {'width': '60%', 'margin': '10px'}),
html.Button("J'ai choisi mon parking", id='parking-button', style=button_style),
html.Div(style={'flex': '1'}, children=[
    html.H2("Team vélo ou Team Tisséo ?", style=styles),
    dcc.Tabs(id="tabs", value='tab-1', children=[
    dcc.Tab(label='Team Vélo', value='tab-0', style=inactive_tab_style,
        selected_style=active_tab_style),
    dcc.Tab(label='Team Tisséo', value='tab-1', style=inactive_tab_style,
        selected_style=active_tab_style),
]),
html.Div(id='tabs-content')
])
])



###############################################  CALLBACKS ET FONCTIONS #####################################################

@app.callback(
    Output('adresse-depart', 'value'),
    [Input('numero', 'value'),
     Input('voie', 'value'),
     Input('code-postal', 'value'),
     Input('ville', 'value')]
)

def update_adresse_depart(numero, voie, code_postal="31000", ville="Toulouse"):
    adresse_depart = f"{numero} {voie}, {code_postal} {ville}"
    return adresse_depart


@app.callback(
    Output('tabs-content', 'children'),
    [Input('tabs', 'value'),
     Input('parking-button', 'n_clicks')]
)

def render_content(tab, n_clicks):
    if tab == 'tab-0':
        if df_station_velo_plus_proche is not None:
            return html.Div(style={'justifyContent': 'center', 'alignItems': 'center'}, children=[
        html.Div([html.Iframe(id='carte_itineraire', srcDoc=open('carte_itineraire.html', 'r').read(),style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center'},
                               width='450', height='450')]),
        html.Div([html.Hr(style={'width': '100%', 'margin': '5px 0'})]),             
        html.Div([dash_table.DataTable(id='df_station_velo_plus_proche', data=df_station_velo_plus_proche.to_dict('records'),
                                   style_data={'color': '#ffc12b','backgroundColor': '#a5282b', 'border': '1px solid #ffc12b'},
                                   style_cell={'textAlign': 'center'})])]),
        
            
    elif tab == 'tab-1':
        if df_arrets_plus_proche is not None:
            return html.Div(style={'justifyContent': 'center', 'alignItems': 'center'}, children=[
        html.Div([html.Iframe(id='carte_tisseo', srcDoc=open('carte_tisseo.html', 'r').read(),style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center'},
                               width='450', height='450')]),
        html.Div([html.Hr(style={'width': '100%', 'margin': '5px 0'})]),             
        html.Div([dash_table.DataTable(id='df_arrets_plus_proche', data=df_arrets_plus_proche.to_dict('records'),
                                   style_data={'color': '#ffc12b','backgroundColor': '#a5282b', 'border': '1px solid #ffc12b'},
                                   style_cell={'textAlign': 'center'})])]),
        
    return html.Div()


if __name__ == '__main__':
    app.run_server(debug=True)
