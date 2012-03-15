from server import server
from server.database import get_database

if __name__ == '__main__':
    server.main(55555, database=get_database("testing"), debug=False)
