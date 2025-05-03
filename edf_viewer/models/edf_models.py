from __future__ import annotations

import base64
import io
import struct
from typing import Annotated, Any

import numpy as np
from pydantic import BaseModel, Field

from edf_viewer.models.binary_reader import BinaryReader


def _get_field_size(name, field):
    if field.annotation is str:
        return field.metadata[0].max_length
    json_schema_extra = getattr(field, "json_schema_extra")
    if json_schema_extra is None or "read_size" not in json_schema_extra:
        msg = f"Need `read_size` attribute for field `{name}`"
        raise ValueError(msg)
    return json_schema_extra["read_size"]


class FileMetadata(BaseModel):
    version: str = Field(..., max_length=8)
    patient_id: str = Field(..., max_length=80)
    recording_id: str = Field(..., max_length=80)
    start_date: str = Field(..., max_length=8)  # You can parse to datetime separately
    start_time: str = Field(..., max_length=8)
    num_bytes_header_record: Annotated[int, Field(..., json_schema_extra={"read_size": 8})]
    reserved: str = Field(..., max_length=44)
    num_data_records: Annotated[int, Field(..., json_schema_extra={"read_size": 8})]
    data_record_duration: Annotated[float, Field(..., json_schema_extra={"read_size": 8})]
    num_signals: Annotated[int, Field(..., json_schema_extra={"read_size": 4})]

    @classmethod
    def from_file(cls, binary_reader: "BinaryReader") -> "FileMetadata":
        values: dict[str, Any] = {}

        for name, field in cls.model_fields.items():
            field_type = field.annotation
            if field_type is None:
                msg = f"Field type needed for field {name}"
                raise ValueError(msg)
            size = _get_field_size(name, field)
            values[name] = field_type(binary_reader.read_ascii(size))

        return cls(**values)


class SignalMetadata(BaseModel):
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
    def from_file(cls, binary_reader: BinaryReader, num_signals: int) -> list[SignalMetadata]:
        field_data: dict[str, list[Any]] = {}
        for name, field in SignalMetadata.model_fields.items():
            field_type = field.annotation
            if field_type is None:
                msg = f"Field type needed for field {name}"
                raise ValueError(msg)
            size = _get_field_size(name, field)
            field_data[name] = [field_type(binary_reader.read_ascii(size)) for _ in range(num_signals)]
        return [cls(**{field: field_data[field][i] for field, _ in field_data.items()}) for i in range(num_signals)]


class DataRecord(BaseModel):
    signal_samples: list[list[int]]
    annotations: str | None = None

    @classmethod
    def from_file(
        cls,
        binary_reader: BinaryReader,
        num_samples_per_signal: list[int],
        annotations_index: int | None = None,
    ) -> DataRecord:
        signal_samples: list[list[int]] = []
        annotations: str | None = None

        for i, num_samples in enumerate(num_samples_per_signal):
            raw_samples = binary_reader.read_bytes(num_samples * 2)
            samples = list(struct.unpack(f"<{num_samples}h", raw_samples))

            # If it's the annotations channel
            if i == annotations_index:
                # Annotations are stored as ASCII in 2-byte little-endian format, so decode:
                bytestring = b"".join(struct.pack("<h", s) for s in samples)
                annotations = bytestring.split(b"\x00", 1)[0].decode("ascii", errors="ignore")
            else:
                signal_samples.append(samples)

        return DataRecord(signal_samples=signal_samples, annotations=annotations)


class Experiment(BaseModel):
    file_metadata: FileMetadata
    signal_metadatas: list[SignalMetadata]
    annotations_index: int | None
    num_data_records: int
    data_record_size: int
    signal_byte_offsets: Any  # np.array doesn't work with Pydantic
    raw_data_records: bytes

    @classmethod
    def from_file(cls, binary_reader: BinaryReader) -> Experiment:
        # Header
        file_metadata = FileMetadata.from_file(binary_reader)
        signal_metadatas = SignalMetadata.from_file(binary_reader, int(file_metadata.num_signals))

        annotations_index = next(
            (i for i, signal_metadata in enumerate(signal_metadatas) if signal_metadata.label == "EDF Annotations"),
            None,
        )

        signal_byte_offsets = np.cumsum(
            np.array(
                [0, *(2 * signal_metadata.num_samples for signal_metadata in signal_metadatas)],
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
    def from_upload(cls, content_string: str) -> Experiment:
        decoded = base64.b64decode(content_string)
        bytes_io = io.BytesIO(decoded)
        binary_reader = BinaryReader(bytes_io)
        return Experiment.from_file(binary_reader)

    @classmethod
    def _determine_num_data_records(
        cls,
        binary_reader: BinaryReader,
        data_record_size: int,
        num_signals: int,
    ) -> int:
        file_size = binary_reader.get_file_size()

        metadata_size = 256 + 256 * num_signals
        remaining_size = file_size - metadata_size

        if remaining_size % data_record_size != 0:
            msg = f"Unexpected file size. Unable to evenly divide {remaining_size} byte into {data_record_size} bytes per data record."
            raise ValueError(msg)
        return remaining_size // data_record_size

    def get_time_series(self, signal_index: int) -> np.ndarray:
        """
        Generate a time series array for the specified signal index.

        Parameters:
            signal_index (int): Index of the signal to generate the time series for.

        Returns:
            np.ndarray: A 1D NumPy array of time values (in seconds) for one data record.
        """
        num_samples = self.signal_metadatas[signal_index].num_samples
        data_record_duration = self.file_metadata.data_record_duration
        sampling_period = data_record_duration / num_samples
        return np.arange(0, data_record_duration, sampling_period)

    def get_signals(self, data_record_indexes: list[int], signal_index: int) -> np.ndarray:
        """
        Extract and convert raw signal samples for the given signal index and data record indices.

        Parameters:
            data_record_indexes (list[int]): List of data record indices to extract.
            signal_index (int): Index of the signal to extract.

        Returns:
            np.ndarray: A 2D NumPy array of shape (num_records, num_samples) containing
                        the transformed signal values in physical units.
        """

        signal_start_offset, signal_stop_offset = self.signal_byte_offsets[signal_index : signal_index + 2]
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
        raw_signals_array: np.ndarray,
        signal_metadata: SignalMetadata,
    ) -> np.ndarray:
        physical_min = signal_metadata.physical_min
        physical_max = signal_metadata.physical_max
        digital_min = signal_metadata.digital_min
        digital_max = signal_metadata.digital_max

        scale_factor = (physical_max - physical_min) / (digital_max - digital_min)
        return physical_min + (raw_signals_array - digital_min) * scale_factor
