"""
Custom exception types: SchemaValidationError, ModelLoadError, InferenceError.

All exceptions in this module inherit from BiasAnalysisError so callers
(API layer, pipeline) can catch the whole family with a single except
clause when needed, while still being able to handle specific failure
modes (validation vs. model loading vs. inference) differently.
"""

from __future__ import annotations


class BiasAnalysisError(Exception):
    """Base class for all Module 2 errors."""


class SchemaValidationError(BiasAnalysisError):
    """Raised when input data does not conform to the expected article schema."""


class UnsupportedInputError(BiasAnalysisError):
    """Raised when an input type/format is not supported by a loader."""


class EmptyContentError(BiasAnalysisError):
    """Raised when an article has no usable text content after cleaning."""


class ModelLoadError(BiasAnalysisError):
    """Raised when the RoBERTa tokenizer or model fails to load."""


class InferenceError(BiasAnalysisError):
    """Raised when the model fails during forward-pass inference."""


__all__ = [
    "BiasAnalysisError",
    "SchemaValidationError",
    "UnsupportedInputError",
    "EmptyContentError",
    "ModelLoadError",
    "InferenceError",
]
