"""
This module defines classes and methods to handle the parsing and processing of EDF (European Data Format) files.
It includes models for file metadata, signal metadata, data records, and the overall experiment, providing functionality
for reading EDF file content, parsing it, and transforming raw signal data into physical units. The code relies on the Pydantic
library for data validation and defines methods for extracting and transforming data from both raw binary and base64-encoded EDF files.

Classes:
    - EDFBaseModel: The base class for all EDF-related models with shared configurations.
    - FileMetadata: Represents file-level metadata in an EDF file (e.g., version, patient ID, recording details).
    - SignalMetadata: Represents metadata for each signal in the EDF file (e.g., label, range, number of samples).
    - DataRecord: Represents a single data record containing signal samples and optionally annotations.
    - Experiment: Represents an entire EDF experiment, including file metadata, signal metadata, and raw data records.

Functions:
    - _get_read_size: Helper function that determines the number of bytes to read for a given field based on its metadata.

Methods in Experiment:
    - from_reader: Parses an EDF experiment from a binary reader, extracting all relevant metadata and data records.
    - from_base64: Parses an EDF experiment from a base64-encoded string.
    - _determine_num_data_records: Infers the number of data records from the file size if the number is unknown.
    - get_time_series: Generates a time series for a specific signal based on its metadata.
    - get_signals: Extracts and transforms signal samples for specified data record indices and a given signal.
    - _transform_signals: Transforms raw digital signal values into physical units using the signal's metadata.

The module supports both binary and base64-encoded EDF files, providing efficient parsing and transformation of the raw signal data
into a usable format for further analysis.
"""

from __future__ import annotations

import base64
import io
import struct
from typing import Annotated, Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field

from edf_viewer.models.binary_reader import BinaryReader


def _get_read_size(name: str, field) -> int:
    """
    Determine the number of bytes to read for a given field based on its metadata.

    Args:
        name (str): The name of the field.
        field: The Pydantic model field object.

    Returns:
        int: Number of bytes to read for this field.

    Raises:
        ValueError: If the field lacks the necessary `read_size` metadata.
    """
    if field.annotation is str:
        return field.metadata[0].max_length
    json_schema_extra = getattr(field, "json_schema_extra")
    if json_schema_extra is None or "read_size" not in json_schema_extra:
        msg = f"Need `read_size` attribute for field `{name}`"
        raise ValueError(msg)
    return json_schema_extra["read_size"]


class EDFBaseModel(BaseModel):
    """Base classs for EDF-releated models with shared configurations."""

    model_config = {
        "extra": "forbid",  # Don't allow unexpected fields
        "frozen": True,  # Make immutable
        "arbitrary_types_allowed": True,
    }


class FileMetadata(EDFBaseModel):
    """
    Represents the file-level metadata in an EDF file, such as version, patient ID, and recording details.
    """

    version: str = Field(..., max_length=8)
    patient_id: str = Field(..., max_length=80)
    recording_id: str = Field(..., max_length=80)
    start_date: str = Field(..., max_length=8)  # You can parse to datetime separately
    start_time: str = Field(..., max_length=8)
    num_bytes_header_record: Annotated[
        int, Field(..., json_schema_extra={"read_size": 8})
    ]
    reserved: str = Field(..., max_length=44)
    num_data_records: Annotated[int, Field(..., json_schema_extra={"read_size": 8})]
    data_record_duration: Annotated[
        float, Field(..., json_schema_extra={"read_size": 8})
    ]
    num_signals: Annotated[int, Field(..., json_schema_extra={"read_size": 4})]

    @classmethod
    def from_reader(cls, binary_reader: BinaryReader) -> "FileMetadata":
        """
        Parse file-level metadata from the binary stream using the BinaryReader.

        Args:
            binary_reader (BinaryReader): The binary stream reader.

        Returns:
            FileMetadata: The parsed file metadata.

        Raises:
            ValueError: If a field is not typed.
        """
        values: dict[str, Any] = {}

        for name, field in cls.model_fields.items():
            field_type = field.annotation
            if field_type is None:
                msg = f"Field type needed for field {name}"
                raise ValueError(msg)
            size = _get_read_size(name, field)
            values[name] = field_type(binary_reader.read_ascii(size))

        return cls(**values)


