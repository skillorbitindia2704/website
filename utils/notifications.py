from models import db
from models.notification import Notification


def notify_user(user_id, message):
    n = Notification(user_id=user_id, message=message, is_read=False)
    db.session.add(n)
    return n
