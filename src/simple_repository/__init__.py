from .repository import crud_factory


def main() -> None:
    print("Hello from simple-repo-asyncsqla!")


__all__ = ["crud_factory"]
