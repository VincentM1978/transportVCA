from datetime import datetime
from babel.dates import format_datetime, format_date, format_time
import dash
from dash import dcc
from dash import html
from dash import dash_table
import pandas as pd
import requests
import plotly.express as px
from dash.dependencies import Input, Output
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import plotly.graph_objects as go
import pytz
from pyroutelib3 import Router
import dash_bootstrap_components as dbc

starting_carte = px.scatter_mapbox(lat=[43.6044622], lon=[1.4442469], zoom=15, height=750, width=750, mapbox_style='open-street-map')
carte_velo = px.scatter_mapbox(lat=[43.6044622], lon=[1.4442469], zoom=12, height=750, width=750, mapbox_style='open-street-map')
carte_tec = px.scatter_mapbox(lat=[43.6044622], lon=[1.4442469], zoom=12, height=750, width=750, mapbox_style='open-street-map')
starting_carte.update_layout(margin=dict(l=0, r=0, t=0, b=30))
carte_velo.update_layout(margin=dict(l=0, r=0, t=0, b=30))
carte_tec.update_layout(margin=dict(l=0, r=0, t=0, b=30))
now = datetime.now()
formatted_date = format_datetime(now, format="cccc d MMMM yyyy, 'il est' H'h'mm", locale='fr_FR')
formatted_date = formatted_date.replace("\955", "h")


###################################################  PARKINGS #####################################################

link_csv_parking_indigo = "https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/parcs-de-stationnement/exports/csv?lang=fr&timezone=Europe%2FBerlin&use_labels=true&delimiter=%3B"
df_parking_indigo = pd.read_csv(link_csv_parking_indigo,sep=";")
colonne_a_garder = ['xlong', 'ylat', 'nom', 'nb_places', 'adresse', 'type_ouvrage', 'gestionnaire', 'gratuit', 'nb_voitures', 'nb_velo']
df_parking_indigo_nettoye = df_parking_indigo.loc[:, colonne_a_garder]
df_parking_indigo_nettoye['gratuit'] = df_parking_indigo_nettoye['gratuit'].replace({'F': 'non', 'T': 'oui'})
df_parking_indigo_nettoye['lat&lon'] = df_parking_indigo_nettoye.apply(lambda x: f"{x['ylat']}, {x['xlong']}", axis=1)
df_parking_indigo_nettoye['relais ?'] = 'non'
link_parking_relais = "https://data.toulouse-metropole.fr/api/records/1.0/search/?dataset=parkings-relais&q=&facet=commune"
response = requests.get(link_parking_relais)
data = response.json()
df_parking_relais = pd.DataFrame(data['records'])
df_parking_relais_nettoye = pd.json_normalize(df_parking_relais['fields'])
df_parking_relais_nettoye = df_parking_relais_nettoye[['nom', 'nb_places', 'xlong', 'ylat', 'adresse','type_ouvrage', 'gratuit', 'nb_voitures', 'nb_velo', 'geo_point_2d']]
df_parking_relais_nettoye['gratuit'] = df_parking_relais_nettoye['gratuit'].replace('F', 'non').replace('T', 'oui')
df_parking_relais_nettoye = df_parking_relais_nettoye.rename(columns={'geo_point_2d':'lat&lon'})
df_parking_relais_nettoye['lat&lon'] = df_parking_relais_nettoye['lat&lon'].astype(str).apply(lambda x : x[1:]).apply(lambda x : x[:-1])
df_parking_relais_nettoye['relais ?'] = 'oui'
df_parking_relais_nettoye['gestionnaire'] = 'Tisseo'
df_parking_global = pd.concat([df_parking_relais_nettoye, df_parking_indigo_nettoye], ignore_index=True)
menu_deroulant_parkings = df_parking_global['nom'].tolist()

################################################################ VÉLOS ##############################################################
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
df_velo_temps_reel['adresse_complete'] = df_velo_temps_reel['address']+", , Toulouse"
df_velo_temps_reel['lat&lon'] = df_velo_temps_reel.apply(lambda x: f"{x['lat']}, {x['lon']}", axis=1)

##################################################### CRÉATION DU DF DES 5 STATIONS LES PLUS PROCHES #####################################################

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
df_arrets_coordonnees['id'] = df_arrets_coordonnees['id'].apply(lambda x : x[10:])
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
df_line_final['lat&lon'] = df_line_final.apply(lambda x: f"{x['lat']}, {x['lon']}", axis=1)
df_stop_area_unique = df_line_final.drop_duplicates(subset = "id_stop_area")
df_stop_area_unique = df_stop_area_unique[['cityName', 'id_stop_area', 'arret',  'lat&lon' ]]

