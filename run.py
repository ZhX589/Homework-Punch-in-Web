from app import app
from app.utils.db import init_db

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
