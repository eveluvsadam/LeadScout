"""Reset the admin-page password.

Run this if you forget your admin password:

    python -m app.reset_admin

It clears the stored password so the next visit to /admin shows the
"Create your admin password" screen again. Your leads are not touched.
"""
from . import database as db


def main() -> None:
    db.init_db()
    db.reset_admin()
    print("Admin password cleared. Open /admin to set a new one.")


if __name__ == "__main__":
    main()
