# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta


class Lot(metaclass=PoolMeta):
    __name__ = 'stock.lot'

    def sort_quantities_fifo(self):
        if getattr(self, 'shelf_life_expiration_date', None):
            return self.shelf_life_expiration_date
        if getattr(self, 'lot_date', None):
            return self.lot_date
        return self.create_date.date()
