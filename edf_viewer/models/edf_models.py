from __future__ import annotations
import base64
import io
import struct
from pathlib import Path

from edf_viewer.models.binary_reader import BinaryReader
from pydantic import BaseModel, Field


def parse_edf_file(edf_file_path: str | Path) -> Experiment:
    """Reads an EDF file from the specified path and returns an EDFFile instance.

    Args:
        edf_file_path (str | Path): Path to the EDF file.

    Returns:
        EDFFile: An instance of the EDFFile class with data from the file.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    edf_file_path = Path(edf_file_path)
    if not edf_file_path.exists():
        msg = f"File '{edf_file_path}' does not exist"
        raise FileNotFoundError(msg)

    with Path(edf_file_path).open("rb") as f:
        binary_reader = BinaryReader(f)
        return Experiment.from_file(binary_reader)


class FileMetadata(BaseModel):
    version: str = Field(..., max_length=8)
    patient_id: str = Field(..., max_length=80)
    recording_id: str = Field(..., max_length=80)
    start_date: str = Field(..., max_length=8)  # You can parse to datetime separately
    start_time: str = Field(..., max_length=8)
    num_bytes_header_record: str = Field(..., max_length=8)
    reserved: str = Field(..., max_length=44)
    num_data_records: str = Field(..., max_length=8)
    data_record_duration: str = Field(..., max_length=8)
    num_signals: str = Field(..., max_length=4)

    @classmethod
    def from_file(cls, binary_reader: BinaryReader) -> FileMetadata:
        return cls(
            version=binary_reader.read_ascii(8),
            patient_id=binary_reader.read_ascii(80),
            recording_id=binary_reader.read_ascii(80),
            start_date=binary_reader.read_ascii(8),
            start_time=binary_reader.read_ascii(8),
            num_bytes_header_record=binary_reader.read_ascii(8),
            reserved=binary_reader.read_ascii(44),
            num_data_records=binary_reader.read_ascii(8),
            data_record_duration=binary_reader.read_ascii(8),
            num_signals=binary_reader.read_ascii(4),
        )


class SignalMetadata(BaseModel):
    label: str = Field(..., max_length=16)
    transducer_type: str = Field(..., max_length=80)
    physical_dimension: str = Field(..., max_length=8)
    physical_min: str = Field(..., max_length=8)
    physical_max: str = Field(..., max_length=8)
    digital_min: str = Field(..., max_length=8)
    digital_max: str = Field(..., max_length=8)
    prefiltering: str = Field(..., max_length=80)
    num_samples: str = Field(..., max_length=8)
    reserved: str = Field(..., max_length=32)

    @classmethod
    def from_file(cls, binary_reader: BinaryReader, num_signals: int) -> list[SignalMetadata]:
        fields = [
            ("label", 16),
            ("transducer_type", 80),
            ("physical_dimension", 8),
            ("physical_min", 8),
            ("physical_max", 8),
            ("digital_min", 8),
            ("digital_max", 8),
            ("prefiltering", 80),
            ("num_samples", 8),
            ("reserved", 32),
        ]

        field_data: dict[str, list[str]] = {}
        for name, size in fields:
            field_data[name] = [binary_reader.read_ascii(size) for _ in range(num_signals)]
        return [cls(**{field: field_data[field][i] for field, _ in fields}) for i in range(num_signals)]


class Header(BaseModel):
    file_metadata: FileMetadata
    signal_metadatas: list[SignalMetadata]

    @classmethod
    def from_file(cls, binary_reader: BinaryReader) -> Header:
        file_metadata = FileMetadata.from_file(binary_reader)
        return cls(
            file_metadata=file_metadata,
            signal_metadatas=SignalMetadata.from_file(binary_reader, int(file_metadata.num_signals)),
        )


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
    header: Header
    records: list[DataRecord]

    @classmethod
    def from_file(cls, binary_reader: BinaryReader) -> Experiment:
        header = Header.from_file(binary_reader)
        records: list[DataRecord] = []
        num_data_records = int(header.file_metadata.num_data_records)

        num_samples_per_signal = [int(signal_metadata.num_samples) for signal_metadata in header.signal_metadatas]

        # Check if num data records is known
        if num_data_records == -1:
            num_data_records = cls._determine_num_data_records(
                binary_reader=binary_reader,
                num_samples_per_signal=num_samples_per_signal,
                num_signals=len(header.signal_metadatas),
            )

        annotations_index = next(
            (
                i
                for i, signal_metadata in enumerate(header.signal_metadatas)
                if signal_metadata.label == "EDF Annotations"
            ),
            None,
        )

        records = [
            DataRecord.from_file(
                binary_reader=binary_reader,
                num_samples_per_signal=num_samples_per_signal,
                annotations_index=annotations_index,
            )
            for _ in range(num_data_records)
        ]

        if not binary_reader.is_eof():
            msg = "Haven't reached end of file"
            raise ValueError(msg)

        return cls(
            header=header,
            records=records,
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
        num_samples_per_signal: list[int],
        num_signals: int,
    ) -> int:
        file_size = binary_reader.get_file_size()

        metadata_size = 256 + 256 * num_signals
        remaining_size = file_size - metadata_size

        total_samples = sum(num_samples_per_signal)
        data_record_size = 2 * total_samples

        if remaining_size % data_record_size != 0:
            msg = f"Unexpected file size. Unable to evenly divide {remaining_size} byte into {data_record_size} bytes per data record."
            raise ValueError(msg)
        return remaining_size // data_record_size
