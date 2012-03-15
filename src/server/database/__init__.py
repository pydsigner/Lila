from redis_database import RedisDatabase
from testing_database import TestingDatabase

class DatabaseNotFound(Exception):
    pass

def get_database(name, *args, **kwargs):
    databases = {"redis":RedisDatabase, "testing":TestingDatabase}
    database = databases.get(name)
    if database is None:
        raise DatabaseNotFound("Did not find database in the factory.")
    else:
        return database(*args, **kwargs)
