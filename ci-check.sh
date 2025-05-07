#!/bin/bash

# Exit immediately if any command fails
set -e

echo "Installing required development dependencies..."
pip install -e .[dev]

# Run Black to format the code
echo "Running black (code formatter)..."
black src/

# Run Darglint to check docstring styles
echo "Running darglint (docstring linter)..."
darglint src/edf_viewer

# Run MyPy to check type correctness
echo "Running mypy (type checker)..."
mypy src/

# Run Pytest for tests
echo "Running pytest (unit tests)..."
pytest src/tests

# Run Ruff for linting
echo "Running ruff (static analysis)..."
ruff check src/

echo "All checks complete!"
