# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class TestStockLotFifoCase(ModuleTestCase):
    'Test stock_lot_fifo module'
    module = 'stock_lot_fifo'

    @with_transaction()
    def test0010lot_fifo(self):
        'Test lot fifo'
        pool = Pool()
        Location = pool.get('stock.location')
        Lot = pool.get('stock.lot')
        LotType = pool.get('stock.lot.type')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        # Create Company
        company = create_company()
        with set_company(company):
            lot_types = LotType.search([
                    ('code', '=', 'storage'),
                    ])
            kg, = Uom.search([('name', '=', 'Kilogram')])
            g, = Uom.search([('name', '=', 'Gram')])
            template, = Template.create([{
                        'name': 'Test lot_fifo',
                        'type': 'goods',
                        'list_price': Decimal(1),
                        'cost_price_method': 'fixed',
                        'default_uom': kg.id,
                        'lot_required': [('add', [x.id for x in lot_types])],
                        }])
            product, = Product.create([{
                        'cost_price': Decimal(0),
                        'template': template.id,
                        }])
            lost_found, = Location.search([('type', '=', 'lost_found')])
            storage, = Location.search([('code', '=', 'STO')])
            self.assertEqual(product.lot_is_required(lost_found, storage),
                True)
            self.assertEqual(product.lot_is_required(storage, lost_found),
                True)
            moves = Move.create([{
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': lost_found.id,
                        'to_location': storage.id,
                        'unit_price': Decimal('1'),
                        }, {
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': lost_found.id,
                        'to_location': storage.id,
                        'unit_price': Decimal('1'),
                        }])
            self.assertRaises(Exception, Move.do, moves[1])
            lot1, lot2 = Lot.create([{
                        'number': '1',
                        'product': product.id,
                        }, {
                        'number': '2',
                        'product': product.id,
                        }])
            move1, move2 = moves
            move1.lot = lot1
            move1.save()
            move2.lot = lot2
            move2.save()
            Move.do(moves)
            self.assertEqual(len(Move.search([
                            ('from_location', '=', storage.id),
                            ('to_location', '=', lost_found.id),
                           ])), 0)
            moves = Move.create([{
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 15,
                        'from_location': storage.id,
                        'to_location': lost_found.id,
                        'unit_price': Decimal('1'),
                        }])
            self.assertEqual(Move.assign_try(moves), False)
            new_moves = Move.search([
                            ('from_location', '=', storage.id),
                            ('to_location', '=', lost_found.id),
                           ])
            self.assertEqual(len(new_moves), 3)
            assigned = set()
            draft = set()
            for move in new_moves:
                self.assertEqual(move.quantity, 5.0)
                if move.state == 'assigned':
                    assigned.add(move)
                    self.assertIsNotNone(move.lot)
                else:
                    draft.add(move)
                    self.assertIsNone(move.lot)
            self.assertEqual(len(assigned), 2)
            self.assertEqual(len(draft), 1)
            lot3, lot4 = Lot.create([{
                        'number': '3',
                        'product': product.id,
                        }, {
                        'number': '4',
                        'product': product.id,
                        }])
            moves = Move.create([{
                        'product': product.id,
                        'lot': lot3.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': lost_found.id,
                        'to_location': storage.id,
                        'unit_price': Decimal('1'),
                        }, {
                        'product': product.id,
                        'lot': lot4.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': lost_found.id,
                        'to_location': storage.id,
                        'unit_price': Decimal('1'),
                        }])
            Move.do(moves)
            self.assertEqual(Move.assign_try(list(draft)), True)
            move, = draft
            self.assertEqual(move.lot, lot3)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            TestStockLotFifoCase))
    return suite
