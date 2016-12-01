from uuid import uuid4

from django.utils.functional import curry
from django.db.models import signals

# from . models import Transaction


def auditor(get_response):
    # transaction = None
    request_uuid = str(uuid4())

    # def get_transaction():
    #     if transaction is None:
    #         print 'TRANSACTION', '*' * 80
    #         transaction = Transaction.objects.create()
    #     return transaction

    def middleware(request):
        if hasattr(request, "user") and request.user.is_authenticated():
            user = request.user
        else:
            user = None

        def signal_handler(sender, instance, **kwargs):
            if hasattr(instance, "created_by"):
                instance.created_by = user
            # if hasattr(instance, "transaction"):
            #     instance.transaction = get_transaction()

        signals.pre_save.connect(signal_handler, dispatch_uid=(request_uuid, request,))
        response = get_response(request)
        signals.pre_save.disconnect(dispatch_uid=(request_uuid,request,))

        return response

    return middleware


# class Middleware(object):
#     def __init__(self, *args, **kwargs):
#         self.transaction = None
#         # return super(Middleware, self).__init__(*args, **kwargs)
# 
#     def get_transaction(self):
#         if not self.transaction:
#             self.transaction = Transaction.objects.create()
#         return self.transaction
# 
#     def process_request(self, request):
#         if hasattr(request, 'user') and request.user.is_authenticated():
#             user = request.user
#         else:
#             user = None
#         signal_handler = curry(self.signal_handler, user)
#         signals.pre_save.connect(signal_handler, dispatch_uid=(self.__class__,request,), weak=False)
# 
#     def process_response(self, request, response):
#         signal_handler.pre_save.disconnect(dispatch_uid=(self.__class__, request,))
#         return response
# 
#     def signal_handler(self, user, sender, instance, **kwargs):
#         if hasattr(instance, "created_by"):
#             instance.created_by = user
#         if hasattr(instance, "transaction"):
#             instance.transaction = self.get_transaction()
