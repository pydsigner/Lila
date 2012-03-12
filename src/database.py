__author__ = 'Jakob'
try:
    import redis
except ImportError:
    pass

class RedisDatabase(object):
    def __init__(self, host, port):
        self.db = redis.Redis(host, port, password="letmeinnow")
        self.user_db = redis.Redis(host, port, db=1, password="letmeinnow")

    def authenticate_user(self, user, password):
        return self.user_db.get(user) == password


class TestDatabase(object):
    def __init__(self):
        self.db = {}
        self.user_db = {}

    def authenticate_user(self, user, password):
        return self.user_db.get(user, False) == password

redis_database = RedisDatabase("localhost", 6379)
test_database = TestDatabase()

if __name__ == '__main__':
    print database.authenticate_user("test", "test")