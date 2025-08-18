"""DDBJ Record Validator.

A Python package for validating DDBJ record JSON format against DDBJ Record specifications.
Supports both v1 and v2 schema versions with comprehensive validation capabilities.
"""

__version__ = "0.1.0"
__author__ = "Bioinformatics and DDBJ Center"
__email__ = "trace@ddbj.nig.ac.jp"
__license__ = "Apache-2.0"

from ddbj_record.validator import SchemaVersion, validate_json_data

__all__ = [
    "SchemaVersion",
    "validate_json_data",
    "__version__",
]
