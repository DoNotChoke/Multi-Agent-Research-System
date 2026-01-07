from importlib import resources

def load_prompt_text(path: str, file_name: str) -> str:
    return resources.files(path).joinpath(file_name).read_text(encoding="utf-8")