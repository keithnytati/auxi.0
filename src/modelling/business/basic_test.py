#!/usr/bin/env python3
"""
This module provides testing code for the
auxi.modelling.business.basic module.
"""

import unittest
from datetime import datetime

from auxi.core.time import Clock
from auxi.modelling.business.basic import BasicActivity
from auxi.modelling.financial.des import GeneralLedger
from auxi.modelling.financial.des import GeneralLedgerStructure

__version__ = '0.2.0rc4'
__license__ = 'LGPL v3'
__copyright__ = 'Copyright 2016, Ex Mente Technologies (Pty) Ltd'
__author__ = 'Christoff Kok, Johan Zietsman'
__credits__ = ['Christoff Kok', 'Johan Zietsman']
__maintainer__ = 'Christoff Kok'
__email__ = 'christoff.kok@ex-mente.co.za'
__status__ = 'Planning'


class BasicActivityUnitTester(unittest.TestCase):
    """
    Tester for the auxi.modelling.business.basic.BasicActivity class.
    """

    def setUp(self):
        self.object = BasicActivity("NameA",
                                    description="DescriptionA",
                                    dt_account="Bank",
                                    cr_account="Sales",
                                    amount=5000,
                                    start=datetime(2016, 2, 1),
                                    end=datetime(2017, 2, 1),
                                    interval=3)

    def test_constructor(self):
        self.assertEqual(self.object.name, "NameA")
        self.assertEqual(self.object.description, "DescriptionA")
        self.assertEqual(self.object.start_datetime, datetime(2016, 2, 1))
        self.assertEqual(self.object.end_datetime, datetime(2017, 2, 1))
        self.assertEqual(self.object.interval, 3)
        self.assertEqual(self.object.amount, 5000)
        self.assertEqual(self.object.dt_account, "Bank")
        self.assertEqual(self.object.cr_account, "Sales")

    def test__meet_exection_criteria(self):
        """
        Test that the activity only meets the execution criteria when
        it's amount is greater than 0.
        """

        clock = Clock("NameA", start_datetime=datetime(2016, 1, 1))
        self.object.prepare_to_run(clock, 13)
        self.assertEqual(self.object._meet_execution_criteria(5), True)
        self.object.amount = 0
        self.assertEqual(self.object._meet_execution_criteria(5), False)

    def test_run(self):
        """
        Test that the activity run method creates a transaction with an amount
        of 5000.
        """

        structure = GeneralLedgerStructure("NameA", description="DescriptionA")
        gl = GeneralLedger("NameA", structure, description="DescriptionA")
        clock = Clock("NameA", start_datetime=datetime(2016, 1, 1))
        clock.tick()
        clock.tick()
        self.object.prepare_to_run(clock, 20)
        self.object.run(clock, gl)
        self.assertEqual(len(gl.transactions), 1)
        self.assertEqual(gl.transactions[0].amount, 5000)

    def test_get_referenced_accounts(self):
        """
        Test that the activity run method get_referenced_accounts accounts
        matches the debit and credit accounts self.object was initialised with.
        """

        result = self.object.get_referenced_accounts()
        self.assertEqual(self.object.dt_account, result[0])
        self.assertEqual(self.object.cr_account, result[1])


if __name__ == '__main__':
    unittest.main()
