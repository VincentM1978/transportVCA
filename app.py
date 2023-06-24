import dash
from dash import dcc
from dash import html
import pandas as pd
import requests
import plotly.express as px
from dash.dependencies import Input, Output, State
from geopy.geocoders import Nominatim
from geopy.distance import geodesic


# Fonction pour calculer les 5 parkings les plus proches
def calculate_closest_parkings(address_reference):
    link_csv_parking = "https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/parcs-de-stationnement/exports/csv?lang=fr&timezone=Europe%2FBerlin&use_labels=true&delimiter=%3B"
    df_parking = pd.read_csv(link_csv_parking, sep=";")

    # Garder uniquement certaines colonnes
    colonne_a_garder = ['xlong', 'ylat', 'nom', 'nb_places', 'adresse', 'type_ouvrage', 'gestionnaire', 'gratuit', 'nb_voitures', 'nb_velo']
    df_parking_nettoye = df_parking.loc[:, colonne_a_garder]

    # Remplacer les données de la colonne gratuit
    df_parking_nettoye['gratuit'] = df_parking_nettoye['gratuit'].replace({'F': 'non', 'T': 'oui'})

    # Concaténer la latitude avec la longitude
    df_parking_nettoye['lat&lon'] = df_parking_nettoye.apply(lambda x: f"{x['ylat']}, {x['xlong']}", axis=1)

    link_parking_relais = "https://data.toulouse-metropole.fr/api/records/1.0/search/?dataset=parkings-relais&q=&facet=commune"
    response = requests.get(link_parking_relais)
    data = response.json()
    df_parking_relais = pd.DataFrame(data['records'])
    df_parking_relais_fields = pd.json_normalize(df_parking_relais['fields'])
    df_parking_relais_fields.drop(['nb_2_rm', 'tarif_2h', 'motdir', 'nbr_abonne_moto', 'insee',
                                   'quota_residant_vl', 'nb_pmr', 'nb_covoit', 'abo_resident', 'infobulle', 'public', 'commune', 'tarif_4h',
                                   'tarif_1h', 'tarif_3h', 'nbr_abonne_vl', 'proprietaire', 'nb_pr',
                                   'fonction', 'infobulle3', 'id', 'abo_non_resident', 'hauteur_max', 'nb_voitures_electriques', 'nb_autopartage', 'gml_id',
                                   'quota_dispo_vl', 'infobulle2', 'nb_arretm', 'tarif_24h', 'nb_2r_el', 'info', 'quota_dispo_moto',
                                   'tarif_pmr', 'gestionnaire', 'type_usager','quota_residant_moto', 'oid', 'nb_amodie',
                                   'geo_shape.coordinates', 'geo_shape.type', 'annee_creation'], axis= 1, inplace= True)

    # Changer l'ordre des colonnes
    df_parking_relais_fields = df_parking_relais_fields.reindex(columns = ['nom', 'nb_places', 'xlong', 'ylat', 'adresse','type_ouvrage', 'gratuit', 'nb_voitures', 'nb_velo', 'geo_point_2d'])
    # Remplacer les valeurs de la colonne gratuit
    df_parking_relais_fields['gratuit'] = df_parking_relais_fields['gratuit'].replace('F', 'non').replace('T', 'oui')
    # Renommer la colonne geo_point_2d
    df_parking_relais_fields = df_parking_relais_fields.rename(columns={'geo_point_2d':'lat&lon'})
    # Passer la colonne lat&lon en string
    df_parking_relais_fields['lat&lon'] = df_parking_relais_fields['lat&lon'].astype(str)
    # Supprimer le premier crochet de la colonne lat&lon
    df_parking_relais_fields['lat&lon'] = df_parking_relais_fields['lat&lon'].apply(lambda x : x[1:])
    # Supprimer le dernier crochet
    df_parking_relais_fields['lat&lon'] = df_parking_relais_fields['lat&lon'].apply(lambda x : x[:-1])

    df_parking_nettoye2 = df_parking_nettoye
    df_parking_nettoye2['relais ?'] = 'non'
    df_parking_relais_fields2 = df_parking_relais_fields
    df_parking_relais_fields2['relais ?'] = 'oui'
    df_parking_global = pd.concat([df_parking_relais_fields2, df_parking_nettoye2], ignore_index=True)
    df_parking_global['gestionnaire'].fillna('Tisseo',inplace=True)

    geolocator = Nominatim(user_agent="my_app")
    location_reference = geolocator.geocode(address_reference)

    if location_reference is not None:
        coordinates_reference = (location_reference.latitude, location_reference.longitude)
        distances = {}
        coordinates_to_compare = df_parking_global['lat&lon']

        for coordinate_to_compare in coordinates_to_compare:
            distance = geodesic(coordinates_reference, coordinate_to_compare).meters
            distances[coordinate_to_compare] = distance

        closest_parkings = sorted(distances, key=distances.get)[:5]

        if closest_parkings:
            df_5_parkings_proches = pd.DataFrame(columns=['Parkings', 'Type de parking', 'Gratuit', 'Nb_places_totales', 'Adresse', 'Distance_pour_y_acceder(m)', 'lat', 'lon'])
            
            for parking in closest_parkings:
                parking_data = df_parking_global[df_parking_global['lat&lon'] == parking]
                nom_parking = parking_data['nom'].values[0]
                type_parking = parking_data['type_ouvrage'].values[0]
                gratuit = parking_data['gratuit'].values[0]
                nb_places = parking_data['nb_places'].values[0]
                adresse = parking_data['adresse'].values[0]
                lat, lon = parking_data['lat&lon'].values[0].split(',')
                distance_parking = distances[parking]

                temp_df = pd.DataFrame({'Parkings': nom_parking,
                                        'Type de parking': type_parking,
                                        'Gratuit': gratuit,
                                        'Nb_places_totales': nb_places,
                                        'Adresse': adresse,
                                        'Distance_pour_y_acceder(m)': distance_parking,
                                        'lat': lat,
                                        'lon': lon}, index=[0])

                df_5_parkings_proches = pd.concat([df_5_parkings_proches, temp_df], ignore_index=True)
                # Création de la carte pour les parkings
                fig_parkings = px.scatter_mapbox(df_5_parkings_proches, lat='lat', lon='lon', hover_name='Parkings',                                              
                                                zoom=15)

                fig_parkings.update_layout(mapbox_style='carto-positron',
                                        mapbox_center=dict(lat=43.599, lon=1.436),
                                        mapbox_zoom=15,
                                        width=1000,
                                        height=600,
                                        coloraxis_colorscale="RdYlBu",
                                        hoverlabel=dict(bgcolor='white', font_size=12, font_family='Arial'))
           
            return df_5_parkings_proches

        else:
            return pd.DataFrame()

    else:
        return pd.DataFrame()


 # Récupérer les données de disponibilité des vélos
