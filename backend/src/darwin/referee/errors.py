class RefereeError(Exception):
    """The referee itself failed (Docker, fastchess, inconsistent output): never the candidate's
    fault, so it must not turn into a verdict against it."""
