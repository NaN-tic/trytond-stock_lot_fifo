# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from collections import defaultdict
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.cache import freeze, unfreeze

__all__ = ['Move']


class Move(metaclass=PoolMeta):
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

        grouped = defaultdict(set)
        for move in moves:
            if move.state != 'draft':
                continue
            key = freeze(move.fifo_search_context)
            grouped[key].add(move.product)

        lots_by_product = defaultdict(list)
        for key, products in grouped.items():
            with Transaction().set_context(unfreeze(key)):
                lots = Lot.search([
                        ('product', 'in', products),
                        ('quantity', '>', 0),
                        ], order=order)
                for lot in lots:
                    # Filtering here is faster than in the search
                    #if lot.quantity <= 0:
                        #continue
                    lots_by_product[lot.product.id].append(lot)

        to_save = []
        for move in moves:
            if move.state != 'draft':
                continue
            if (move.lot or not move.product.lot_is_required(
                        move.from_location, move.to_location)):
                continue

            lots = lots_by_product[move.product.id]
            remainder = move.internal_quantity
            while lots and remainder > 0.0:
                lot = lots.pop(0)
                production_quantity = 0.0
                if getattr(move, 'production_input', False):
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
                        move.unit)
                    move.lot = lot
                    to_save.append(move)
                    lots.insert(0, lot)
                else:
                    quantity = Uom.compute_qty(
                        move.product.default_uom, assigned_quantity,
                        move.unit)
                    new_moves += cls.copy([move], {
                                'lot': lot.id,
                                'quantity': quantity,
                                })

                consumed_quantities[lot.id] += assigned_quantity
                remainder -= assigned_quantity
            if not lots:
                move.quantity = Uom.compute_qty(move.product.default_uom,
                    remainder, move.unit)
                to_save.append(move)
            lots_by_product[move.product.id] = lots

        cls.save(to_save)
        moves = cls.search([('id', 'in', moves + new_moves)])
        return super().assign_try(moves,
            with_childs=with_childs, grouping=grouping)
