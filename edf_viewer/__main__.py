import argparse

from edf_viewer.app import start_app


def parse_arguments():
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


def main():
    args = parse_arguments()
    start_app(
        port=args.port,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
