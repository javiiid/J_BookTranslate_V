class TranslationStopped(KeyboardInterrupt):
    """A cooperative stop request that preserves resumable job state."""

    pass


def handle_interrupt(signum, frame):
    print("\nProcess interrupted by user.")
    raise KeyboardInterrupt