############################################### Création de l'application Dash ###############################################
app = dash.Dash(__name__, prevent_initial_callbacks='initial_duplicate', suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.LUX])
app.title = 'Transports Toulouse VCA'
server = app.server

######################################### Styles CSS personnalisés #########################################
styles = {
    'textAlign': 'center',
    'padding': '20px'
}

page_style = {
        'width': '100%',
        'height': '100%',  
        'display': 'flex',  
        'flexDirection': 'column',
        'alignItems': 'center'
    }

line_style = {
    'width': '100%',
    'borderTop': '1px white solid',
    'margin': '10px 0'
}

input_style = {
    'width': '50%', 'margin': '10px'
    }

button_style = {
            'margin': '10px auto',
            'border': 'double 3px white',
            'padding': '10px 20px',
            'font-size': '18px',
            'cursor': 'pointer'
        }


###################################################  LAYOUT #####################################################

app.layout = html.Div(style=page_style, children=[
    html.H1(children="Transports Toulouse VCA", style=styles),
    html.Hr(style=line_style),
    html.H3(children=f'Nous sommes le {formatted_date}.', style=styles),
    html.H3(children='Entrez votre adresse de départ et cliquez sur le bouton pour trouver le parking le plus proche.', style=styles),
    
   html.Div(children=[
    html.Div([
        html.Label("Numéro:", style=styles),
        dcc.Input(id='numero', placeholder='Entrez le numéro', type='text', style=input_style)
    ], style={'display': 'inline-block'}),

    html.Div([
        html.Label("Voie:", style=styles),
        dcc.Input(id='voie', placeholder='Entrez la voie', type='text', style=input_style)
    ], style={'display': 'inline-block'}),

    html.Div([
        html.Label("Code postal:", style=styles),
        dcc.Input(id='code-postal', placeholder='Entrez le code postal', type='number', style=input_style)
    ], style={'display': 'inline-block'}),

    html.Div([
        html.Label("Ville:", style=styles),
        dcc.Input(id='ville', placeholder='Entrez la ville', type='text', style=input_style)
    ], style={'display': 'inline-block'})
]),


    dcc.Input(id="adresse-depart", type="text", disabled=True, style={'justify-content' : 'center','width': '600px'}),
    html.Button('Rechercher', id='submit-button', style=button_style),
    dcc.Graph(id='carte_parkings', figure=starting_carte),
    html.Div(id='content'),
    html.Hr(style=line_style),
    html.H3(children='Sélectionnez le parking dans lequel vous souhaitez vous garer.', style=styles),
    html.Div(id='menu-deroulant-parkings', style=input_style),
    html.Hr(style=line_style),
    html.Div(children = [html.H3("Sélectionnez un moyen de transport en cliquant sur le bouton associé")]),
    html.Div(style={'display': 'flex', 'justify-content':'space-around'}, children=[
        html.Div(style={'flex': '1', 'margin-left': '100px'}, children=[
            html.Div(children=[
                html.Div(style={'justify-items': 'stretch'}, children=[
                    html.Button("Je préfère le vélo", id='velo_button', style=button_style)
                ]),
            ]),
            dcc.Graph(id='carte_velo', figure=carte_velo),
            html.Div(id='content_velo')
        ]),
        html.Div(style={'flex': '1', 'margin-left': '10px'}, children=[
            html.Button("Je préfère les transports en commun", id='tec_button', style=button_style),
            dcc.Graph(id='carte_tec', figure=carte_tec),
            html.Div(id='content_tec'),
            html.Div(id='menu-deroulant-arrets', style=input_style),
            html.Button("J'ai choisi mon arrêt.", id='arret-button', style=button_style),
            html.Div(id='content_horaires')
        ])
    ])
])


###############################################  CALLBACKS ET FONCTIONS #####################################################

@app.callback(
    [Output('adresse-depart', 'value'),
     Output('carte_parkings', 'figure'),
     Output('content', 'children'),
     Output('menu-deroulant-parkings', 'children')
    ],
    [Input('numero', 'value'),
     Input('voie', 'value'),
     Input('code-postal', 'value'),
     Input('ville', 'value'),
     Input('submit-button', 'n_clicks')]
)

