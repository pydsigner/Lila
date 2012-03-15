import redis

class RedisDatabase(object):
    def __init__(self, host, port):
        self.db = redis.Redis(host, port, password="letmeinnow")
        self.user_db = redis.Redis(host, port, db=1, password="letmeinnow")

    def authenticate_user(self, user, password):
        """
        Get the users SHA552 password from the database,
        This may be None, which in this case is useful as
        None == "fakepassword" means that the authentication 
        will fail.
        """
        user_password = self.user_db.get(user)
        if user_password is None:
            return (False, 998)
        else:
            if user_password == password:
                return (True, 999)
            else:
                return (False, 997)
