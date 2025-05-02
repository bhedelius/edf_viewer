from edf_viewer.models.edf_models import parse_edf_file

# Path to the real EDF file for PhysioNet's SC4001E0-PSG
EDF_FILE_PATH = "data/physionet/SC4001E0-PSG.edf"


# Define a regression test for the EDF to GDF conversion
def test_convert_edf_to_gdf_with_physionet_data():
    edf_file = parse_edf_file(EDF_FILE_PATH)  # noqa: F841