def update_adresse_depart(numero, voie, code_postal, ville, n_clicks):
    adresse_depart = f"{numero} {voie}, {code_postal} {ville}"

    if n_clicks is not None:
        geolocator = Nominatim(user_agent="my_app")
        location_reference = geolocator.geocode(adresse_depart)
    else:
        location_reference = None
    if location_reference is not None:
        coordinates_to_compare = df_parking_global['lat&lon']
        coordinates_reference = (location_reference.latitude, location_reference.longitude)
        distances = {}
        for coordinate_to_compare in coordinates_to_compare:
            distance = geodesic(coordinates_reference, coordinate_to_compare).meters
            distances[coordinate_to_compare] = distance
        closest_parkings = sorted(distances, key=distances.get)[:5]
        if closest_parkings:
            df_5_parkings_proches = pd.DataFrame(columns=['Parking', 'Type de parking', 'Gratuit', 'Nb_places_totales', 'Adresse', 'Distance(m)', 'lat', 'lon'])
            for parking in closest_parkings:
                parking_data = df_parking_global[df_parking_global['lat&lon'] == parking]
                nom = parking_data['nom'].values[0]
                type_parking = parking_data['type_ouvrage'].values[0]
                gratuit = parking_data['gratuit'].values[0]
                nb_places = parking_data['nb_voitures'].values[0]
                adresse = parking_data['adresse'].values[0]
                lat = parking_data['ylat'].values[0]
                lon = parking_data['xlong'].values[0]
                
                distance = distances[parking]
                df_5_parkings_proches = pd.concat([df_5_parkings_proches, pd.DataFrame({
                    'Parking': [nom],
                    'Type de parking': [type_parking],
                    'Gratuit': [gratuit],
                    'Nb_places_totales': [nb_places],
                    'Adresse': [adresse],
                    'lat': [lat],
                    'lon': [lon],
                    'Distance(m)': [round(distance)]
                })], ignore_index=True)
            df_5_parkings_proches_dash = df_5_parkings_proches.drop(columns=['lon', 'lat'], axis=1).reset_index(drop=True).rename_axis('index').reset_index()
            df_5_parkings_proches_dash['index'] = df_5_parkings_proches_dash['index'] + 1        
            carte = go.Figure()
            for i in range(5):
                lat_parking = df_5_parkings_proches['lat'][i]
                lon_parking = df_5_parkings_proches['lon'][i]
                

                carte.add_trace(go.Scattermapbox(
                    lat=[lat_parking],
                    lon=[lon_parking],
                    mode='markers',
                    marker=go.scattermapbox.Marker(
                        size=20,
                        color='#a5282b',
                        opacity=1),
                    name=df_5_parkings_proches['Parking'][i],
                    text = [f" <b>Nom du parking:</b> {df_5_parkings_proches['Parking'][i]} <b>Distance:</b> {df_5_parkings_proches['Distance(m)'].astype(str)[i]} Metres"],
                    hoverinfo = ['text']    
            )
                )
            
            carte.update_layout(
                mapbox_style='open-street-map',
                mapbox_center_lon=df_5_parkings_proches['lon'][0],
                mapbox_center_lat=df_5_parkings_proches['lat'][0],
                mapbox=dict(
                    zoom=15
                ),margin=dict(l=0, r=0, t=0, b=30)
            )
            

        return adresse_depart, carte, html.Div(children = [dash_table.DataTable(id='df_5_parkings_proches_dash',data = df_5_parkings_proches_dash.to_dict('records'),
                                                style_data={'border': '1px solid #ffc12b'},
                                                style_cell={'textAlign': 'center'})]),dcc.Dropdown(id='menu-deroulant-parkings', options=[{'label': parking, 'value': parking} for parking in df_5_parkings_proches['Parking']])
    else:
        return "Adresse non trouvée", starting_carte, '', ''
    
    


@app.callback(
    [Output('carte_velo', 'figure'),
    Output('content_velo', 'children'),
    ],
    [Input('velo_button', 'n_clicks'),
     Input('menu-deroulant-parkings', 'value')
     ]
)

