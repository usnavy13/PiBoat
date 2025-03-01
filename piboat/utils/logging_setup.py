import logging
import pkg_resources

def setup_logging(name, log_file=None):
    """
    Set up logging configuration for a module
    
    Args:
        name (str): Logger name
        log_file (str, optional): Path to log file. If None, only console logging is used.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    handlers = [logging.StreamHandler()]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True
    )
    
    logger = logging.getLogger(name)
    
    return logger


def log_library_versions(logger):
    """
    Log versions of key libraries for debugging
    
    Args:
        logger (logging.Logger): Logger instance to use
    """
    libraries = ['aiortc', 'av', 'websockets', 'numpy', 'aiohttp']
    
    for lib in libraries:
        try:
            version = pkg_resources.get_distribution(lib).version
            logger.info(f"{lib} version: {version}")
        except Exception as e:
            logger.warning(f"Could not determine {lib} version: {e}") 