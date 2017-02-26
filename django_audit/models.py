"""
MAKE AUDIT TRAILS GREAT AGAIN!

Examples

let's audit our user profile model, UserProfile, which
is defined like so


class UserProfile(models.Model):
    user = models.ForeignKey(User, null=False)
    email_notifications = models.BooleanField(default=False)


we will consider the `user` attribute to be immutable and the
`email_notifications` attribute to be mutable. when we talk
about mutability here we're refering to the user's point of
view (what can a user directly change via your applications
views, here we consider the `user` attribute to be handled
automatically in your app logic and not directly modifiable by
your app users).

Let's split the model:


class UserProfile(AbstractAuditModel):
    current_revision = models.ForeignKey("UserProfileRevision", null=True, default=None)
    user = models.ForeignKey(User, null=False)


class UserProfileRevision(AbstractRevision):
    tracked_model = models.ForeignKey("UserProfile", null=True, default=None, related_name="revisions")
    email_notifications = models.BooleanField(default=False)


That all we need, now we can track all the changes to your UserProfile:

profile = UserProfile.objects.create(
    user = user,
    email_notifications = ...
"""

from __future__ import unicode_literals

from django.conf import settings
from django.db import models

from sets import Set


def revision_attr(name):
    """
    """
    return property(
        fget=lambda self: getattr(self.current_revision, name),
        fset=lambda self, value: setattr(self.current_revision, name, value),
    )


class AuditModelManager(models.Manager):
    """
    a default model manager for all AbstractAuditModels
    """
    def get_queryset(self, *args, **kwargs):
        return super(AuditModelManager, self).get_queryset(*args, **kwargs) \
            .select_related('current_revision')


class PublishedAuditModelManager(AuditModelManager):
    """
    filters out the deleted instances (is_deleted=True)
    """
    def get_queryset(self, *args, **kwargs):
        return super(PublishedAuditModelManager, self).get_queryset(*args, **kwargs) \
            .filter(current_revision__is_deleted=False)


class DeletedAuditModelManager(AuditModelManager):
    """
    filters out the published instances (is_deleted=False)
    """
    def get_queryset(self, *args, **kwargs):
        return super(DeletedAuditModelManager, self).get_queryset(*args, **kwargs) \
            .filter(current_revision__is_deleted=True)


class AbstractRevision(models.Model):
    """
    abstract base for revision models.
    """
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, default=None, related_name="%(app_label)s_%(class)s_set")
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        super(AbstractRevision, self).__init__(*args, **kwargs)
        # assert hasattr(self, "tracked_model"), "child model must provide a tracked_model (models.ForeignKey)"

    def delete(self):
        """
        revisions are never deleted, instead we flip the is_deleted attribute
        to true, and save the revision.
        """
        if not self.is_deleted:
            self.is_deleted = True
            self.save()

    def save(self, *args, **kwargs):
        """
        revisions are never updated (the trick is setting self.pk to None,
        which causes django to insert a new record). after saving this new
        instance, we update the current_revision of our tracked_model to point
        to self.
        """
        self.pk = None
        super(AbstractRevision, self).save(*args, **kwargs)
        self.tracked_model.current_revision = self
        self.tracked_model.save()

    def get_values(self):
        """
        returns a dictionary of fields which contains values
        """
        values_dict = self.__class__.objects.values().get(pk=self.pk)
        d = { k: v for k,v in zip(values_dict.keys(), values_dict.values()) \
            if v is not None and v is not u'' 
        }
        return d
    
    def get_empty_values(self):
        """
        returns a dictionary of fields which contain empty values
        """
        values_dict = self.__class__.objects.values().get(pk=self.pk)
        d = { k: v for k,v in zip(values_dict.keys(), values_dict.values()) \
            if v is None or v is u'' 
        }
        return d

    def values(self):
        """
        returns a dictionary of all fields and values
        """
        return self.__class__.objects.values().get(pk=self.pk)

    @staticmethod
    def diff(rev_1, rev_2):
        """
        compare two revisions to one another, returns the set of differences 
        intersections, symmetrical_difference and 
        symmetrical_differences - differences

        example:
        >>> rev_1 = PatientRevision.objects.get(pk=1)
        >>> rev_2 = PatientRevision.objects.get(pk=2)
        >>> new_values, unchanged_values, changed_items, old_values = \
        >>>     PatientRevision.diff_revsions(rev_1, rev_2)

        """
        assert isinstance(rev_1, AbstractRevision)
        assert isinstance(rev_2, AbstractRevision)
        if rev_1.created_at == rev_2.created_at:
            print 'should not compare object to itself.'
            return None
        
        set_1 = Set(( (k,v) for k,v in zip(rev_1.get_values().keys(), rev_1.get_values().values()) if k != u'id' and k != u'created_at' and k != 'tracked_model_id' ))
        set_2 = Set(( (k,v) for k,v in zip(rev_2.get_values().keys(), rev_2.get_values().values()) if k != u'id' and k != u'created_at' and k != 'tracked_model_id' ))
        
        # new values
        diff = set_1 - set_2 # elements in s but not in t
        # common values
        intersection = set_1 & set_2 # elements common to s and t
        # pairs of changed values
        sym_diff = set_1 ^ set_2 # elements in s and t but not in both
        # changed values - set for consistency
        mod = sym_diff - diff
        return diff, intersection, sym_diff, mod

    class Meta:
        abstract = True


class AbstractAuditModel(models.Model):
    """
    abstract base for your tracked models, any model that needs an audit trail
    should extend this one.

    the inheriting classes require a nullable ForeignKey attribute, named
    `current_revision` that links to the revision model.
    """
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, default=None, related_name="%(app_label)s_%(class)s_set")
    created_at = models.DateTimeField(auto_now_add=True)

    is_deleted = revision_attr("is_deleted")

    objects = AuditModelManager()
    published_objects = PublishedAuditModelManager()
    deleted_objects = DeletedAuditModelManager()

    def __init__(self, *args, **kwargs):
        super(AbstractAuditModel, self).__init__(*args, **kwargs)
        # assert hasattr(self, "current_revision"), "child model must provide a current_revision (models.ForeignKey)"

    def delete(self):
        """
        audit models are never deleted, instead a flag is flipped on their revision.
        """
        self.current_revision.delete()

    def save(self, *args, **kwargs):
        """
        when a new auditmodel is saved we create the first revision, then update the
        first revision's tracked_model to point to self, then save it.
        """
        super(AbstractAuditModel, self).save(*args, **kwargs)
        if not self.current_revision:
            revision = self.__class__.current_revision.field.related_model()
            revision.tracked_model = self
            revision.save()

    class Meta:
        abstract = True


def get_field_names(model):
    assert isinstance(model, models.Model)
    return [ f.name for f in model._meta.get_fields() ]