def render_content( n_clicks, parking_choisi):
    if n_clicks is not None:
            
        adresse_du_parking_choisi = df_parking_global[df_parking_global['nom'] == parking_choisi]['adresse'].values[0]
        geolocator = Nominatim(user_agent="my_app")
        location_reference = geolocator.geocode(adresse_du_parking_choisi)

        if location_reference is not None:
            coordinates_to_compare = df_parking_global['lat&lon']
            coordinates_reference = (location_reference.latitude, location_reference.longitude)
            distances = {}
            for coordinate_to_compare in coordinates_to_compare:
                distance = geodesic(coordinates_reference, coordinate_to_compare).meters
                distances[coordinate_to_compare] = distance
            closest_parkings = sorted(distances, key=distances.get)[:5]

            if closest_parkings:
                df_5_parkings_proches = pd.DataFrame(columns=['Parking', 'Type de parking', 'Gratuit', 'Nb_places_totales', 'Adresse', 'Distance(m)', 'lat', 'lon'])
                for parking in closest_parkings:
                    parking_data = df_parking_global[df_parking_global['lat&lon'] == parking]
                    nom = parking_data['nom'].values[0]
                    type_parking = parking_data['type_ouvrage'].values[0]
                    gratuit = parking_data['gratuit'].values[0]
                    nb_places = parking_data['nb_voitures'].values[0]
                    adresse = parking_data['adresse'].values[0]
                    lat = parking_data['ylat'].values[0]
                    lon = parking_data['xlong'].values[0]
                    distance = distances[parking]
                    df_5_parkings_proches = pd.concat([df_5_parkings_proches, pd.DataFrame({
                        'Parking': [nom],
                        'Type de parking': [type_parking],
                        'Gratuit': [gratuit],
                        'Nb_places_totales': [nb_places],
                        'Adresse': [adresse],
                        'lat': [lat],
                        'lon': [lon],
                        'Distance(m)': [round(distance)]
                    })], ignore_index=True)
                    
                    df_5_parkings_proches_dash = df_5_parkings_proches.drop(columns=['lon', 'lat'], axis=1).reset_index(drop=True).rename_axis('index').reset_index()
                    df_5_parkings_proches_dash['index'] = df_5_parkings_proches_dash['index'] + 1
                    adresse_du_parking_choisi = df_5_parkings_proches['Adresse'][0]
                    address_reference = adresse_du_parking_choisi

                    coordinates_to_compare = df_velo_temps_reel['lat&lon']
                    geolocator = Nominatim(user_agent="my_app")
                    location_reference = geolocator.geocode(address_reference)
                    coordinates_reference = (location_reference.latitude, location_reference.longitude)
                    min_distance = float('inf')
                    closest_address = None

                    for coordinate_to_compare in coordinates_to_compare:
                        distance = geodesic(coordinates_reference, coordinate_to_compare).meters

                        if distance < min_distance:
                            min_distance = distance
                            closest_address = coordinate_to_compare

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
                    df_station_velo_plus_proche = df_station_velo_plus_proche.rename(columns={0: 'Borne vélo', 1: 'Vélos disponibles', 2: 'Bornes disponibles', 3: 'Adresse', 4: 'Distance (m)'})
                    df_station_velo_plus_proche['Distance (m)'] = df_station_velo_plus_proche['Distance (m)'].astype(int)
                    
                    lat_parking = df_5_parkings_proches['lat'][0]
                    lon_parking = df_5_parkings_proches['lon'][0]

                    router = Router('foot')
                    depart_name = parking_choisi
                    arrivee_name = Station_velo_la_plus_proche
                    arrivee_row = df_velo_temps_reel[df_velo_temps_reel['name'] == arrivee_name].iloc[0]
                    depart_lat = lat_parking
                    depart_lon = lon_parking
                    arrivee_lat = arrivee_row['lat']
                    arrivee_lon = arrivee_row['lon']
                    depart = router.findNode(depart_lat, depart_lon)
                    arrivee = router.findNode(arrivee_lat, arrivee_lon)
                    status, itineraire = router.doRoute(depart, arrivee)
                    
                    if status == 'success':
                        itineraire_coordonnees = [router.nodeLatLon(node) for node in itineraire]
                        depart_trace = go.Scattermapbox(
                            lat=[depart_lat],
                            lon=[depart_lon],
                            mode='markers',
                            marker=dict(
                                size=20,
                                color='#a5282b',
                                symbol='circle'
                            ),name='Départ',
                            text=['Point de départ'],
                            hoverinfo='text'
                        )

                        arrivee_trace = go.Scattermapbox(
                            lat=[arrivee_lat],
                            lon=[arrivee_lon],
                            mode='markers',
                            marker=dict(
                                size=20,
                                color='darkblue',
                                symbol='circle'
                            ),name = 'Arrivée',
                            text=['Point d\'arrivée'],
                            hoverinfo='text'
                        )

                        itineraire_trace = go.Scattermapbox(
                            lat=[coord[0] for coord in itineraire_coordonnees],
                            lon=[coord[1] for coord in itineraire_coordonnees],
                            mode='lines',
                            line=dict(
                                color='green',
                                width=2
                            ),name = 'Itinéraire'
                        )

                        carte_velo = go.Figure(data=[itineraire_trace, depart_trace, arrivee_trace])
                        carte_velo.update_layout(
                            mapbox=dict(
                                center=dict(lat=depart_lat, lon=depart_lon),
                                zoom=17,
                                style='open-street-map'
                            ),
                            margin=dict(l=0, r=0, t=0, b=30)
                        )                        
                        return (carte_velo, html.Div(children = [html.H4(f"La borne vélo la plus proche est : \n\n"),
                                                    html.Br(),
                                                    dash_table.DataTable(id='df_station_velo_plus_proche',data = df_station_velo_plus_proche.to_dict('records'), style_data={'border': '1px solid #ffc12b'},style_cell={'textAlign': 'center'}),
                                                    html.Br()]))

        else:
            n_clicks = 0

        return (starting_carte, html.Div(children = [html.H4("La borne vélo la plus proche est : \n")]))

    else:
        return (starting_carte, html.Div(children = [html.H4("")]))




