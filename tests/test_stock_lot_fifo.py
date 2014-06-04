#!/usr/bin/env python
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from itertools import combinations
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.tests.test_tryton import test_depends
from trytond.transaction import Transaction


class TestStockLotFifoCase(unittest.TestCase):
    'Test stock_lot_fifo module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock_lot_fifo')
        self.category = POOL.get('product.category')
        self.company = POOL.get('company.company')
        self.location = POOL.get('stock.location')
        self.lot = POOL.get('stock.lot')
        self.lot_type = POOL.get('stock.lot.type')
        self.move = POOL.get('stock.move')
        self.product = POOL.get('product.product')
        self.template = POOL.get('product.template')
        self.uom = POOL.get('product.uom')
        self.user = POOL.get('res.user')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0010lot_fifo(self):
        'Test lot fifo'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            lot_types = self.lot_type.search([
                    ('code', 'in', ['supplier', 'customer', 'storage']),
                    ])
            kg, = self.uom.search([('name', '=', 'Kilogram')])
            g, = self.uom.search([('name', '=', 'Gram')])
            template, = self.template.create([{
                        'name': 'Test lot_fifo',
                        'type': 'goods',
                        'list_price': Decimal(1),
                        'cost_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': kg.id,
                        'lot_required': [('add', [x.id for x in lot_types])],
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            supplier, = self.location.search([('code', '=', 'SUP')])
            storage, = self.location.search([('code', '=', 'STO')])
            customer, = self.location.search([('code', '=', 'CUS')])
            for from_, to in combinations([supplier, storage, customer], 2):
                self.assertEqual(product.lot_is_required(from_, to), True)
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            currency = company.currency
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })
            moves = self.move.create([{
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            self.assertRaises(Exception, self.move.do, moves)
            lot1, lot2 = self.lot.create([{
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
            self.move.do(moves)
            self.assertEqual(len(self.move.search([
                            ('from_location', '=', storage.id),
                            ('to_location', '=', customer.id),
                           ])), 0)
            moves = self.move.create([{
                        'product': product.id,
                        'uom': kg.id,
                        'quantity': 15,
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            self.assertEqual(self.move.assign_try(moves), False)
            new_moves = self.move.search([
                            ('from_location', '=', storage.id),
                            ('to_location', '=', customer.id),
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
            lot3, lot4 = self.lot.create([{
                        'number': '3',
                        'product': product.id,
                        }, {
                        'number': '4',
                        'product': product.id,
                        }])
            moves = self.move.create([{
                        'product': product.id,
                        'lot': lot3.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }, {
                        'product': product.id,
                        'lot': lot4.id,
                        'uom': kg.id,
                        'quantity': 5,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            self.move.do(moves)
            self.assertEqual(self.move.assign_try(list(draft)), True)
            move, = draft
            self.assertEqual(move.lot, lot3)


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            TestStockLotFifoCase))
    return suite