url = 'https://transport.data.gouv.fr/gbfs/toulouse/gbfs.json'
try:
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    df_source = pd.DataFrame(data)
except requests.exceptions.RequestException as e:
    print('Une erreur est survenue lors de l\'appel à l\'API :', e)

# Récupérer les informations sur les stations de vélo
lien_json = "https://transport.data.gouv.fr/gbfs/toulouse/station_information.json"
lien_json2 = "https://transport.data.gouv.fr/gbfs/toulouse/station_status.json"
df_info = pd.read_json(lien_json)
df_statut = pd.read_json(lien_json2)

stations_list = df_info['data'].values[0]
statut_list = df_statut['data'].values[0]

# Convertir la liste de dictionnaires en DataFrame pour les informations sur les stations
df_stations = pd.DataFrame(stations_list)

# Convertir la liste de dictionnaires en DataFrame pour les disponibilités
df_disponibilites = pd.DataFrame(statut_list)

# Fusionner les DataFrames df_stations et df_disponibilites
df_velo_temps_reel = pd.merge(df_stations, df_disponibilites, how="left", on='station_id')


# Création de la carte pour les parkings
df_5_parkings_proches = pd.DataFrame(columns=['Parkings', 'Type de parking', 'Gratuit', 'Nb_places_totales', 'Adresse', 'Distance_pour_y_acceder(m)', 'lat', 'lon'])
fig_parkings = px.scatter_mapbox(df_5_parkings_proches, lat='lat', lon='lon',zoom=15)

fig_parkings.update_layout(mapbox_style='carto-positron',
                        mapbox_center=dict(lat=43.599, lon=1.436),
                        mapbox_zoom=12,
                        width=1000,
                        height=600,
                        coloraxis_colorscale="RdYlBu",
                        hoverlabel=dict(bgcolor='white', font_size=12, font_family='Arial'))

# Création de la carte pour les vélos disponibles
fig_recup = px.scatter_mapbox(df_velo_temps_reel, lat='lat', lon='lon', hover_name='name',
                              hover_data=['address', 'capacity', 'last_reported', 'num_bikes_available'],
                              color='num_bikes_available', color_continuous_scale='RdYlBu', zoom=12)

fig_recup.update_layout(mapbox_style='carto-positron',
                        mapbox_center=dict(lat=43.599, lon=1.436),
                        mapbox_zoom=12,
                        width=1000,
                        height=600,
                        coloraxis_colorscale="RdYlBu",
                        hoverlabel=dict(bgcolor='white', font_size=12, font_family='Arial'))

