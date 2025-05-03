from pathlib import Path

from models.binary_reader import BinaryReader
from edf_viewer.models.edf_models import Experiment

# Path to the real EDF file for PhysioNet's SC4001E0-PSG
EDF_FILE_PATH = "data/physionet/SC4001E0-PSG.edf"


# Define a regression test for the EDF to GDF conversion
def test_convert_edf_to_gdf_with_physionet_data():
    edf_file_path = Path(EDF_FILE_PATH)
    if not edf_file_path.exists():
        msg = f"File '{edf_file_path}' does not exist"
        raise FileNotFoundError(msg)

    with Path(edf_file_path).open("rb") as f:
        binary_reader = BinaryReader(f)
        experiment = Experiment.from_file(binary_reader)
    experiment.get_signals([0, 1], 0)