class SignalMetadata(EDFBaseModel):
    """
    Represents metadata for a signal in an EDF file, including label, physical and digital range, and number of samples.
    """

    label: str = Field(..., max_length=16)
    transducer_type: str = Field(..., max_length=80)
    physical_dimension: str = Field(..., max_length=8)
    physical_min: Annotated[int, Field(..., json_schema_extra={"read_size": 8})]
    physical_max: Annotated[int, Field(..., json_schema_extra={"read_size": 8})]
    digital_min: Annotated[int, Field(..., json_schema_extra={"read_size": 8})]
    digital_max: Annotated[int, Field(..., json_schema_extra={"read_size": 8})]
    prefiltering: str = Field(..., max_length=80)
    num_samples: Annotated[int, Field(..., json_schema_extra={"read_size": 8})]
    reserved: str = Field(..., max_length=32)

    @classmethod
    def from_reader(
        cls, binary_reader: BinaryReader, num_signals: int
    ) -> list[SignalMetadata]:
        """
        Parse signal metadata for each signal from the binary stream.

        Args:
            binary_reader (BinaryReader): The binary stream reader.
            num_signals (int): Number of signals to read.

        Returns:
            list[SignalMetadata]: List of parsed signal metadata.

        Raises:
            ValueError: If a field is not typed.
        """
        field_data: dict[str, list[Any]] = {}
        for name, field in SignalMetadata.model_fields.items():
            field_type = field.annotation
            if field_type is None:
                msg = f"Field type needed for field {name}"
                raise ValueError(msg)
            size = _get_read_size(name, field)
            field_data[name] = [
                field_type(binary_reader.read_ascii(size)) for _ in range(num_signals)
            ]
        return [
            cls(**{field: field_data[field][i] for field, _ in field_data.items()})
            for i in range(num_signals)
        ]


class DataRecord(EDFBaseModel):
    """
    Represents a single data record in an EDF file, containing signal samples and optionally annotations.
    """

    signal_samples: list[list[int]]
    annotations: str | None = None

    @classmethod
    def from_reader(
        cls,
        binary_reader: BinaryReader,
        num_samples_per_signal: list[int],
        annotations_index: int | None = None,
    ) -> DataRecord:
        """
        Parse a single data record from the binary stream.

        Args:
            binary_reader (BinaryReader): The binary stream reader.
            num_samples_per_signal (list[int]): Number of samples for each signal.
            annotations_index (int | None): Index of the annotations signal, if any.

        Returns:
            DataRecord: Parsed data record including signal samples and optional annotations.
        """
        signal_samples: list[list[int]] = []
        annotations: str | None = None

        for i, num_samples in enumerate(num_samples_per_signal):
            raw_samples = binary_reader.read_bytes(num_samples * 2)
            samples = list(struct.unpack(f"<{num_samples}h", raw_samples))

            # If it's the annotations channel
            if i == annotations_index:
                # Annotations are stored as ASCII in 2-byte little-endian format, so decode:
                bytestring = b"".join(struct.pack("<h", s) for s in samples)
                annotations = bytestring.split(b"\x00", 1)[0].decode(
                    "ascii", errors="ignore"
                )
            else:
                signal_samples.append(samples)

        return DataRecord(signal_samples=signal_samples, annotations=annotations)


