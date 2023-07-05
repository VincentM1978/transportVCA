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

adresse_depart='place arnaud bernard, 31000, Toulouse'

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

df_info = pd.read_json("https://transport.data.gouv.fr/gbfs/toulouse/station_information.json")
df_statut = pd.read_json("https://transport.data.gouv.fr/gbfs/toulouse/station_status.json")

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

# Initialiser le géocodeur une seule fois en tant que variable globale
geolocator = Nominatim(user_agent="my_app")


def load_data():
    lien_information = "https://transport.data.gouv.fr/gbfs/toulouse/station_information.json"
    lien_status = "https://transport.data.gouv.fr/gbfs/toulouse/station_status.json"

    df_info = pd.read_json(lien_information)
    df_statut = pd.read_json(lien_status)

    stations_list = df_info['data'][0]
    df_stations = pd.DataFrame(stations_list)

    statut_list = df_statut['data'][0]
    df_disponibilites = pd.DataFrame(statut_list)

    df_disponibilites['last_reported'] = pd.to_datetime(df_disponibilites['last_reported'], unit='s').dt.tz_localize('UTC')
    paris_tz = pytz.timezone('Europe/Paris')
    df_disponibilites['last_reported'] = df_disponibilites['last_reported'].dt.tz_convert(paris_tz)
    df_disponibilites['last_reported'] = df_disponibilites['last_reported'].dt.strftime('%d/%m/%Y %H:%M:%S')

    df_velo_temps_reel = pd.merge(df_stations,
        df_disponibilites,
        how="left",
        left_on='station_id',
        right_on='station_id')

    df_velo_temps_reel['name'] = df_velo_temps_reel['name'].apply(lambda x : x[8:])
    df_velo_temps_reel['adresse_complete'] = df_velo_temps_reel['address'] + ", , Toulouse"
    df_velo_temps_reel['lat&lon'] = df_velo_temps_reel.apply(lambda x: f"{x['lat']}, {x['lon']}", axis=1)

    return df_velo_temps_reel

def find_closest_station(address_reference, df_velo_temps_reel):
    geolocator = Nominatim(user_agent="my_app")
    location_reference = geolocator.geocode(address_reference)
    coordinates_reference = (location_reference.latitude, location_reference.longitude)

    min_distance = float('inf')
    closest_address = None

    for coordinate_to_compare in df_velo_temps_reel['lat&lon']:
        distance = geodesic(coordinates_reference, coordinate_to_compare).meters

        if distance < min_distance:
            min_distance = distance
            closest_address = coordinate_to_compare

    return closest_address



def get_station_info(closest_address, df_velo_temps_reel):
    Station_velo_la_plus_proche = df_velo_temps_reel['name'][df_velo_temps_reel['lat&lon'] == closest_address].item()
    nb_velos_dispos = df_velo_temps_reel['num_bikes_available'][df_velo_temps_reel['lat&lon'] == closest_address].item()
    nb_bornes_dispos = df_velo_temps_reel['num_docks_available'][df_velo_temps_reel['lat&lon'] == closest_address].item()
    adresse_de_la_station = df_velo_temps_reel['address'][df_velo_temps_reel['lat&lon'] == closest_address].item()
    distance = int(df_velo_temps_reel['distance'][df_velo_temps_reel['lat&lon'] == closest_address].item())

    df_station_velo_plus_proche = pd.DataFrame({
        'Nom station': [Station_velo_la_plus_proche],
        'Nombre de vélos disponibles': [nb_velos_dispos],
        'Nombre de bornes disponibles': [nb_bornes_dispos],
        'Adresse': [adresse_de_la_station],
        'Distance': [distance]
    })

    return df_station_velo_plus_proche

def create_map(df_velo_temps_reel):
    fig = px.scatter_mapbox(
        df_velo_temps_reel,
        lat="lat",
        lon="lon",
        hover_name="name",
        hover_data=["num_bikes_available", "num_docks_available"],
        color_continuous_scale=px.colors.cyclical.IceFire,
        size="num_bikes_available",
        size_max=15,
        zoom=12
    )

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_zoom=12,
        mapbox_center={"lat": 43.6043, "lon": 1.4437},  # Coordonnées de Toulouse
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )

    return fig


###################################################  CRÉATION DE LA CARTE DES 5 PARKINGS LES PLUS PROCHES #####################################################

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
            df_5_parkings_proches = df_5_parkings_proches.append({
                'Parkings': nom,
                'Type de parking': type_parking,
                'Gratuit': gratuit,
                'Nb_places_totales': nb_places,
                'Adresse': adresse,
                'lat' : lat,
                'lon' : lon,
                'Distance(m)' : round(distance)

            }, ignore_index=True)


        # Stocker les 5 parkings les plus proches dans une liste pour créer une menu déroulant
        menu_deroulant_parkings = df_parking_global[df_parking_global['lat&lon'].isin(closest_parkings)]['nom'].tolist()
        #print("Parkings les plus proches :", nom_parking)

    else:
        print("Aucune adresse trouvée parmi la liste")

else:
    print("Adresse de référence introuvable")


# Nous supprimons les deux colonnes lat & lon 
df_5_parkings_proches_dash = df_5_parkings_proches.drop(columns=['lon', 'lat'], axis=1)

# Faire démarrer l'indexation à 1 au lieu de 0   
df_5_parkings_proches_dash = df_5_parkings_proches_dash.reset_index(drop=True)
df_5_parkings_proches_dash.index = df_5_parkings_proches_dash.index + 1




###################################################  CRÉATION DES CARTES #####################################################

# Créer une carte folium avec les 5 parkings de notre DF df_5_parkings_proches
carte_5_parkings_les_plus_proches = folium.Map(location=[lat, lon], zoom_start=15)

