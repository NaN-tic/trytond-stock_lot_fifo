#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Move']
__metaclass__ = PoolMeta


class Move:
    __name__ = 'stock.move'

    @classmethod
    def assign_try(cls, moves, grouping=('product',)):
        '''
        If lots required assign lots in FIFO before assigning move.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        Lot = pool.get('stock.lot')
        Date = pool.get('ir.date')

        today = Date.today()
        new_moves = []
        lots_by_product = {}
        consumed_quantities = {}
        for move in moves:
            if (not move.lot and move.product.lot_is_required(
                        move.from_location, move.to_location)):
                if not move.product.id in lots_by_product:
                    search_context = {
                        'stock_date_end': today,
                        'locations': [move.from_location.id],
                        'stock_assign': True,
                        'forecast': False,
                        }
                    with Transaction().set_context(search_context):
                        lots_by_product[move.product.id] = Lot.search([
                                ('product', '=', move.product.id),
                                ('quantity', '>', 0.0),
                                ], order=[('create_date', 'ASC')])

                lots = lots_by_product[move.product.id]
                remainder = move.internal_quantity
                while lots and remainder > 0.0:
                    lot = lots.pop(0)
                    consumed_quantities.setdefault(lot.id, 0.0)
                    lot_quantity = lot.quantity - consumed_quantities[lot.id]
                    assigned_quantity = min(lot_quantity, remainder)
                    if assigned_quantity == remainder:
                        move.quantity = Uom.compute_qty(
                            move.product.default_uom, assigned_quantity,
                            move.uom)
                        move.lot = lot
                        move.save()
                        lots.insert(0, lot)
                    else:
                        quantity = Uom.compute_qty(
                            move.product.default_uom, assigned_quantity,
                            move.uom)
                        new_moves.extend(cls.copy([move], {
                                    'lot': lot.id,
                                    'quantity': quantity,
                                    }))

                    consumed_quantities[lot.id] += assigned_quantity
                    remainder -= assigned_quantity
                if not lots:
                    move.quantity = Uom.compute_qty(move.product.default_uom,
                        remainder, move.uom)
                    move.save()
                lots_by_product[move.product.id] = lots

        return super(Move, cls).assign_try(new_moves + moves, grouping)
