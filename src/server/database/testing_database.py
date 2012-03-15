class TestingDatabase(object):
    def __init__(self):
        self.users = {"testing": "testing","test":"test"}
    def authenticate_user(self, user, password):
        user_password = self.users.get(user)
        if user_password is None:
            return (False, 998)
        else:
            if user_password == password:
                return (True, 999)
            else:
                return (False, 997)
