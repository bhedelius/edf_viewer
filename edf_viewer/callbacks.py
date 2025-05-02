# callbacks.py

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
def on_file_upload(uploaded_file: str):
    """Upload a new EDF file and populate dropdowns."""

    if uploaded_file is None:
        raise ValueError("No uploaded file found.")

    # Decode the uploaded file
    _, content_string = uploaded_file.split(",", 1)
    experiment = Experiment.from_upload(
        content_string
    )  # Load the experiment object once

    # Create dropdown options
    data_record_options = [
        {"label": f"Record {i}", "value": i} for i in range(len(experiment.records))
    ]
    signal_options = [
        {"label": sm.label, "value": i}
        for i, sm in enumerate(experiment.header.signal_metadatas)
        if not sm.label.startswith("EDF Annotations")
    ]

    # Set the default value to the first option if available
    data_record_value = data_record_options[0]["value"] if data_record_options else None
    signal_value = signal_options[0]["value"] if signal_options else None

    # Prepare metadata
    file_metadata = experiment.header.file_metadata
    metadata_tuple = (
        f"Patient ID: {file_metadata.patient_id}",
        f"Recording ID: {file_metadata.recording_id}",
        f"Start date (dd.mm.yy): {file_metadata.start_date}",
        f"Start time (hh.mm.ss): {file_metadata.start_time}",
    )
    metadata = [
        html.P(
            line.rstrip(), style={"margin": "0", "padding": "0", "line-height": "1.2"}
        )
        for line in metadata_tuple
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
        Output("signal-annotations", "children"),
    ],
    Input("data-record-dropdown", "value"),
    Input("signal-dropdown", "value"),
    Input("edf-store", "data"),
)
def update_plot_and_metadata(
    data_record_index: int | None,
    signal_index: int | None,
    content_string: str,
):
    """
    Update the plot, metadata, and annotations based on the selected data record and signal.

    Args:
        data_record_index (int | None): The index of the selected data record. If `None`,
            no update is made.
        signal_index (int | None): The index of the selected signal. If `None`, no update
            is made.
        content_string (str | None): The content string representing the uploaded EDF file.
                If `None`, the function returns no updates.

    Returns:
        tuple: A tuple containing:
            - A Plotly figure for the selected signal, or an empty figure if no valid data is available.
            - A list of HTML paragraphs containing metadata for the selected signal.
            - A string of annotations associated with the selected signal or a default message if no annotations are available.

    Notes:
        - If any of the input values are `None` or the `experiment` object cannot be loaded,
          the function will return default values (empty plot, message prompting user to select a signal, and a default annotation message).
    """
    if content_string is None:
        raise ValueError("No experimental data found.")
    if data_record_index is None:
        raise ValueError("No data record selected")
    if signal_index is None:
        raise ValueError("No signal selected")

    # Load the experiment object
    experiment = Experiment.from_upload(content_string)

    # Extract data record and signal information
    data_record = experiment.records[data_record_index]
    signal_values = data_record.signal_samples[signal_index]

    # Create a plot for the selected signal
    signal_metadata: SignalMetadata = experiment.header.signal_metadatas[signal_index]
    figure = go.Figure(
        data=[
            go.Scatter(
                x=list(range(len(signal_values))),
                y=scale_signal_to_physical(
                    signal_values,
                    signal_metadata,
                ),
            )
        ],
        layout={
            "title": {
                "text": f"Signal: {signal_metadata.label.rstrip()}",
                "x": 0.5,
            },
            "yaxis_title": f"Amplitude ({signal_metadata.physical_dimension.rstrip()})",
        },
    )

    # Fetch signal metadata
    metadata_tuple = (
        f"Transducer type: {signal_metadata.transducer_type}",
        f"Prefiltering: {signal_metadata.prefiltering}",
        f"Reserved: {signal_metadata.reserved}",
    )
    metadata = [
        html.P(
            line.rstrip(), style={"margin": "0", "padding": "0", "line-height": "1.2"}
        )
        for line in metadata_tuple
    ]

    return figure, metadata, data_record.annotations


def scale_signal_to_physical(
    signal_values: list[int],
    signal_metadata: SignalMetadata,
):
    """
    Scales digital signal values to their corresponding physical values using metadata.

    Args:
        signal_values (list[int]): A list of digital signal values (as integers) to be scaled.
        signal_metadata (SignalMetadata): Metadata containing the signal's digital and physical
            minimum and maximum values.

    Returns:
        list[float]: A list of scaled physical signal values corresponding to the input digital
            signal values.
    """
    # Convert min/max values once to floats
    digital_min = float(signal_metadata.digital_min)
    digital_max = float(signal_metadata.digital_max)
    physical_min = float(signal_metadata.physical_min)
    physical_max = float(signal_metadata.physical_max)

    # Calculate the scaling factor (physical range / digital range)
    scale_factor = (physical_max - physical_min) / (digital_max - digital_min)

    # Return scaled signal values
    return [
        physical_min + (value - digital_min) * scale_factor for value in signal_values
    ]