class Experiment(EDFBaseModel):
    """
    Represents an entire EDF experiment, including file metadata, signal metadata, and raw data records.
    """

    file_metadata: FileMetadata
    signal_metadatas: list[SignalMetadata]
    annotations_index: int | None
    num_data_records: int
    data_record_size: int
    signal_byte_offsets: NDArray[np.int_]
    raw_data_records: bytes

    @classmethod
    def from_reader(cls, binary_reader: BinaryReader) -> Experiment:
        """
        Parse an EDF experiment from a binary reader.

        Args:
            binary_reader (BinaryReader): The binary stream reader.

        Returns:
            Experiment: The parsed experiment object.

        Raises:
            ValueError: If EOF isn't reached when expected.
        """
        # Header
        file_metadata = FileMetadata.from_reader(binary_reader)
        signal_metadatas = SignalMetadata.from_reader(
            binary_reader, int(file_metadata.num_signals)
        )

        annotations_index = next(
            (
                i
                for i, signal_metadata in enumerate(signal_metadatas)
                if signal_metadata.label == "EDF Annotations"
            ),
            None,
        )

        signal_byte_offsets = np.cumsum(
            np.array(
                [
                    0,
                    *(
                        2 * signal_metadata.num_samples
                        for signal_metadata in signal_metadatas
                    ),
                ],
                dtype=int,
            )
        )

        data_record_size = signal_byte_offsets[-1]
        num_data_records = int(file_metadata.num_data_records)
        if num_data_records == -1:
            # Calculate num_data_records if it is unknown
            num_data_records = cls._determine_num_data_records(
                binary_reader=binary_reader,
                data_record_size=data_record_size,
                num_signals=len(signal_metadatas),
            )

        raw_data_records = binary_reader.read_bytes(num_data_records * data_record_size)
        if not binary_reader.is_eof():
            msg = "Haven't reached end of file"
            raise ValueError(msg)

        return cls(
            file_metadata=file_metadata,
            signal_metadatas=signal_metadatas,
            annotations_index=annotations_index,
            num_data_records=num_data_records,
            data_record_size=data_record_size,
            signal_byte_offsets=signal_byte_offsets,
            raw_data_records=raw_data_records,
        )

    @classmethod
    def from_base64(cls, b64_string: str) -> Experiment:
        """
        Construct an Experiment from a base64-encoded EDF string.

        Args:
            b64_string (str): Base64-encoded EDF file contents.

        Returns:
            Experiment: The parsed experiment object.
        """
        decoded = base64.b64decode(b64_string)
        bytes_io = io.BytesIO(decoded)
        binary_reader = BinaryReader(bytes_io)
        return Experiment.from_reader(binary_reader)

    @classmethod
    def _determine_num_data_records(
        cls,
        binary_reader: BinaryReader,
        data_record_size: int,
        num_signals: int,
    ) -> int:
        """
        Infer the number of data records from the file size.

        Args:
            binary_reader (BinaryReader): The binary stream reader.
            data_record_size (int): The size of each data record in bytes.
            num_signals (int): Number of signals.

        Returns:
            int: The inferred number of data records.

        Raises:
            ValueError: If the file size cannot be evenly divided into data records.
        """
        file_size = binary_reader.get_file_size()

        metadata_size = 256 + 256 * num_signals
        remaining_size = file_size - metadata_size

        if remaining_size % data_record_size != 0:
            msg = f"Unexpected file size. Unable to evenly divide {remaining_size} byte into {data_record_size} bytes per data record."
            raise ValueError(msg)
        return remaining_size // data_record_size

    def get_time_series(self, signal_index: int) -> NDArray[np.float64]:
        """
        Generate a time series array for the specified signal index.

        Parameters:
            signal_index (int): Index of the signal to generate the time series for.

        Returns:
            NDArray: A 1D NumPy array of time values (in seconds) for the signal.
        """
        num_samples = self.signal_metadatas[signal_index].num_samples
        data_record_duration = self.file_metadata.data_record_duration
        sampling_period = data_record_duration / num_samples
        return np.arange(0, data_record_duration, sampling_period, dtype=np.float64)

    def get_signals(
        self, data_record_indexes: list[int], signal_index: int
    ) -> NDArray[np.float64]:
        """
        Extract and convert raw signal samples for the given signal index and data record indices.

        Parameters:
            data_record_indexes (list[int]): List of data record indices to extract.
            signal_index (int): Index of the signal to extract.

        Returns:
            NDArray: A 2D NumPy array of shape (num_records, num_samples) containing
                        the transformed signal values in physical units.
        """
        signal_start_offset, signal_stop_offset = self.signal_byte_offsets[
            signal_index : signal_index + 2
        ]
        raw_signals = []

        for data_record_index in data_record_indexes:
            data_record_start = self.data_record_size * data_record_index
            signal_start = data_record_start + signal_start_offset
            signal_stop = data_record_start + signal_stop_offset
            raw_samples = self.raw_data_records[signal_start:signal_stop]
            raw_samples_array = np.frombuffer(raw_samples, dtype="<i2")
            raw_signals.append(raw_samples_array)

        raw_signals_array = np.array(raw_signals)
        signal_metadata = self.signal_metadatas[signal_index]
        return self._transform_signals(raw_signals_array, signal_metadata)

    @staticmethod
    def _transform_signals(
        raw_signals_array: NDArray[np.float64],
        signal_metadata: SignalMetadata,
    ) -> NDArray[np.float64]:
        """
        Convert raw digital signal values to physical units using the signal's metadata.

        Args:
            raw_signals_array (NDArray): Array of raw signal samples in digital format.
            signal_metadata (SignalMetadata): Metadata containing the physical and digital min/max values.

        Returns:
            NDArray: The transformed signal values in physical units.
        """
        # Retrieve physical and digital min/max values from signal metadata
        physical_min = signal_metadata.physical_min
        physical_max = signal_metadata.physical_max
        digital_min = signal_metadata.digital_min
        digital_max = signal_metadata.digital_max

        # Compute the scale factor based on the range of the physical and digital values
        scale_factor = (physical_max - physical_min) / (digital_max - digital_min)

        # Map digital values to the physical range
        return physical_min + (raw_signals_array - digital_min) * scale_factor
