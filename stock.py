# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
from trytond.pool import Pool, PoolMeta


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @classmethod
    def assign_try(cls, moves, with_childs=True, grouping=('product',),
            pblc=None):
        if 'lot' not in grouping:
            moves_with_lot, moves_without_lot = [], []
            for move in moves:
                if (move.lot or move.product.lot_is_required(
                        move.from_location, move.to_location)):
                    moves_with_lot.append(move)
                else:
                    moves_without_lot.append(move)
            success = super().assign_try(
                moves_with_lot, with_childs=with_childs,
                grouping=grouping + ('lot',), pblc=pblc)
            success &= super().assign_try(
                moves_without_lot, with_childs=with_childs,
                grouping=grouping, pblc=pblc)
        else:
            success = super().assign_try(
                moves, with_childs=with_childs, grouping=grouping, pblc=pblc)
        return success

    def sort_quantities(self, quantities, locations, grouping):
        """
        Override to sort quantities using FIFO.
        'quantities' contains the result of Product.products_by_location()
        from Move.assign_try()
        e.g: quantities = [((location.id, product.id, lot.id), quantity)]
        quantities[0] = ((location.id, product.id, lot.id), quantity)
        quantities[0][0] = (location.id, product.id, lot.id)
        quantities[0][0][0-2] = location.id/product.id/lot.id
        """
        pool = Pool()
        Lot = pool.get('stock.lot')

        quantities = super().sort_quantities(quantities, locations, grouping)

        if 'lot' not in grouping:
            return quantities

        # 'grouping' is a tuple of keys for sorting 'quantities'.
        # By default, 'quantities' contains the location as key, and the other
        # ones are defined in 'grouping'; ('product', 'lot').
        # Assuming 'lot' key position: (quantities[0][0][2]) would crash if
        # another module adds an extra key to 'grouping', so getting its index
        # in 'grouping' + 1 because of location, prevents this error.
        lot_idx = grouping.index('lot') + 1
        lots = Lot.search([('id', 'in', {q[0][lot_idx] for q in quantities})])
        lot2date = {lot.id: lot.sort_quantities_fifo() for lot in lots}
        return sorted(quantities,
            key=lambda x: lot2date.get(x[0][lot_idx], datetime.datetime.max.date()))
