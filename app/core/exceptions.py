class BatchProcessingError(Exception):
    """
    Custom exception for errors that occur during batch processing.
    This allows batch-related errors to be identified and handled separately
    from generic Python exceptions.
    """
    pass


class TranslationStopped(KeyboardInterrupt):
    """A cooperative stop request that preserves resumable job state."""

    pass


def handle_interrupt(signum, frame):
    print("\nProcess interrupted by user.")
    raise KeyboardInterrupt
