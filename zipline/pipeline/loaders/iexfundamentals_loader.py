import numpy as np

from zipline.pipeline.data.sources import iex

from .base import PipelineLoader


class IEXKeyStatsLoader(PipelineLoader):

    def __init__(self, asset_finder):
        self._asset_finder = asset_finder

    def load_adjusted_array(self, columns, dates, assets, mask):
        asset_finder = self._asset_finder

        key_stats = iex.key_stats()
        out = {}
        for c in columns:
            data = [
                key_stats.get(a.symbol, {}).get(c.name, c.missing_value)
                for a in asset_finder.retrieve_all(assets)
            ]
            out[c] = np.tile(np.array(data, dtype=c.dtype), (len(dates), 1))
        return out