@app.callback(
    [Output('carte_tec', 'figure'),
    Output('content_tec', 'children'),       
    ],
    [Input('tec_button', 'n_clicks'),
     Input('menu-deroulant-parkings', 'value')
     ]
)

def render_content2(n_clicks, parking_choisi):
    if n_clicks is not None:
            
        adresse_du_parking_choisi = df_parking_global[df_parking_global['nom'] == parking_choisi]['adresse'].values[0]
        geolocator = Nominatim(user_agent="my_app")
        location_reference = geolocator.geocode(adresse_du_parking_choisi)

        if location_reference is not None:
            coordinates_to_compare = df_stop_area_unique['lat&lon']
            coordinates_reference = (location_reference.latitude, location_reference.longitude)
            distances = {}
            for coordinate_to_compare in coordinates_to_compare:
                distance = geodesic(coordinates_reference, coordinate_to_compare).meters
                distances[coordinate_to_compare] = distance
            closest_stations = sorted(distances, key=distances.get)[:5]

            if closest_stations:
                closest_stops = df_stop_area_unique[df_stop_area_unique['lat&lon'].isin(closest_stations)]['arret'].tolist()
                closest_stops_id = df_stop_area_unique[df_stop_area_unique['lat&lon'].isin(closest_stations)]['id_stop_area'].tolist()
                LatLon_closest_stops = df_stop_area_unique[df_stop_area_unique['lat&lon'].isin(closest_stations)]['lat&lon'].tolist()
                list_distances = []
                for station in closest_stations:
                    distance = distances[station]
                    list_distances.append(distances[station])
                df_arrets_plus_proches = pd.concat([pd.Series(closest_stops), pd.Series(closest_stops_id), pd.Series(LatLon_closest_stops), pd.Series(list_distances)], axis=1)
                df_arrets_plus_proches = df_arrets_plus_proches.rename(columns={0: 'Arrets', 1: 'id_stop_area', 2: 'lat&lon', 3: 'Distance (m)'})
                df_arrets_plus_proches['Distance (m)'] = df_arrets_plus_proches['Distance (m)'].astype(int)
                df_arrets_plus_proches[['lat','lon']] = df_arrets_plus_proches['lat&lon'].str.split(",",expand=True).astype(float)
                carte_tec = go.Figure()
                for i in range(5):
                    coordonnees_lat_arrets_tisseo = df_arrets_plus_proches['lat'][i]
                    coordonnees_lon_arrets_tisseo = df_arrets_plus_proches['lon'][i]
                    nom_arret_tisseo = f'ARRET_{i + 1}'
                    carte_tec.add_trace(go.Scattermapbox(
                        lat=[coordonnees_lat_arrets_tisseo],
                        lon=[coordonnees_lon_arrets_tisseo],
                        mode='markers',
                        marker=go.scattermapbox.Marker(
                            size=20,
                            color='#a5282b',
                            opacity=1),
                        name=df_arrets_plus_proches['Arrets'][i],
                        text = [f" <b>Nom de l'arrêt:</b> {df_arrets_plus_proches['Arrets'][i]} <b>Distance:</b> {df_arrets_plus_proches['Distance (m)'].astype(str)[i]} Metres"],
                        hoverinfo = ['text']))
                
                carte_tec.update_layout(
                    mapbox_style='open-street-map',
                    mapbox_center_lon=df_arrets_plus_proches['lon'][0],
                    mapbox_center_lat=df_arrets_plus_proches['lat'][0],
                    mapbox=dict(
                        zoom=15
                    ),margin=dict(l=0, r=0, t=0, b=30)
                )
              
                return carte_tec, html.Div(children=[
                    html.H4(f"La station la plus proche est : \n\n"),
                    html.Br(),
                    dash_table.DataTable(
                    id='df_arrets_plus_proches',
                    data=df_arrets_plus_proches[['Arrets', 'Distance (m)']].to_dict('records'),
                    style_data={'border': '1px solid #ffc12b'},
                    style_cell={'textAlign': 'center'}
                    ),
                    html.Br(),
                    html.H5("Sélectionnez votre station pour voir les dix prochains horaires."),
                    dcc.Dropdown(
                    id='menu-deroulant-arrets',
                    options=[{'label': arret, 'value': arret} for arret in df_arrets_plus_proches['Arrets']]
    )
])
            else:
                print("Aucune station trouvée")
        

        else:
            return starting_carte, html.Div(children = [html.H4(f"Adresse non trouvée ")])

    else:
        return starting_carte, html.Div(children = [html.H4("")])


