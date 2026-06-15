# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "vgi-python[http]>=0.8.0",
# ]
# ///
"""HTTP entrypoint for the Easter VGI worker."""

from easter_worker import EasterWorker


def main() -> None:
    """Run the Easter worker as an HTTP server."""
    EasterWorker.main_http()


if __name__ == "__main__":
    main()
