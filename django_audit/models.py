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


# def nullable_fk(model_name):
#     return models.ForeignKey(model_name, null=True, default=Non)


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

