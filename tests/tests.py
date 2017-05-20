# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase

# Create your tests here.
from django.test import TestCase
from . models import *

from www.settings import TIME_ZONE


class TestAuditTrails(TestCase):
    def setUp(self):
        self.audit = Dummy()
        self.audit.save()

        # revision 1
        self.audit.current_revision.first_name = 'John'
        self.audit.current_revision.last_name = 'Dope'
        self.audit.current_revision.save()

        # revision 2
        self.audit.current_revision.last_name = 'Doe'
        self.audit.current_revision.save()

    def test_diff_revisions(self):
        obj = [ val for val in  DummyRevision.objects.all() ]
        rev_1 = obj[-1]
        rev_2 = obj[-2]

        diff, intersection, sym_diff, mod = DummyRevision.diff(rev_1, rev_2)

        # new value
        self.assertTrue(len(diff) == 1)
        self.assertTrue(('last_name', 'Doe') in diff)

        # unchanged value
        self.assertTrue(len(sym_diff) == 2)
        self.assertTrue(('first_name', 'John') in intersection)
        self.assertTrue(('is_deleted', False) in intersection)

        # modified value
        self.assertTrue(len(mod) == 1)
        self.assertTrue(('last_name', 'Dope') in mod)

        # new and modified value pair
        self.assertTrue(len(sym_diff) == 2)
        self.assertTrue(('last_name', 'Dope') in sym_diff)
        self.assertTrue(('last_name', 'Doe') in sym_diff)
