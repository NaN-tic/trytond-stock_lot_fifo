# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Move']


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'stock.move'

    @property
    def fifo_search_context(self):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        return {
            'stock_date_end': today,
            'locations': [self.from_location.id],
            'stock_assign': True,
            'forecast': False,
            }

    @property
    def fifo_search_domain(self):
        return [
            ('product', '=', self.product.id),
            ]

    @staticmethod
    def _get_fifo_search_order_by():
        pool = Pool()
        Lot = pool.get('stock.lot')

        order = []
        if hasattr(Lot, 'shelf_life_expiration_date'):
            order.append(('shelf_life_expiration_date', 'ASC'))
            order.append(('expiration_date', 'ASC'))
        if hasattr(Lot, 'lot_date'):
            order.append(('lot_date', 'ASC'))
        order.append(('create_date', 'ASC'))
        return order

    @classmethod
    def assign_try(cls, moves, with_childs=True, grouping=('product',)):
        '''
        If lots required assign lots in FIFO before assigning move.
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        Lot = pool.get('stock.lot')

        new_moves = []
        lots_by_product = {}
        consumed_quantities = {}
        order = cls._get_fifo_search_order_by()
        for move in moves:
            if (not move.lot and move.product.lot_is_required(
                        move.from_location, move.to_location)):

                if move.product.id not in lots_by_product:
                    with Transaction().set_context(move.fifo_search_context):
                        lots_by_product[move.product.id] = [x for x in
                            Lot.search(move.fifo_search_domain, order=order)
                            if x.quantity > 0]

                lots = lots_by_product[move.product.id]
                remainder = move.internal_quantity
                while lots and remainder > 0.0:
                    lot = lots.pop(0)
                    consumed_quantities.setdefault(lot.id, 0.0)
                    lot_quantity = lot.quantity - consumed_quantities[lot.id]
                    if not lot_quantity > 0.0:
                        continue
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

        return super(Move, cls).assign_try(new_moves + moves,
            with_childs=with_childs, grouping=grouping)