@app.callback(
    [Output('content_horaires', 'children'),       
    ],
    [Input('arret-button', 'n_clicks'),
     Input('menu-deroulant-arrets', 'value')
     ]
)

def render_content3(n_clicks, nom_arret_choisi):
    if n_clicks is not None:

        if nom_arret_choisi is not None:
                            
            df_lignes_arrets_choisies = df_line_final[df_line_final['arret'] == nom_arret_choisi]
            id_stop_area_selectionne = df_lignes_arrets_choisies['id_stop_area'].iloc[0]
            service_name = 'stops_schedules'
            format_type = 'xml'
            parameters_stop_area = 'stopAreaId=stop_area:'+id_stop_area_selectionne
            api_key = '15cbfcdf-76bb-4136-980a-6dc1f1d96cd5'
            url_stop_area_id = f"https://api.tisseo.fr/v2/{service_name}.json?{parameters_stop_area}&key={api_key}"
            response = requests.get(url_stop_area_id)
            data = response.json()
            df_schedules_stop_area = pd.json_normalize(data['departures'], record_path= "departure", meta= 'stopArea')
            df_schedules_stop_area = df_schedules_stop_area[['dateTime', 'destination', 'line.name', 'line.network', 'line.shortName', 'stopArea']]
            df_schedules_stop_area = pd.concat([df_schedules_stop_area.drop(['stopArea'], axis=1), df_schedules_stop_area['stopArea'].apply(pd.Series)], axis=1)
            df_schedules_stop_area = df_schedules_stop_area.drop(['cityId'], axis=1)
            df_schedules_stop_area = df_schedules_stop_area.explode('destination')
            df_destination = df_schedules_stop_area['destination'].apply(pd.Series)
            df_destination = df_destination.rename(columns={"id": "id_stop_area_destination", "name": "name_stop_area_destination", "cityName": "cityName_destination"})
            df_concat = pd.concat([df_schedules_stop_area, df_destination], axis=1)
            df_concat = df_concat.drop(['destination', 'line.network', 'id_stop_area_destination', 'name_stop_area_destination'], axis=1)
            df_concat = df_concat.rename(columns={"id": "id_stop_area"})
            df_concat['id_stop_area'] = df_concat['id_stop_area'].apply(lambda x : x[10:])
            df_horaires_utilisateur = df_concat.drop(columns=['name', 'cityName', 'id_stop_area'], axis = 1)
            df_horaires_utilisateur = df_horaires_utilisateur.rename(columns={
                'dateTime': 'Prochains horaires',
                'line.name': 'Nom de la ligne',
                'line.shortName': 'Numéro de ligne',
                'cityName_destination': 'Ville de destination'
            })

            df_horaires_utilisateur = df_horaires_utilisateur.reindex(columns=['Prochains horaires', 'Numéro de ligne', 'Nom de la ligne', 'Ville de destination' ])
            return [html.Div([dash_table.DataTable(id='df_horaires_utilisateur',data = df_horaires_utilisateur.to_dict('records'),style_data={'border': '1px solid #ffc12b'},style_cell={'textAlign': 'center'})])]
        
        else:
            return dbc.Label((f"Choisissez un arrêt"))

    else:
        return [dbc.Label((f""))]

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)
