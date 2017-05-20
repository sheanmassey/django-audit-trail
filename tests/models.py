# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

from django_audit.models import AbstractRevision, AbstractAuditModel


class Dummy(AbstractAuditModel):
    current_revision = models.ForeignKey('DummyRevision', null=True, default=None)
    immutable_field = models.CharField(max_length=100)

class DummyRevision(AbstractRevision):
    tracked_model = models.ForeignKey('Dummy', null=True, default=None, related_name='revisions')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    # inherited fields
    # tracked_model_id = ...
    # is_deleted = ...
