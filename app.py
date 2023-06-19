# Importer les bibliothèques nécessaires
from dash import Dash, html, dcc, dash_table
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd
import requests
import pytz

# Connection à l'API de disponibilité des vélos Toulouse
url = 'https://transport.data.gouv.fr/gbfs/toulouse/gbfs.json'

try:
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    df_source = pd.DataFrame(data)
except requests.exceptions.RequestException as e:
    print('Une erreur est survenue lors de l\'appel à l\'API :', e)

# Lien Internet vers le fichier JSON
lien_json = "https://transport.data.gouv.fr/gbfs/toulouse/station_information.json"
lien_json2 = "https://transport.data.gouv.fr/gbfs/toulouse/station_status.json"

# Charger le fichier JSON en tant que DataFrame
df_info = pd.read_json(lien_json)
df_statut = pd.read_json(lien_json2)

stations_list = df_info['data'].values[0]
statut_list = df_statut['data'].values[0]

# Convertir la liste de dictionnaires en DataFrame pour les informations sur les stations
df_stations = pd.DataFrame(stations_list)

# Convertir la liste de dictionnaires en DataFrame pour les disponibilités
df_disponibilites = pd.DataFrame(statut_list)

# Convertir la colonne last_reported en objets datetime au fuseau horaire UTC
df_disponibilites['last_reported'] = pd.to_datetime(df_disponibilites['last_reported'], unit='s').dt.tz_localize('UTC')

# Convertir la colonne last_reported en heure locale Paris
paris_tz = pytz.timezone('Europe/Paris')
df_disponibilites['last_reported'] = df_disponibilites['last_reported'].dt.tz_convert(paris_tz)

# Formater la colonne last_reported en une chaîne de caractères sans indication de fuseau horaire
df_disponibilites['last_reported'] = df_disponibilites['last_reported'].dt.strftime('%d/%m/%Y %H:%M:%S')

# Fusionner les DataFrames df_stations et df_disponibilites
df_velo_temps_reel = pd.merge(df_stations, df_disponibilites, how="left", on='station_id')

# Supprimer le code station de la colonne 'name' => démarrer au 8ème caractère
df_velo_temps_reel['name'] = df_velo_temps_reel['name'].apply(lambda x: x[8:])

# Configuration des couleurs personnalisées pour le graphique
custom_colors = [[0.0, "rgb(255, 0, 0)"], [0.05, "rgb(255,163,49)"],[0.25, "rgb(0, 255, 0)"],[1.0, "rgb(0, 255, 0)"]]

# Création de la carte pour les vélos disponibles
fig_recup = go.Figure(data=go.Scattermapbox(
    lat=df_velo_temps_reel['lat'],
    lon=df_velo_temps_reel['lon'],
    mode='markers',
    marker=dict(
        size=8,
        color=df_velo_temps_reel['num_bikes_available'],
        colorscale='RdYlBu',
        cmin=df_velo_temps_reel['num_bikes_available'].min(),
        cmax=df_velo_temps_reel['num_bikes_available'].max(),
        colorbar=dict(
            title='Nombre de vélos disponibles'
        )
    ),
    hovertemplate='<b>%{customdata[0]}</b><br><br>' +
                  'Adresse: %{customdata[1]}<br>' +
                  'Nombre de vélos maximum: %{customdata[2]}<br>' +
                  'Dernière mise à jour: %{customdata[3]}<br>' +
                  'Nombre de vélos disponibles: %{customdata[4]}',
    customdata=df_velo_temps_reel[['name', 'address', 'capacity', 'last_reported', 'num_bikes_available']],
))

fig_recup.update_layout(
    mapbox=dict(
        style='carto-positron',
        center=dict(lat=43.599, lon=1.436),
        zoom=12
    ),
    width=1000,
    height=600,
    coloraxis_colorscale=custom_colors,
    hoverlabel=dict(
        bgcolor='white',
        font_size=12,
        font_family='Arial'
    )
)

# Création de la carte pour les places disponibles pour remise des vélos
fig_remise = go.Figure(data=go.Scattermapbox(
    lat=df_velo_temps_reel['lat'],
    lon=df_velo_temps_reel['lon'],
    mode='markers',
    marker=dict(
        size=8,
        color=df_velo_temps_reel['num_docks_available'],
        colorscale='RdYlBu',
        cmin=df_velo_temps_reel['num_docks_available'].min(),
        cmax=df_velo_temps_reel['num_docks_available'].max(),
        colorbar=dict(
            title='Nombre de places disponibles'
        )
    ),
    hovertemplate='<b>%{customdata[0]}</b><br><br>' +
                  'Adresse: %{customdata[1]}<br>' +
                  'Nombre de vélos maximum: %{customdata[2]}<br>' +
                  'Dernière mise à jour: %{customdata[3]}<br>' +
                  'Nombre de places disponibles: %{customdata[5]}',
    customdata=df_velo_temps_reel[['name', 'address', 'capacity', 'last_reported', 'num_bikes_available', 'num_docks_available']],
))

fig_remise.update_layout(
    mapbox=dict(
        style='carto-positron',
        center=dict(lat=43.599, lon=1.436),
        zoom=12
    ),
    width=1000,
    height=600,
    coloraxis_colorscale=custom_colors,
    hoverlabel=dict(
        bgcolor='white',
        font_size=12,
        font_family='Arial'
    )
)

# Création de l'application Dash
app = Dash(__name__)

# Styles CSS personnalisés pour le titre et l'arrière-plan
styles = {
    'backgroundColor': 'red',
    'color': 'gold',
    'textAlign': 'center',
    'padding': '20px'
}

# Création des onglets
app.layout = html.Div(children=[
    html.H1(children='Carte en temps réel des vélos à Toulouse', style=styles),

    html.Div(children='''
        Visualisation de la disponibilité des vélos et des places pour remise des vélos.
    '''),

    dcc.Tabs(id='tabs', value='tab-1', children=[
        dcc.Tab(label='Places disponibles', value='tab-1'),
        dcc.Tab(label='Vélos disponibles', value='tab-2'),
    ]),

    html.Div(id='tab-content')
])


@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs', 'value')]
)
def render_content(tab):
    if tab == 'tab-1':
        return dcc.Graph(id='map-remise', figure=fig_remise)
    elif tab == 'tab-2':
        return dcc.Graph(id='map-recup', figure=fig_recup)


if __name__ == '__main__':
    app.run_server(debug=True)
