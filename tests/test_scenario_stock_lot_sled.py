import unittest
import datetime
from decimal import Decimal
from proteus import Model
from dateutil.relativedelta import relativedelta
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Activate modules
        activate_modules(['stock_lot_fifo', 'stock_lot_sled'])
        Location = Model.get('stock.location')
        Lot = Model.get('stock.lot')
        ProductTemplate = Model.get('product.template')
        ProductUom = Model.get('product.uom')
        Move = Model.get('stock.move')

        today = datetime.date.today()

        # Create company
        _ = create_company()
        company = get_company()

        # Create customer
        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.save()

        # Create product
        unit, = ProductUom.find([('name', '=', 'Unit')])
        template = ProductTemplate()
        template.name = 'Product'
        template.default_uom = unit
        template.type = 'goods'
        template.list_price = Decimal('20')
        template.save()
        product, = template.products

        # Get stock locations
        supplier_loc, = Location.find([('code', '=', 'SUP')])
        storage_loc, = Location.find([('code', '=', 'STO')])
        lost_found_loc, = Location.find([('type', '=', 'lost_found')])
        warehouse_loc, = Location.find([('code', '=', 'WH')])
        customer_loc, = Location.find([('code', '=', 'CUS')])
        output_loc, = Location.find([('code', '=', 'OUT')])

        # Create lot
        lot = Lot()
        lot.number = 'LOT'
        lot.product = product
        lot.save()

        # Create supplier moves without and with lot
        move1_in = Move()
        move1_in.from_location = supplier_loc
        move1_in.to_location = storage_loc
        move1_in.product = product
        move1_in.company = company
        move1_in.quantity = 10
        move1_in.unit_price = Decimal('1')
        move1_in.currency = company.currency
        move1_in.save()
        move1_in.click('do')
        move2_in = Move()
        move2_in.from_location = supplier_loc
        move2_in.to_location = storage_loc
        move2_in.product = product
        move2_in.company = company
        move2_in.lot = lot
        move2_in.quantity = 20
        move2_in.unit_price = Decimal('2')
        move2_in.currency = company.currency
        move2_in.save()
        move2_in.click('do')

        # Create Shipment Out with two moves: with lot and withlot lot
        ShipmentOut = Model.get('stock.shipment.out')
        shipment_out = ShipmentOut()
        shipment_out.planned_date = today
        shipment_out.customer = customer
        shipment_out.warehouse = warehouse_loc
        outgoing_move = shipment_out.outgoing_moves.new()
        outgoing_move.product = product
        outgoing_move.quantity = 8
        outgoing_move.from_location = output_loc
        outgoing_move.to_location = customer_loc
        outgoing_move.unit_price = Decimal('1')
        outgoing_move.currency = company.currency
        outgoing_move = shipment_out.outgoing_moves.new()
        outgoing_move.product = product
        outgoing_move.lot = lot
        outgoing_move.quantity = 18
        outgoing_move.from_location = output_loc
        outgoing_move.to_location = customer_loc
        outgoing_move.unit_price = Decimal('1')
        outgoing_move.currency = company.currency
        shipment_out.save()
        shipment_out.click('wait')
        shipment_out.click('assign_try')
        self.assertEqual(shipment_out.state, 'assigned')
        move1, move2 = shipment_out.inventory_moves
        self.assertEqual((move1.lot, move1.quantity), (None, 8.0))
        self.assertEqual((move2.lot, move2.quantity), (lot, 18.0))

        # Save product lot required
        template.lot_required = ['storage']
        template.save()

        # Create two new lots with shelf_life_expiration_date
        lot2 = Lot()
        lot2.number = 'LOT2'
        lot2.product = product
        lot2.shelf_life_expiration_date = today + relativedelta(days=10)
        lot2.save()

        lot3 = Lot()
        lot3.number = 'LOT3'
        lot3.product = product
        lot3.shelf_life_expiration_date = today + relativedelta(days=2)
        lot3.save()

        # Create new supplier moves with lot
        move3_in = Move()
        move3_in.from_location = supplier_loc
        move3_in.to_location = storage_loc
        move3_in.product = product
        move3_in.company = company
        move3_in.lot = lot2
        move3_in.quantity = 10
        move3_in.unit_price = Decimal('1')
        move3_in.currency = company.currency
        move3_in.save()
        move3_in.click('do')
        move4_in = Move()
        move4_in.from_location = supplier_loc
        move4_in.to_location = storage_loc
        move4_in.product = product
        move4_in.company = company
        move4_in.lot = lot3
        move4_in.quantity = 20
        move4_in.unit_price = Decimal('2')
        move4_in.currency = company.currency
        move4_in.save()
        move4_in.click('do')

        # Create Shipment Out with two moves: without lot (assign try set lot)
        shipment_out = ShipmentOut()
        shipment_out.planned_date = today
        shipment_out.customer = customer
        shipment_out.warehouse = warehouse_loc
        outgoing_move = shipment_out.outgoing_moves.new()
        outgoing_move.product = product
        outgoing_move.quantity = 8
        outgoing_move.from_location = output_loc
        outgoing_move.to_location = customer_loc
        outgoing_move.unit_price = Decimal('1')
        outgoing_move.currency = company.currency
        outgoing_move = shipment_out.outgoing_moves.new()
        outgoing_move.product = product
        outgoing_move.quantity = 18
        outgoing_move.from_location = output_loc
        outgoing_move.to_location = customer_loc
        outgoing_move.unit_price = Decimal('1')
        outgoing_move.currency = company.currency
        shipment_out.save()
        shipment_out.click('wait')
        shipment_out.click('assign_try')
        self.assertEqual(shipment_out.state, 'assigned')

        move1, move2, move3, move4 = shipment_out.inventory_moves
        # lot by create_date
        self.assertEqual((move1.lot, move1.quantity), (lot, 2.0))
        # lot by shelf_life_expiration_date + days 2
        self.assertEqual((move2.lot, move2.quantity), (lot3, 14.0))
        # lot by shelf_life_expiration_date + days 2
        self.assertEqual((move3.lot, move3.quantity), (lot3, 6.0))
        # lot by shelf_life_expiration_date + days 10
        self.assertEqual((move4.lot, move4.quantity), (lot2, 4.0))
