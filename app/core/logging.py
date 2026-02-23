import logging

def setup_logging():
    """Logging yapılandırmasını başlatır."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("backend.log"),
            logging.StreamHandler()
        ]
    )