for i in range(5):
    lat_parking = df_5_parkings_proches['lat'][i]
    lon_parking = df_5_parkings_proches['lon'][i]
    nom_parking = f'PARKING_{i + 1}'

    folium.Marker(location=[lat_parking, lon_parking], popup="<i>Nom du parking :\n</i>"+df_5_parkings_proches['Parkings'][i]).add_to(carte_5_parkings_les_plus_proches)

carte_5_parkings_les_plus_proches.save('carte_5_parkings_les_plus_proches.html')


############################################### Création de l'application Dash ###############################################
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server
app.title = 'Vélos à Toulouse' # Titre de l'onglet de l'application


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
        'height': '100vh',  # 'vh' signifie viewport height (hauteur de la fenêtre du navigateur)
        'display': 'flex',  # Utiliser flexbox pour aligner et centrer le contenu
        'flexDirection': 'column',  # Aligner le contenu en colonne
        'justifyContent': 'center',  # Centrer verticalement le contenu
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

app.layout = html.Div(
    style=page_style, children=[
    html.H1(children="Transports Toulouse VCA", style=styles),
    html.Hr(style=line_style),
    html.Hr(style=line_style),
    html.H3(children='Entrez votre adresse de départ et cliquez sur le bouton pour trouver le parking le plus proche.'),
    html.Div(style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center'},
            children=[
            html.Label("Numéro:", style=styles),
            dcc.Input(
            id='numero',
            placeholder='Entrez le numéro',
            type='text',
            style=input_style
        ),
        html.Label("Voie:", style=styles),
        dcc.Input(
            id='voie',
            placeholder='Entrez la voie',
            type='text',
            style=input_style
        ),
        html.Label("Code postal:", style=styles),
        dcc.Input(
            id='code-postal',
            placeholder='Entrez le code postal',
            type='number',
            value='31000',
            style=input_style
        ),
        html.Label("Ville:", style=styles),
        dcc.Input(
            id='ville',
            placeholder='Entrez la ville',
            type='text',
            value='Toulouse',
            style=input_style
        )]),
        dcc.Input(id="adresse-depart", type="text", disabled=True),
        html.Button(
        'Rechercher',
        id='submit-button',
        style=button_style
    ),
    html.Div(style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center'}, children=[
        html.Div([html.Iframe(id='carte_5_parkings_les_plus_proches', srcDoc=open('carte_5_parkings_les_plus_proches.html', 'r').read(),
                               width='450', height='450')]),
        html.Div([html.Hr(style={'width': '15%', 'margin': '100px 0'})]),             
        html.Div([dash_table.DataTable(id='df_5_parkings_proches_dash', data=df_5_parkings_proches_dash.to_dict('records'),
                                   style_data={'color': '#ffc12b','backgroundColor': '#a5282b', 'border': '1px solid #ffc12b'},
                                   style_cell={'textAlign': 'center'})])]),
    html.Hr(style=line_style),
    html.H3(children='Sélectionnez le parking dans lequel vous souhaitez vous garer.'),
    dcc.Dropdown(menu_deroulant_parkings, id='parking-dropdown', value='Choisissez votre parking', style = {'width': '60%', 'margin': '10px'}),
    html.Button("J'ai choisi mon parking", id='parking-button', style=button_style),
    html.Div([
    dcc.Tabs(id="tabs", value='tab-0', children=[
        dcc.Tab(label='Team Vélo', value='tab-0', style={'display': 'inline-block'}),
        dcc.Tab(label='Team Tisséo', value='tab-1', style={'display': 'inline-block'}),
    ]),
    html.Div(id='tabs-content')]),
    html.Div([
    html.H1('Station de vélo la plus proche'),
    dcc.Graph(id='city-map', figure=create_map(df_velo_temps_reel)),  # Utilisez votre fonction create_map ici
    html.Hr(),
    html.H3('Informations sur la station de vélo la plus proche'),
    dash_table.DataTable(id='data-table', columns=[{'name': col, 'id': col} for col in df_velo_temps_reel.columns],
                 data=[{}])]
    )
])



###############################################  CALLBACKS #####################################################

@app.callback(
    Output('adresse-depart', 'value'),
    [Input('numero', 'value'),
     Input('voie', 'value'),
     Input('code-postal', 'value'),
     Input('ville', 'value')]
)

@app.callback(
    Output('city-map', 'figure'),
    Output('data-table', 'data'),
    Input('adresse-input', 'value')
)


@app.callback(
    Output('tabs-content', 'children'),
    Input('tabs', 'value')
)

###############################################  FONCTIONS #####################################################

def update_adresse_depart(numero, voie, code_postal="31000", ville="Toulouse"):
    adresse_depart = f"{numero} {voie}, {code_postal} {ville}"
    return adresse_depart

def update_map_data_table(selected_address):
    closest_address = find_closest_station(selected_address, df_velo_temps_reel)
    df_station_velo_plus_proche = get_station_info(closest_address, df_velo_temps_reel)

    # Create the map
    fig = create_map(df_velo_temps_reel)

    return fig, df_station_velo_plus_proche.to_dict('records')


def render_content(tab):
    if tab == 'tab-0':
        return html.Div([
            dcc.Graph(id='city-map', figure=create_map(df_velo_temps_reel)),
            html.Hr(),
            html.H3('Informations sur la station de vélo la plus proche'),
            dash_table.DataTable(
                id='data-table',
                columns=[{'name': col, 'id': col} for col in df_velo_temps_reel.columns],
                data=[{}]
            )
        ])
    elif tab == 'tab-1':
        return html.Div("Hello World")

if __name__ == '__main__':
    app.run_server(debug=True)
