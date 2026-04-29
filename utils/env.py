from dotenv import find_dotenv, load_dotenv


def load_env() -> bool:
    """Load the nearest `.env` file, walking upward from the caller's cwd."""
    return load_dotenv(find_dotenv(usecwd=True))
