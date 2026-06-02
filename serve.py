# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "vgi[http,oauth]",
#     "vgi-rpc[sentry]",
# ]
#
# [tool.uv.sources]
# vgi = { path = "../vgi-python" }
# vgi-rpc = { path = "../vgi-rpc" }
# ///
from easter_worker import EasterWorker

if __name__ == "__main__":
    EasterWorker.main_http()
