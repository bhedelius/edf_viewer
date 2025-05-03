from datetime import datetime

import plotly.graph_objs as go
from dash import Input, Output, callback, html, set_props


from edf_viewer.models.edf_models import Experiment, SignalMetadata


def handle_error(err: Exception):
    set_props(
        "error-alert",
        {
            "children": str(err),
            "is_open": True,
        },
    )


@callback(
    [
        Output("data-record-dropdown", "options"),
        Output("data-record-dropdown", "value"),
        Output("signal-dropdown", "options"),
        Output("signal-dropdown", "value"),
        Output("file-metadata", "children"),
        Output("edf-store", "data"),
    ],
    Input("upload-file", "contents"),
    prevent_initial_call=True,
    on_error=handle_error,
)
def on_file_upload(uploaded_file: str) -> tuple:
    """
    Handles the upload of an EDF file and initializes UI elements with its data.

    Args:
        uploaded_file (str): The base64-encoded contents of the uploaded EDF file.

    Returns:
        tuple: A tuple containing:
            - list[dict]: Dropdown options for data records (label and value pairs).
            - int | None: Default selected data record index.
            - list[dict]: Dropdown options for signal selections.
            - int | None: Default selected signal index.
            - list[html.P]: Formatted file metadata paragraphs.
            - str: The raw base64 content string used to re-parse the EDF file later.

    Raises:
        ValueError: If no uploaded file is found or the content string is malformed.
    """

    if uploaded_file is None:
        raise ValueError("No uploaded file found.")

    # Decode the uploaded file
    _, content_string = uploaded_file.split(",", 1)
    experiment = Experiment.from_upload(content_string)  # Load the experiment object once

    # Create dropdown options
    data_record_options = [{"label": f"Record {i}", "value": i} for i in range(experiment.num_data_records)]
    signal_options = [
        {"label": sm.label, "value": i}
        for i, sm in enumerate(experiment.signal_metadatas)
        if not sm.label.startswith("EDF Annotations")
    ]

    # Set the default value to the first option if available
    data_record_value = data_record_options[0]["value"] if data_record_options else None
    signal_value = signal_options[0]["value"] if signal_options else None

    # Prepare metadata
    file_metadata = experiment.file_metadata
    dt_str = f"{file_metadata.start_date} {file_metadata.start_time}"
    dt = datetime.strptime(dt_str, "%d.%m.%y %H.%M.%S")
    formatted_date = dt.strftime("%B %-d, %Y")  # American-style date (e.g., "April 15, 2025")
    formatted_time = dt.strftime("%-I:%M:%S %p")
    metadata_tuple = (
        f"Patient ID: {file_metadata.patient_id}",
        f"Recording ID: {file_metadata.recording_id}",
        f"Start date: {formatted_date}",
        f"Start time: {formatted_time}",
    )
    metadata = [
        html.P(line.rstrip(), style={"margin": "0", "padding": "0", "line-height": "1.2"}) for line in metadata_tuple
    ]

    return (
        data_record_options,
        data_record_value,
        signal_options,
        signal_value,
        metadata,
        content_string,
    )


@callback(
    [
        Output("signal-plot", "figure"),
        Output("signal-metadata", "children"),
        # Output("signal-annotations", "children"),  # TODO: Update this
    ],
    Input("data-record-dropdown", "value"),
    Input("signal-dropdown", "value"),
    Input("edf-store", "data"),
)
def update_plot_and_metadata(
    data_record_indexes: list[int] | int,
    signal_index: int | None,
    content_string: str,
):
    """
    Update the plot and metadata based on the selected data record and signal.

    Args:
        data_record_indexes (list[int] | int): The index or indices of the selected data
            record(s). If multiple records are selected, they are provided as a list.
            If a single record is selected, it is provided as an integer.
        signal_index (int | None): The index of the selected signal. If `None`, no update
            is made, and the function returns no updates.
        content_string (str): The content string representing the uploaded EDF file.
            This is the base64-encoded file that was uploaded and is required to extract
            signal data.

    Returns:
        tuple: A tuple containing:
            - figure (plotly.graph_objects.Figure): The Plotly figure displaying the signal
              plot for the selected data record(s).
            - metadata (list[html.P]): A list of HTML paragraphs containing metadata for
              the selected signal, such as transducer type, prefiltering, and reserved fields.

    Raises:
        ValueError: If no signal is selected or if the content string is `None`.
    """
    if content_string is None:
        raise ValueError("No experimental data found.")
    if signal_index is None:
        raise ValueError("No signal selected")
    if isinstance(data_record_indexes, int):
        data_record_indexes = [data_record_indexes]

    # Load the experiment object
    experiment = Experiment.from_upload(content_string)

    # Extract data record and signal information
    time_series = experiment.get_time_series(signal_index)
    signal_values = experiment.get_signals(data_record_indexes, signal_index)

    # Create a plot for the selected signal
    traces = [
        go.Scatter(
            x=time_series,
            y=signal_values[i],  # Select the signal values for this data record
            mode="lines",  # Use lines to connect the points
            name=f"Data Record {data_record_indexes[i]}",  # Use the data record index as the legend name
        )
        for i in range(signal_values.shape[0])  # Loop over the data record dimension
    ]
    signal_metadata: SignalMetadata = experiment.signal_metadatas[signal_index]
    figure = go.Figure(
        data=traces,
        layout={
            "title": {
                "text": f"Signal: {signal_metadata.label.rstrip()}",
                "x": 0.5,
            },
            "xaxis_title": "time (sec)",
            "yaxis_title": f"Amplitude ({signal_metadata.physical_dimension.rstrip()})",
            "legend": {
                "title": "Data Records",
            },
        },
    )

    # Fetch signal metadata
    metadata_tuple = (
        f"Transducer type: {signal_metadata.transducer_type}",
        f"Prefiltering: {signal_metadata.prefiltering}",
        f"Reserved: {signal_metadata.reserved}",
    )
    metadata = [
        html.P(line.rstrip(), style={"margin": "0", "padding": "0", "line-height": "1.2"}) for line in metadata_tuple
    ]

    return figure, metadata
