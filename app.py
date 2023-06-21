import dash
from dash import dcc
from dash import html
import pandas as pd
import plotly.express as px
import requests
from dash.dependencies import Input, Output, State
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

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

# Création de la carte pour les places disponibles pour remise des vélos
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

# Définir le titre de l'application
app.title = "Transports Toulouse VCA"

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

# Création des onglets
app.layout = html.Div(style={'backgroundColor': styles['backgroundColor']}, children=[
    html.H1(children="Transports Toulouse VCA", style=styles),

    html.Hr(),
    html.Hr(),
   
    html.H2("Trouver le parking le plus proche", style=styles),
    html.Div(
        children=[
            dcc.Input(
                id='adresse-depart',
                type='text',
                placeholder='Entrez votre adresse de départ',
                style={'width': '300px', 'margin': '0 auto', 'font-size': '18px', 'color': '#ffc12b'}
            ),
            html.Button(
                'Trouver',
                id='submit-button',
                n_clicks=0,
                style={'display': 'block', 'margin': '20px auto', 'font-size': '18px'}
            )
        ],
        style={'text-align': 'center'}
    ),
    html.Div(
        id='output-container-button',
        children='Entrez votre adresse de départ et cliquez sur le bouton pour trouver le parking le plus proche.',
        style={'color': '#ffc12b', 'font-size': '18px'}
    ),

    html.Hr(),

    html.H2("Visualisation de la disponibilité des vélos et des places pour remise des vélos.", style=styles),
    dcc.Tabs(id="tabs", value='tab-1', children=[
        dcc.Tab(label='Carte des vélos disponibles', value='tab-1', style=inactive_tab_style,
                selected_style=active_tab_style),
        dcc.Tab(label='Carte des places disponibles pour remise des vélos', value='tab-2',
                style=inactive_tab_style, selected_style=active_tab_style),
    ]),
    html.Div(id='tabs-content')
])


@app.callback(
    Output('tabs-content', 'children'),
    [Input('tabs', 'value')]
)
def render_content(tab):
    if tab == 'tab-1':
        return html.Div([
            dcc.Graph(figure=fig_recup)
        ])
    elif tab == 'tab-2':
        return html.Div([
            dcc.Graph(figure=fig_remise)
        ])


@app.callback(
    Output('output-container-button', 'children'),
    [Input('submit-button', 'n_clicks')],
    [State('adresse-depart', 'value')]
)
def update_output(n_clicks, adresse_depart):
    if n_clicks > 0:
        if adresse_depart:
            geolocator = Nominatim(user_agent="geoapiExercises")
            location = geolocator.geocode(adresse_depart)
            user_coordinates = (location.latitude, location.longitude)
            distances = df_velo_temps_reel.apply(lambda row: geodesic(user_coordinates, (row['lat'], row['lon'])),
                                                 axis=1)
            distances = distances.fillna(float('inf'))
            distances_numeric = distances.apply(lambda x: x.meters)  # Convert distances to numeric values
            closest_station_index = distances_numeric.idxmin()
            closest_station = df_velo_temps_reel.loc[closest_station_index]
            return html.Div([
                html.P(f"Le parking le plus proche de votre adresse de départ est : {closest_station['name']} ({closest_station['address']})")
            ])
        else:
            return html.Div([
                html.P('Veuillez entrer une adresse de départ.')
            ])
    else:
        return html.Div([
            html.P('Entrez votre adresse de départ et cliquez sur le bouton pour trouver le parking le plus proche.')
        ])




if __name__ == '__main__':
    app.run_server(debug=True)
