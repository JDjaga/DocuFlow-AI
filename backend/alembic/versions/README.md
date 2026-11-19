# Alembic migration scripts are stored in this folder.

Generate the first one from the `backend/` folder:

    alembic revision --autogenerate -m "initial schema"
    alembic upgrade head

You do not need to do this just to run the project - the application
creates the initial schema automatically on startup.
