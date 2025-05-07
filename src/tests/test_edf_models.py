import base64
from pathlib import Path

from edf_viewer.models.binary_reader import BinaryReader
from edf_viewer.models.edf_models import Experiment

# Path to the EDF file for PhysioNet's SC4001E0-PSG
EDF_FILE_PATH = "data/physionet/SC4001E0-PSG.edf"


def encode_edf_file_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        encoded_string = base64.b64encode(f.read()).decode("utf-8")
    return encoded_string


def test_convert_edf_to_gdf_with_physionet_data_from_base64():
    edf_file_path = Path(EDF_FILE_PATH)
    if not edf_file_path.exists():
        msg = f"File '{edf_file_path}' does not exist"
        raise FileNotFoundError(msg)
    b64_string = encode_edf_file_to_base64(str(edf_file_path))
    experiment = Experiment.from_base64(b64_string)
    experiment.get_signals([0, 1], 0)


# Define a regression test for the EDF to GDF conversion
def test_convert_edf_to_gdf_with_physionet_data():
    with (
        Path(EDF_FILE_PATH).open("rb") as f,
        BinaryReader(f) as binary_reader,
    ):
        experiment = Experiment.from_reader(binary_reader)
    experiment.get_signals([0, 1], 0)