# Création de la  pour les places disponibles pour remise des vélos
fig_remise = px.scatter_mapbox(df_velo_temps_reel, lat='lat', lon='lon', hover_name='name',
                               hover_data=['address', 'capacity', 'last_reported', 'num_docks_available'],
                               color='num_docks_available', color_continuous_scale='RdYlBu', zoom=12)

fig_remise.update_layout(mapbox_style='carto-positron',
                         mapbox_center=dict(lat=43.599, lon=1.436),
                         mapbox_zoom=12,
                         width=1000,
                         height=600,
                         coloraxis_colorscale="RdYlBu",
                         hoverlabel=dict(bgcolor='white', font_size=12, font_family='Arial'))


# Création de l'application Dash
app = dash.Dash(__name__)
server = app.server


# Styles CSS personnalisés pour le titre et l'arrière-plan
styles = {
    'backgroundColor': '#a5282b',
    'color': '#ffc12b',
    'textAlign': 'center',
    'padding': '20px'
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

# Mise en page de l'application
app.layout = html.Div(
    style={
        'backgroundColor': '#a5282b',
        'width': '100%',
        'height': '100vh',  # 'vh' signifie viewport height (hauteur de la fenêtre du navigateur)
        'display': 'flex',  # Utiliser flexbox pour aligner et centrer le contenu
        'flexDirection': 'column',  # Aligner le contenu en colonne
        'justifyContent': 'center',  # Centrer verticalement le contenu
        'alignItems': 'center',  # Centrer horizontalement le contenu
    }, children=[
    html.H1(children="Transports Toulouse VCA", style=styles),
    html.Hr(),
    html.Hr(),
    html.H1("Recherche de parkings", style=styles),
    html.Hr(),
    html.H2("Trouver les parkings les plus proches de votre adresse de départ", style=styles),
    html.Hr(),
    html.Label("Adresse de départ :", style=styles),
    dcc.Input(
        id='adresse-depart',
        placeholder='Entrez votre adresse',
        type='text',
        style={'width': '60%', 'margin': '10px auto'}
    ),

    html.Button(
        'Rechercher',
        id='submit-button',
        style={
            'margin': '10px auto',
            'backgroundColor': '#ffc12b',
            'color': '#a5282b',
            'border': 'none',
            'padding': '10px 20px',
            'font-size': '18px',
            'cursor': 'pointer'
        }
    ),

    html.Div(id='resultat-parking', className='resultat-parking', style=styles),


    html.Div(style={'flex': '1'}, children=[
        html.H2("Visualisation de la disponibilité des vélos et des places pour remise des vélos.", style=styles),
        dcc.Tabs(id="tabs", value='tab-1', children=[
            dcc.Tab(label='Carte des parking', value='tab-0', style=inactive_tab_style,
                    selected_style=active_tab_style),
            dcc.Tab(label='Carte des vélos disponibles', value='tab-1', style=inactive_tab_style,
                    selected_style=active_tab_style),
            dcc.Tab(label='Carte des places disponibles pour remise des vélos', value='tab-2',
                    style=inactive_tab_style, selected_style=active_tab_style),
        ]),
        html.Div(id='tabs-content')
    ])

])

@app.callback(
    Output('tabs-content', 'children'),
    [Input('tabs', 'value'),
     Input('submit-button', 'n_clicks')],
    [State('adresse-depart', 'value')]
)
def render_content(tab, n_clicks, adresse_depart):
    if n_clicks and adresse_depart:
        if tab == 'tab-0' and 'fig_parkings' not in globals():
            return ''
        elif tab == 'tab-0':
            return html.Div([
                dcc.Graph(figure=fig_parkings)
            ])
        elif tab == 'tab-1':
            return html.Div([
                dcc.Graph(figure=fig_recup)
            ])
        elif tab == 'tab-2':
            return html.Div([
                dcc.Graph(figure=fig_remise)
            ])
    return html.Div()

# Callback pour afficher les résultats de recherche de parkings
@app.callback(
    Output('resultat-parking', 'children'),
    [Input('submit-button', 'n_clicks')],
    [State('adresse-depart', 'value')]
)

def afficher_resultats_parkings(n_clicks, adresse):
    if n_clicks is None:
        return ''
    else:
        parkings_df = calculate_closest_parkings(adresse)
        rows = [
            html.Tr([html.Td(parkings_df.iloc[i][col]) for col in parkings_df.columns])
            for i in range(len(parkings_df))
        ]
        return rows


if __name__ == '__main__':
    app.run_server(debug=True)
