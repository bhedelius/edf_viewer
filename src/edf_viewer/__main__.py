"""
This module provides a command-line interface (CLI) for starting the EDF Viewer app.

It allows the user to specify the port and enable debug mode when launching the Dash web application for visualizing EDF files.

Functions:
    parse_arguments():
        Parses command-line arguments passed to the script. Specifically, it handles arguments for setting the port
        on which the app will run and enabling debug mode.

    main():
        Entry point for the script. It parses the command-line arguments and starts the EDF Viewer app with the provided
        configuration (port and debug mode).
"""

import argparse

from edf_viewer.app import start_app


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for the EDF Viewer app.

    This function uses argparse to handle the following options:
    - `--port`: Specifies the port number on which the Dash app will run (default: 8050).
    - `--debug`: A flag to enable debug mode for the app (default: False).

    Returns:
        argparse.Namespace: The parsed arguments, including `port` and `debug`.
    """
    parser = argparse.ArgumentParser(description="Start the EDF Viewer app.")
    parser.add_argument(
        "--port",  # Optional argument to specify the port
        type=int,
        default=8050,  # Default port is 8050
        help="Port to run the Dash app on (default: 8050)",
    )
    parser.add_argument(
        "--debug",  # Optional argument for enabling debug mode
        action="store_true",  # This will store `True` if the flag is set
        help="Run the app in debug mode (default: False)",
    )
    return parser.parse_args()


def main() -> None:
    """
    The main entry point of the script.

    This function:
    - Parses command-line arguments.
    - Calls `start_app` to launch the EDF Viewer app with the specified port and debug mode.
    """
    args = parse_arguments()
    start_app(
        port=args.port,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
