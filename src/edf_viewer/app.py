"""
This module sets up and runs a Dash web application for visualizing and analyzing EDF (European Data Format) files.

The application allows users to upload EDF files, select data records and signals, and view related signal metadata,
annotations, and plots. The layout consists of file upload components, dropdowns for selecting data records and signals,
and display areas for metadata, annotations, and signal plots.

Functions:
    start_app(port: int = 8050, debug: bool = False):
        Initializes and starts the Dash application, configuring the layout and defining the structure of the user interface.
        The app allows interaction with EDF files and displays metadata, annotations, and visualizations.

    Args:
        port (int): The port on which the app will run. Defaults to 8050.
        debug (bool): If True, enables debugging. Defaults to False.
"""

import dash
import dash_bootstrap_components as dbc  # type: ignore
from dash import dcc, html

from edf_viewer.callbacks import (
    on_file_upload,  # noqa: F401 used implicitly
    update_plot_and_metadata,  # noqa: F401 used implicitly
)


def start_app(port: int = 8050, debug: bool = False) -> None:
    """
    Initialize and start the Dash web application for visualizing EDF files.

    This function creates a Dash app, sets the layout, and defines the structure
    of the web interface. The app allows users to upload EDF files, select data
    records and signals, and view signal metadata, annotations, and plots.

    Args:
        port (int): The port on which to run the app. Default is 8050.
        debug (bool): Flag to enable debugging. Default is False.
    """
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="EDF Viewer",
    )

    app.layout = html.Div(
        style={
            "maxWidth": "1000px",
            "margin": "0 auto",
            "padding": "15px",
            "fontFamily": "Arial, sans-serif",
            "fontSize": "1em",
        },
        children=[
            dbc.Alert(
                id="error-alert",
                color="danger",
                children="An error occurred.",
                is_open=False,
                duration=5000,
            ),
            dcc.Store(id="edf-store"),
            dcc.Store(id="experiment-store", storage_type="memory"),
            html.H1(
                "EDF Viewer",
                style={
                    "textAlign": "center",
                    "marginBottom": "20px",
                    "fontSize": "2em",
                },
            ),
            # Upload + Dropdowns
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "marginBottom": "25px",
                },
                children=[
                    html.Div(
                        dcc.Upload(
                            id="upload-file",
                            children=html.Button(
                                "Upload EDF File",
                                style={"padding": "10px 20px", "fontSize": "16px"},
                            ),
                            multiple=False,
                        ),
                        style={"width": "30%", "textAlign": "center"},
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Select Data Record",
                                htmlFor="data-record-dropdown",
                                style={
                                    "marginBottom": "5px",
                                    "fontSize": "1.1em",
                                },
                            ),
                            dcc.Dropdown(
                                id="data-record-dropdown",
                                placeholder="Select Data Record",
                                style={"width": "100%"},
                                multi=True,
                            ),
                        ],
                        style={"width": "30%"},
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Select Signal",
                                htmlFor="signal-dropdown",
                                style={
                                    "marginBottom": "5px",
                                    "fontSize": "1.1em",
                                },
                            ),
                            dcc.Dropdown(
                                id="signal-dropdown",
                                placeholder="Select Signal",
                                style={"width": "100%"},
                            ),
                        ],
                        style={"width": "30%"},
                    ),
                ],
            ),
            html.Hr(style={"margin": "20px 0"}),
            # File Metadata + Annotations + Signal Metadata
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "marginBottom": "25px",
                },
                children=[
                    html.Div(
                        children=[
                            html.H4(
                                "File Metadata",
                                style={
                                    "borderBottom": "1px solid #ccc",
                                    "marginBottom": "10px",
                                    "fontSize": "1.2em",
                                },
                            ),
                            html.Div(
                                id="file-metadata",
                                style={
                                    "fontSize": "1em",
                                    "lineHeight": "1.5",
                                },
                            ),
                        ],
                        style={"width": "30%"},
                    ),
                    html.Div(
                        children=[
                            html.H4(
                                "Annotations",
                                style={
                                    "borderBottom": "1px solid #ccc",
                                    "marginBottom": "10px",
                                    "fontSize": "1.2em",
                                },
                            ),
                            html.Div(
                                id="signal-annotations",
                                style={
                                    "fontSize": "1em",
                                    "lineHeight": "1.5",
                                },
                            ),
                        ],
                        style={"width": "30%"},
                    ),
                    html.Div(
                        children=[
                            html.H4(
                                "Signal Metadata",
                                style={
                                    "borderBottom": "1px solid #ccc",
                                    "marginBottom": "10px",
                                    "fontSize": "1.2em",
                                },
                            ),
                            html.Div(
                                id="signal-metadata",
                                style={
                                    "fontSize": "1em",
                                    "lineHeight": "1.5",
                                },
                            ),
                        ],
                        style={"width": "30%"},
                    ),
                ],
            ),
            # Signal Plot
            dcc.Graph(
                id="signal-plot",
                style={
                    "padding": "10px",
                    "margin": "0px",
                    "height": "450px",
                },
            ),
        ],
    )

    app.run(port=port, debug=debug)
