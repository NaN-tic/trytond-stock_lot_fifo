# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import lot
from . import stock

def register():
    Pool.register(
        lot.Lot,
        stock.Move,
        module='stock_lot_fifo', type_='model')
