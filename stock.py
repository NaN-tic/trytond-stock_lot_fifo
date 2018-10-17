#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Move']
__metaclass__ = PoolMeta


class Move:
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
            ('quantity', '>', 0.0),
            ]

    @staticmethod
    def _get_fifo_search_order_by():
        return [('create_date', 'ASC')]

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
        assigned_moves = []
        to_write = []
        for move in moves:
            if (not move.lot and move.product.lot_is_required(
                        move.from_location, move.to_location)):
                if not move.product.id in lots_by_product:
                    with Transaction().set_context(move.fifo_search_context):
                        lots_by_product[move.product.id] = Lot.search(
                            move.fifo_search_domain, order=order)

                lots = lots_by_product[move.product.id]
                remainder = move.internal_quantity
                while lots and remainder > 0.0:
                    lot = lots.pop(0)
                    production_quantity = 0.0
                    if hasattr(move, 'production_input'):
                        for production_input in move.production_input.inputs:
                            if (production_input.product == move.product
                                    and production_input.state == 'draft'
                                    and lot == production_input.lot):
                                production_quantity += production_input.quantity
                    consumed_quantities.setdefault(lot.id, production_quantity)
                    lot_quantity = lot.quantity - consumed_quantities[lot.id]
                    if not lot_quantity > 0.0:
                        continue
                    assigned_quantity = min(lot_quantity, remainder)
                    if assigned_quantity == remainder:
                        move.quantity = Uom.compute_qty(
                            move.product.default_uom, assigned_quantity,
                            move.uom)
                        move.lot = lot
                        if move.state == 'assigned':
                            assigned_moves.append(move)
                        to_write.extend(([move], move._save_values))
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
                    remainder_quantity = Uom.compute_qty(
                        move.product.default_uom, remainder, move.uom)
                    if move.quantity != remainder_quantity:
                        move.quantity = remainder_quantity
                        if move.state == 'assigned':
                            assigned_moves.append(move)
                        to_write.extend(([move], move._save_values))
                lots_by_product[move.product.id] = lots
        if assigned_moves:
            cls.write(assigned_moves, {'state': 'draft'})
        if to_write:
            cls.write(*to_write)
        if assigned_moves:
            cls.write(assigned_moves, {'state': 'assigned'})

        return super(Move, cls).assign_try(new_moves + moves,
            with_childs=with_childs, grouping=grouping)
